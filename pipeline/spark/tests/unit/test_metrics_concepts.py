"""연도·시즌 접기와 개념 접기가 만나는 자리 (`metrics/concepts.build_grouping`, S15P21A102-385).

열쇠와 회차 순서는 `load_grouping` 과 같게 `registry/edition` 으로 만든다.

두 층을 따로 본다 — **무엇을 합산하나**(문자열 규칙)와 **무엇으로 보이나**(최신 회차는 행사
개념에만).
"""

from __future__ import annotations

from trendin.spark.metrics.concepts import ConceptRef, build_grouping
from trendin.spark.registry.edition import edition_key, edition_order

# 2026-09-24 24H 순위와 같은 모양. 무게는 그날 언급량이다.
VOGUE_WORLD = 1
VOGUE_WORLD_2026 = 2
VOGUE_WORLD_MILANO_2026 = 3
VOGUE_WORLD_MILANO = 4  # `Vogue World: Milano` — 쌍점은 비교키가 이미 뗐다
GIGI_HADID = 5
VOGUE = 6

NAMES = {
    VOGUE_WORLD: "vogue world",
    VOGUE_WORLD_2026: "vogue world 2026",
    VOGUE_WORLD_MILANO_2026: "vogue world milano 2026",
    VOGUE_WORLD_MILANO: "vogue world milano",
    GIGI_HADID: "gigi hadid",
    VOGUE: "vogue",
}
WEIGHTS = {
    VOGUE_WORLD: 69,
    VOGUE_WORLD_2026: 66,
    VOGUE_WORLD_MILANO_2026: 66,
    VOGUE_WORLD_MILANO: 33,
    GIGI_HADID: 29,
    VOGUE: 7,
}
SHARE = 0.1


def event(*keyword_ids: int, concept_id: int = 900) -> list[ConceptRef]:
    return [ConceptRef(keyword_id, concept_id, True, "event") for keyword_id in keyword_ids]


def group(refs=(), *, names=NAMES, weights=WEIGHTS, silenced=frozenset(), domains=None):
    """`load_grouping` 과 같은 열쇠 — 순서는 `(연도, 시즌, -기준형 낱말 수)`."""
    domains = domains or {}
    keys = {keyword_id: edition_key(name) for keyword_id, name in names.items()}
    return build_grouping(
        list(refs),
        weights,
        keywords=set(names),
        silenced_keywords=frozenset(silenced),
        edition_keys={
            keyword_id: (domains.get(keyword_id, "fashion"), key)
            for keyword_id, key in keys.items()
        },
        edition_orders={
            keyword_id: (*order, -len(keys[keyword_id].split()))
            for keyword_id, name in names.items()
            if (order := edition_order(name)) is not None
        },
        representative_min_share=SHARE,
    )


# --- 합산 — 문자열 규칙 ------------------------------------------------------


def test_개념이_없어도_연도만_다른_표기를_합산한다():
    """행사인지 모르므로 이름은 무게로 고른다 — `Vogue World`(69) 가 대표다."""
    grouping = group()

    assert grouping.representative == {
        VOGUE_WORLD_2026: VOGUE_WORLD,
        VOGUE_WORLD_MILANO: VOGUE_WORLD_MILANO_2026,
    }
    assert grouping.edition_folded == 2
    # 잡지와 사람은 건드리지 않는다
    assert VOGUE not in grouping.representative
    assert GIGI_HADID not in grouping.representative


def test_기준형이_없어도_회차끼리_합산한다():
    """순위에서만 합치므로 되돌릴 수 있다."""
    names = {10: "met gala 2026", 11: "met gala 2027", 12: "met gala after party"}
    grouping = group(names=names, weights={10: 40, 11: 5, 12: 3})

    assert grouping.representative == {11: 10}


def test_두_낱말_장소는_합산되지만_이름은_그대로다():
    """⚠️ 알려진 한계 — 사전 분류에 장소가 없어 `Los Angeles 2028`(올림픽)이 도시에 합산된다.
    보이는 이름까지 회차로 바뀌지는 않는다. 장소 판별은 S15P21A102-386."""
    names = {20: "los angeles", 21: "los angeles 2028"}
    grouping = group(names=names, weights={20: 300, 21: 40})

    assert grouping.representative == {21: 20}


# --- 보이는 이름 — 최신 회차는 행사 개념에만 --------------------------------------


def test_행사_개념이면_최신_회차가_보인다():
    """`Vogue World`(69) 가 더 많이 나왔어도 보이는 이름은 `Vogue World 2026` 이다."""
    grouping = group(event(VOGUE_WORLD_2026))

    assert grouping.representative[VOGUE_WORLD] == VOGUE_WORLD_2026


