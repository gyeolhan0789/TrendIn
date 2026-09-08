"""DLQ 싱크 ([02 §5]).

계약 위반과 검증 실패는 조용히 버리지 않는다. 원본 메시지와 사유를 남겨 사람이 되돌릴 수
있게 한다 — DLQ 는 자동 재시도하지 않는다. 여기 오는 것들은 대부분 다시 해도 같은 결과다
(체크섬은 다시 계산해도 틀리고, 스키마 버전은 저절로 안 내려간다).

**싱크를 인터페이스로 둔 이유** — 계약상 쓸 곳이 둘인데(DLQ 토픽 + 내부 테이블) 토픽이
아직 없다. 토픽명이 담당 2 소관이라 정해지지 않았고, 그걸 기다리면 검증 로직 전체가
막힌다. 검증과 `error_type` 분기는 어디에 쓰든 같으므로 싱크만 갈아 끼우게 나눠 뒀다.
지금은 테이블만 쓰고, 토픽이 생기면 `TopicDlqSink` 하나를 더한다.

그 사이 **재투입 경로는 없다.** 복구는 `--source objects` 재처리로 한다 ([02 §6]).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from trendin.spark.common.config import Config
from trendin.spark.common.logging import get_logger
from trendin.spark.io import jdbc
from trendin.spark.io.ledger import safe_job

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

log = get_logger(__name__)

TABLE = "pl_processing_error"
STAGE_TABLE = "pl_stage_processing_error"

# 02 §5 의 DLQ 메시지 스키마를 컬럼으로 편 것. 토픽 싱크가 생기면 같은 값을 JSON 으로 낸다.
COLUMNS = (
    "event_id",
    "job",
    "error_type",
    "error_detail",
    "original_event",
    "topic_partition",
    "topic_offset",
    "retry_count",
    "failed_at",
)

DDL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    event_id        text        NOT NULL,
    job             text        NOT NULL,
    error_type      text        NOT NULL,
    error_detail    text,
    -- 원본 메시지 그대로. 파싱에 실패한 것도 여기 남아야 사람이 볼 수 있다.
    original_event  text,
    topic_partition integer,
    topic_offset    bigint,
    retry_count     integer     NOT NULL,
    failed_at       timestamptz NOT NULL,
    PRIMARY KEY (event_id, job)
);

CREATE TABLE IF NOT EXISTS {STAGE_TABLE} (LIKE {TABLE});

-- "지난주에 어떤 사유로 몇 건이 막혔나" 를 세는 조회가 쓴다.
CREATE INDEX IF NOT EXISTS pl_processing_error_type_idx ON {TABLE} (job, error_type, failed_at);
"""

MERGE_SQL = f"""
INSERT INTO {TABLE} ({", ".join(COLUMNS)})
SELECT DISTINCT ON (event_id, job) {", ".join(COLUMNS)}
  FROM {STAGE_TABLE}
 ORDER BY event_id, job, failed_at DESC
ON CONFLICT (event_id, job) DO UPDATE SET
    error_type      = EXCLUDED.error_type,
    error_detail    = EXCLUDED.error_detail,
    original_event  = EXCLUDED.original_event,
    topic_partition = EXCLUDED.topic_partition,
    topic_offset    = EXCLUDED.topic_offset,
    -- 같은 이벤트가 또 막혔다. 몇 번째인지가 사람이 볼 신호다.
    retry_count     = {TABLE}.retry_count + 1,
    failed_at       = EXCLUDED.failed_at;

TRUNCATE {STAGE_TABLE};
"""


class DlqSink(Protocol):
    """DLQ 한 곳. 토픽이 생기면 같은 형태의 구현이 하나 는다."""

    def ensure_schema(self) -> None: ...

    def write(self, rejected: "DataFrame") -> None:
        """거절된 이벤트를 남긴다. 컬럼은 `COLUMNS` 다."""
        ...


class TableDlqSink:
    """`pl_processing_error` 미러. 조회·집계 경로다 ([02 §5])."""

    def __init__(self, config: Config, *, job: str) -> None:
        self._config = config
        self._job = safe_job(job)

    def ensure_schema(self) -> None:
        jdbc.execute(self._config, DDL)
        log.info("DLQ 스키마 확인: %s", TABLE)

    def write(self, rejected: "DataFrame") -> None:
        jdbc.append(rejected.select(*COLUMNS), STAGE_TABLE, self._config)
        jdbc.execute(self._config, MERGE_SQL)


def build_dlq_sink(config: Config, *, job: str) -> DlqSink:
    """지금은 테이블 하나뿐이다.

    `ingest.dlq.topic` 이 설정에 있으면 토픽 싱크를 붙일 자리인데, 아직 구현이 없다.
    값이 채워져 있는데 조용히 무시하면 "DLQ 를 토픽에도 쓰고 있다" 고 믿게 되므로 경고한다.
    """
    topic = str(config.get("ingest.dlq.topic", "") or "")
    if topic:
        log.warning(
            "ingest.dlq.topic=%s 이 설정돼 있지만 토픽 싱크는 아직 없다 — 테이블에만 쓴다",
            topic,
        )
    return TableDlqSink(config, job=job)
