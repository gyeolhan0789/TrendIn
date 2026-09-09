"""판별 → 처리 이력 상태 ([02 §2] · [08 §3]). SparkSession 없이 검사한다 ([09 §4] 층 1).

`decide()` 가 틀리면 정상 이벤트가 DLQ 로 가거나 그 반대가 된다. 둘 다 조용히 일어나고
몇 주 뒤 통계의 구멍으로만 나타난다.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from trendin.spark.ingest.routing import (
    COMPLETED,
    FAILED,
    SOURCE_FAILED,
    STAGE_CONTRACT,
    STAGE_NORMALIZE,
    decide,
)

CONTRACT = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "contract"


def fixture(name: str) -> dict:
    """계약 fixture 를 그대로 판별에 넣는다.

    손으로 옮겨 적은 메시지가 아니라 생산 측이 `events.py` 로 만들어 준 파일을 쓴다. 메시지가
    바뀌면 생산 측 `test_contract_fixtures.py` 가 fixture 를 갱신하게 만들고, 그 갱신이
    이 테스트까지 내려온다 — 두 벌이 갈릴 자리가 없어진다.
    """
    return json.loads((CONTRACT / name).read_text(encoding="utf-8"))


def test_기사_이벤트는_COMPLETED_다():
    decision = decide(fixture("article-event.json"))

    assert decision.shape == "ARTICLE"
    assert decision.status == COMPLETED
    assert not decision.rejected
    # 메시지를 통과한 기사는 정제까지 간다 — 객체 검증에 걸려도, 필터로 버려져도 거기서
    # 끝난다. 171 에서 `object` 에서 올라갔고, 그래서 170 이 `object` 까지 적어 둔 기사들이
    # 이 배포에서 다시 처리된다 ([08 §3] 의 단계 승격).
    assert decision.stage == STAGE_NORMALIZE


def test_성공_요약은_COMPLETED_다():
    decision = decide(fixture("run-summary-success.json"))

    assert decision.shape == "SUMMARY"
    assert decision.status == COMPLETED
    assert not decision.rejected
    # 요약 이벤트는 객체가 없어 계약 단계가 마지막 단계다.
    assert decision.stage == STAGE_CONTRACT


def test_실패_요약은_SOURCE_FAILED_고_DLQ_가_아니다():
    """수집이 실패한 것이지 우리가 실패한 것이 아니다. 처리 이력에 남아야 누락과 구분된다."""
    decision = decide(fixture("run-summary-failed.json"))

    assert decision.shape == "SUMMARY"
    assert decision.status == SOURCE_FAILED
    assert not decision.rejected
    assert decision.error_type is None


def test_object_key_가_null_인_success_요약을_거절하지_않는다():
    """배치 계약의 "success 인데 object_key null 이면 DLQ" 를 남겨두면 여기서 걸린다.

    그대로 두면 정상 실행마다 소스당 하나씩 DLQ 가 쌓이고, 수집 상태가 통째로 사라진다.
    """
    event = fixture("run-summary-success.json")

    assert event["object_key"] is None
    assert event["record_count"] > 0
    assert decide(event).status == COMPLETED


@pytest.mark.parametrize(
    "mutate,expected",
    [
        ({"schema_version": 99}, "UNKNOWN_SCHEMA_VERSION"),
        ({"domain": "development"}, "UNKNOWN_DOMAIN"),
        ({"checksum": None}, "CONTRACT_VIOLATION"),
        ({"url": None}, "CONTRACT_VIOLATION"),
        ({"event_id": ""}, "CONTRACT_VIOLATION"),
    ],
)
def test_거절되면_FAILED_고_사유가_남는다(mutate, expected):
    event = fixture("article-event.json") | mutate

    decision = decide(event)

    assert decision.rejected
    assert decision.error_type == expected
    assert decision.status == FAILED
    assert decision.detail  # 사람이 읽을 사유가 비어 있으면 DLQ 를 봐도 알 수 없다
    # 메시지에서 걸렸으니 객체까지 가지 않는다.
    assert decision.stage == STAGE_CONTRACT


def test_파싱_실패는_PARSE_ERROR_고_FAILED_다():
    decision = decide({"_corrupt_record": "{ not json"})

    assert decision.error_type == "PARSE_ERROR"
    assert decision.status == FAILED
    assert decision.shape is None
