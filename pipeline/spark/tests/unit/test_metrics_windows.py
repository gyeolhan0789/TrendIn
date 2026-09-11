"""구간 경계와 기준일 D — [07 §4].

**백엔드와의 대응이 이 파일의 핵심이다.** `AnalysisWindow.completed` 가 같은 구간을 독립으로
계산하고 `KeywordMetricRepository` 가 등호로 조회하므로, 한 자리만 어긋나도 목록이 통째로
빈다 — 값이 틀린 것이 아니라 **아무것도 안 나오는** 증상으로 나타난다.
"""

from __future__ import annotations

from datetime import date

import pytest

from trendin.spark.metrics import windows as w

# 2026-09-10 에 돌린 실행. D 는 어제인 2026-09-09 다.
TODAY = date(2026, 9, 10)
D = date(2026, 9, 9)


# --- 기준일 ---------------------------------------------------------------


def test_기준일은_실행일의_전날이다():
    assert w.reference_day(TODAY, 1) == D


def test_offset_0_은_진행_중인_오늘을_기준일로_삼는다():
    # 규격이 막은 선택이지만 함수는 계산해 준다 — 막는 것은 설정의 기본값이다 ([07 §4]).
    assert w.reference_day(TODAY, 0) == TODAY


def test_음수_offset_은_거부한다():
    with pytest.raises(w.WindowError):
        w.reference_day(TODAY, -1)


# --- 현재·직전 구간 --------------------------------------------------------


@pytest.mark.parametrize(
    "period, start, end",
    [
        ("24H", date(2026, 9, 9), date(2026, 9, 10)),
        ("7D", date(2026, 9, 3), date(2026, 9, 10)),
        ("30D", date(2026, 8, 11), date(2026, 9, 10)),
    ],
)
def test_현재_구간은_D_를_포함하고_D_다음날에서_끝난다(period, start, end):
    window = w.current_window(period, D)
    assert (window.start, window.end) == (start, end)
    assert window.days == w.period_days(period)


@pytest.mark.parametrize(
    "period, start, end",
    [
        ("24H", date(2026, 9, 8), date(2026, 9, 9)),
        ("7D", date(2026, 8, 27), date(2026, 9, 3)),
        ("30D", date(2026, 7, 12), date(2026, 8, 11)),
    ],
)
def test_직전_구간은_현재와_길이가_같고_바로_앞에_붙는다(period, start, end):
    previous = w.previous_window(period, D)
    current = w.current_window(period, D)
    assert (previous.start, previous.end) == (start, end)
    assert previous.end == current.start
    assert previous.days == current.days


def test_반열린_구간이라_경계가_겹치지_않는다():
    current = w.current_window("7D", D)
    previous = w.previous_window("7D", D)
    assert previous.contains(previous.end - _one_day())
    assert not previous.contains(previous.end)
    assert current.contains(current.start)
    assert not current.contains(current.end)


# --- 백엔드 대응 회귀 -------------------------------------------------------


@pytest.mark.parametrize("period", ["24H", "7D", "30D"])
def test_현재_구간_끝이_실행일_자정이다(period):
    """백엔드 `AnalysisWindow.completed` 의 `recentEnd` = 오늘 KST 자정.

    `reference_day_offset: 1` 이 그 일치를 준다. 0 으로 두면 우리 구간이 하루 앞서
    백엔드 조회가 빈 목록을 받는다.
    """
    window = w.current_window(period, w.reference_day(TODAY, 1))
    assert window.end == TODAY


@pytest.mark.parametrize("period", ["24H", "7D", "30D"])
def test_직전_구간이_백엔드의_previous_와_같다(period):
    """백엔드: `previousStart = recentStart − 기간`, `previousEnd = recentStart`."""
    current = w.current_window(period, D)
    previous = w.previous_window(period, D)
    assert previous.end == current.start
    assert (current.start - previous.start).days == w.period_days(period)


def test_자정_문자열에_KST_오프셋이_붙는다():
    # 오프셋이 없으면 PostgreSQL 이 세션 시간대로 해석하고, 그 시간대가 무엇인지는
    # 보장되지 않는다 ([08 §4]).
    assert w.midnight(D) == "2026-09-09 00:00:00+09:00"


# --- NEW 의 조용함 창 ------------------------------------------------------


def test_조용함_창은_직전_구간과_다르다():
    """`24H` 의 직전 7일은 `[D−7, D)` 이고 직전 구간은 `[D−1, D)` 다 ([07 §6])."""
    quiet = w.quiet_window("24H", D, 7)
    previous = w.previous_window("24H", D)
    assert (quiet.start, quiet.end) == (date(2026, 9, 2), date(2026, 9, 9))
    assert quiet != previous
    assert quiet.end == previous.end


@pytest.mark.parametrize(
    "period, quiet_days, start",
    [("24H", 7, date(2026, 9, 2)), ("7D", 30, date(2026, 8, 4)), ("30D", 90, date(2026, 5, 13))],
)
def test_조용함_창은_현재_구간_바로_앞의_N일이다(period, quiet_days, start):
    quiet = w.quiet_window(period, D, quiet_days)
    assert quiet.start == start
    assert quiet.end == w.current_window(period, D).start


def test_배경_구간은_현재_구간을_포함하지_않는다():
    """현재를 배경에 넣으면 자기 자신과 비교하게 되어 급증이 스스로를 희석한다."""
    background = w.background_window("7D", D, 90)
    current = w.current_window("7D", D)
    assert background.end == current.start
    assert not background.contains(current.start)


# --- 재계산 구간과 지평 -----------------------------------------------------


def test_재계산_구간은_D_를_포함한_W일이다():
    window = w.history_window(D, 30)
    assert (window.start, window.end) == (date(2026, 8, 11), date(2026, 9, 10))
    assert window.days == 30
    assert len(window.dates()) == 30


def test_지평은_주어진_창_전부를_덮는다():
    horizon = w.horizon(D, [w.current_window("24H", D), w.quiet_window("30D", D, 90)])
    assert horizon.start == date(2026, 5, 13)
    assert horizon.end == date(2026, 9, 10)


# --- 경계와 거부 -----------------------------------------------------------


def test_모르는_기간은_거부한다():
    with pytest.raises(w.WindowError):
        w.period_days("1H")


def test_뒤집힌_구간은_만들_수_없다():
    with pytest.raises(w.WindowError):
        w.Window(date(2026, 9, 9), date(2026, 9, 9))


def test_조용함_창은_0일일_수_없다():
    with pytest.raises(w.WindowError):
        w.quiet_window("24H", D, 0)


def _one_day():
    from datetime import timedelta

    return timedelta(days=1)
