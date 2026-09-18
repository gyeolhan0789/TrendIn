"""과거분 백필. 주기 실행 경로 밖의 일회성 명령이다.

    python -m trendin.fashion.collect.backfill vogue --since 2026-03-17T00:00+09:00 --store

주기 실행(S15P21A102-167)의 DAG 가 import 할 대상이 여기 없다. 백필이 매일 도는 걸
막는 건 규율이 아니라 이 분리다.

2페이지부터 돌고, **발행일로 멈춘다** (S15P21A102-290). 한 페이지의 기사가 전부 `--since`
보다 오래되면 그 뒤는 더 오래된 것들뿐이다. 페이지 수로 멈추지 않는 이유는 소스마다 한 페이지
건수와 발행 속도가 달라서 "6개월"이 몇 페이지인지 소스마다 다시 재야 해서다.
`?paged=1` 은 파라미터 없는 요청과 같은 10건이라 주기 수집과 겹친다.

중복은 여기서 거르지 않는다. 이미 받은 기사를 걸러 내는 건 수집 장부
(S15P21A102-166)의 일이고, 여기서 흉내 내면 그 실행에서 방금 본 id 만 아는 반쪽짜리
판정이 장부의 판정과 두 벌로 남는다.

`--store` 를 주면 주기 실행과 **같은** 저장·장부 부품을 태운다(S15P21A102-167). 장부가
이미 받은 기사는 기사 페이지를 받지 않는다(불변식 12). 다만 **한 페이지가 통째로 아는 기사여도
멈추지 않는다.** 예전엔 멈췄는데, 그러면 끊긴 실행을 이어 돌리거나 옛 30페이지 백필 뒤에
깊이를 늘려 다시 돌릴 때 2페이지에서 멈춰 그 뒤가 영영 안 채워진다. 넘기는 비용은 피드
요청뿐이다. 기사 페이지를 못 받은 기사는 장부에 대기 행으로 남으므로(S15P21A102-312) 상한
(3회·24시간) 안에 같은 명령을 다시 돌리면 다시 받는다. 과거분 기사는 주기 실행의 후보에 다시
들어오지 않아, 상한에 닿으면 본문 없이 저장돼 굳는다.

발급은 여기서 하지 않는다 — 발급 태스크가 장부의 미발급 행을 전부 내므로, 다음 주기 실행이
백필분을 이어 낸다.

**목록 소스(바자·코스모)는 받지 않는다.** `ListingAdapter.discover(page=...)` 가 이미
"목록에 보이는 만큼만이다" 라며 거부한다 — 과거분이라는 개념 자체가 없다. CLI 가 그걸
모르고 받으면 HTML 을 피드로 파싱해 0 건을 내고 성공으로 끝난다.
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime

from trendin.common.collect import flow
from trendin.common.collect.cli import offset_datetime
from trendin.common.collect.db import Database
from trendin.common.collect.ledger import PostgresLedger
from trendin.common.collect.minio_store import MinioObjectStore
from trendin.common.collect.session import CollectSession, FetchFailed
from trendin.common.collect.stores import InMemoryValidatorStore
from trendin.fashion.collect import sources
from trendin.fashion.collect.rss import RssAdapter

logger = logging.getLogger("trendin.collect.backfill")

FIRST_PAGE = 2

# 발행일에 끝내 닿지 못할 때의 마지막 퓨즈다. vogue 6개월이 약 130페이지라 넉넉하다.
MAX_PAGES = 1000


class WalkAborted(RuntimeError):
    """발행일로 멈추기 전에 피드가 이상해졌다. 성공이 아니라 설정을 고쳐야 하는 신호다."""


# 과거분은 페이지 넘김이 되는 피드만 있다(확정 9). 목록 소스는 `discover(page=...)` 가 거부하고,
# `page_param` 이 없는 피드는 넘길 페이지가 없다.
BACKFILLABLE = tuple(
    k for k in sorted(sources.BY_KEY) if sources.get(k).route == "rss" and sources.get(k).page_param
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="backfill", description=__doc__)
    parser.add_argument("source", choices=sorted(sources.BY_KEY), help="소스 키")
    parser.add_argument(
        "--since",
        type=offset_datetime,
        required=True,
        help=(
            "이 발행일보다 오래된 기사만 남은 페이지에서 멈춘다. "
            "ISO-8601, 오프셋 필수. 기본값은 없다"
        ),
    )
    parser.add_argument("--json", action="store_true", help="article.json 을 JSON Lines 로")
    parser.add_argument(
        "--store",
        action="store_true",
        help="MinIO 와 장부에 실제로 쓴다. 기본은 쓰지 않고 훑기만 한다",
    )
    return parser


def walk_pages(
    adapter, *, since: datetime, ledger, store, emit_json: bool = False
) -> tuple[int, int]:
    """`FIRST_PAGE` 부터 넘기다 기사가 전부 `since` 보다 오래된 페이지에서 멈춘다.

    "빈 응답" 을 멈춤 조건으로 못 쓰는 이유는 2026-09-03 실측 때문이다 — `?paged=999` 도
    404 가 아니라 200 에 오래된 10 건을 준다. 그 10 건의 발행일이 멈춤을 알려 준다.
    """
    total = stored = 0
    source_key = adapter.source.key if adapter.source is not None else "?"
    previous_ids = None
    for page in range(FIRST_PAGE, FIRST_PAGE + MAX_PAGES):
        try:
            result = adapter.discover(page=page)
        except FetchFailed as exc:
            if exc.status not in (404, 410):
                raise
            # 역사가 6개월보다 짧은 피드는 끝을 넘기면 404 를 준다. 다 받은 것이지 실패가 아니다.
            logger.info("%s: %d 페이지가 없다 — 피드 끝이다", source_key, page)
            break
        if result.not_modified:
            continue

        candidates = result.candidates
        if not candidates:
            if result.failures:
                raise WalkAborted(f"{source_key}: {page} 페이지의 item 이 하나도 후보가 못 됐다")
            logger.info("%s: %d 페이지가 비었다 — 피드 끝이다", source_key, page)
            break
        ids = [c.article_id for c in candidates]
        if ids == previous_ids:
            # 페이지 파라미터를 무시하는 피드다(hypebeast 2026-09-03). 발행일이 영영 안 줄어든다.
            raise WalkAborted(
                f"{source_key}: {page} 페이지가 앞 페이지와 같다 — page_param 이 안 먹는 피드다"
            )
        previous_ids = ids
        if not any(c.published_at is not None for c in candidates):
            # 발행일을 하나도 못 읽었다. 멈추면 남은 구간이 안 채워진 채 성공으로 보인다.
            raise WalkAborted(f"{source_key}: {page} 페이지의 기사에 발행일이 하나도 없다")
        if not any(c.published_at is not None and c.published_at >= since for c in candidates):
            logger.info("%s: %d 페이지에 %s 이후 기사가 없다 — 멈춘다", source_key, page, since)
            break
        # 한 페이지 안에서도 거른다. 수정일 순으로 섞어 내는 피드는 오래된 기사 뒤에 새 기사가 온다.
        # 발행일 없는 기사는 여기서 빼지 않는다 — 저장 루프가 주기 실행과 같게
        # 실패로 남긴다(불변식 9).
        candidates = [c for c in candidates if c.published_at is None or c.published_at >= since]

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

        # 장부가 붙었으니 이미 받은 기사는 기사 페이지도 받지 않는다(불변식 12).
        new_ids = ledger.filter_new(source_key, [c.article_id for c in candidates])
        fresh = [c for c in candidates if c.article_id in new_ids]
        # 주기 실행과 **같은** 루프다. 따로 짜면 저장 확인·장부 기록 순서가 두 벌로 갈린다.
        page_stored, _members_only, _paywalled, failures = flow.store_candidates(
            adapter, fresh, ledger=ledger, store=store
        )
        total += len(fresh)
        stored += page_stored
        for failure in failures:
            logger.warning("%s: %s %s", source_key, failure.ref, failure.reason)
    else:
        raise WalkAborted(f"{source_key}: {MAX_PAGES} 페이지를 넘겨도 {since} 에 닿지 않았다")
    return total, stored


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    source = sources.get(args.source)
    if args.source not in BACKFILLABLE:
        raise SystemExit(
            f"과거분이 없는 소스다 — 목록 소스이거나 페이지 넘김이 안 되는 피드다: {args.source}"
            f" (백필 가능: {', '.join(BACKFILLABLE)})"
        )

    ledger = store = None
    if args.store:
        ledger = PostgresLedger(Database.from_env())
        store = MinioObjectStore.from_env()

    with CollectSession(
        allowed_url_prefixes=source.allowed_url_prefixes,
        validators=InMemoryValidatorStore(),
    ) as session:
        try:
            total, stored = walk_pages(
                RssAdapter(source, session),
                since=args.since,
                ledger=ledger,
                store=store,
                emit_json=args.json,
            )
        except WalkAborted as exc:
            raise SystemExit(str(exc)) from exc

    logger.info("%s: %d건 (저장 %d건)", source.key, total, stored)
    print(f"{source.key}: {total}건" + (f", 저장 {stored}건" if args.store else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
