"""층 1·2 병합 판정 ([05 §2·§3]). 층 1.

**자동 병합이 틀리면 되돌릴 수 없다** ([05 §1]). 그래서 이 파일의 시험 대부분이 "합쳐지지
않는 것" 을 지킨다 — 규격이 명시적으로 거부한 경우들이다.
"""

from __future__ import annotations

import json

from registry_support import make_registry_thresholds as thresholds

from trendin.spark.registry import merge, normalize
from trendin.spark.registry.merge import AbbreviationEvidence, bounded_distance

DOMAIN = "fashion"


# --- 편집 거리 -------------------------------------------------------------


def test_길이_차가_상한을_넘으면_계산하지_않는다():
    """조기 종료가 이중 루프를 감당 가능하게 만드는 부분이다 (`merge.py` 의 비용 절)."""
    assert bounded_distance("kubernetes", "k8s", 2) is None
    assert bounded_distance("react", "react", 2) == 0
    assert bounded_distance("react", "raect", 2) == 2
    assert bounded_distance("react", "reactt", 1) == 1
    assert bounded_distance("react", "vue", 2) is None


def test_한글은_자모로_센다():
    """**2026-09-09 실데이터 리허설에서 잡힌 결함.** 음절로 세면 딴 낱말이 거리 1 로 보여
    `데님 셔츠` 가 `데님 팬츠` 로 자동 병합됐다 ([05 §3], `merge.bounded_distance` 의 표).

    `variant_min_length` 로는 못 막는다 — 이미 5자를 넘는다. 거리의 정의를 고친 자리다.
    """
    # 딴 낱말 — 음절 거리 1~2 인데 자모로는 멀다.
    assert bounded_distance("데님 셔츠", "데님 팬츠", 2) is None
    assert bounded_distance("가을 슈즈", "플랫 슈즈", 2) is None
    assert bounded_distance("데님 셋업", "데님 팬츠", 2) is None

    # 진짜 오타 — 자모 하나가 틀렸다 (ㅔ/ㅐ).
    assert bounded_distance("플렛 슈즈", "플랫 슈즈", 2) == 1

    # 라틴 문자는 NFD 가 건드리지 않으므로 그대로다.
    assert bounded_distance("kubernetes", "kubernets", 2) == 1


# --- 층 1 조건부 복수형 ([05 §2]) ------------------------------------------


def test_한쪽_DF_가_압도하면_접는다():
    pairs = normalize.plural_pairs(
        {"agent": 60, "agents": 4}, domain=DOMAIN, thresholds=thresholds()
    )

    assert [(pair.representative, pair.absorbed) for pair in pairs] == [("agent", "agents")]
    assert pairs[0].layer == merge.LAYER_DETERMINISTIC


def test_양쪽이_다_흔하면_접지_않는다():
    """**2026-09-09 실측 그대로다** — `사람들`(35문서) 대 `사람`(71) 은 비율 2.03 이다.

    [05 §2] 가 이 쌍이 접히지 않는 것을 근거로 "토큰화에서 접는 것이 여기서 접는 것보다
    싸다" 를 판단했다. 이 시험이 그 판단의 회귀 방어다.
    """
    df = {"사람": 71, "사람들": 35}

    pairs = normalize.plural_pairs(df, domain=DOMAIN, thresholds=thresholds())

    assert pairs == ()


def test_한쪽만_코퍼스에_있으면_접지_않는다():
    """과교정 방어 ([05 §2]) — `CSS`→`CS`, `glasses`→`glasse` 가 이 조건에 걸린다."""
    assert normalize.plural_pairs({"css": 40}, domain=DOMAIN, thresholds=thresholds()) == ()
    assert normalize.plural_pairs({"glasses": 40}, domain=DOMAIN, thresholds=thresholds()) == ()


def test_복수형이_더_흔하면_그쪽이_대표다():
    pairs = normalize.plural_pairs(
        {"glasses": 50, "glasse": 2}, domain=DOMAIN, thresholds=thresholds()
    )

    assert [(pair.representative, pair.absorbed) for pair in pairs] == [("glasses", "glasse")]


def test_마지막_토큰에서만_뗀다():
    """`agents list` 를 `agent list` 로 바꾸면 딴 낱말이 된다 (`normalize.py`)."""
    pairs = normalize.plural_pairs(
        {"ai agents": 3, "ai agent": 40, "agents list": 3, "agent list": 40},
        domain=DOMAIN,
        thresholds=thresholds(),
    )

    # `ai agents` 는 접히고 `agents list` 는 접히지 않는다 — 복수는 늘 끝에 붙는다.
    assert [(pair.representative, pair.absorbed) for pair in pairs] == [("ai agent", "ai agents")]


