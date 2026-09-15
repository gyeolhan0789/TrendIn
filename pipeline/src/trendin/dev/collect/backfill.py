"""Hacker News 구간 백필. 주기 실행 경로 밖의 일회성 명령이다.

    python -m trendin.dev.collect.backfill hn --since 2026-08-03T00:00+09:00 --store

주기 실행은 최근 6시간만 본다. 그보다 앞선 구간 — 첫 채움(6주)과 실행이 오래 멈춘 동안 빠진
구간 — 은 이 명령이 받는다. 페이지가 아니라 시각 구간을 받는 이유는 Algolia 가 한 질의에
1000건까지만 주고 페이지를 넘기지 못하게 해서다. 대신 `created_at_i` 로 구간을 자른다.

구간을 `SLICE` 조각으로 돌며 조각마다 저장까지 끝낸다. 도중에 죽어도 받은 조각은 장부에
남고, 같은 명령을 다시 돌리면 장부가 이미 받은 글을 거른다. 그래서 fashion 백필과 달리
"이미 받은 조각이면 멈춘다" 를 두지 않는다 — 빈 구간이 어느 조각에 있을지 모른다.

발급은 여기서 하지 않는다. 다음 주기 실행의 발급 태스크가 장부의 미발급 행을 전부 낸다.
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timedelta, timezone

from trendin.common.collect import flow
from trendin.common.collect.db import Database
from trendin.common.collect.ledger import PostgresLedger
from trendin.common.collect.minio_store import MinioObjectStore
from trendin.common.collect.session import CollectSession
from trendin.common.collect.stores import InMemoryValidatorStore
from trendin.dev.collect import sources
from trendin.dev.collect.hackernews import WINDOW, HackerNewsAdapter

logger = logging.getLogger("trendin.collect.backfill")

# 구간으로 과거분을 받을 수 있는 route 는 `api` 뿐이다. 소스가 늘어도 hn 어댑터가 엉뚱한
# 소스에 붙지 않게 여기서 거른다.
BACKFILLABLE = tuple(k for k in sorted(sources.BY_KEY) if sources.get(k).route == "api")

# 한 번에 받는 구간의 상한. 첫 채움 깊이(설계 문서 #9)와 같다. 아카이브 전량 백필은 범위 밖이라
# `--since` 를 멀리 잘못 줘도 돌지 않게 막는다. 더 긴 공백은 나눠 돌린다 — 장부가 겹친 글을 거른다.
MAX_RANGE = timedelta(weeks=6)

# 주기 실행의 창과 같은 길이다. 한 조각이 한 번의 질의로 끝나는 크기라 1000건 상한에 드물게 닿는다.
SLICE = WINDOW


def _offset_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError(f"오프셋이 없다 — KST 면 +09:00 을 붙인다: {value!r}")
    return parsed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="backfill", description=__doc__)
    parser.add_argument("source", choices=BACKFILLABLE, help="소스 키")
    parser.add_argument(
        "--since",
        type=_offset_datetime,
        required=True,
        help="구간 시작(포함). ISO-8601, 오프셋 필수. 기본값은 없다. 구간은 6주까지",
    )
    parser.add_argument("--until", type=_offset_datetime, help="구간 끝(제외). 기본은 지금")
    parser.add_argument("--json", action="store_true", help="article.json 을 JSON Lines 로")
    parser.add_argument(
        "--store",
        action="store_true",
        help="MinIO 와 장부에 실제로 쓴다. 기본은 쓰지 않고 훑기만 한다",
    )
    return parser


def walk_range(
    adapter: HackerNewsAdapter,
    *,
    since: datetime,
    until: datetime,
    ledger,
    store,
    emit_json: bool = False,
) -> tuple[int, int]:
    """`since` 부터 `until` 까지 `SLICE` 씩 돈다. 장부가 붙으면 없는 글만 저장한다."""
    total = stored = 0
    source_key = adapter.source.key
    start = since
    while start < until:
        end = min(start + SLICE, until)
        result = adapter.discover_range(start, end)
        for failure in result.failures:
            logger.warning("%s: 발견 실패 %s — %s", source_key, failure.ref, failure.reason)
        start = end

        candidates = result.candidates
        if ledger is None:
            # 훑기만 한다. 장부가 없으니 중복도 못 거른다 — 그 판정은 장부 몫이다.
            for candidate in candidates:
                try:
                    _raw, article = adapter.materialize(candidate)
                except Exception as exc:
                    logger.warning("%s: %s 정규화 실패 — %s", source_key, candidate.article_id, exc)
                    continue
                total += 1
                if emit_json:
                    print(json.dumps(article.to_json_dict(), ensure_ascii=False))
            continue

        new_ids = ledger.filter_new(source_key, [c.article_id for c in candidates])
        fresh = [c for c in candidates if c.article_id in new_ids]
        # 주기 실행과 **같은** 루프다. 따로 짜면 저장 확인·장부 기록 순서가 두 벌로 갈린다.
        slice_stored, _members_only, failures = flow.store_candidates(
            adapter, fresh, ledger=ledger, store=store
        )
        total += len(fresh)
        stored += slice_stored
        for failure in failures:
            logger.warning("%s: %s %s", source_key, failure.ref, failure.reason)
    return total, stored


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    until = args.until or datetime.now(timezone.utc)
    if args.since >= until:
        raise SystemExit(f"--since 가 --until 보다 앞서야 한다: {args.since} >= {until}")
    if until - args.since > MAX_RANGE:
        raise SystemExit(
            f"구간이 6주를 넘는다: {args.since} ~ {until}. 더 긴 공백은 구간을 나눠 돌린다"
        )

    source = sources.get(args.source)
    ledger = store = None
    if args.store:
        ledger = PostgresLedger(Database.from_env())
        store = MinioObjectStore.from_env()

    with CollectSession(
        allowed_url_prefixes=source.allowed_url_prefixes,
        validators=InMemoryValidatorStore(),
    ) as session:
        total, stored = walk_range(
            HackerNewsAdapter(source, session),
            since=args.since,
            until=until,
            ledger=ledger,
            store=store,
            emit_json=args.json,
        )

    logger.info("%s: %d건 (저장 %d건)", source.key, total, stored)
    print(f"{source.key}: {total}건" + (f", 저장 {stored}건" if args.store else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
