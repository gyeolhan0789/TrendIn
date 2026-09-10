"""병합 쌍 → 대표 하나 ([05 §1]). 층 1.

**이미 승격된 것이 얽히면 자동 적용하지 않는다** ([05 §7]). 그 판단이 이 파일의 절반이다 —
사후 병합은 `member_interest_keywords` 이관과 삭제가 따라오고, 그 절차는 백엔드와 함께
수동으로 한다.
"""

from __future__ import annotations

from trendin.spark.registry import alias
from trendin.spark.registry.merge import (
    LAYER_EVIDENCE,
    RULE_ABBREVIATION,
    RULE_VARIANT,
    MergePair,
    signal_of,
)

DOMAIN = "fashion"


def pair(representative: str, absorbed: str, *, rule: str = RULE_VARIANT, confidence=0.5):
    return MergePair(
        domain=DOMAIN,
        representative=representative,
        absorbed=absorbed,
        layer=LAYER_EVIDENCE,
        rule=rule,
        confidence=confidence,
        signal=signal_of(rule=rule),
    )


def test_대표는_DF_최대이고_동률은_사전순():
    df = {"a": 10, "b": 10, "c": 3}

    result = alias.resolve([pair("a", "c"), pair("b", "c")], df=df)

    assert {(item.alias_key, item.canonical_key) for item in result.aliases} == {
        ("b", "a"),
        ("c", "a"),
    }
    assert result.merged_groups == 1


def test_사슬은_한_홉으로_평탄해진다():
    """재집계의 `coalesce(al.canonical_key, ...)` 가 한 홉만 따라가므로 정확성 조건이다
    (`io/keywords.ALIAS_MERGE_SQL`)."""
    df = {"canonical": 100, "middle": 20, "leaf": 2}

    result = alias.resolve([pair("canonical", "middle"), pair("middle", "leaf")], df=df)

    assert {(item.alias_key, item.canonical_key) for item in result.aliases} == {
        ("middle", "canonical"),
        ("leaf", "canonical"),
    }


def test_승격된_것이_하나면_DF_가_낮아도_그것이_대표다():
    """대표를 옮기면 이미 발급된 `keyword_id` 를 버려야 하고 그건 사후 병합이다."""
    df = {"promoted": 5, "richer": 80}

    result = alias.resolve([pair("richer", "promoted")], df=df, promoted={"promoted"})

    assert [(item.alias_key, item.canonical_key) for item in result.aliases] == [
        ("richer", "promoted")
    ]


def test_승격된_것끼리는_병합하지_않고_큐로_보낸다():
    df = {"left": 50, "right": 40}

    result = alias.resolve([pair("left", "right")], df=df, promoted={"left", "right"})

    assert result.aliases == ()
    assert [(item.representative, item.absorbed) for item in result.parked] == [("left", "right")]


def test_사슬로_승격된_것이_둘_엮이면_덩이를_통째로_보류한다():
    """`a(승격) — b — c(승격)`. `b` 만 한쪽에 붙이는 것은 "a 와 c 는 별개다" 라는 판단이고
    증거는 그 반대를 말한다 — **의심스러우면 보류한다** ([05 §5])."""
    df = {"a": 50, "b": 10, "c": 40}

    result = alias.resolve([pair("a", "b"), pair("c", "b")], df=df, promoted={"a", "c"})

    assert result.aliases == ()
    assert len(result.parked) == 2


def test_근거는_가장_강한_쌍에서_온다():
    """층이 낮고 신뢰도가 높은 쪽이 강하다. 약어 쌍(신뢰도 1.0)이 변형 쌍을 이긴다."""
    df = {"mcp": 40, "model context protocol": 9}

    result = alias.resolve(
        [
            pair("mcp", "model context protocol", rule=RULE_VARIANT, confidence=0.33),
            pair("mcp", "model context protocol", rule=RULE_ABBREVIATION, confidence=1.0),
        ],
        df=df,
    )

    assert [item.rule for item in result.aliases] == [RULE_ABBREVIATION]


def test_자기_자신을_가리키는_쌍은_버린다():
    assert alias.resolve([pair("a", "a")], df={"a": 5}).aliases == ()
