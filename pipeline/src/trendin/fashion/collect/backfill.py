"""과거분 백필. 주기 실행 경로 밖의 일회성 명령이다.

    python -m trendin.fashion.collect.backfill vogue --pages 30

주기 실행(S15P21A102-167)의 DAG 가 import 할 대상이 여기 없다. 백필이 매일 도는 걸
막는 건 규율이 아니라 이 분리와 `--pages` 상한이다 — 2026-09-03 실측에서 `?paged=999`
도 404 가 아니라 200 에 오래된 10건을 줘서, "빈 응답이면 멈춘다" 는 종료 조건이 없다.

2페이지부터 돈다. `?paged=1` 은 파라미터 없는 요청과 같은 10건이라 주기 수집과 겹친다.

중복은 여기서 거르지 않는다. 이미 받은 기사를 걸러 내는 건 수집 장부
(S15P21A102-166)의 일이고, 여기서 흉내 내면 그 실행에서 방금 본 id 만 아는 반쪽짜리
판정이 장부의 판정과 두 벌로 남는다. 이 명령은 페이지를 그대로 돌고 후보를 다 낸다.

`--store` 를 주면 주기 실행과 **같은** 저장·장부 부품을 태운다(S15P21A102-167). 그러면
장부가 붙으므로 이미 받은 기사는 거기서 걸린다(불변식 12). 발급은 여기서 하지 않는다 —
발급 태스크가 장부의 미발급 행을 전부 내므로, 다음 주기 실행이 백필분을 이어 낸다.
"""

from __future__ import annotations

import argparse
import json
import logging

from trendin.common.collect import flow
from trendin.common.collect.db import Database
from trendin.common.collect.ledger import PostgresLedger
from trendin.common.collect.minio_store import MinioObjectStore
from trendin.common.collect.session import CollectSession
from trendin.common.collect.stores import InMemoryValidatorStore
from trendin.fashion.collect import sources
from trendin.fashion.collect.rss import RssAdapter

logger = logging.getLogger("trendin.collect.backfill")

FIRST_PAGE = 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="backfill", description=__doc__)
    parser.add_argument("source", choices=sorted(sources.BY_KEY), help="소스 키")
    parser.add_argument(
        "--pages",
        type=int,
        required=True,
        help=(
            f"몇 페이지를 돌지. {FIRST_PAGE}페이지부터 센다. "
            "기본값은 없다 — 실수로 30페이지가 돌지 않게"
        ),
    )
    parser.add_argument("--json", action="store_true", help="article.json 을 JSON Lines 로")
    parser.add_argument(
        "--store",
        action="store_true",
        help="MinIO 와 장부에 실제로 쓴다. 기본은 쓰지 않고 훑기만 한다",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    if args.pages < 1:
        raise SystemExit("--pages 는 1 이상이어야 한다")

    source = sources.get(args.source)
    total = 0
    stored = 0

    ledger = store = None
    if args.store:
        ledger = PostgresLedger(Database.from_env())
        store = MinioObjectStore.from_env()

    with CollectSession(
        allowed_url_prefixes=source.allowed_url_prefixes,
        validators=InMemoryValidatorStore(),
    ) as session:
        adapter = RssAdapter(source, session)
        for page in range(FIRST_PAGE, FIRST_PAGE + args.pages):
            result = adapter.discover(page=page)
            if result.not_modified:
                continue

            candidates = result.candidates
            if ledger is None:
                # 훑기만 한다. 장부가 없으니 중복도 못 거른다 — 그 판정은 장부 몫이다.
                for candidate in candidates:
                    try:
                        _raw, article = adapter.materialize(candidate)
                    except Exception as exc:
                        logger.warning(
                            "%s: %s 정규화 실패 — %s", source.key, candidate.article_id, exc
                        )
                        continue
                    total += 1
                    if args.json:
                        print(json.dumps(article.to_json_dict(), ensure_ascii=False))
                continue

            # 장부가 붙었으니 이미 받은 기사는 기사 페이지도 받지 않는다(불변식 12).
            new_ids = ledger.filter_new(source.key, [c.article_id for c in candidates])
            fresh = [c for c in candidates if c.article_id in new_ids]
            # 주기 실행과 **같은** 루프다. 따로 짜면 저장 확인·장부 기록 순서가 두 벌로 갈린다.
            page_stored, failures = flow.store_candidates(
                adapter, fresh, ledger=ledger, store=store
            )
            total += len(fresh)
            stored += page_stored
            for failure in failures:
                logger.warning("%s: %s %s", source.key, failure.ref, failure.reason)

    logger.info("%s: %d건 (저장 %d건)", source.key, total, stored)
    print(f"{source.key}: {total}건" + (f", 저장 {stored}건" if args.store else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
