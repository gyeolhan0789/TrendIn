"""`contents` 적재와 `contents.id` 회수.

규격은 [03 §8](../../../../spark/docs/03-normalization-spec.md) 과 [08 §4] 다.

**서비스 테이블에 쓰는 이 묶음의 유일한 자리다.** S2·S4 는 `pl_` 내부 테이블만 쓴다
([08 §1]). 그래서 여기만 백엔드 소유 스키마에 의존한다.

**🚫 `contents` 테이블이 아직 없다.** 백엔드 엔티티에 `Content` 가 없고
(`backend/.../trend/domain/` 에 `keywords`·`trends`·`keyword_metrics`·
`keyword_metric_history` 만 있다) `ddl-auto` 가
`create` 라 재배포마다 스키마가 다시 만들어진다. 규격의 단일 출처는 02~08 이므로
([10] 머리말) **여기 DDL 과 MERGE 는 [erd](../../../../spark/docs/erd/erd-00-current.md) 가
정의한 `contents` 를 그대로 상정해 짜 두고**, 테이블이 없으면 `service_table_ready()` 가
`False` 를 준다. 그 판단을 조용히 삼키지 않는 것이 중요하다 — 건너뛴 배치는 `curated` 에는
쓰이고 `contents` 에는 없어서, 나중에 `extract` 가 `pl_content_id_map` 에서 아무것도 못 찾는다.

**Spark 는 서비스 테이블에 DDL 을 걸지 않는다** ([08 §1]). 아래 `DDL` 이 만드는 것은
`pl_stage_contents` 와 `pl_content_id_map` 둘 — 둘 다 우리 것이다.

**쓰기는 스테이징 + 서버사이드 MERGE 다** ([08 §4]). Spark 의 JDBC 는 순수 INSERT 라
upsert 를 못 하고, `contents.url` 에 UNIQUE 가 걸려 있어 재처리가 곧 배치 실패가 된다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from trendin.spark.common.config import Config
from trendin.spark.common.logging import get_logger
from trendin.spark.io import jdbc

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

log = get_logger(__name__)

# 백엔드 소유. 우리는 읽고 쓰기만 한다.
TABLE = "contents"
# 우리 것.
STAGE_TABLE = "pl_stage_contents"
MAP_TABLE = "pl_content_id_map"

# `contents` 의 칸 여섯 ([03 §8]). `id` 는 DB 가 발행하므로 넣지 않는다.
#
# **`summary` 가 없다.** v2 에서 그 컬럼이 사라졌고([erd] §5 9번), 그게 방어다 — 소스가 준
# 리드문은 매체의 저작물이라 화면에 나가면 불변식 3 을 깬다. v1 에서는 빈 컬럼이 있어
# "여기에 넣지 마라" 를 규칙으로 지켜야 했는데, 이제 스키마가 대신 막는다.
COLUMNS = (
    "title",
    "source",
    "url",
    "body_object_key",
    "published_at",
    "collected_at",
)

# 스테이징에는 `url_hash` 도 싣는다. MERGE 가 `RETURNING id, url` 로 받은 뒤 매핑 테이블의
# 키를 만드는 데 쓰는데, SQL 안에서 `sha256(url::bytea)` 로 다시 계산하면 파이썬이 계산한
# 값과 갈릴 수 있다 — 정규화된 URL 의 인코딩이 한 글자만 달라도 다른 해시가 된다.
STAGE_COLUMNS = ("url_hash", *COLUMNS)

DDL = f"""
-- 스테이징은 제약이 없다. 순수 INSERT 를 빠르게 받고 MERGE 뒤 비운다.
CREATE TABLE IF NOT EXISTS {STAGE_TABLE} (
    url_hash        bytea       NOT NULL,
    title           text        NOT NULL,
    source          text,
    url             text        NOT NULL,
    body_object_key text,
    published_at    timestamptz,
    collected_at    timestamptz
);

-- `url_hash` → `contents.id` ([08 §3]). 키를 해시로 두는 이유는 긴 URL 문자열을 조인 키로
-- 쓰지 않기 위해서다 — `extract` 가 이 표를 평범한 JDBC 소스로 읽어 조인한다.
--
-- `content_id` 에 FK 를 걸지 않는다 ([08 §6]) — `pl_*` 는 서비스 테이블에 FK 를 걸지 않고
-- 논리적 참조로만 둔다. 무결성은 파이프라인이 책임진다. `ddl-auto: create` 인 동안
-- 서비스 테이블이 재배포마다 다시 만들어지므로, FK 가 있으면 그때 이 표까지 딸려 깨진다.
CREATE TABLE IF NOT EXISTS {MAP_TABLE} (
    url_hash   bytea       PRIMARY KEY,
    content_id bigint      NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);