# --- 층 2 약어 ↔ 전개형 ([05 §3]) -----------------------------------------


def evidence(**overrides) -> AbbreviationEvidence:
    values = dict(
        abbreviation_key="mcp",
        expansion_key="model context protocol",
        initials_match=True,
        document_count=5,
        source_count=3,
    )
    values.update(overrides)
    return AbbreviationEvidence(**values)


DF = {"mcp": 40, "model context protocol": 9}


def test_세_조건을_다_만족하면_병합하고_대표는_빈번한_쪽이다():
    pairs = merge.abbreviation_pairs([evidence()], domain=DOMAIN, df=DF, thresholds=thresholds())

    assert [(pair.representative, pair.absorbed) for pair in pairs] == [
        ("mcp", "model context protocol")
    ]
    assert pairs[0].layer == merge.LAYER_EVIDENCE
    assert pairs[0].confidence == 1.0


def test_초성_대응이_없으면_병합하지_않는다():
    """한국어 전개형이 이 경우다 (`io/candidates.py` 의 `initials_match` 주석)."""
    assert (
        merge.abbreviation_pairs(
            [evidence(initials_match=False)], domain=DOMAIN, df=DF, thresholds=thresholds()
        )
        == ()
    )


def test_문서_하한과_소스_하한에_각각_걸린다():
    assert (
        merge.abbreviation_pairs(
            [evidence(document_count=2)], domain=DOMAIN, df=DF, thresholds=thresholds()
        )
        == ()
    ), "한 사람의 오기를 막는 조건"
    assert (
        merge.abbreviation_pairs(
            [evidence(source_count=1)], domain=DOMAIN, df=DF, thresholds=thresholds()
        )
        == ()
    ), "한 커뮤니티의 관용을 막는 조건"


def test_소스_하한은_설정으로_낮출_수_없다():
    """[05 §3]·[05 §5] 가 못 박은 값이라 규격의 일부다 (`registry/thresholds.MIN_SOURCES`)."""
    assert thresholds().min_sources == 2


def test_한쪽이_후보로_남아_있지_않으면_병합하지_않는다():
    """필터나 DF 문턱에 걸려 사라진 표기는 합칠 대상이 없다."""
    assert (
        merge.abbreviation_pairs(
            [evidence()], domain=DOMAIN, df={"mcp": 40}, thresholds=thresholds()
        )
        == ()
    )


# --- 층 2 표기 변형 ([05 §3]) ---------------------------------------------


def test_편집_거리와_DF_압도를_함께_만족해야_흡수한다():
    scan = merge.variant_pairs(
        {"kubernetes": 80, "kubernets": 2}, domain=DOMAIN, thresholds=thresholds()
    )

    assert [(pair.representative, pair.absorbed) for pair in scan.pairs] == [
        ("kubernetes", "kubernets")
    ]
    assert not scan.skipped


def test_양쪽이_비슷하게_흔하면_오타로_보지_않는다():
    df = {"kubernetes": 80, "kubernets": 40}

    assert merge.variant_pairs(df, domain=DOMAIN, thresholds=thresholds()).pairs == ()


def test_짧은_표기에는_적용하지_않는다():
    """[05 §3] — 4자 이하에서 거리 1은 완전히 다른 낱말인 경우가 흔하다 (`Vue` ↔ `Sue`)."""
    limits = thresholds()

    for df in ({"vue": 80, "sue": 2}, {"모델": 80, "모텔": 2}):
        assert merge.variant_pairs(df, domain=DOMAIN, thresholds=limits).pairs == ()


def test_색인_상한을_넘으면_건너뛰고_그_사실을_남긴다():
    """조용히 몇 분을 태우는 것이 가장 나쁘다 (`merge.py` 의 비용 절).

    **`skipped` 가 이 시험의 요점이다.** 쌍이 `()` 인 것만으로는 "찾을 것이 없었다" 와
    "찾아보지 않았다" 가 구분되지 않아, 상한을 둔 목적(크게 남기기)이 달성되지 않는다.
    """
    df = {f"keyword{index:04d}": 100 for index in range(50)}

    scan = merge.variant_pairs(df, domain=DOMAIN, thresholds=thresholds(variant_max_index_size=10))

    assert scan.pairs == ()
    assert scan.skipped
    assert scan.index_size == 50