def test_운영_DB_모양이면_넷이_한_자리고_기준형이_짧은_회차가_보인다():
    """`Vogue World 2026` 개념에 Milano 두 표기가 붙어 있다 (2026-09-24 정리 뒤).

    둘 다 2026 이라 연도로는 못 가른다. 기준형이 짧은 `vogue world 2026` 이 **언급량과 무관하게**
    대표다 — 언급량이 뒤집혀도 바뀌지 않는다."""
    refs = event(VOGUE_WORLD_2026, VOGUE_WORLD_MILANO_2026, VOGUE_WORLD_MILANO)
    for weights in (
        {**WEIGHTS, VOGUE_WORLD_2026: 60, VOGUE_WORLD_MILANO_2026: 70},
        {**WEIGHTS, VOGUE_WORLD_2026: 70, VOGUE_WORLD_MILANO_2026: 60},
    ):
        grouping = group(refs, weights=weights)
        assert grouping.representative == {
            VOGUE_WORLD: VOGUE_WORLD_2026,
            VOGUE_WORLD_MILANO_2026: VOGUE_WORLD_2026,
            VOGUE_WORLD_MILANO: VOGUE_WORLD_2026,
        }


def test_가장_늦은_회차가_보인다():
    names = {10: "met gala", 11: "met gala 2025", 12: "met gala 2026"}
    grouping = group(event(10), names=names, weights={10: 50, 11: 40, 12: 30})

    assert grouping.representative == {10: 12, 11: 12}


def test_예고_기사_한_건은_이름을_못_가져간다():
    """덩이 전체의 10% 미만인 회차는 후보가 아니다 — `2027` 1건이 `2026` 을 밀어내지 않는다."""
    names = {1: "vogue world", 2: "vogue world 2026", 3: "vogue world 2027"}
    grouping = group(event(2), names=names, weights={1: 69, 2: 60, 3: 1})

    assert grouping.representative == {1: 2, 3: 2}


def test_점유율은_덩이_전체_언급량으로_잰다():
    """경계값 — 전체 100 중 10 이면 후보이고 9 면 아니다."""
    names = {1: "vogue world", 2: "vogue world 2027"}

    passing = group(event(1), names=names, weights={1: 90, 2: 10})
    failing = group(event(1), names=names, weights={1: 91, 2: 9})

    assert passing.representative == {1: 2}
    assert failing.representative == {2: 1}


def test_회차가_모두_모자라면_무게로_고른다():
    names = {1: "vogue world", 2: "vogue world 2026"}
    grouping = group(event(1), names=names, weights={1: 95, 2: 5})

    assert grouping.representative == {2: 1}


def test_시즌은_연도_다음으로_견준다():
    """`fw26` < `ss27` — 2026 가을겨울 뒤에 2027 봄여름이 온다."""
    names = {
        30: "paris fashion week",
        31: "paris fashion week ss27",
        32: "paris fashion week fw26",
    }
    grouping = group(event(30), names=names, weights={30: 50, 31: 20, 32: 30})

    assert grouping.representative == {30: 31, 32: 31}


def test_브랜드는_합산해도_이름이_브랜드다():
    """`Saint Laurent SS27` 은 컬렉션이다. 합산은 해도 브랜드 자리가 컬렉션 이름이 되면 안 된다."""
    names = {40: "saint laurent", 41: "saint laurent ss27"}
    grouping = group(
        [ConceptRef(40, 500, True, "brand")], names=names, weights={40: 900, 41: 12}
    )

    assert grouping.representative == {41: 40}


def test_분류를_모르는_개념도_최신_회차를_내지_않는다():
    """`category` 가 비어 있는 옛 행 — 행사로 확인되지 않았으면 무게로 고른다."""
    grouping = group([ConceptRef(VOGUE_WORLD_2026, 900, True)])

    assert grouping.representative[VOGUE_WORLD_2026] == VOGUE_WORLD


# --- 개념과 부딪칠 때 -----------------------------------------------------


def test_연도_덩이가_두_개념에_걸리면_접지_않는다():
    """사전이 기준형과 회차를 서로 다른 개념에 붙였으면 규칙이 사전을 덮지 않는다."""
    grouping = group(event(VOGUE_WORLD, concept_id=900) + event(VOGUE_WORLD_2026, concept_id=901))

    assert VOGUE_WORLD_2026 not in grouping.representative
    assert VOGUE_WORLD not in grouping.representative


