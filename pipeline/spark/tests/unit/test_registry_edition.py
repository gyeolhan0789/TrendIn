"""연도·시즌만 다른 표기의 기준형 (`registry/edition.py`, S15P21A102-385).

입력은 원표기가 아니라 **비교키**다 — 실제 경로와 같게 `extract/keys.normalized_key` 를 먼저
거친다. `Vogue World: Milano` 의 쌍점은 거기서 이미 빠진다.
"""

from __future__ import annotations

import pytest

from trendin.spark.extract.keys import normalized_key
from trendin.spark.registry.edition import edition_base, edition_key, edition_order


def base(surface: str) -> str | None:
    return edition_base(normalized_key(surface))


# --- 2026-09-24 실제 사례 -------------------------------------------------


def test_보그_월드_네_표기가_두_덩이로_모인다():
    """24H 순위 1~4위. 도시가 붙은 쪽과 안 붙은 쪽은 낱말을 떼야 같아지므로 따로 남는다."""
    keys = {
        surface: edition_key(normalized_key(surface))
        for surface in (
            "Vogue World",
            "Vogue World 2026",
            "Vogue World Milano 2026",
            "Vogue World: Milano",
        )
    }
    assert keys == {
        "Vogue World": "vogue world",
        "Vogue World 2026": "vogue world",
        "Vogue World Milano 2026": "vogue world milano",
        "Vogue World: Milano": "vogue world milano",
    }


def test_잡지와_행사는_갈린다():
    """앞부분이 같다고 접지 않는다 — `Vogue World` 는 행사이고 `Vogue` 는 잡지다."""
    assert edition_key(normalized_key("Vogue")) == "vogue"
    assert edition_key(normalized_key("Vogue World")) == "vogue world"
    assert edition_key(normalized_key("Vogue Italia")) == "vogue italia"


# --- 접는 것 --------------------------------------------------------------


@pytest.mark.parametrize(
    ("surface", "expected"),
    [
        # 행사 회차 — 끝의 연도
        ("Met Gala 2026", "met gala"),
        ("Met Gala 2027", "met gala"),
        ("London Fashion Week 2026", "london fashion week"),
        ("Festival di Venezia 2026", "festival di venezia"),
        ("Copenhagen Fashion Week 2027", "copenhagen fashion week"),
        # 시즌 코드 — 붙여 쓴 것, 네 자리 연도, 띄어 쓴 시즌 표시
        ("Paris Fashion Week SS27", "paris fashion week"),
        ("Paris Fashion Week FW26", "paris fashion week"),
        ("Milan Fashion Week AW26", "milan fashion week"),
        ("Gucci Womenswear SS2027", "gucci womenswear"),
        ("Chanel Pre-Fall PF26", "chanel pre fall"),
        ("Chanel Cruise RS27", "chanel cruise"),
        ("Prada Menswear SS 2027", "prada menswear"),
        ("Dior Homme S/S 2027", "dior homme"),
        # 앞의 연도, 한국어·일본어 연도 표기
        ("2026 Met Gala", "met gala"),
        ("멧 갈라 2026", "멧 갈라"),
        ("2026년 멧 갈라", "멧 갈라"),
        ("파리 패션위크 2026년", "파리 패션위크"),
        ("東京 コレクション 2026年", "東京 コレクション"),
        # 연도와 시즌이 둘 다 붙은 것
        ("Paris Fashion Week SS27 2026", "paris fashion week"),
    ],
)
def test_연도와_시즌을_뗀다(surface, expected):
    assert base(surface) == expected


# --- 접지 않는 것 ---------------------------------------------------------


@pytest.mark.parametrize(
    "surface",
    [
        # 떼고 한 낱말이 남는다 — 대개 도시·브랜드·일반어다. 시즌 코드여도 마찬가지다
        "Milano 2026",
        "Cannes 2027",
        "Summer 2026",
        "Gucci 2026",
        "Gucci SS27",
        "Paris SS27",
        "Prada SS 2027",
        "Dior S/S 2027",
        # 맞는 경우도 놓친다 — 틀린 합산보다 낫다
        "LFW SS27",
        "PFW FW26",
        # 모델명·창립 연도 — 연도 범위 밖이거나 연도 꼴이 아니다
        "Air Max 90",
        "Air Jordan 1",
        "Chanel No 5",
        "Levi's 501",
        "Louis Vuitton 1854",
        "Stone Island 1982",
        "Air Max 2090",
        # 연도가 가운데 있다 — 떼면 이름이 바뀐다
        "Vogue World 2026 Milano",
        # 떼어 낼 것이 없다
        "Vogue World",
        "Vogue World Milano",
        "London Fashion Week",
        "LFW",
        # 시즌 표시 자체가 전부다
        "SS27",
        "2026 S/S",
        "SS 2027",
        # 숫자뿐이다
        "2026",
        "2026 27",
    ],
)
def test_위험하거나_뗄_것이_없으면_접지_않는다(surface):
    assert base(surface) is None


def test_시즌_표시는_연도가_뒤에_있을_때만_뗀다():
    """`ss` 혼자는 시즌인지 이름의 일부인지 모른다."""
    assert base("Paris SS") is None
    assert base("Paris Fashion Week SS") is None


def test_열쇠는_기준형이_없으면_자기_자신이다():
    assert edition_key("vogue world milano") == "vogue world milano"
    assert edition_key("milano 2026") == "milano 2026"


# --- 회차 순서 — 보이는 이름을 고르는 데 쓴다 ---------------------------------


@pytest.mark.parametrize(
    ("surface", "expected"),
    [
        ("Vogue World 2026", (2026, -1)),
        ("2026 Met Gala", (2026, -1)),
        ("멧 갈라 2026년", (2026, -1)),
        ("Paris Fashion Week SS27", (2027, 1)),
        ("Paris Fashion Week FW26", (2026, 3)),
        ("London Fashion Week AW2026", (2026, 3)),
        ("Prada Menswear SS 2027", (2027, 1)),
        ("Dior Homme S/S 2027", (2027, 1)),
        ("Chanel Pre-Fall PF26", (2026, 2)),
        ("Chanel Cruise RS27", (2027, 0)),
        # 둘이 붙으면 늦은 쪽
        ("Paris Fashion Week SS27 2026", (2027, 1)),
    ],
)
def test_회차_순서를_읽는다(surface, expected):
    assert edition_order(normalized_key(surface)) == expected


def test_시즌_순서는_보여지는_차례다():
    """리조트 → 봄여름 → 프리폴 → 가을겨울. 연도가 먼저다 (`fw26` < `rs27` < `ss27`)."""
    orders = [
        edition_order(normalized_key(surface))
        for surface in ("X Show FW26", "X Show RS27", "X Show SS27", "X Show PF27", "X Show FW27")
    ]
    assert orders == sorted(orders)


@pytest.mark.parametrize("surface", ["Vogue World", "Milano 2026", "Air Max 90", "SS27"])
def test_회차가_아니면_순서도_없다(surface):
    assert edition_order(normalized_key(surface)) is None
