"""미등록 표기가 나온 기사의 본문을 curated 에서 읽는다.

**미등록만 읽는다.** 창 전체를 읽을 이유가 없다 — 이미 개념에 붙은 표기는 문맥이 필요 없고,
문맥이 필요한 것은 판정을 기다리는 미등록뿐이다.

**없으면 조용히 비운다.** Spark 세션이 없거나(`scripts/concept-run.py` 가 노트북에서 부른다)
curated 를 못 읽으면 문맥 없이 계속 돈다. 문맥은 판정을 돕는 것이지 선행 조건이 아니다 —
`concept_groups` 가 개념 표 없이도 도는 것과 같은 규약이다.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date, timedelta
from typing import Any

from trendin.spark.common.config import Config
from trendin.spark.common.logging import get_logger
from trendin.spark.io import jdbc

log = get_logger(__name__)

BODY_KEYS_SQL = """
SELECT id, url, published_at::date FROM contents
 WHERE id = ANY(%s) AND body_object_key IS NOT NULL AND published_at IS NOT NULL
"""


def body_keys(config: Config, article_ids: Sequence[int]) -> dict[int, tuple[str, str]]:
    """기사 번호 → (url, 발행일). 발행일은 파티션을 자르는 데 쓴다."""
    if not article_ids:
        return {}
    with jdbc.connection(config) as conn, conn.cursor() as cur:
        cur.execute(BODY_KEYS_SQL, (list(article_ids),))
        return {int(row[0]): (str(row[1]), str(row[2])) for row in cur.fetchall()}


def load_bodies(
    spark: Any | None, config: Config, article_ids: Iterable[int], *, curated_root: str | None
) -> dict[int, str]:
    """기사 번호 → 본문. 읽지 못하면 빈 사전을 돌려준다.

    **객체 키를 하나씩 열지 않는다.** 2026-09-22 운영에서 판정 대상 기사 3,434개가 서로 다른
    parquet 파일 2,318개에 흩어져 있었다 — 경로를 그만큼 나열하면 목록 조회만으로 몇 분이
    걸린다. 대신 curated 뿌리를 읽으면서 `published_date` 파티션으로 자르고 url 로 거른다.
    `extract/source.py` 가 쓰는 방식과 같다.

    한 번에 읽고 실패는 통째로 삼킨다. 기사 하나 때문에 개념 작업이 서면 안 되고, 문맥이
    없으면 자동 연결이 보수적으로 돌 뿐이다.
    """
    ids = list(dict.fromkeys(int(item) for item in article_ids))
    if spark is None or not curated_root or not ids:
        return {}
    try:
        keys = body_keys(config, ids)
        if not keys:
            return {}
        by_url = {url: article_id for article_id, (url, _) in keys.items()}
        dates = sorted({date for _, date in keys.values()})
        # **날짜를 하루씩 넓힌다.** `contents.published_at` 은 timestamptz 이고 curated 의
        # `published_date` 는 정제 때 계산한 파티션이라, 자정 언저리 기사가 하루 어긋날 수 있다.
        # 좁혀서 놓치는 것보다 한 칸 더 읽는 편이 싸다.
        first = (date.fromisoformat(dates[0]) - timedelta(days=1)).isoformat()
        last = (date.fromisoformat(dates[-1]) + timedelta(days=1)).isoformat()

        from pyspark.sql import functions as F

        rows = (
            spark.read.option("basePath", curated_root.rstrip("/"))
            .parquet(curated_root.rstrip("/"))
            .where(F.col("published_date") >= F.lit(first))
            .where(F.col("published_date") <= F.lit(last))
            .where(F.col("url").isin(list(by_url)))
            .where(F.col("dup_of").isNull())
            .select("url", "body")
            .collect()
        )
    except Exception:
        log.exception("본문을 읽지 못했다 — 문맥 없이 계속한다")
        return {}

    bodies: dict[int, str] = {}
    for row in rows:
        article_id = by_url.get(row["url"])
        if article_id is not None and isinstance(row["body"], str):
            bodies[article_id] = row["body"]
    return bodies
