"""개념 테이블에 없는 표기끼리의 변형 후보 (`registry/nil_candidates.py`, S15P21A102-386).

입력은 원표기가 아니라 **비교키**다 — 실제 경로와 같게 `extract/keys.normalized_key` 를 먼저
거친다.
"""

from __future__ import annotations

import pytest

from trendin.spark.extract.keys import normalized_key
from trendin.spark.registry import nil_candidates
from trendin.spark.registry.nil_candidates import Pair, Term, candidate_pairs, clusters, degrees


def terms(*surfaces: str, docs: dict[str, set[str]] | None = None) -> list[Term]:
    docs = docs or {}
    return [Term(normalized_key(s), frozenset(docs.get(s, ()))) for s in surfaces]


def pair_set(pairs: list[Pair]) -> set[tuple[str, str]]:
    return {(p.a, p.b) for p in pairs}


def key_pair(x: str, y: str) -> tuple[str, str]:
    a, b = sorted((normalized_key(x), normalized_key(y)))
    return (a, b)


# --- 2026-09-24 실제 사례 -------------------------------------------------


VOGUE_WORLD = (
    "Vogue World",
    "Vogue World 2025",
    "Vogue World 2026",
    "Vogue World: Milano",
    "Vogue World 2026: Milano",
    "Vogue World Milano 2026",
    "Vogue World : Milan",
    "Vogue World: Hollywood",
)


def test_보그_월드_변형이_한_덩이로_모인다():
    """24H 순위 1~4위. 회차·개최지 표기가 모두 한 덩이로 판정에 넘어간다."""
    groups = clusters(candidate_pairs(terms(*VOGUE_WORLD)))
    assert groups == [tuple(sorted(normalized_key(s) for s in VOGUE_WORLD))]


def test_잡지와_행사는_후보가_아니다():
    """한 낱말만 겹치면 후보가 아니다 — `Vogue` 는 잡지, `Vogue World` 는 행사다."""
    assert candidate_pairs(terms("Vogue", "Vogue World", "Vogue Italia")) == []


# --- 규칙 -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("short", "long", "rule"),
    [
        ("Saint Laurent", "Yves Saint Laurent", "contain"),
        ("Vogue World", "Vogue World: Milano", "contain"),
        ("미니 드레스", "블랙 미니 드레스", "contain"),
        ("Vogue World 2026: Milano", "Vogue World Milano 2026", "prefix"),
        ("Met Gala", "2026 Met Gala", "edition"),
    ],
)
def test_문자열_규칙(short, long, rule):
    """후보일 뿐이다 — `미니 드레스` ↔ `블랙 미니 드레스` 처럼 다른 것도 올라간다."""
    (pair,) = candidate_pairs(terms(short, long))
    assert (pair.a, pair.b) == key_pair(short, long)
    assert rule in pair.rules


def test_연도를_앞에_붙인_회차는_포함이면서_회차다():
    (pair,) = candidate_pairs(terms("Met Gala", "Met Gala 2026"))
    assert pair.rules == ("contain", "edition")


def test_머리글자는_같은_기사에_함께_나올_때만_후보다():
    """머리글자만 보면 `dc` 가 `DC Comics` 도 `Doja Cat` 도 된다."""
    together = {"LFW": {"a1", "a2"}, "London Fashion Week": {"a1", "a3"}}
    (pair,) = candidate_pairs(terms("LFW", "London Fashion Week", docs=together))
    assert pair.rules == ("acronym",)
    assert pair.shared_docs == 1

    apart = {"DC": {"a1"}, "Doja Cat": {"a2"}}
    assert candidate_pairs(terms("DC", "Doja Cat", docs=apart)) == []


def test_한국어_음절은_머리글자로_보지_않는다():
    """`스키` ↔ `스트레이 키즈` 는 음절이 우연히 맞은 것이다."""
    docs = {"스키": {"a1"}, "스트레이 키즈": {"a1"}}
    assert candidate_pairs(terms("스키", "스트레이 키즈", docs=docs)) == []


def test_앞_두_낱말이_같은_무리가_크면_형제_품목이다():
    """`gonna a …` 는 모두 치마의 종류다. 머리에 딸린 표기가 많으면 그 머리로 잇지 않는다."""
    siblings = [
        "gonna a matita",
        "gonna a pieghe",
        "gonna a ruota",
        "gonna a tubino",
        "gonna a palloncino",
    ]
    assert len(siblings) > nil_candidates.PREFIX_GROUP_MAX
    assert candidate_pairs(terms(*siblings)) == []


def test_앞_두_낱말이_같은_무리가_작으면_후보다():
    assert pair_set(candidate_pairs(terms("abito da sera", "abito da sposa"))) == {
        key_pair("abito da sera", "abito da sposa")
    }


def test_같은_쌍은_한_번만_나온다():
    pairs = candidate_pairs(terms("Met Gala", "2026 Met Gala", "Met Gala 2026"))
    assert len(pairs) == len(pair_set(pairs))
    assert all(p.a < p.b for p in pairs)


# --- 덩이 -----------------------------------------------------------------


def test_흔한_머리말은_덩이를_잇지_않는다():
    """`fashion week` 이 도시마다 붙어도 파리·런던 패션위크가 한 덩이가 되지 않는다."""
    cities = [
        "Paris",
        "London",
        "Milano",
        "New York",
        "Copenhagen",
        "Tokyo",
        "Seoul",
        "Berlin",
        "Madrid",
    ]
    surfaces = ["Fashion Week"] + [f"{city} Fashion Week" for city in cities]
    pairs = candidate_pairs(terms(*surfaces))
    assert len(pairs) > nil_candidates.HUB_DEGREE
    groups = clusters(pairs)
    assert all(len(group) == 2 for group in groups)
    assert all(normalized_key("Fashion Week") in group for group in groups)


def test_너무_큰_덩이는_둘씩_나눈다(monkeypatch):
    monkeypatch.setattr(nil_candidates, "MAX_CLUSTER", 3)
    pairs = candidate_pairs(terms("Met Gala", "2026 Met Gala", "Met Gala 2026", "MET Gala 2027"))
    groups = clusters(pairs)
    assert all(len(group) == 2 for group in groups)
    assert set(groups) == pair_set(pairs)


def test_이어지지_않은_쌍은_다른_덩이다():
    groups = clusters(
        candidate_pairs(terms("Met Gala", "2026 Met Gala", "Saint Laurent", "Yves Saint Laurent"))
    )
    assert groups == sorted(
        [key_pair("Met Gala", "2026 Met Gala"), key_pair("Saint Laurent", "Yves Saint Laurent")]
    )


def test_흔한_머리말은_전체_표기로_센다():
    """판정할 쌍만 추려 세면 흔한 말이 흔해 보이지 않는다 — 24H 순위의 패션위크 덩이."""
    cities = [
        "Paris",
        "London",
        "Milano",
        "New York",
        "Copenhagen",
        "Tokyo",
        "Seoul",
        "Berlin",
        "Madrid",
    ]
    everything = candidate_pairs(
        terms("Fashion Week", *[f"{city} Fashion Week" for city in cities])
    )
    picked = [p for p in everything if "paris" in p.b or "london" in p.b]
    assert all(len(g) == 2 for g in clusters(picked, degrees(everything)))
    # 추린 쌍만으로 세면 `fashion week` 이 셋을 한 덩이로 잇는다
    assert clusters(picked) == [
        tuple(
            sorted(
                normalized_key(s)
                for s in ("Fashion Week", "London Fashion Week", "Paris Fashion Week")
            )
        )
    ]
