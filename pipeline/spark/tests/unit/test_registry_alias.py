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
# `spark/conf/base.yaml` 의 `alias.max_group_size` 와 같은 숫자다.
MAX_GROUP_SIZE = 10


def resolve(pairs, *, df, max_group_size=MAX_GROUP_SIZE, promoted=()):
    return alias.resolve(pairs, df=df, max_group_size=max_group_size, promoted=promoted)


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

    result = resolve([pair("a", "c"), pair("b", "c")], df=df)

    assert {(item.alias_key, item.canonical_key) for item in result.aliases} == {
        ("b", "a"),
        ("c", "a"),
    }
    assert result.merged_groups == 1


def test_사슬은_한_홉으로_평탄해진다():
    """재집계의 `coalesce(al.canonical_key, ...)` 가 한 홉만 따라가므로 정확성 조건이다
    (`io/keywords.ALIAS_MERGE_SQL`)."""
    df = {"canonical": 100, "middle": 20, "leaf": 2}

    result = resolve([pair("canonical", "middle"), pair("middle", "leaf")], df=df)

    assert {(item.alias_key, item.canonical_key) for item in result.aliases} == {
        ("middle", "canonical"),
        ("leaf", "canonical"),
    }


def test_승격된_것이_하나면_DF_가_낮아도_그것이_대표다():
    """대표를 옮기면 이미 발급된 `keyword_id` 를 버려야 하고 그건 사후 병합이다."""
    df = {"promoted": 5, "richer": 80}

    result = resolve([pair("richer", "promoted")], df=df, promoted={"promoted"})

    assert [(item.alias_key, item.canonical_key) for item in result.aliases] == [
        ("richer", "promoted")
    ]


def test_승격된_것끼리는_병합하지_않고_큐로_보낸다():
    df = {"left": 50, "right": 40}

    result = resolve([pair("left", "right")], df=df, promoted={"left", "right"})

    assert result.aliases == ()
    assert [(item.representative, item.absorbed) for item in result.parked] == [("left", "right")]


def test_사슬로_승격된_것이_둘_엮이면_덩이를_통째로_보류한다():
    """`a(승격) — b — c(승격)`. `b` 만 한쪽에 붙이는 것은 "a 와 c 는 별개다" 라는 판단이고
    증거는 그 반대를 말한다 — **의심스러우면 보류한다** ([05 §5])."""
    df = {"a": 50, "b": 10, "c": 40}

    result = resolve([pair("a", "b"), pair("c", "b")], df=df, promoted={"a", "c"})

    assert result.aliases == ()
    assert len(result.parked) == 2


def test_근거는_가장_강한_쌍에서_온다():
    """층이 낮고 신뢰도가 높은 쪽이 강하다. 약어 쌍(신뢰도 1.0)이 변형 쌍을 이긴다."""
    df = {"mcp": 40, "model context protocol": 9}

    result = resolve(
        [
            pair("mcp", "model context protocol", rule=RULE_VARIANT, confidence=0.33),
            pair("mcp", "model context protocol", rule=RULE_ABBREVIATION, confidence=1.0),
        ],
        df=df,
    )

    assert [item.rule for item in result.aliases] == [RULE_ABBREVIATION]


def test_자기_자신을_가리키는_쌍은_버린다():
    assert resolve([pair("a", "a")], df={"a": 5}).aliases == ()


# --- 덩이 크기 차단기 (S15P21A102-398) ------------------------------------


def star(center: str, size: int, *, rule: str = RULE_ABBREVIATION):
    """`center` 하나에 나머지가 붙은 덩이. 구성원 수가 `size` 다."""
    leaves = [f"{center}-{index:02d}" for index in range(size - 1)]
    df = {center: 1000, **{leaf: 5 for leaf in leaves}}
    return [pair(center, leaf, rule=rule) for leaf in leaves], df


def test_상한_이하_덩이는_그대로_병합한다():
    pairs, df = star("chanel", MAX_GROUP_SIZE)

    result = resolve(pairs, df=df)

    assert len(result.aliases) == MAX_GROUP_SIZE - 1
    assert {item.canonical_key for item in result.aliases} == {"chanel"}
    assert result.oversized == ()


def test_상한을_넘은_덩이는_통째로_보류하고_큐에도_보내지_않는다():
    """대표 하나만 빼는 것이 아니라 덩이 전체다. 수천 쌍이 큐로 가면 큐가 목록이 된다."""
    pairs, df = star("vogue", MAX_GROUP_SIZE + 1)

    result = resolve(pairs, df=df)

    assert result.aliases == ()
    assert result.parked == ()
    assert result.merged_groups == 0
    assert result.oversized == (("vogue", MAX_GROUP_SIZE + 1),)


def test_사슬로_이어져_커진_덩이도_보류한다():
    """2026-09-20 의 모양. 쌍마다는 한 홉이지만 union-find 가 끝까지 잇는다."""
    chain = ["chanel", "camel", "bagel", "bague", "vogue"]
    df = {"chanel": 1410, "camel": 28, "bagel": 1, "bague": 11, "vogue": 1515}
    pairs = [pair(left, right) for left, right in zip(chain, chain[1:])]

    assert resolve(pairs, df=df, max_group_size=4).aliases == ()
    assert {item.canonical_key for item in resolve(pairs, df=df, max_group_size=5).aliases} == {
        "vogue"
    }, "상한 안이면 막지 않는다 — 차단기일 뿐 정확도를 만드는 규칙이 아니다"


def test_큰_덩이를_보류해도_다른_덩이는_병합한다():
    big, big_df = star("vogue", MAX_GROUP_SIZE + 1)
    small = [pair("boots", "boot")]

    result = resolve([*big, *small], df={**big_df, "boots": 50, "boot": 5})

    assert [(item.alias_key, item.canonical_key) for item in result.aliases] == [("boot", "boots")]
    assert [key for key, _ in result.oversized] == ["vogue"]
