"""자동 반영 되돌리기 — 무엇을 내릴지 고르는 계산 (`concept/rollback.py`)."""

from __future__ import annotations

from trendin.spark.concept.rollback import DECISION, LINK, MINT, Change, plan

RUN_A = "auto-20260923T003612Z"
RUN_B = "auto-20260923T020912Z"

LEDGER = (
    Change(1, RUN_A, DECISION, "ko", "무신사", decision="LINK", concept_id=77),
    Change(2, RUN_A, LINK, "ko", "무신사", decision="LINK", concept_id=77, expression_id=901),
    Change(3, RUN_A, DECISION, "ko", "블루종", decision="EXCLUDE"),
    Change(4, RUN_A, DECISION, "la", "zendaya", decision="NEW_CONCEPT"),
    Change(5, RUN_A, MINT, "la", "zendaya", decision="NEW_CONCEPT", concept_id=5001,
           expression_id=902),
    Change(6, RUN_B, LINK, "la", "trench coats", decision="LINK", concept_id=12,
           expression_id=903),
)


def test_회차_하나를_통째로_고른다() -> None:
    chosen = plan(LEDGER, run_id=RUN_A)
    assert chosen.change_ids == (1, 2, 3, 4, 5)
    assert chosen.expressions == (901, 902)
    assert chosen.concepts == (5001,)
    assert chosen.keys == (("ko", "무신사"), ("ko", "블루종"), ("la", "zendaya"))


def test_제외_판정만_있던_표기도_되돌린다() -> None:
    """`EXCLUDE` 는 사전 행 없이도 순위에서 표기를 뺀다. 표기를 되돌릴 목록에 꼭 있어야 한다."""
    chosen = plan(LEDGER, key=("ko", "블루종"))
    assert chosen.change_ids == (3,)
    assert chosen.expressions == () and chosen.concepts == ()
    assert chosen.keys == (("ko", "블루종"),)


def test_표기_하나만_고르면_다른_표기는_건드리지_않는다() -> None:
    chosen = plan(LEDGER, key=("ko", "무신사"))
    assert chosen.change_ids == (1, 2)
    assert chosen.expressions == (901,)
    assert chosen.concepts == ()


def test_다른_회차는_섞지_않는다() -> None:
    chosen = plan(LEDGER, run_id=RUN_B)
    assert chosen.change_ids == (6,)
    assert chosen.expressions == (903,)


def test_이미_되돌린_줄은_다시_고르지_않는다() -> None:
    ledger = (*LEDGER[:1], Change(2, RUN_A, LINK, "ko", "무신사", expression_id=901,
                                  reverted=True))
    chosen = plan(ledger, run_id=RUN_A)
    assert chosen.change_ids == (1,)
    assert chosen.expressions == ()


def test_아무것도_안_정하면_아무것도_고르지_않는다() -> None:
    """원장 전체를 한 번에 되돌리는 길은 두지 않는다. 실수로 치기에 너무 크다."""
    assert plan(LEDGER).empty
