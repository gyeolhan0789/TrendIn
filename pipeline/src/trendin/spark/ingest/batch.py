"""마이크로배치 하나를 처리 이력과 DLQ 로 가르는 배선 ([02 §2] · [01 §4]).

`foreachBatch` 가 부르는 자리다. 판별은 `ingest/routing.py`(순수 함수), 저장은
`io/ledger.py` · `io/dlq.py` 가 하고, 여기는 **순서**만 정한다.

순서가 의미를 갖는다:

1. 판별 — 원본 메시지 그대로. `event_id` 를 손대기 **전에** 한다
2. 배치 안 중복 제거 — 같은 `event_id` 가 한 배치에 두 번 올 수 있다 (at-least-once)
3. 처리 이력 대조 — 그 단계까지 이미 적힌 것은 통째로 건너뛴다 (중복 차단 2)
4. **객체 검증** — 메시지를 통과한 기사 이벤트만 ([02 §3])
5. **정제·적재** — 객체 검증까지 통과한 기사만 ([03])
6. 거절된 메시지를 DLQ 로, 전부를 처리 이력으로

**3 번이 4 번보다 먼저인 이유** — 객체 조회는 이 단계에서 가장 비싼 일이다. 이미 처리한
이벤트를 걸러낸 뒤에 조회해야 재실행이 MinIO 를 다시 조회하지 않는다.

**6 번이 거절된 메시지도 처리 이력에 남기는 이유** — 안 남기면 재실행마다 같은 이벤트가 다시 DLQ 로
가고, `retry_count` 가 사람이 손대지 않았는데도 올라간다.

**정제에서 필터로 버려진 문서는 DLQ 로 가지 않는다.** 그건 계약 위반이 아니라 정상적인 판정
결과다 ([03 §6]) — 짧은 본문과 근사 중복은 생산자가 고칠 것이 없다. 사유는 처리 이력의
`detail` 과 `pl_batch_stat` 에 남는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from trendin.spark.common.logging import get_logger
from trendin.spark.ingest.routing import FAILED, decide
from trendin.spark.io import dlq as dlq_io
from trendin.spark.io import ledger as ledger_io
from trendin.spark.io.schema import EVENT_SCHEMA

if TYPE_CHECKING:
    from pyspark.sql import Column, DataFrame

log = get_logger(__name__)

# 메시지 칸 전부. `_corrupt_record` 도 판별 입력이라 포함한다.
ENVELOPE_COLUMNS = tuple(field.name for field in EVENT_SCHEMA.fields)

# 파싱조차 안 된 메시지의 이력 키. `event_id` 가 없으니 위치(partition·offset)로 만든다.
#
# 빈 문자열을 그대로 키로 쓰면 서로 다른 깨진 메시지가 처리 이력의 같은 행을 덮어쓴다. 그러면
# 두 번째 것부터는 흔적이 사라지고, DLQ 에 한 건만 남아 "한 번 깨졌다" 로 보인다.
#
# **대가는 재발행에서 드러난다.** 키가 내용이 아니라 위치라서, 같은 깨진 바이트가 새 오프셋에
# 다시 오면 처리 이력이 못 걸러 DLQ 행이 하나 더 는다 (2026-09-08 실측 확인). 그게 맞다고 본다 —
# 생산자가 깨진 메시지를 또 냈다는 사실 자체가 신호이고, 내용으로 묶으면 그 반복이 보이지
# 않는다. 정상 이벤트는 `event_id` 가 안정적이라 이 경로를 타지 않는다.
UNPARSEABLE_KEY_PREFIX = "_unparseable"


@dataclass(frozen=True, slots=True)
class BatchResult:
    """배치 하나의 처리 결과. 로그와 테스트가 읽는다."""

    received: int = 0
    duplicates: int = 0
    articles: int = 0
    summaries: int = 0
    rejected: int = 0
    # 정제 필터로 버려진 문서 수 ([03 §6]). 거절(`rejected`)과 다르다 — DLQ 로 가지 않는다.
    filtered: int = 0

    @property
    def recorded(self) -> int:
        return self.articles + self.summaries + self.rejected


def _decision_schema():
    from pyspark.sql.types import StringType, StructField, StructType

    return StructType(
        [
            StructField("shape", StringType(), True),
            StructField("error_type", StringType(), True),
            StructField("detail", StringType(), True),
            StructField("status", StringType(), True),
            StructField("stage", StringType(), True),
        ]
    )


def _decision_udf():
    """`decide()` 를 행마다 부른다.

    파이썬 UDF 인 이유 — 판별이 `if` 열 몇 개라 SQL 식으로도 쓸 수 있지만, 그러면 계약이
    파이썬과 SQL 두 곳에 살게 된다. [00 §3] 규모(하루 수백 건)에서 왕복 비용은 무시할 수
    있고, 계약이 한 곳에 있는 값이 훨씬 크다.
    """
    from pyspark.sql import functions as F

    def _apply(row):
        decision = decide(row.asDict())
        return (
            decision.shape,
            decision.error_type,
            decision.detail,
            decision.status,
            decision.stage,
        )

    return F.udf(_apply, _decision_schema())


def with_decision(events: "DataFrame") -> "DataFrame":
    """판별 칸을 붙이고 이력 키를 확정한다.

    **판별이 `event_id` 치환보다 먼저다.** 뒤집으면 `event_id` 가 빈 이벤트에 우리가 만든
    키가 들어가서, `classify` 의 "event_id 가 없다" 계약 위반이 영영 안 잡힌다.
    """
    from pyspark.sql import functions as F

    envelope = F.struct(*[F.col(name) for name in ENVELOPE_COLUMNS])
    judged = events.withColumn("_decision", _decision_udf()(envelope))

    blank = F.trim(F.coalesce(F.col("event_id"), F.lit(""))) == ""
    fallback = F.concat_ws("-", F.lit(UNPARSEABLE_KEY_PREFIX), F.col("partition"), F.col("offset"))
    return (
        judged.select(
            "*",
            F.when(blank, fallback).otherwise(F.col("event_id")).alias("_ledger_key"),
            F.col("_decision.shape").alias("event_shape"),
            F.col("_decision.error_type").alias("error_type"),
            F.col("_decision.detail").alias("detail"),
            F.col("_decision.status").alias("ledger_status"),
            F.col("_decision.stage").alias("stage"),
        )
        .drop("_decision", "event_id")
        .withColumnRenamed("_ledger_key", "event_id")
    )


def deduplicate(judged: "DataFrame") -> "DataFrame":
    """배치 안에서 `event_id` 하나를 한 번만 남긴다. 먼저 온 오프셋을 남긴다.

    `dropDuplicates` 대신 오프셋으로 고르는 이유는 재현성이다. 계약상 같은 `event_id` 는
    같은 내용이지만, 그게 깨졌을 때 어느 쪽이 남았는지 설명할 수 있어야 한다.
    """
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    order = Window.partitionBy("event_id").orderBy(F.col("partition"), F.col("offset"))
    return (
        judged.withColumn("_rank", F.row_number().over(order))
        .where(F.col("_rank") == 1)
        .drop("_rank")
    )


def _timestamp(name: str) -> "Column":
    """ISO-8601 문자열을 timestamptz 로. 못 읽으면 `null` 이다.

    `to_timestamp` 가 아니라 `try_` 인 이유 — Spark 4 는 ANSI 가 기본이라 값 하나가
    이상하면 **배치 전체가 죽는다.** `collected_at` 은 계약 위반 판별 대상이 아니므로
    (`contract._check_article`) 이상한 값이 판별을 통과해 여기까지 온다.
    """
    from pyspark.sql import functions as F

    return F.try_to_timestamp(F.col(name))


def ledger_rows(judged: "DataFrame", *, job: str) -> "DataFrame":
    from pyspark.sql import functions as F

    return judged.select(
        F.col("event_id"),
        F.lit(job).alias("job"),
        F.col("stage"),
        F.col("event_shape"),
        F.col("ledger_status").alias("status"),
        F.col("error_type"),
        F.col("detail"),
        F.col("domain"),
        F.col("source_id"),
        F.col("run_id"),
        F.col("article_id"),
        F.col("record_count").cast("bigint").alias("record_count"),
        _timestamp("collected_at").alias("collected_at"),
        F.col("partition").cast("int").alias("topic_partition"),
        F.col("offset").cast("bigint").alias("topic_offset"),
        F.current_timestamp().alias("processed_at"),
    )


def dlq_rows(judged: "DataFrame", *, job: str) -> "DataFrame":
    from pyspark.sql import functions as F

    return judged.select(
        F.col("event_id"),
        F.lit(job).alias("job"),
        F.col("error_type"),
        F.col("detail").alias("error_detail"),
        # 원본 바이트를 그대로 남긴다. 파싱에 실패한 것도 사람이 볼 수 있어야 한다.
        F.col("raw_value").alias("original_event"),
        F.col("partition").cast("int").alias("topic_partition"),
        F.col("offset").cast("bigint").alias("topic_offset"),
        # 처음 막힌 것이다. 다시 막히면 MERGE 가 서버에서 올린다.
        F.lit(0).alias("retry_count"),
        F.current_timestamp().alias("failed_at"),
    )


def tally(fresh: "DataFrame") -> tuple[int, int, int]:
    """`(기사, 요약, 거절)` 건수. 한 번의 집계로 센다.

    세 번 `count()` 하면 배치를 세 번 훑는다. 캐시가 있어도 공짜가 아니고, 무엇보다 세
    숫자가 같은 스냅샷에서 나왔다는 보장이 없어진다.
    """
    from pyspark.sql import functions as F

    articles = summaries = rejected = 0
    rows = fresh.groupBy("event_shape", "error_type").agg(F.count(F.lit(1)).alias("n")).collect()
    for row in rows:
        if row["error_type"] is not None:
            rejected += row["n"]
        elif row["event_shape"] == "ARTICLE":
            articles += row["n"]
        elif row["event_shape"] == "SUMMARY":
            summaries += row["n"]
    return articles, summaries, rejected


def count_filtered(fresh: "DataFrame") -> int:
    """정제 필터로 버려진 문서 수. 정제 단계를 안 돌렸으면 0 이다.

    칸이 있는지 먼저 보는 이유는 `normalize=None` 인 실행(층 2 테스트, 정제가 붙기 전 배포)에서
    그 칸이 아예 없기 때문이다. `tally` 와 합치지 않은 이유는 축이 달라서다 — 그쪽은
    `(event_shape, error_type)` 로 묶고 이건 사유 칸 하나를 본다.
    """
    from pyspark.sql import functions as F

    from trendin.spark.ingest.normalize import FILTER_REASON

    if FILTER_REASON not in fresh.columns:
        return 0
    return fresh.where(F.col(FILTER_REASON).isNotNull() & (F.col(FILTER_REASON) != "")).count()


def apply_object_stage(
    fresh: "DataFrame", verify: Callable[["DataFrame"], "DataFrame"]
) -> "DataFrame":
    """메시지를 통과한 기사 이벤트만 객체 검증에 보내고, 결과를 나머지와 합친다 ([02 §3]).

    요약 이벤트와 이미 거절된 이벤트는 조회할 객체가 없으므로 지나간다. 검증에서 걸리면
    상태를 `FAILED` 로 내린다 — 그 한 자리에서만 뒤집는다. `verify` 안에서 상태까지
    건드리게 하면 "어디서 FAILED 가 됐나" 를 두 곳에서 찾아야 한다.
    """
    from pyspark.sql import functions as F

    from trendin.spark.ingest.objects import ARTICLE_JSON

    # **양쪽에 칸을 먼저 맞춘다.** 검증이 `article_json` 을 붙여 오는데(정제 단계가 그 값을
    # 쓴다) 지나가는 쪽에는 그 칸이 없어서, 맞추지 않으면 `unionByName` 이 그 자리에서 죽는다.
    # 요약 이벤트와 거절된 이벤트에는 읽을 객체가 없으므로 `null` 이 맞는 값이다.
    aligned = fresh.withColumn(ARTICLE_JSON, F.lit(None).cast("string"))

    targets = F.col("error_type").isNull() & (F.col("event_shape") == "ARTICLE")
    passthrough = aligned.where(~targets | targets.isNull())
    verified = verify(aligned.where(targets)).withColumn(
        "ledger_status",
        F.when(F.col("error_type").isNotNull(), F.lit(FAILED)).otherwise(F.col("ledger_status")),
    )
    return passthrough.unionByName(verified)


def apply_normalize_stage(
    fresh: "DataFrame", normalize: Callable[["DataFrame"], "DataFrame"]
) -> "DataFrame":
    """객체 검증까지 통과한 기사만 정제에 보내고, 결과를 나머지와 합친다 ([03]).

    **`article_json` 이 있는 행만 보낸다.** 요약 이벤트와 거절된 이벤트에는 읽을 내용이 없고,
    객체 검증을 건너뛴 실행(`verify_objects=None`, 층 2 테스트)에서는 그 칸이 통째로 `null`
    이라 정제가 빈 프레임을 받는다 — 그게 맞는 동작이다. **검증하지 않은 내용을 정제하지 않는다.**

    **필터 사유를 `detail` 에 접어 넣는다.** 그래야 `ledger_rows` 가 바뀌지 않고, 처리 이력
    한 행만 봐도 그 문서가 왜 `curated` 에 없는지 알 수 있다. `ledger_status` 는 건드리지
    않는다 — 필터로 버린 것은 실패가 아니라 판정이다 ([03 §6]).
    """
    from pyspark.sql import functions as F

    from trendin.spark.ingest.normalize import FILTER_REASON
    from trendin.spark.ingest.objects import ARTICLE_JSON

    aligned = fresh.withColumn(FILTER_REASON, F.lit(None).cast("string"))

    targets = (
        F.col("error_type").isNull()
        & (F.col("event_shape") == "ARTICLE")
        & F.col(ARTICLE_JSON).isNotNull()
    )
    passthrough = aligned.where(~targets | targets.isNull())
    normalized = normalize(fresh.where(targets))

    filtered = F.col(FILTER_REASON).isNotNull() & (F.col(FILTER_REASON) != "")
    return passthrough.unionByName(
        normalized.withColumn(
            "detail", F.when(filtered, F.col(FILTER_REASON)).otherwise(F.col("detail"))
        )
    )


def process_batch(
    batch: "DataFrame",
    *,
    job: str,
    ledger: "ledger_io.Ledger",
    dlq: "dlq_io.DlqSink",
    verify_objects: Callable[["DataFrame"], "DataFrame"] | None = None,
    normalize: Callable[["DataFrame"], "DataFrame"] | None = None,
    force: bool = False,
    decided: bool = False,
) -> BatchResult:
    """배치 하나. 처리 이력에 없는 이벤트만 처리하고, 거절된 메시지는 DLQ 에도 남긴다.

    `verify_objects` · `normalize` 가 `None` 이면 그 단계를 건너뛴다. 주입으로 받는 이유는
    층 2 가 MinIO·PostgreSQL 없이 라우팅을 검사해야 하기 때문이다 ([09 §4]) — 진짜 구현은
    `ingest/objects.verifier()` 와 `ingest/normalize.normalizer()` 가 만든다.

    `force` 는 `--force` 재처리다 ([02 §6]) — 처리 이력의 기록을 무시하고 다시 처리한다.

    `decided` 는 백필 전용이다 ([02 §6] 모드 B). 재구성한 봉투는 판별 칸이 이미 채워져 있고,
    `with_decision` 을 다시 태우면 **우리가 방금 만든 봉투를 `classify` 로 검증하게 된다** —
    `url`·`published_at` 이 없으므로 재구성한 이벤트 전부가 `CONTRACT_VIOLATION` 으로 DLQ 에
    간다. 진짜 검증은 객체 쪽에 그대로 남아 있다 (`ingest/backfill.py` 의 표).

    **중복 제거는 두 경로 모두 탄다.** 목록 조회가 같은 키를 두 번 주지는 않지만, 그 보장이
    계약에 있는 것이 아니라 구현에 있다.
    """
    from pyspark.sql import functions as F

    judged = deduplicate(batch if decided else with_decision(batch)).cache()
    verified = None
    try:
        received = judged.count()
        fresh = judged if force else ledger.filter_new(judged)
        if verify_objects is not None:
            fresh = apply_object_stage(fresh, verify_objects)
        # 객체 검증 결과를 여기서 **한 번** 고정한다. 캐시하지 않으면 정제 단계와 그 뒤의
        # 처리 이력·DLQ 쓰기가 각자 lineage 를 다시 계산해 MinIO 를 두 번 읽고, 그 사이 객체가
        # 바뀌면 `curated` 에 쓴 문서와 처리 이력의 판정이 서로 다른 내용을 말한다.
        verified = fresh.cache()
        verified.count()
        fresh = verified
        if normalize is not None:
            fresh = apply_normalize_stage(fresh, normalize)
        fresh = fresh.cache()
        try:
            articles, summaries, rejected = tally(fresh)
            filtered = count_filtered(fresh)

            if rejected:
                dlq.write(dlq_rows(fresh.where(F.col("error_type").isNotNull()), job=job))
            if articles or summaries or rejected:
                ledger.record(ledger_rows(fresh, job=job))
        finally:
            fresh.unpersist()
    finally:
        if verified is not None:
            verified.unpersist()
        judged.unpersist()

    result = BatchResult(
        received=received,
        duplicates=received - (articles + summaries + rejected),
        articles=articles,
        summaries=summaries,
        rejected=rejected,
        filtered=filtered,
    )
    log.info(
        "배치 처리: 받음=%d 처리 이력에서 걸림=%d 기사=%d 요약=%d DLQ=%d 정제에서 버림=%d",
        result.received,
        result.duplicates,
        result.articles,
        result.summaries,
        result.rejected,
        result.filtered,
    )
    return result
