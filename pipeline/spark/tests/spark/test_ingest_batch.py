"""배치 하나가 처리 이력과 DLQ 로 갈리는 경로 ([09 §4] 층 2).

층 1 은 판별이 맞는지만 본다. 여기서 보는 것은 **배선** — 파싱이 메시지를 제대로 펴는지,
중복이 실제로 걸러지는지, 거절된 메시지가 두 곳에 다 남는지다. 그건 DataFrame 을 실제로 돌려야
드러난다.

MinIO · PostgreSQL 은 쓰지 않는다. 입력은 인메모리 DataFrame, 싱크는 가짜다.

봉투를 만드는 발판은 `envelope_support` 에 있다 — 평시 경로는 장부 뷰에서 타입이 있는
채로 받지만, 판별이 "칸이 비었다" 와 "파싱이 깨졌다" 를 가르는지 보려면 깨진 JSON 을
만들 수단이 필요하다.
"""

from __future__ import annotations

import json
import pathlib

import pytest
from envelope_support import frame_from_events, frame_from_messages

from trendin.spark.ingest.batch import (
    UNPARSEABLE_KEY_PREFIX,
    deduplicate,
    process_batch,
    with_decision,
)

CONTRACT = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "contract"


def fixture(name: str) -> dict:
    """계약 fixture 를 그대로 다시 처리한다. 손으로 옮겨 적은 메시지를 쓰지 않는다."""
    return json.loads((CONTRACT / name).read_text(encoding="utf-8"))


def from_events(spark, events, *, partition=0, start=0):
    return frame_from_events(spark, events, partition=partition, start=start)


class FakeLedger:
    """처리 이력 대신. 배치가 쓰는 것은 `filter_new` 와 `record` 둘뿐이다.

    `known` 은 `(event_id, stage)` 쌍이다 — 진짜 처리 이력이 그 둘로 대조하기 때문이다
    (`io/ledger.filter_new`). `event_id` 만 대신하면 단계 승격을 테스트할 수 없다.
    """

    def __init__(self, known=()):
        self.known = {pair if isinstance(pair, tuple) else (pair, "contract") for pair in known}
        self.recorded = []

    def filter_new(self, events):
        from pyspark.sql import functions as F

        keep = F.lit(True)
        for event_id, stage in sorted(self.known):
            keep = keep & ~((F.col("event_id") == event_id) & (F.col("stage") == stage))
        return events.where(keep)

    def record(self, rows):
        self.recorded.extend(row.asDict() for row in rows.collect())


def fake_verifier(outcomes):
    """`event_id` -> `(error_type, detail)` 표대로 판별하는 가짜 객체 검증.

    MinIO 를 띄우지 않고 라우팅만 본다. 진짜 조회는 `ingest/objects.verify()` 가 하고
    층 1(`test_object_verify.py`)이 검사한다.
    """

    def _verify(articles):
        from pyspark.sql import functions as F

        error_type = F.lit(None).cast("string")
        detail = F.lit("")
        for event_id, (kind, text) in outcomes.items():
            hit = F.col("event_id") == event_id
            error_type = F.when(hit, F.lit(kind)).otherwise(error_type)
            detail = F.when(hit, F.lit(text)).otherwise(detail)
        return articles.withColumn("error_type", error_type).withColumn("detail", detail)

    return _verify


class FakeDlq:
    def __init__(self):
        self.written = []

    def ensure_schema(self):
        pass

    def write(self, rejected):
        self.written.extend(row.asDict() for row in rejected.collect())


# --- 파싱 -----------------------------------------------------------------


def test_메시지_칸이_펴진다(spark):
    parsed = from_events(spark, [fixture("article-event.json")]).collect()

    assert len(parsed) == 1
    row = parsed[0]
    assert row["event_id"] == "vogue-854414"
    assert row["object_key"] == "fashion/vogue/rss/2026/09/03/854414/article.json"
    assert row["members_only"] is False
    assert row["paywalled"] is False
    assert row["source_country"] == "KR"
    assert row["record_count"] == 1
    # message key 는 메시지 밖 정보다. 계약이 순서 보장을 여기에 걸어 뒀다.
    assert row["message_key"] == "vogue"
    assert row["_corrupt_record"] is None


def test_JSON_이_아니면_원본이_corrupt_칸에_남는다(spark):
    """구조체가 통째로 null 인 경로다.

    여기서 원본을 안 넣으면 판별이 `PARSE_ERROR` 가 아니라 "schema_version 이 없다" 로
    나온다. 사유가 틀리면 생산자가 엉뚱한 곳을 본다.
    """
    parsed = frame_from_messages(spark, [("vogue", "{ not json", 0, 7)])

    row = parsed.collect()[0]
    assert row["_corrupt_record"] == "{ not json"
    assert row["event_id"] is None


# --- 판별과 이력 키 -------------------------------------------------------


