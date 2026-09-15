"""트렌드 유형 판별과 무정보어 제거 — [07 §6]."""

from __future__ import annotations

import math
from datetime import date

import pytest

from trendin.spark.metrics.growth import MetricRow, assign_ranks, build_row
from trendin.spark.metrics.thresholds import (
    MIN_SOURCES,
    AggregateThresholds,
    NewWindow,
    RisingThresholds,
    ZScoreThresholds,
)
from trendin.spark.metrics.trends import (
    CURRENT,
    NEW,
    RISING,
    Evidence,
    is_current,
    is_new,
    is_rising,
    judge,
    zscore,
)

RISING_THRESHOLDS = RisingThresholds(
    min_growth_amount=3, min_growth_rate=50.0, min_mention_count=5, top_n=5
)
ZSCORE = ZScoreThresholds(background_days=90, min_background_days=10, min_z=2.0)
WINDOW_24H = NewWindow(quiet_days=7, quiet_max=1, min_mentions=5)


def row(keyword_id: int, mentions: int, previous: int, *, period: str = "24H") -> MetricRow:
    return build_row(
        keyword_id=keyword_id,
        domain="fashion",
        period=period,
        period_start=date(2026, 9, 9),
        period_end=date(2026, 9, 10),
        mention_count=mentions,
        previous_mention_count=previous,
    )


def evidence(*, sources: int = 2, quiet: int = 0, z: float | None = 5.0) -> Evidence:
    return Evidence(sources=sources, quiet_mentions=quiet, zscore=z)


# --- z-score ---------------------------------------------------------------


def test_배경이_모자라면_z_를_내지_않는다():
    """갓 뜬 키워드는 배경이 없는 것이지 흔한 것이 아니다."""
    assert zscore(3.0, [1, 2, 1], min_days=10) is None


def test_늘_흔한_말은_z_가_0_근처다():
    """`요즘` 처럼 매일 비슷하게 나오는 말. 배경 평균과 같으면 튀지 않는다."""
    background = [5, 4, 6, 5, 5, 4, 6, 5, 5, 5, 4, 6]
    assert abs(zscore(5.0, background, min_days=10)) < 0.5


