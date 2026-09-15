"""JSON 봉투를 배치가 받는 프레임 모양으로 펴는 시험용 헬퍼.

**이건 시험 발판이지 평시 경로가 아니다.** 평시에 봉투는 장부 뷰에서 타입이 있는 채로
오므로(`ingest/collected.py`) 프로덕션에는 JSON 파싱이 없다. 그런데 배치의 판별 경로
(`with_decision` → `io/contract.classify`)는 "칸이 비었다" · "파싱이 통째로 실패했다" 를
여전히 구분해야 하고, 그 구분을 시험하려면 깨진 JSON 을 만들 수단이 필요하다.

Kafka 를 걷어내면서(S15P21A102-247) `io/kafka.parse_events` 가 사라졌고, 그 함수가 하던
모양 맞추기를 여기로 옮겼다. 메타 칸 이름을 Kafka 시절 그대로 두는 이유는 `io/schema.py`
의 `META_COLUMNS` 와 같다 — 처리 이력이 그 이름으로 값을 받고 있다.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from trendin.spark.io.schema import CORRUPT_FIELD, EVENT_SCHEMA, META_COLUMNS

RAW_SCHEMA = "key string, value string, partition int, offset long, timestamp timestamp"
NOW = datetime(2026, 9, 3, 2, 0, tzinfo=timezone.utc)

_PARSE_OPTIONS = {"mode": "PERMISSIVE", "columnNameOfCorruptRecord": CORRUPT_FIELD}


def raw_rows(spark, messages, *, now: datetime = NOW):
    """`(key, value, partition, offset)` 를 원본 행 모양으로."""
    rows = [(key, value, part, off, now) for key, value, part, off in messages]
    return spark.createDataFrame(rows, RAW_SCHEMA)


def parse_rows(raw):
    """원본 행을 봉투 칸으로 편다.

    **파싱이 통째로 실패하면 구조체 자체가 `null` 이다.** 그 경우 `_corrupt_record` 도
    `null` 이라, 그대로 두면 판별이 `PARSE_ERROR` 가 아니라 "schema_version 이 없다" 로
    나온다. 사유가 틀리면 사람이 엉뚱한 곳을 보게 되므로 여기서 원본 문자열을 넣어 준다.
    """
    from pyspark.sql import functions as F

    value = F.col("value").cast("string")
    parsed = raw.select(
        F.col("key").cast("string").alias("message_key"),
        F.col("partition").alias("partition"),
        F.col("offset").alias("offset"),
        F.col("timestamp").alias("kafka_timestamp"),
        value.alias("raw_value"),
        F.from_json(value, EVENT_SCHEMA, _PARSE_OPTIONS).alias("_event"),
    )
    fields = [
        F.col("_event").getField(field.name).alias(field.name)
        for field in EVENT_SCHEMA.fields
        if field.name != CORRUPT_FIELD
    ]
    corrupt = (
        F.when(F.col("_event").isNull(), F.col("raw_value"))
        .otherwise(F.col("_event").getField(CORRUPT_FIELD))
        .alias(CORRUPT_FIELD)
    )
    return parsed.select(*META_COLUMNS, *fields, corrupt)


def frame_from_messages(spark, messages, *, now: datetime = NOW):
    """`(key, value, partition, offset)` 목록에서 바로 봉투 프레임으로."""
    return parse_rows(raw_rows(spark, messages, now=now))


def frame_from_events(spark, events, *, partition: int = 0, start: int = 0, now: datetime = NOW):
    """봉투 사전 목록에서. 직렬화·오프셋 부여까지 여기서 한다."""
    messages = [
        (event.get("source_id"), json.dumps(event, ensure_ascii=False), partition, start + index)
        for index, event in enumerate(events)
    ]
    return frame_from_messages(spark, messages, now=now)