def test_모호한_표기는_연도_덩이에도_넣지_않는다():
    """두 개념에 걸린 표기는 어느 쪽으로도 접지 않는다는 규약을 연도 규칙이 깨지 않는다."""
    grouping = group(event(VOGUE_WORLD, concept_id=900) + event(VOGUE_WORLD, concept_id=901))

    assert VOGUE_WORLD not in grouping.representative
    assert VOGUE_WORLD_2026 not in grouping.representative


# --- 제외 전파 -------------------------------------------------------------


def test_제외된_기준형이면_회차도_빠진다():
    """`vogue world` 가 제외됐는데 `vogue world 2026` 이 순위로 돌아오면 제외를 우회한 것이다."""
    grouping = group(silenced={VOGUE_WORLD})

    assert {VOGUE_WORLD, VOGUE_WORLD_2026} <= grouping.silenced
    assert VOGUE_WORLD_2026 not in grouping.representative
    # 다른 덩이는 그대로 접힌다
    assert grouping.representative == {VOGUE_WORLD_MILANO: VOGUE_WORLD_MILANO_2026}


def test_제외된_회차면_기준형도_빠진다():
    grouping = group(silenced={VOGUE_WORLD_MILANO_2026})

    assert {VOGUE_WORLD_MILANO, VOGUE_WORLD_MILANO_2026} <= grouping.silenced


def test_세지_않는_개념에_붙은_기준형도_마찬가지다():
    grouping = group([ConceptRef(VOGUE_WORLD, 900, False, "generic")])

    assert {VOGUE_WORLD, VOGUE_WORLD_2026} <= grouping.silenced


def test_세는_개념이_있으면_제외가_번지지_않는다():
    """사전이 `Vogue World 2026` 을 세는 행사로 두었으면 `vogue world` 제외 하나가 그걸 덮지 않는다.
    대신 둘을 접지도 않는다 — 부딪친 덩이는 그대로 둔다."""
    grouping = group(event(VOGUE_WORLD_2026), silenced={VOGUE_WORLD})

    assert VOGUE_WORLD in grouping.silenced
    assert VOGUE_WORLD_2026 not in grouping.silenced
    assert VOGUE_WORLD_2026 not in grouping.representative
    assert VOGUE_WORLD not in grouping.representative


def test_제외는_다른_덩이로_번지지_않는다():
    """`vogue` 는 `vogue world` 와 덩이가 다르다 — 잡지 제외가 행사를 끌고 가지 않는다."""
    grouping = group(silenced={VOGUE})

    assert grouping.silenced == frozenset({VOGUE})


# --- 경계 -----------------------------------------------------------------


def test_도메인이_다르면_같은_이름도_접지_않는다():
    grouping = group(
        names={20: "dev summit 2026", 21: "dev summit"},
        weights={20: 5, 21: 9},
        domains={20: "dev"},
    )

    assert grouping.representative == {}


def test_원자료가_없는_키워드는_덩이에_넣지_않는다():
    """지표 행이 안 만들어질 키워드를 대표로 뽑으면 덩이가 통째로 순위에서 사라진다."""
    grouping = build_grouping(
        [],
        {VOGUE_WORLD: 69},
        keywords={VOGUE_WORLD},
        edition_keys={
            VOGUE_WORLD: ("fashion", "vogue world"),
            VOGUE_WORLD_2026: ("fashion", "vogue world"),
        },
        edition_orders={VOGUE_WORLD_2026: (2026, -1, -2)},
    )

    assert grouping.representative == {}


def test_열쇠를_안_주면_옛_동작_그대로다():
    grouping = build_grouping([], WEIGHTS, keywords=set(NAMES))

    assert grouping.representative == {}
    assert grouping.edition_folded == 0


def test_회차가_없는_개념_덩이는_무게로_고른다():
    """개념 접기의 옛 규칙 그대로 — `jeans`(9) 가 `청바지`(4) 를 흡수한다."""
    grouping = group(
        [ConceptRef(40, 100, True, "apparel"), ConceptRef(41, 100, True, "apparel")],
        names={40: "jeans", 41: "청바지"},
        weights={40: 9, 41: 4},
    )

    assert grouping.representative == {41: 40}


# --- 대표 이름은 한글·로마자에서 --------------------------------------------------


def test_가나_표기가_더_많아도_로마자_표기가_대표다():
    """`シャネル`(9) · `Chanel`(4) · `샤넬`(2) — 일본 매체가 많이 써도 이름은 `Chanel` 이다."""
    grouping = build_grouping(
        [ConceptRef(1, 100, True), ConceptRef(2, 100, True), ConceptRef(3, 100, True)],
        {1: 9, 2: 4, 3: 2},
        keywords={1, 2, 3},
        readable=frozenset({2, 3}),
    )
    assert grouping.representative == {1: 2, 3: 2}