def test_찾을_것이_없는_것은_건너뛴_것이_아니다():
    """색인이 비어 쌍이 없는 것은 경보가 아니다 — 볼 것이 없었을 뿐이다."""
    scan = merge.variant_pairs({"kubernetes": 1}, domain=DOMAIN, thresholds=thresholds())

    assert scan.pairs == ()
    assert not scan.skipped


# --- 관측이 없는 후보 (2026-09-09 실데이터 리허설) -------------------------
#
# `pl_candidate` 는 지우지 않으므로([08 §3]) 관측이 사라진 마스터 행이 남는다. 실측에서
# fashion 후보 14,444개 중 **8,583개**가 그랬고, 표본이 `가고` · `가기` 처럼 형태소 분석기로
# 갈아타기 전 규칙 기반 토큰화가 남긴 어미 잡음이었다. 손으로 만든 사전에는 없던 경우다.


def test_관측이_없는_후보는_병합_판정에_참여하지_않는다():
    assert merge.observed({"살아있다": 3, "유령": 0}) == {"살아있다": 3}


def test_DF_0_후보가_섞여도_죽지_않는다():
    """압도 비율이 0 으로 나눠지던 자리다. 세 규칙 모두 그 후보를 건너뛴다."""
    df = {"kubernetes": 80, "kubernets": 0, "agent": 60, "agents": 0, "유령": 0}

    assert merge.variant_pairs(df, domain=DOMAIN, thresholds=thresholds()).pairs == ()
    assert normalize.plural_pairs(df, domain=DOMAIN, thresholds=thresholds()) == ()
    assert (
        merge.abbreviation_pairs(
            [evidence(abbreviation_key="유령", expansion_key="kubernetes")],
            domain=DOMAIN,
            df=df,
            thresholds=thresholds(),
        )
        == ()
    )


def test_관측이_있는_쪽끼리는_그대로_병합된다():
    """유령 후보를 빼는 것이 살아 있는 병합을 막지 않아야 한다."""
    df = {"kubernetes": 80, "kubernets": 2, "유령": 0}

    scan = merge.variant_pairs(df, domain=DOMAIN, thresholds=thresholds())

    assert [(pair.representative, pair.absorbed) for pair in scan.pairs] == [
        ("kubernetes", "kubernets")
    ]


def _brute_force_variants(df, th):
    """고치기 전의 이중 루프 그대로 — 새 탐색이 이것과 같은 쌍을 같은 순서로 내야 한다."""
    long_enough = {k: n for k, n in merge.observed(df).items() if len(k) >= th.variant_min_length}
    index = sorted(k for k, n in long_enough.items() if n >= th.variant_df_dominance)
    out = []
    for absorbed in sorted(long_enough):
        for representative in index:
            if representative == absorbed:
                continue
            if long_enough[representative] < th.variant_df_dominance * long_enough[absorbed]:
                continue
            distance = bounded_distance(absorbed, representative, th.variant_max_edit_distance)
            if distance is not None:
                out.append((representative, absorbed, distance))
    return out


def test_변형_탐색은_전수_비교와_같은_쌍을_같은_순서로_낸다():
    """S15P21A102-395 — 길이별 색인 · DF 순 조기 종료가 결과를 바꾸지 않는다."""
    th = thresholds(variant_min_length=5, variant_max_edit_distance=2, variant_df_dominance=10)
    # 대표 넷(DF 90~300)과 오타 · 복수 · 딴 낱말(DF 1~40). 딴 낱말(`denim skirt` · `데님 팬츠`)은
    # 거리가 가깝거나 압도가 모자라 빠져야 한다.
    df = {
        "denim shirt": 300,
        "denim shirts": 12,
        "denim skirt": 40,
        "demin shirt": 3,
        "denim shrit": 1,
        "leather jacket": 250,
        "lether jacket": 2,
        "leather jackets": 30,
        "leathr jacket": 1,
        "데님 셔츠": 200,
        "데님 셔즈": 4,
        "데님 팬츠": 5,
        "플랫 슈즈": 120,
        "플렛 슈즈": 2,
        "플랫 슈즈즈": 1,
        "cardigan": 90,
        "cardigans": 9,
        "cardgan": 1,
        "carddigan": 0,
        "knitwear": 15,
        "knit wear": 1,
    }
    scan = merge.variant_pairs(df, domain=DOMAIN, thresholds=th)
    found = [
        (p.representative, p.absorbed, json.loads(p.signal)["edit_distance"]) for p in scan.pairs
    ]
    assert found == _brute_force_variants(df, th)
    assert found  # 비교할 쌍이 실제로 있어야 시험이 뜻을 갖는다
