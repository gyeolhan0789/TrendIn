"""`event_id` 처리 이력 — 멱등성 중복 차단 2 ([01 §4] · [08 §3]).

checkpoint(중복 차단 1)만으로는 부족하다. checkpoint 는 파일이라 디스크가 날아가거나 실수로
지우면 토픽을 처음부터 다시 읽는데, 그때 이 표가 "이미 처리한 것" 을 걸러낸다. 생산자가
at-least-once 라 같은 `event_id` 가 실제로 두 번 나오는 자리도 있다 ([02 §1]).

**쓰기는 스테이징 + 서버사이드 MERGE 다** ([08 §4]). Spark 의 JDBC 는 순수 INSERT 라
같은 `event_id` 를 다시 쓰면 배치가 죽는다. 스테이징에 넣고 드라이버가 한 트랜잭션으로
병합하면 전부 반영되거나 전부 아니다.

**동시에 두 개가 돌면 안 된다.** 스테이징 테이블을 공유하므로 `ingest` DAG 은
`max_active_runs=1` 이어야 한다. 겹치면 한쪽의 행이 다른 쪽 트랜잭션에 딸려 들어간다.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from trendin.spark.common.config import Config
from trendin.spark.common.logging import get_logger
from trendin.spark.io import jdbc

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

log = get_logger(__name__)

TABLE = "pl_processing_ledger"
STAGE_TABLE = "pl_stage_processing_ledger"

# 처리 이력 한 행의 칸. Spark 가 이 순서로 쓰고 MERGE 가 이 순서로 읽는다.
COLUMNS = (
    "event_id",
    "job",
    "stage",
    "event_shape",
    "status",
    "error_type",
    "detail",
    "domain",
    "source_id",
    "run_id",
    "article_id",
    "record_count",
    "collected_at",
    "topic_partition",
    "topic_offset",
    "processed_at",
)

# Job 이름은 코드 상수지만 SQL 에 문자열로 들어간다. 값이 어디서 오든 여기서 한 번 막는다.
_SAFE_NAME = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")

DDL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    event_id        text        NOT NULL,
    job             text        NOT NULL,
    -- 이 Job 이 이벤트를 어디까지 끌고 갔는지. 단계가 늘면 값이 는다 (ingest/routing.py).
    stage           text        NOT NULL,
    -- ARTICLE | SUMMARY. event_id 형식만으로는 갈리지 않아서 컬럼으로 둔다 ([08 §3]).
    event_shape     text,
    status          text        NOT NULL,
    error_type      text,
    detail          text,
    domain          text,
    source_id       text,
    run_id          text,
    article_id      text,
    record_count    bigint,
    collected_at    timestamptz,
    topic_partition integer,
    topic_offset    bigint,
    processed_at    timestamptz NOT NULL,
    PRIMARY KEY (event_id, job)
);

-- 스테이징은 제약이 없다. 순수 INSERT 를 빠르게 받고 MERGE 뒤 비운다.
CREATE TABLE IF NOT EXISTS {STAGE_TABLE} (LIKE {TABLE});

-- ([02 §4]) 수집 상태 집계가 (일자, 소스) 로 훑는다.
CREATE INDEX IF NOT EXISTS pl_processing_ledger_collected_idx
    ON {TABLE} (job, source_id, collected_at);
"""