def test_세_fixture_가_각자의_형태로_판별된다(spark):
    events = [
        fixture("article-event.json"),
        fixture("run-summary-success.json"),
        fixture("run-summary-failed.json"),
    ]

    judged = {row["event_id"]: row for row in with_decision(from_events(spark, events)).collect()}

    assert judged["vogue-854414"]["event_shape"] == "ARTICLE"
    assert judged["vogue-854414"]["ledger_status"] == "COMPLETED"
    assert judged["vogue-20260903T100000"]["ledger_status"] == "COMPLETED"
    assert judged["wkorea-20260903T100000"]["ledger_status"] == "SOURCE_FAILED"
    assert all(row["error_type"] is None for row in judged.values())


def test_event_id_가_비면_계약_위반으로_잡고_위치로_키를_만든다(spark):
    """치환이 판별보다 먼저면 "event_id 가 없다" 가 영영 안 잡힌다."""
    event = fixture("article-event.json") | {"event_id": ""}

    row = with_decision(from_events(spark, [event], partition=3, start=11)).collect()[0]

    assert row["error_type"] == "CONTRACT_VIOLATION"
    assert row["event_id"] == f"{UNPARSEABLE_KEY_PREFIX}-3-11"


def test_깨진_메시지끼리_처리_이력_키가_겹치지_않는다(spark):
    """같은 키로 뭉치면 두 번째부터 흔적이 사라진다 — DLQ 에 한 건만 남는다."""
    parsed = frame_from_messages(
        spark, [("vogue", "{ bad", 0, 1), ("vogue", "{ also bad", 1, 4)]
    )

    keys = {row["event_id"] for row in with_decision(parsed).collect()}

    assert keys == {f"{UNPARSEABLE_KEY_PREFIX}-0-1", f"{UNPARSEABLE_KEY_PREFIX}-1-4"}


# --- 중복 ----------------------------------------------------------------


def test_배치_안_중복은_먼저_온_오프셋만_남는다(spark):
    payload = json.dumps(fixture("article-event.json"), ensure_ascii=False)
    parsed = frame_from_messages(spark, [("vogue", payload, 0, 9), ("vogue", payload, 0, 4)])

    rows = deduplicate(with_decision(parsed)).collect()

    assert len(rows) == 1
    assert rows[0]["offset"] == 4


# --- 배치 전체 -----------------------------------------------------------


def test_정상_배치는_전부_처리_이력으로_가고_DLQ_는_비어_있다(spark):
    ledger, dlq = FakeLedger(), FakeDlq()
    batch = from_events(
        spark,
        [
            fixture("article-event.json"),
            fixture("run-summary-success.json"),
            fixture("run-summary-failed.json"),
        ],
    )

    result = process_batch(batch, job="ingest", ledger=ledger, dlq=dlq)

    assert (result.received, result.articles, result.summaries, result.rejected) == (3, 1, 2, 0)
    assert len(ledger.recorded) == 3
    assert dlq.written == []
    # 기사는 객체 단계를 목표로 하고 요약은 계약 단계가 마지막 단계다 ([02 §2·§3]).
    stages = {row["event_id"]: row["stage"] for row in ledger.recorded}
    assert stages["vogue-854414"] == "normalize"
    assert stages["vogue-20260903T100000"] == "contract"
    assert stages["wkorea-20260903T100000"] == "contract"
    assert {row["job"] for row in ledger.recorded} == {"ingest"}


@pytest.mark.parametrize(
    "mutate,expected",
    [
        ({"schema_version": 99}, "UNKNOWN_SCHEMA_VERSION"),
        ({"domain": "development"}, "UNKNOWN_DOMAIN"),
        ({"checksum": None}, "CONTRACT_VIOLATION"),
    ],
)
def test_거절된_메시지는_DLQ_와_처리_이력_양쪽에_남는다(spark, mutate, expected):
    """처리 이력에 안 남기면 재실행마다 같은 이벤트가 다시 DLQ 로 가고, 사람이 손대지 않았는데
    `retry_count` 가 올라간다."""
    ledger, dlq = FakeLedger(), FakeDlq()
    batch = from_events(spark, [fixture("article-event.json") | mutate])

    result = process_batch(batch, job="ingest", ledger=ledger, dlq=dlq)

    assert result.rejected == 1
    assert [row["error_type"] for row in dlq.written] == [expected]
    assert [row["status"] for row in ledger.recorded] == ["FAILED"]
    # 메시지에서 걸렸으니 객체까지 가지 않는다.
    assert [row["stage"] for row in ledger.recorded] == ["contract"]
    # 원본 메시지가 그대로 남아야 사람이 되돌릴 수 있다 ([02 §5]).
    assert json.loads(dlq.written[0]["original_event"])["event_id"] == "vogue-854414"
    assert dlq.written[0]["retry_count"] == 0


def test_처리_이력에_있는_이벤트는_두_번째부터_걸린다(spark):
    ledger, dlq = FakeLedger(known={("vogue-854414", "normalize")}), FakeDlq()
    batch = from_events(spark, [fixture("article-event.json"), fixture("run-summary-success.json")])

    result = process_batch(batch, job="ingest", ledger=ledger, dlq=dlq)

    assert result.received == 2
    assert result.duplicates == 1
    assert result.articles == 0
    assert [row["event_id"] for row in ledger.recorded] == ["vogue-20260903T100000"]


