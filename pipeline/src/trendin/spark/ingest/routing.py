"""이벤트 하나가 처리 이력에 어떤 상태로 남는지 ([02 §2] · [08 §3]).

`io/contract.classify()` 가 "어디로 가는가" 를 정하고, 여기서 그 판별을 **처리 이력 상태**로
옮긴다. 둘을 나눈 이유는 판별이 계약이고 상태는 우리 저장 방식이라 바뀌는 이유가 다르기
때문이다 — DLQ 사유가 늘어도 처리 이력 상태는 그대로일 수 있다.

**pyspark 를 import 하지 않는다.** 매핑 하나에 대한 순수 함수라 SparkSession 없이 검사할
수 있다 ([09 §4] 층 1). Spark 쪽 배선은 `ingest/batch.py` 가 이 함수를 UDF 로 감싼다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from trendin.spark.io.contract import EventShape, classify

# 처리 이력 상태 ([08 §3]).
#
# `SOURCE_FAILED` 는 기사 이벤트에 나올 수 없다 — 기사 이벤트의 `status` 는 늘 `success`
# 이고(불변식 5), 아니면 `classify` 가 먼저 계약 위반으로 걷어낸다.
COMPLETED = "COMPLETED"
SOURCE_FAILED = "SOURCE_FAILED"
FAILED = "FAILED"

# 이 Job 이 이벤트를 어디까지 끌고 갔는지.
#
# **`COMPLETED` 가 "정제·적재까지 끝났다" 를 뜻하지 않는다.** 단계가 늘 때마다 값이 늘고,
# `ledger.filter_new()` 는 `(event_id, stage)` 로 대조한다. 그래서 옛 단계까지만 적힌 행은
# 새 단계에서 다시 처리되고 그 자리에서 갱신된다 — 단계를 더할 때 손으로 옮길 것이 없다.
#
# 요약 이벤트는 객체가 없어 `contract` 가 마지막 단계다 ([02 §2]).
STAGE_CONTRACT = "contract"
STAGE_OBJECT = "object"


@dataclass(frozen=True, slots=True)
class Decision:
    """이벤트 하나의 처리 결과. DLQ 로 갈지, 처리 이력에 어떤 상태·단계로 남을지."""

    shape: str | None
    error_type: str | None
    detail: str
    status: str
    stage: str

    @property
    def rejected(self) -> bool:
        return self.error_type is not None


def decide(event: Mapping[str, Any]) -> Decision:
    """판별하고 처리 이력 상태와 **도달할 단계**까지 정한다.

    한 번에 정하는 이유는 Spark 에서 행마다 파이썬을 왕복하기 때문이다. 판별과 상태를 따로
    부르면 왕복이 두 배가 되고, 무엇보다 두 곳이 갈릴 수 있다.

    단계를 **미리** 정하는 것이 핵심이다. 메시지 판별을 통과한 기사 이벤트는 객체 검증에서
    통과하든 걸리든 `object` 에서 끝나므로, 처리 이력 대조를 그 단계로 할 수 있다. 나중에
    정하면 대조 시점에 값이 없어서 `filter_new` 가 단계를 구분하지 못한다.
    """
    verdict = classify(event)
    if not verdict.ok:
        assert verdict.error_type is not None  # noqa: S101 — Verdict 의 불변식
        # 메시지에서 걸렸으니 객체까지 가지 않는다.
        return Decision(None, verdict.error_type.value, verdict.detail, FAILED, STAGE_CONTRACT)

    shape = verdict.shape.value if verdict.shape is not None else None
    if verdict.shape is EventShape.SUMMARY:
        if event.get("status") == "failed":
            # 수집이 실패한 것이지 우리가 실패한 것이 아니다. DLQ 가 아니라 처리 이력에 남는다
            # ([02 §2]) — 그래야 "그날 아무 일도 없던 것" 과 구분된다.
            return Decision(shape, None, "", SOURCE_FAILED, STAGE_CONTRACT)
        return Decision(shape, None, "", COMPLETED, STAGE_CONTRACT)
    return Decision(shape, None, "", COMPLETED, STAGE_OBJECT)