def test_갑자기_늘어난_말은_z_가_크다():
    background = [0, 1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
    assert zscore(8.0, background, min_days=10) > 2.0


def test_배경이_전부_같으면_커진_쪽은_무한대다():
    """표준편차가 0 이라 나눌 수 없다. "배경에 전혀 없던 것이 나타났다" 는 z 가 무한대다."""
    assert zscore(4.0, [0] * 12, min_days=10) == math.inf


def test_배경이_전부_같고_현재도_같으면_0_이다():
    assert zscore(0.0, [0] * 12, min_days=10) == 0.0


def test_0_인_날을_배경에_포함한다():
    """0 을 빼면 "가끔 크게 뜨는 말" 의 평균이 실제보다 높아져 급증이 묻힌다."""
    sparse = [0] * 11 + [10]
    dense = [10] * 12
    assert zscore(10.0, sparse, min_days=10) > zscore(10.0, dense, min_days=10)


# --- CURRENT ---------------------------------------------------------------


def test_CURRENT_는_상위_N_이다():
    ranked = assign_ranks([row(index, 10 - index, 1) for index in range(1, 8)])
    picked = {item.keyword_id for item in ranked if is_current(item, 5)}
    assert picked == {1, 2, 3, 4, 5}


def test_순위가_없으면_CURRENT_가_아니다():
    """언급량 0 으로 떨어진 키워드에는 순위가 없다."""
    assert not is_current(assign_ranks([row(1, 0, 9)])[0], 5)


# --- RISING ----------------------------------------------------------------


def test_세_조건을_다_넘어야_RISING_이다():
    assert is_rising(row(1, 9, 3), evidence(), RISING_THRESHOLDS, ZSCORE)


@pytest.mark.parametrize(
    "mentions, previous, 이유",
    [
        (7, 5, "증가량 2 < A=3"),
        (8, 6, "증가율 33% < B=50"),
        (4, 1, "언급량 4 < C=5"),
    ],
)
def test_한_조건이라도_모자라면_아니다(mentions, previous, 이유):
    assert not is_rising(row(1, mentions, previous), evidence(), RISING_THRESHOLDS, ZSCORE), 이유


def test_직전이_0_이면_RISING_이_아니다():
    """`growth_rate` 가 `None` 이라 탈락한다. 그런 키워드는 `NEW` 가 담당한다."""
    assert not is_rising(row(1, 50, 0), evidence(), RISING_THRESHOLDS, ZSCORE)


def test_극소_표본은_증가율이_높아도_아니다():
    """1건 → 3건이 200% 다. 하한 C 가 없으면 목록이 이런 것으로 찬다."""
    assert not is_rising(row(1, 3, 1), evidence(), RISING_THRESHOLDS, ZSCORE)


def test_한_매체에서만_쏟아진_키워드는_RISING_이_아니다():
    assert not is_rising(
        row(1, 9, 3), evidence(sources=MIN_SOURCES - 1), RISING_THRESHOLDS, ZSCORE
    )


def test_늘_흔한_말은_z_에서_걸린다():
    """`요즘`·`매력` — 지표는 넘지만 배경 대비 튀지 않는다 ([07 §6])."""
    assert not is_rising(row(1, 90, 60), evidence(z=0.3), RISING_THRESHOLDS, ZSCORE)


def test_배경이_없으면_z_로_막지_않는다():
    assert is_rising(row(1, 9, 3), evidence(z=None), RISING_THRESHOLDS, ZSCORE)


# --- NEW -------------------------------------------------------------------


def test_이전이_조용하고_최근이_시끄러우면_NEW_다():
    assert is_new(row(1, 5, 0), evidence(quiet=1), WINDOW_24H)


def test_이전이_시끄러웠으면_NEW_가_아니다():
    """3주간 후보로 조용히 관측되다 오늘 승격된 키워드가 여기서 걸린다."""
    assert not is_new(row(1, 9, 0), evidence(quiet=2), WINDOW_24H)


def test_최근이_모자라면_NEW_가_아니다():
    assert not is_new(row(1, 4, 0), evidence(quiet=0), WINDOW_24H)


def test_한_매체에서만_쏟아진_키워드는_NEW_가_아니다():
    """자동 발견에서 `NEW` 목록은 노이즈가 가장 먼저 도착하는 곳이다."""
    assert not is_new(row(1, 9, 0), evidence(sources=1, quiet=0), WINDOW_24H)


def test_반년_전_한_번_스친_표기도_다시_NEW_다():
    """v1 이 `first_seen_at` 때문에 틀렸던 경우 ([07 §6] 의 표 세 번째 줄)."""
    assert is_new(row(1, 30, 0), evidence(quiet=0), WINDOW_24H)


# --- 판별 묶음 --------------------------------------------------------------


def thresholds(**overrides) -> AggregateThresholds:
    base = dict(
        periods=("24H",),
        reference_day_offset=1,
        recompute_window_days=30,
        active_window_days=30,
        current_top_n=5,
        rising=RISING_THRESHOLDS,
        new_windows={"24H": WINDOW_24H},
        new_top_n=5,
        zscore=ZSCORE,
        author_daily_cap=None,
    )
    base.update(overrides)
    return AggregateThresholds(**base)


def test_한_키워드가_NEW_이면서_RISING_일_수_있다():
    """배타적이지 않다 — v1 은 우선순위로 하나만 골랐는데 그 제약이 없어졌다.

    조용하다가 나타나(`NEW`) 빠르게 늘고(`RISING`) 상위 5위 안에 든(`CURRENT`) 키워드에는
    셋이 다 붙는다. 그게 사실에 맞다.
    """
    rows = assign_ranks([row(1, 9, 3)])
    verdict = judge(rows, {(1, "24H"): evidence(quiet=0)}, thresholds())
    assert set(verdict[(1, "24H")]) == {CURRENT, RISING, NEW}


def test_RISING_은_상위_N_만_남는다():
    rows = assign_ranks([row(index, 20 + index, 5) for index in range(1, 9)])
    found = {(item.keyword_id, "24H"): evidence(z=5.0) for item in rows}
    verdict = judge(rows, found, thresholds(rising=_top(RISING_THRESHOLDS, 2)))
    assert sum(1 for types in verdict.values() if RISING in types) == 2


def test_근거가_없는_행은_판별하지_않는다():
    """소스 수를 못 구한 키워드를 조용히 통과시키지 않는다."""
    assert judge(assign_ranks([row(1, 9, 3)]), {}, thresholds()) == {}


def test_한_기간의_판정이_다른_기간으로_번지지_않는다():
    """`trends` 에 합집합을 싣던 때는 번졌다 — `24H` 에서만 급상승한 키워드가 `7D` 목록에서도
    배지를 달았다. 판정 자리가 `keyword_metrics` 로 옮겨오면서 기간별로 갈린다 ([07 §6]).
    """
    rows = assign_ranks([row(1, 9, 3), row(1, 9, 9, period="7D")])
    found = {(1, "24H"): evidence(quiet=5), (1, "7D"): evidence(quiet=5)}
    verdict = judge(rows, found, thresholds())
    assert RISING in verdict[(1, "24H")]
    assert RISING not in verdict[(1, "7D")]


def test_배열_차례가_고정이다():
    """같은 내용인데 값의 차례만 뒤바뀌면 `IS DISTINCT FROM` 이 참이 되어 빈 UPDATE 가 나간다."""
    rows = assign_ranks([row(1, 9, 3)])
    verdict = judge(rows, {(1, "24H"): evidence(quiet=0)}, thresholds())
    assert verdict[(1, "24H")] == (CURRENT, RISING, NEW)


def _top(rising: RisingThresholds, top_n: int) -> RisingThresholds:
    from dataclasses import replace

    return replace(rising, top_n=top_n)
