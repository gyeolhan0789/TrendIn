"""후보 생성 — 정확 일치가 없을 때 사전에서 무엇을 끌어오나.

**후보는 답이 아니다.** 여기 시험은 "맞는 개념이 목록에 들어왔나" 와 "등급이 제대로 매겨졌나"
까지만 본다. 고르는 것은 판정의 몫이다.
"""

from __future__ import annotations

from trendin.spark.concept.candidates import (
    SOURCE_SOUND,
    SOURCE_SOUND_NEAR,
    SOURCE_SPACE,
    SOURCE_SPELL,
    CandidateIndex,
)
from trendin.spark.concept.dictionary import Concept, Dictionary, Expression

CONCEPTS = (
    Concept(concept_id=1, canonical_name="Louis Vuitton", category="brand"),
    Concept(concept_id=2, canonical_name="Chanel", category="brand"),
    Concept(concept_id=3, canonical_name="Cartier", category="brand"),
    Concept(concept_id=4, canonical_name="denim", category="material"),
    Concept(concept_id=5, canonical_name="trench coat", category="apparel"),
    Concept(concept_id=6, canonical_name="Gucci", category="brand"),
)
EXPRESSIONS = (
    Expression(expression_id=11, concept_id=1, lang="la", normalized="louis vuitton"),
    Expression(expression_id=12, concept_id=1, lang="ko", normalized="루이비통"),
    Expression(expression_id=21, concept_id=2, lang="la", normalized="chanel"),
    Expression(expression_id=31, concept_id=3, lang="la", normalized="cartier"),
    Expression(expression_id=32, concept_id=3, lang="ko", normalized="카르티에"),
    Expression(expression_id=41, concept_id=4, lang="la", normalized="denim"),
    Expression(expression_id=51, concept_id=5, lang="la", normalized="trench coat"),
    Expression(expression_id=61, concept_id=6, lang="la", normalized="gucci"),
)


def index() -> CandidateIndex:
    return CandidateIndex(Dictionary(CONCEPTS, EXPRESSIONS))


def test_띄어쓰기만_다른_표기를_1등급으로_올린다() -> None:
    found = index().generate("ko", "루이 비통")
    assert found[0].concept_id == 1
    assert found[0].source == SOURCE_SPACE


def test_붙여_쓴_표기도_같은_규칙으로_찾는다() -> None:
    found = index().generate("la", "trenchcoat")
    assert found[0].concept_id == 5
    assert found[0].source == SOURCE_SPACE


def test_음차를_소리로_찾는다() -> None:
    found = index().generate("ko", "샤넬")
    assert found[0].concept_id == 2
    assert found[0].source == SOURCE_SOUND


def test_소리가_한_글자_어긋나도_찾는다() -> None:
    # `구찌`(kusi) 와 `Gucci`(kuksi) 는 소리키가 같지 않다. 정확 일치로는 못 만난다.
    found = index().generate("ko", "구찌")
    assert [c.concept_id for c in found] == [6]
    assert found[0].source == SOURCE_SOUND_NEAR


def test_같은_언어_안의_표기_흔들림을_찾는다() -> None:
    # `까르띠에` 와 `카르티에` 는 된소리만 다르다 — 소리키가 같아 2등급으로 만난다.
    found = index().generate("ko", "까르띠에")
    assert found[0].concept_id == 3
    assert found[0].source in (SOURCE_SOUND, SOURCE_SPELL)


def test_자기_자신은_후보가_아니다() -> None:
    # 정확 일치는 사전 조회가 이미 붙였다. 여기까지 왔다면 후보로 다시 내놓지 않는다.
    assert all(c.expression_id != 41 for c in index().generate("la", "denim"))


def test_개념당_한_번만_나온다() -> None:
    found = index().generate("ko", "루이 비통")
    assert len(found) == len({c.concept_id for c in found})


def test_등급_순서로_끊는다() -> None:
    found = index().generate("ko", "루이 비통", limit=1)
    assert len(found) == 1
    assert found[0].tier == 1


def test_빈_키는_후보가_없다() -> None:
    assert index().generate("ko", "") == ()