def test_읽을_수_있는_표기가_없으면_무게로_고른다():
    grouping = build_grouping(
        [ConceptRef(1, 100, True), ConceptRef(2, 100, True)],
        {1: 9, 2: 4},
        keywords={1, 2},
        readable=frozenset(),
    )
    assert grouping.representative == {2: 1}


def test_가나_아랍_문자가_있으면_읽을_수_없는_이름이다():
    from trendin.spark.metrics.concepts import readable_name

    assert readable_name("chanel") and readable_name("샤넬") and readable_name("2027 s/s 컬렉션")
    assert not readable_name("シャネル") and not readable_name("شانيل")


# --- 대표 이름은 개념 이름과 같은 표기에서 먼저 (S15P21A102-398) ----------------------


def test_개념_이름과_같은_표기가_무게보다_먼저다():
    """`pelle`(9) · `leather`(4) · `가죽`(2) — 이탈리아 매체가 많이 써도 이름은 `leather` 다.
    셋 다 로마자·한글이라 `readable` 만으로는 `pelle` 가 이겼다."""
    grouping = build_grouping(
        [ConceptRef(1, 112, True), ConceptRef(2, 112, True), ConceptRef(3, 112, True)],
        {1: 9, 2: 4, 3: 2},
        keywords={1, 2, 3},
        readable=frozenset({1, 2, 3}),
        named=frozenset({2, 3}),
    )
    assert grouping.representative == {1: 2, 3: 2}


def test_개념_이름이_둘이면_그_사이는_무게로_고른다():
    """영어 이름으로 늘 바꾸지 않는다 — `팬츠`(9) 가 `pants`(4) 보다 많으면 `팬츠` 다."""
    grouping = build_grouping(
        [ConceptRef(1, 50, True), ConceptRef(2, 50, True)],
        {1: 4, 2: 9},
        keywords={1, 2},
        readable=frozenset({1, 2}),
        named=frozenset({1, 2}),
    )
    assert grouping.representative == {1: 2}


def test_개념_이름과_같은_표기가_없으면_읽을_수_있는_표기에서_고른다():
    """`borse`(9) · `bags`(4) · `バッグ`(20) — 개념 이름(`bag` · `가방`) 표기가 승격되지 않았다."""
    grouping = build_grouping(
        [ConceptRef(1, 11, True), ConceptRef(2, 11, True), ConceptRef(3, 11, True)],
        {1: 9, 2: 4, 3: 20},
        keywords={1, 2, 3},
        readable=frozenset({1, 2}),
        named=frozenset(),
    )
    assert grouping.representative == {2: 1, 3: 1}


def test_행사_덩이는_개념_이름보다_최신_회차가_먼저다():
    """행사 개념의 영어 이름이 `Vogue World` 여도 보이는 이름은 최신 회차다 (머리말의 차례)."""
    refs = event(VOGUE_WORLD, VOGUE_WORLD_2026)
    names = {VOGUE_WORLD: NAMES[VOGUE_WORLD], VOGUE_WORLD_2026: NAMES[VOGUE_WORLD_2026]}
    keys = {keyword_id: edition_key(name) for keyword_id, name in names.items()}
    grouping = build_grouping(
        refs,
        WEIGHTS,
        keywords=set(names),
        edition_keys={keyword_id: ("fashion", key) for keyword_id, key in keys.items()},
        edition_orders={
            keyword_id: (*order, -len(keys[keyword_id].split()))
            for keyword_id, name in names.items()
            if (order := edition_order(name)) is not None
        },
        representative_min_share=SHARE,
        named=frozenset({VOGUE_WORLD}),
    )
    assert grouping.representative == {VOGUE_WORLD: VOGUE_WORLD_2026}


# --- 모호한 표기와 숨기기 (S15P21A102-398) ------------------------------------------


def test_두_개념에_걸려도_둘_다_세지_않으면_뺀다():
    """`Dior` 가 브랜드와 디자이너에 함께 걸리고 둘 다 숨길 분류다 — 어느 쪽이든 세지 않는다."""
    grouping = build_grouping(
        [ConceptRef(1, 10, False, "brand"), ConceptRef(1, 20, False, "designer")],
        {1: 9},
        keywords={1},
    )
    assert grouping.silenced == frozenset({1})


def test_두_개념_중_하나라도_세면_모호하게_혼자_둔다():
    """하나는 세고 하나는 안 센다 — 옛 모호 규약대로 접지도 빼지도 않는다."""
    grouping = build_grouping(
        [ConceptRef(1, 10, True, "brand"), ConceptRef(1, 20, False, "designer")],
        {1: 9},
        keywords={1},
    )
    assert grouping.silenced == frozenset()
    assert grouping.representative == {}
