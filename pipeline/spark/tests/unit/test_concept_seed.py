"""초기사전 파일 파싱 — 모양이 틀리면 죽고, 표현은 (언어, 비교키) 로 접힌다."""

from __future__ import annotations

import pytest

from trendin.spark.concept.seed import KIND_CANONICAL, KIND_SYNONYM, KIND_VARIANT, parse_seed

BOTTEGA = {
    "id": "Q894874",
    "labels": {
        "en": "Bottega Veneta",
        "ko": "보테가 베네타",
        "ja": "ボッテガ・ヴェネタ",
        "fr": "Bottega Veneta",
    },
    "aliases": {"ko": ["보테가베네타"], "ja": ["ボッテガ・ベネタ", "BOTTEGA VENETA"]},
}


def doc(**overrides):
    base = {"source": "wikidata", "category": "brand", "items": [BOTTEGA]}
    return {**base, **overrides}


def test_대표_이름은_영어_라벨이고_한국어_표시_이름은_ko_라벨이다():
    (concept,) = parse_seed(doc(), file_name="brands.json")
    assert concept.canonical_name == "Bottega Veneta"
    assert concept.display_ko == "보테가 베네타"
    assert concept.category == "brand"
    assert concept.source == "wikidata:Q894874"
    assert concept.countable is True


def test_표현은_라벨은_synonym_별칭은_variant_영어는_canonical():
    (concept,) = parse_seed(doc(), file_name="brands.json")
    kinds = {(e.lang, e.normalized): e.kind for e in concept.expressions}
    assert kinds[("en", "bottega veneta")] == KIND_CANONICAL
    assert kinds[("ko", "보테가 베네타")] == KIND_SYNONYM
    assert kinds[("ko", "보테가베네타")] == KIND_VARIANT
    # 프랑스어 라벨은 영어와 같은 글자지만 언어가 달라 별도 표현이다 — 조회는 어차피 라틴 무관.
    assert ("fr", "bottega veneta") in kinds


def test_같은_언어_같은_비교키는_한_번만_남는다():
    (concept,) = parse_seed(doc(), file_name="brands.json")
    ja = [e for e in concept.expressions if e.lang == "ja"]
    # ボッテガ・ヴェネタ(라벨) 와 ボッテガ・ベネタ(별칭) 는 다른 키다.
    # BOTTEGA VENETA 는 라틴이라 또 다른 키다.
    assert len(ja) == 3
    assert len({(e.lang, e.normalized) for e in concept.expressions}) == len(concept.expressions)


def test_영어_라벨이_없으면_거부한다():
    bad = {"id": "Q1", "labels": {"ko": "이름만 한국어"}}
    with pytest.raises(ValueError, match="labels.en"):
        parse_seed(doc(items=[bad]), file_name="x.json")


def test_위키데이터_항목은_id_가_필요하다():
    bad = {"labels": {"en": "Nameless"}}
    with pytest.raises(ValueError, match="id"):
        parse_seed(doc(items=[bad]), file_name="x.json")


def test_손으로_만든_초기사전은_파일_이름이_출처다():
    item = {"labels": {"en": "boots", "ko": "부츠", "ja": "ブーツ", "fr": "bottes"}}
    (concept,) = parse_seed(
        doc(source="seed", category="footwear", items=[item]), file_name="vocab.json"
    )
    assert concept.source == "seed:vocab.json"


def test_상위와_일반_단어_표시를_읽는다():
    items = [
        {"labels": {"en": "boots", "ko": "부츠"}},
        {"labels": {"en": "ankle boots", "ko": "앵클부츠"}, "parent": "boots"},
    ]
    boots, ankle = parse_seed(
        doc(source="seed", category="footwear", items=items), file_name="v.json"
    )
    assert boots.parent_name is None and ankle.parent_name == "boots"
    (feeling,) = parse_seed(
        doc(
            source="seed",
            category="generic",
            items=[{"labels": {"en": "feeling", "ko": "느낌"}, "countable": False}],
        ),
        file_name="g.json",
    )
    assert feeling.countable is False


def test_같은_파일_안_대표_이름_중복은_먼저_온_것만_남는다():
    items = [BOTTEGA, {**BOTTEGA, "id": "Q999", "labels": {"en": "bottega veneta"}}]
    concepts = parse_seed(doc(items=items), file_name="brands.json")
    assert [c.source for c in concepts] == ["wikidata:Q894874"]


@pytest.mark.parametrize("bad", [doc(source="llm"), doc(category="shoes"), doc(items="아니오")])
def test_파일_모양이_틀리면_거부한다(bad):
    with pytest.raises(ValueError):
        parse_seed(bad, file_name="x.json")


def test_이용_조건은_출처의_기본값이_붙는다():
    # 위키데이터 구조화 데이터는 CC0 다. 행마다 남겨 둬야 나중에 무엇을 배포할 수 있는지 안다.
    (concept,) = parse_seed(doc(), file_name="brands.json")
    assert concept.license == "CC0-1.0"

    (handmade,) = parse_seed(
        {"source": "seed", "category": "apparel", "items": [{"labels": {"en": "vest"}}]},
        file_name="vocabulary-apparel.json",
    )
    assert handmade.license is None


def test_파일이_이용_조건을_적으면_그것이_이긴다():
    # Wiktionary 처럼 조건이 다른 데서 만든 파일을 손으로 내릴 때 쓴다.
    (concept,) = parse_seed(
        {
            "source": "seed",
            "license": "CC-BY-SA-4.0",
            "category": "apparel",
            "items": [{"labels": {"en": "vest", "ko": "조끼"}}],
        },
        file_name="wiktionary-apparel.json",
    )
    assert concept.license == "CC-BY-SA-4.0"


def test_모르는_출처는_받지_않는다():
    # 이용 조건을 모르는 데이터가 섞이면 되짚을 수 없다. 새 출처는 SOURCE_LICENSES 에 등록한다.
    with pytest.raises(ValueError, match="source"):
        parse_seed(doc(source="wiktionary"), file_name="x.json")
