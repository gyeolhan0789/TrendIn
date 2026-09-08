"""Kafka `raw-file-ready` 소비 ([02 §1]).

`Trigger.AvailableNow` 로 그때까지 쌓인 오프셋까지 읽고 스스로 끝난다 ([01 §1]). 오프셋
관리는 checkpoint 가 하므로 이 모듈은 "어디까지 읽었나" 를 모른다.

**스키마를 추론하지 않는다.** `from_json` 에 `EVENT_SCHEMA` 를 명시하고 `PERMISSIVE` +
`_corrupt_record` 로 받는다. 이벤트 하나가 깨졌다고 배치 전체를 버릴 이유가 없다.

옵션을 만드는 부분과 파싱하는 부분을 나눠 둔 이유는 층 1 에서 브로커 없이 검사하기
위해서다 ([09 §4]).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from trendin.spark.common.config import Config
from trendin.spark.common.logging import get_logger
from trendin.spark.io.schema import CORRUPT_FIELD, EVENT_SCHEMA

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

log = get_logger(__name__)

DEFAULT_GROUP_ID_PREFIX = "trendin-spark"
DEFAULT_STARTING_OFFSETS = "earliest"

# 메시지 자체가 아니라 메시지가 어디서 왔는지를 담는 칸. 계약에 message key 와 순서 보장이
# 들어 있어서(`spark-integration.md` §2) 메시지만 봐서는 확인할 수 없는 것이 있다.
META_COLUMNS = ("message_key", "partition", "offset", "kafka_timestamp", "raw_value")

_PARSE_OPTIONS = {"mode": "PERMISSIVE", "columnNameOfCorruptRecord": CORRUPT_FIELD}


def group_id_prefix(config: Config, *, job: str) -> str:
    """`{kafka.group_id_prefix}-{job}` — `ingest` 면 `trendin-spark-ingest` ([02 §1]).

    Spark 는 이 접두어 뒤에 자기 식별자를 붙여 실제 group 을 만든다. `kafka.group.id` 를
    직접 박지 않는 이유는 Structured Streaming 이 오프셋을 checkpoint 로 관리하기 때문이다
    — group 을 고정하면 브로커가 들고 있는 커밋 오프셋과 checkpoint 가 두 벌이 된다.
    """
    prefix = str(config.get("kafka.group_id_prefix", DEFAULT_GROUP_ID_PREFIX)).rstrip("-")
    return f"{prefix}-{job}"


def kafka_options(
    config: Config, *, job: str, starting_offsets: str = DEFAULT_STARTING_OFFSETS
) -> dict[str, str]:
    """`readStream.format("kafka")` 에 넣을 옵션 전부.

    `failOnDataLoss=true` 인 이유 ([02 §1]) — retention 이 지나 오프셋이 사라졌는데 조용히
    건너뛰면 그 구간이 통째로 유실된다. 유실은 통계의 구멍으로 나타나고 구멍은 몇 주 뒤에야
    눈에 띈다. 차라리 Job 을 실패시키고 사람이 `--source objects` 로 복구하게 한다.
    """
    return {
        "kafka.bootstrap.servers": str(config.require("kafka.bootstrap_servers")),
        "subscribe": str(config.require("kafka.topics.raw_file_ready")),
        "startingOffsets": starting_offsets,
        "failOnDataLoss": "true",
        "groupIdPrefix": group_id_prefix(config, job=job),
    }


def parse_events(raw: "DataFrame") -> "DataFrame":
    """Kafka 원본 행을 메시지 칸으로 편다. 구조체로 두지 않고 펴는 이유는 하류가 전부
    칸 이름으로 판별하기 때문이다 — `event.object_key` 보다 `object_key` 가 읽기 쉽다.

    **파싱이 통째로 실패하면 구조체 자체가 `null` 이다.** 그 경우 `_corrupt_record` 도
    `null` 이라, 그대로 두면 판별이 `PARSE_ERROR` 가 아니라 "schema_version 이 없다" 로
    나온다. 사유가 틀리면 생산자가 엉뚱한 곳을 보게 되므로 여기서 원본 문자열을 넣어 준다.
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


def read_events(
    spark: Any,
    config: Config,
    *,
    job: str,
    starting_offsets: str = DEFAULT_STARTING_OFFSETS,
) -> "DataFrame":
    """토픽을 읽는 스트리밍 DataFrame. 트리거와 싱크는 부른 쪽이 정한다."""
    options = kafka_options(config, job=job, starting_offsets=starting_offsets)
    log.info(
        "kafka 소비 준비: topic=%s bootstrap=%s groupIdPrefix=%s",
        options["subscribe"],
        options["kafka.bootstrap.servers"],
        options["groupIdPrefix"],
    )
    return parse_events(spark.readStream.format("kafka").options(**options).load())
