"""자동 반영을 되돌린다 — 무엇을 내릴지 고르는 계산만 여기 둔다.

자동 판정이 사전과 순위에 닿는 자리는 셋이다 (`io/concepts.CHANGE` 의 `action`).

- `LINK` — 기존 개념에 표현 한 줄이 붙었다. 되돌리면 그 표현을 `REJECTED` 로 내린다.
- `MINT` — 세지 않는 새 개념과 그 표현이 생겼다. 개념은 `RETIRED`, 표현은 `REJECTED` 로 내린다.
- `DECISION` — 판정 표에 결론이 적혔다. `EXCLUDE` 는 적히는 순간 순위에서 빠진다. 되돌리면 그
  표기에 사람 보류를 더 최근 결정으로 남긴다.

**지우지 않고 상태만 내린다.** 사전은 `ACTIVE` 만 읽으므로 내리는 것으로 충분하고, 무엇이
있었는지는 원장과 행이 그대로 증언한다. 잘못 되돌렸으면 상태를 다시 올리면 된다.

**되돌린 표기에는 사람 보류를 남긴다.** 판정 표는 표기마다 최신 결정만 읽힌다. 사람이 내린
`DEFER` 는 `concept/workflow.reusable` 이 계속 믿으므로 다음 회차가 그 표기를 다시 묻지 않고,
`auto_link.apply_links` 는 사람 결정이 있는 표기를 덮지 않는다. 보류 없이 표현만 내리면 다음
회차가 캐시된 같은 답으로 같은 실수를 다시 한다.

**pyspark 를 import 하지 않는다** (층 1).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

DECISION = "DECISION"
LINK = "LINK"
MINT = "MINT"
ACTIONS = (DECISION, LINK, MINT)


@dataclass(frozen=True, slots=True)
class Change:
    """원장 한 줄. 자동 판정이 한 표기에 대해 한 일 하나다."""

    id: int
    run_id: str
    action: str
    lang: str
    normalized: str
    decision: str | None = None
    concept_id: int | None = None
    expression_id: int | None = None
    reverted: bool = False

    @property
    def key(self) -> tuple[str, str]:
        return (self.lang, self.normalized)


@dataclass(frozen=True, slots=True)
class Plan:
    """되돌릴 것. 네 묶음을 한 트랜잭션에서 함께 처리한다 (`io/concepts.ConceptSink.revert`)."""

    change_ids: tuple[int, ...]
    expressions: tuple[int, ...]
    concepts: tuple[int, ...]
    keys: tuple[tuple[str, str], ...]

    @property
    def empty(self) -> bool:
        return not self.change_ids


def plan(
    changes: Iterable[Change],
    *,
    run_id: str | None = None,
    key: tuple[str, str] | None = None,
) -> Plan:
    """회차 하나 또는 표기 하나에 대해 아직 안 되돌린 변경을 모은다.

    둘 다 비우면 아무것도 고르지 않는다 — 원장 전체를 한 번에 되돌리는 명령은 두지 않는다.
    그건 실수로 치기에 너무 크다.
    """
    if run_id is None and key is None:
        return Plan((), (), (), ())
    picked = [
        change
        for change in changes
        if not change.reverted
        and (run_id is None or change.run_id == run_id)
        and (key is None or change.key == key)
    ]
    expressions = {
        change.expression_id
        for change in picked
        if change.action in (LINK, MINT) and change.expression_id is not None
    }
    concepts = {
        change.concept_id
        for change in picked
        if change.action == MINT and change.concept_id is not None
    }
    return Plan(
        change_ids=tuple(sorted(change.id for change in picked)),
        expressions=tuple(sorted(expressions)),
        concepts=tuple(sorted(concepts)),
        keys=tuple(sorted({change.key for change in picked})),
    )