"""

# **`DO NOTHING` 이 아니라 `DO UPDATE` 인 것이 핵심이다** ([08 §4]). `DO NOTHING` 은 충돌한
# 행에 대해 `RETURNING` 을 내주지 않아서, 이미 있는 문서의 `id` 를 못 받는다. 재처리에서
# 그게 곧바로 문제가 된다 — `keyword_contents` 를 만들 수 없다.
#
# `DISTINCT ON (url)` 이 필요한 이유는 한 배치에 같은 URL 이 두 번 들어올 수 있기 때문이다.
# 그대로 두면 `ON CONFLICT` 가 "같은 행을 두 번 건드릴 수 없다" 로 죽는다. 중복 제거 2단계가
# Spark 쪽에서도 걸러내지만(`normalize/dedup.py`), SQL 이 혼자서도 성립해야 한다.
#
# **`title` 과 `body_object_key` 만 갱신한다.** `url` 은 충돌 키라 같고, `published_at` ·
# `collected_at` 은 소스가 준 사실이라 재처리가 덮을 이유가 없다. `body_object_key` 를 갱신
# 대상에 넣는 것은 [02 §6] 의 요구다 — 파티션 파일명이 바뀌는 재처리에서 함께 갱신해야 한다.
MERGE_SQL = f"""
WITH staged AS (
    SELECT DISTINCT ON (url) url_hash, {", ".join(COLUMNS)}
      FROM {STAGE_TABLE}
     ORDER BY url, collected_at DESC
), upserted AS (
    INSERT INTO {TABLE} ({", ".join(COLUMNS)})
    SELECT {", ".join(COLUMNS)} FROM staged
    ON CONFLICT (url) DO UPDATE SET
        title           = EXCLUDED.title,
        body_object_key = EXCLUDED.body_object_key
    RETURNING id, url
)
INSERT INTO {MAP_TABLE} (url_hash, content_id, updated_at)
SELECT s.url_hash, u.id, now()
  FROM upserted u
  JOIN staged s ON s.url = u.url
ON CONFLICT (url_hash) DO UPDATE SET
    content_id = EXCLUDED.content_id,
    updated_at = EXCLUDED.updated_at;

TRUNCATE {STAGE_TABLE};
"""

# 테이블이 있는지. `to_regclass` 는 없으면 예외 대신 `NULL` 을 준다 — `information_schema`
# 조회보다 짧고 스키마 검색 경로를 그대로 따른다.
EXISTS_SQL = f"SELECT to_regclass('{TABLE}') IS NOT NULL"


class ContentsSink:
    """`contents` 한 곳. 배선을 갈아 끼우면 테스트가 진짜 DB 없이 돈다."""

    def __init__(self, config: Config) -> None:
        self._config = config

    def ensure_schema(self) -> None:
        """**우리 테이블만** 만든다. `contents` 는 백엔드 소유라 건드리지 않는다 ([08 §1])."""
        jdbc.execute(self._config, DDL)
        log.info("적재 스키마 확인: %s · %s", STAGE_TABLE, MAP_TABLE)

    def service_table_ready(self) -> bool:
        """`contents` 가 실제로 있는지.

        **없으면 만들지 않고 `False` 를 준다.** 만들면 백엔드의 `ddl-auto` 가 다음 재배포에
        다른 형태로 다시 만들고, 그 사이 쌓인 행은 사라진다. 무엇보다 서비스 테이블의 형태를
        소비 측이 정하는 결합이 생긴다 — [08 §1] 이 그 경계를 그은 이유다.
        """
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute(EXISTS_SQL)
            row = cur.fetchone()
        return bool(row and row[0])

    def upsert(self, rows: "DataFrame", *, conn=None) -> None:
        """스테이징에 넣고 서버에서 병합한다. `pl_content_id_map` 이 같은 트랜잭션에서 채워진다.

        **한 트랜잭션인 이유** ([08 §4]) — 절반만 반영된 상태가 가장 나쁘다. 스테이징 INSERT 까지
        같은 연결에서 한다(`jdbc.stage_and_merge`) — Spark JDBC 로 넣으면 그 부분이 별개
        트랜잭션이라 MERGE 가 죽었을 때 스테이징 행이 남아 다음 실행에 섞였다. `contents` 에
        행은 들어갔는데 매핑이 없으면, 재실행이 `ON CONFLICT` 로 같은 `id` 를 다시 받아
        복구되지만 그 사이 `extract` 는 그 문서를 못 본다. 반대로 매핑만 있으면 없는 `id` 를
        가리킨다.

        `conn` 은 처리 이력과 한 트랜잭션으로 묶을 때 부른 쪽이 준다
        (`ingest/batch.process_batch`). 그러면 여기서 커밋하지 않는다 — `contents` 는 들어갔는데
        이력이 없는 상태가 다음 실행의 중복 적재이기 때문이다 (S15P21A102-341).
        """
        jdbc.stage_and_merge(
            self._config,
            stage_table=STAGE_TABLE,
            columns=STAGE_COLUMNS,
            frame=rows,
            merge_sql=MERGE_SQL,
            conn=conn,
        )

    def id_map(self, spark) -> "DataFrame":
        """`(url_hash, content_id)` 전부. `extract` 가 읽는 것과 같은 경로다 ([08 §4])."""
        return jdbc.read_table(spark, f"SELECT url_hash, content_id FROM {MAP_TABLE}", self._config)


def contents_rows(documents: "DataFrame") -> "DataFrame":
    """표준 문서 → 스테이징 행. 매핑은 대부분 1:1 이라 여기서 하는 일이 적다 ([03 §8]).

    **`title` 대체 규칙이 없다.** 배치 계약 시절에는 "소스에 제목 개념이 없으면 `null`" 이라
    본문 앞부분을 잘라 넣는 규칙이 있었는데, `article.json` 의 `title` 은 필수이고 공백만
    있어도 생산자가 거부한다(불변식 9). 그래서 제목 위치 가중치([04 §6])가 오염될 경로가
    없어졌다.

    **`published_date` 는 나가지 않는다.** 집계용 내부 값이다 ([03 §8]).
    """
    from pyspark.sql import functions as F

    return documents.select(
        F.col("url_hash"),
        F.col("title"),
        # 값 규약이 확정 전이다 ([00 §7] 18번). 지금은 이벤트의 `source_id` 를 그대로 넣는다.
        F.col("source_id").alias("source"),
        F.col("url"),
        F.col("body_object_key"),
        F.col("published_at"),
        F.col("collected_at"),
    )