def test_force_는_처리_이력을_무시한다(spark):
    """`--force` 재처리 ([02 §6])."""
    ledger, dlq = FakeLedger(known={("vogue-854414", "normalize")}), FakeDlq()
    batch = from_events(spark, [fixture("article-event.json")])

    result = process_batch(batch, job="ingest", ledger=ledger, dlq=dlq, force=True)

    assert result.articles == 1
    assert result.duplicates == 0


def test_전부_걸리면_아무것도_쓰지_않는다(spark):
    """빈 DataFrame 을 JDBC 로 보내면 스테이징만 건드리고 MERGE 가 헛돈다."""
    ledger, dlq = FakeLedger(known={("vogue-854414", "normalize")}), FakeDlq()
    batch = from_events(spark, [fixture("article-event.json")])

    result = process_batch(batch, job="ingest", ledger=ledger, dlq=dlq)

    assert result.recorded == 0
    assert ledger.recorded == []
    assert dlq.written == []


# --- 객체 검증 단계 ([02 §3]) --------------------------------------------


def test_객체_검증은_기사_이벤트만_탄다(spark):
    """요약 이벤트에는 조회할 객체가 없다. 보내면 `object_key` 가 null 이라 헛돈다."""
    seen = []

    def _verify(articles):
        seen.extend(row["event_id"] for row in articles.collect())
        return articles

    ledger, dlq = FakeLedger(), FakeDlq()
    batch = from_events(
        spark,
        [
            fixture("article-event.json"),
            fixture("run-summary-success.json"),
            fixture("run-summary-failed.json"),
        ],
    )

    process_batch(batch, job="ingest", ledger=ledger, dlq=dlq, verify_objects=_verify)

    assert seen == ["vogue-854414"]


def test_메시지에서_거절된_기사는_객체를_조회하지_않는다(spark):
    """이미 DLQ 로 갈 이벤트를 위해 MinIO 를 두드릴 이유가 없다."""
    seen = []

    def _verify(articles):
        seen.extend(row["event_id"] for row in articles.collect())
        return articles

    ledger, dlq = FakeLedger(), FakeDlq()
    batch = from_events(spark, [fixture("article-event.json") | {"checksum": None}])

    process_batch(batch, job="ingest", ledger=ledger, dlq=dlq, verify_objects=_verify)

    assert seen == []


@pytest.mark.parametrize(
    "error_type",
    ["OBJECT_NOT_FOUND", "CHECKSUM_MISMATCH", "ARTICLE_CONTRACT_VIOLATION"],
)
def test_객체_단계_실패는_FAILED_로_내려_DLQ_와_처리_이력에_남는다(spark, error_type):
    ledger, dlq = FakeLedger(), FakeDlq()
    verify = fake_verifier({"vogue-854414": (error_type, "사유")})
    batch = from_events(spark, [fixture("article-event.json")])

    result = process_batch(batch, job="ingest", ledger=ledger, dlq=dlq, verify_objects=verify)

    assert (result.articles, result.rejected) == (0, 1)
    assert [row["error_type"] for row in dlq.written] == [error_type]
    row = ledger.recorded[0]
    assert (row["status"], row["stage"], row["error_type"]) == ("FAILED", "normalize", error_type)


def test_객체_단계를_통과하면_COMPLETED_그대로다(spark):
    ledger, dlq = FakeLedger(), FakeDlq()
    verify = fake_verifier({})
    batch = from_events(spark, [fixture("article-event.json")])

    result = process_batch(batch, job="ingest", ledger=ledger, dlq=dlq, verify_objects=verify)

    assert result.articles == 1
    row = ledger.recorded[0]
    assert (row["status"], row["stage"], row["error_type"]) == ("COMPLETED", "normalize", None)


def test_계약_단계까지만_적힌_기사는_정제_단계에서_다시_처리된다(spark):
    """단계를 더할 때 손으로 옮길 것이 없어야 한다.

    `event_id` 만 대조했다면 이 행이 객체 검증을 통째로 건너뛰고, **아무 증상도 없었다.**
    """
    ledger = FakeLedger(known={("vogue-854414", "contract")})
    dlq = FakeDlq()
    batch = from_events(spark, [fixture("article-event.json")])

    result = process_batch(
        batch, job="ingest", ledger=ledger, dlq=dlq, verify_objects=fake_verifier({})
    )

    assert result.articles == 1
    assert ledger.recorded[0]["stage"] == "normalize"


def test_정제_단계까지_적힌_기사는_걸러진다(spark):
    ledger = FakeLedger(known={("vogue-854414", "normalize")})
    dlq = FakeDlq()
    batch = from_events(spark, [fixture("article-event.json")])

    result = process_batch(
        batch, job="ingest", ledger=ledger, dlq=dlq, verify_objects=fake_verifier({})
    )

    assert (result.received, result.duplicates, result.articles) == (1, 1, 0)
    assert ledger.recorded == []
