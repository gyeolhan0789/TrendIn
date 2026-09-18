"""표현 사전 조회 — 라틴은 언어 무관, 나머지는 언어별, 개념당 하나."""

from __future__ import annotations

import pytest

from trendin.spark.concept.dictionary import Concept, Dictionary, Expression

BOOTS = Concept(1201, "boots", "footwear")
BOTTEGA = Concept(3007, "Bottega Veneta", "brand")
COAT = Concept(1305, "coat", "apparel")
COURT = Concept(9001, "court", "sports")
HERMES = Concept(3010, "Hermès", "brand")


def build() -> Dictionary:
    return Dictionary(
        concepts=[BOOTS, BOTTEGA, COAT, COURT, HERMES],
        expressions=[
            Expression(1, 1201, "ko", "부츠"),
            Expression(2, 1201, "ja", "ブーツ"),
            Expression(3, 1201, "en", "boots"),
            Expression(4, 1201, "fr", "bottes"),
            Expression(5, 3007, "en", "bottega veneta"),
            Expression(6, 3007, "ko", "보테가 베네타"),
            Expression(7, 3007, "ko", "보테가베네타"),
            Expression(8, 1305, "ko", "코트", ambiguous=True),
            Expression(9, 9001, "ko", "코트", ambiguous=True),
            Expression(10, 3010, "fr", "hermès"),
        ],
    )


def test_한글은_언어별로_찾는다():
    hits = build().lookup("ko", "부츠")
    assert [h.concept.concept_id for h in hits] == [1201]
    assert hits[0].expression.expression_id == 1


def test_라틴은_기사_언어와_무관하게_찾는다():
    dictionary = build()
    # 영어 표현으로 등록됐지만 프랑스어·이탈리아어·언어무관(la) 어느 칸으로 물어도 나온다.
    for lang in ("en", "fr", "it", "la"):
        assert [h.concept.concept_id for h in dictionary.lookup(lang, "bottega veneta")] == [3007]


def test_라틴은_악센트를_뺀_2차_키로도_찾는다():
    hits = build().lookup("la", "hermes")
    assert [h.concept.concept_id for h in hits] == [3010]


def test_모호한_표기는_개념_둘을_번호순으로_돌려준다():
    hits = build().lookup("ko", "코트")
    assert [h.concept.concept_id for h in hits] == [1305, 9001]
    assert all(h.expression.ambiguous for h in hits)


def test_한_개념에_표현이_여럿이어도_결과는_하나다():
    dictionary = build()
    # 보테가 베네타 · 보테가베네타 둘 다 3007 인데 각각 조회하면 하나씩 나온다.
    assert len(dictionary.lookup("ko", "보테가 베네타")) == 1
    assert len(dictionary.lookup("ko", "보테가베네타")) == 1


def test_언어_칸이_잘못_붙어도_키만으로_한_번_더_본다():
    # 일본어 표기를 ko 로 물어도 (문자 체계가 가나라 실제로는 안 일어나지만) 키로 찾아낸다.
    assert [h.concept.concept_id for h in build().lookup("ko", "ブーツ")] == [1201]


def test_없는_것은_빈_튜플이다():
    assert build().lookup("ko", "발레코어") == ()
    assert build().lookup("ko", "") == ()


def test_개념_없는_표현은_만들_때_죽는다():
    with pytest.raises(KeyError):
        Dictionary(concepts=[BOOTS], expressions=[Expression(1, 9999, "ko", "유령")])


def test_길이는_표현_수다():
    assert len(build()) == 10
