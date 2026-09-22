"""사전을 적재하지 않고 메모리에만 얹어 보는 경로 — 전후 비교의 근거가 되는 곳.

여기서 제일 중요한 것은 **표현을 늘리면 모호성도 는다**는 것을 이 경로가 재현하느냐다.
적재 경로는 조회할 때마다 `io/concepts.EXPRESSIONS_SQL` 이 다시 세므로 저절로 보이지만,
메모리 경로가 그것을 빠뜨리면 "표현만 늘고 매핑은 그대로" 라는 틀린 낙관이 나온다.
"""

from __future__ import annotations

import pytest

from trendin.spark.concept.dictionary import Concept, Dictionary, Expression
from trendin.spark.concept.seed import SeedConcept, SeedExpression, apply_seed_in_memory


def dictionary(*, ambiguous: bool = False) -> Dictionary:
    return Dictionary(
        [Concept(1, "vest", "apparel"), Concept(2, "boots", "footwear")],
        [
            Expression(10, 1, "en", "vest", ambiguous),
            Expression(11, 2, "en", "boots", ambiguous),
        ],
    )


def seed(name, category, *expressions, parent=None) -> SeedConcept:
    return SeedConcept(
        canonical_name=name,
        category=category,
        source=f"seed:{name}.json",
        parent_name=parent,
        expressions=tuple(
            SeedExpression(lang=lang, surface=text, normalized=text, kind="synonym")
            for lang, text in expressions
        ),
    )


def test_새_개념과_표현은_음수_번호를_받아_DB_번호와_섞이지_않는다():
    merged, result = apply_seed_in_memory(dictionary(), [seed("coat", "apparel", ("ko", "코트"))])

    assert result.concepts_new == 1
    assert result.expressions_new == 1
    (added,) = [c for c in merged.concepts() if c.canonical_name == "coat"]
    assert added.concept_id < 0
    (hit,) = merged.lookup("ko", "코트")
    assert hit.expression.expression_id < 0
    assert hit.concept.concept_id == added.concept_id


def test_이미_있는_표현은_다시_세지_않는다():
    merged, result = apply_seed_in_memory(dictionary(), [seed("vest", "apparel", ("en", "vest"))])

    assert (result.concepts_new, result.expressions_new) == (0, 0)
    assert len(merged) == 2


def test_검수가_내린_쌍은_되살아나지_않는다():
    added = seed("vest", "apparel", ("ko", "조끼"))

    kept, _ = apply_seed_in_memory(dictionary(), [added])
    dropped, result = apply_seed_in_memory(
        dictionary(), [added], rejected=frozenset({("ko", "조끼", 1)})
    )

    assert kept.lookup("ko", "조끼")
    assert dropped.lookup("ko", "조끼") == ()
    assert result.expressions_new == 0


def test_표현이_늘어_같은_표기가_두_개념에_걸리면_모호해진다():
    merged, _ = apply_seed_in_memory(
        dictionary(),
        [seed("vest", "apparel", ("ko", "조끼")), seed("waistcoat", "apparel", ("ko", "조끼"))],
    )

    hits = merged.lookup("ko", "조끼")
    assert len(hits) == 2
    assert all(hit.expression.ambiguous for hit in hits)
    # 겹치지 않은 표기는 그대로다 — 한 번 켜지면 전부 켜지는 식이면 안 된다.
    (boots,) = merged.lookup("en", "boots")
    assert boots.expression.ambiguous is False


def test_표에_이미_적힌_모호성은_꺼지지_않는다():
    merged, _ = apply_seed_in_memory(dictionary(ambiguous=True), [seed("coat", "apparel")])

    (vest,) = merged.lookup("en", "vest")
    assert vest.expression.ambiguous is True


def test_상위_개념은_같은_묶음_안에서_잇고_이미_있으면_덮지_않는다():
    merged, result = apply_seed_in_memory(
        dictionary(),
        [seed("boot", "footwear"), seed("ankle boot", "footwear", parent="boot")],
    )

    assert result.parents_set == 1
    (child,) = [c for c in merged.concepts() if c.canonical_name == "ankle boot"]
    (parent,) = [c for c in merged.concepts() if c.canonical_name == "boot"]
    assert child.parent_id == parent.concept_id


def test_상위가_같은_묶음에_없으면_세운다():
    with pytest.raises(ValueError, match="상위"):
        apply_seed_in_memory(dictionary(), [seed("ankle boot", "footwear", parent="boot")])


def test_대표_이름이_대소문자만_다르면_하나로_본다():
    # DB 유일키는 대소문자를 가리는데 이름 조회는 접는다. 갈려 있어도 번호가 작은 쪽에 붙인다.
    split = Dictionary(
        [Concept(1, "Vest", "apparel"), Concept(5, "vest", "apparel")],
        [Expression(10, 1, "en", "vest")],
    )

    merged, result = apply_seed_in_memory(split, [seed("VEST", "apparel", ("ko", "조끼"))])

    assert result.concepts_new == 0
    (hit,) = merged.lookup("ko", "조끼")
    assert hit.concept.concept_id == 1