# DISTINCT ON 이 필요한 이유 — 한 배치 안에 같은 event_id 가 두 번 들어올 수 있다
# (생산자가 at-least-once). 그대로 두면 ON CONFLICT 가 "같은 행을 두 번 건드릴 수 없다"
# 로 죽는다. Spark 쪽에서도 걸러내지만, SQL 이 혼자서도 성립해야 한다.
MERGE_SQL = f"""
INSERT INTO {TABLE} ({", ".join(COLUMNS)})
SELECT DISTINCT ON (event_id, job) {", ".join(COLUMNS)}
  FROM {STAGE_TABLE}
 ORDER BY event_id, job, processed_at DESC
ON CONFLICT (event_id, job) DO UPDATE SET
    stage           = EXCLUDED.stage,
    event_shape     = EXCLUDED.event_shape,
    status          = EXCLUDED.status,
    error_type      = EXCLUDED.error_type,
    detail          = EXCLUDED.detail,
    domain          = EXCLUDED.domain,
    source_id       = EXCLUDED.source_id,
    run_id          = EXCLUDED.run_id,
    article_id      = EXCLUDED.article_id,
    record_count    = EXCLUDED.record_count,
    collected_at    = EXCLUDED.collected_at,
    topic_partition = EXCLUDED.topic_partition,
    topic_offset    = EXCLUDED.topic_offset,
    processed_at    = EXCLUDED.processed_at;

TRUNCATE {STAGE_TABLE};
"""


def safe_job(job: str) -> str:
    if not _SAFE_NAME.match(job):
        raise ValueError(f"Job 이름에 쓸 수 없는 문자가 있다: {job!r}")
    return job


class Ledger:
    """`pl_processing_ledger` 하나. 배선을 갈아 끼우면 테스트가 진짜 DB 없이 돈다."""

    def __init__(self, config: Config, *, job: str) -> None:
        self._config = config
        self._job = safe_job(job)

    @property
    def job(self) -> str:
        return self._job

    def ensure_schema(self) -> None:
        """DDL 을 멱등하게 적용한다. 스트림을 걸기 전에 한 번 부른다.

        `pl_*` 는 파이프라인 내부 테이블이라 우리가 만든다. 서비스 테이블은 백엔드 소유고
        Spark 에 DDL 권한이 없다 ([08 §1]) — 그 경계를 넘지 않는다.
        """
        jdbc.execute(self._config, DDL)
        log.info("처리 이력 스키마 확인: %s", TABLE)

    def known_event_ids(self, spark: Any) -> "DataFrame":
        """이 Job 이 이미 적어 둔 `(event_id, stage)` 전부.

        두 칸만 읽는다. [00 §3] 규모(연 25만 행)에서 전량 읽기가 수 MB 라 견딜 만하고,
        배치의 `event_id` 를 IN 절로 밀어 넣는 방식보다 코드가 단순하다. 처리 이력이 그보다
        커지면 배치 키를 스테이징에 올려 DB 쪽에서 anti-join 하는 편으로 바꾼다.
        """
        query = f"SELECT event_id, stage FROM {TABLE} WHERE job = '{self._job}'"
        return jdbc.read_table(spark, query, self._config)

    def filter_new(self, events: "DataFrame") -> "DataFrame":
        """그 단계까지 이미 적힌 이벤트를 걸러낸다 — 중복 차단 2 가 실제로 막는 자리.

        **`event_id` 만이 아니라 `(event_id, stage)` 로 대조한다.** 판별이 도달할 단계를
        미리 정해 주므로(`ingest/routing.decide`) 여기서 그 값을 그대로 쓴다.

        그래서 단계가 늘 때 손으로 옮길 것이 없다. 객체 검증이 붙기 전에 `contract` 까지만
        적힌 기사 이벤트는 이제 `object` 를 목표로 오므로 대조에 걸리지 않고, 다시 처리되어
        같은 행이 `object` 로 갱신된다(처리 이력 PK 가 `(event_id, job)` 이라 행은 늘지 않는다).
        `event_id` 만 봤다면 그 행들이 객체 검증을 통째로 건너뛰었고, **아무 증상도 없었다.**
        """
        known = self.known_event_ids(events.sparkSession)
        return events.join(known, on=["event_id", "stage"], how="left_anti")

    def record(self, rows: "DataFrame") -> None:
        """스테이징에 넣고 서버에서 병합한다. 빈 배치면 아무것도 하지 않는다."""
        staged = rows.select(*COLUMNS)
        jdbc.append(staged, STAGE_TABLE, self._config)
        jdbc.execute(self._config, MERGE_SQL)
