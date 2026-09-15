"""[07] 단계 배선 — 원자료에서 두 표의 행이 나오기까지.

**DB 없이 돈다.** `MetricSink` 자리에 가짜를 끼운다 — `aggregate` 는 Spark 도 쓰지 않으므로
([09 §4] 층 1) 이 시험이 배선 전체를 덮는다.
"""

from __future__ import annotations

from datetime import date, timedelta

from trendin.spark.metrics import batch
from trendin.spark.metrics.batch import Series
from trendin.spark.metrics.thresholds import (
    AggregateThresholds,
    NewWindow,
    RisingThresholds,
    ZScoreThresholds,
)
from trendin.spark.metrics.windows import current_window, history_window

TODAY = date(2026, 9, 10)
D = date(2026, 9, 9)


def thresholds(**overrides) -> AggregateThresholds:
    base = dict(
        periods=("24H",),
        reference_day_offset=1,
        recompute_window_days=7,
        active_window_days=7,
        current_top_n=5,
        rising=RisingThresholds(
            min_growth_amount=3, min_growth_rate=50.0, min_mention_count=5, top_n=5
        ),
        new_windows={"24H": NewWindow(quiet_days=7, quiet_max=1, min_mentions=5)},
        new_top_n=5,
        zscore=ZScoreThresholds(background_days=30, min_background_days=10, min_z=2.0),
        author_daily_cap=None,
    )
    base.update(overrides)
    return AggregateThresholds(**base)


class FakeSink:
    """`MetricSink` 의 자리. 읽은 것을 그대로 주고 쓴 것을 들고 있는다."""

    def __init__(self, daily, *, covered=None, sources=None):
        self.daily = daily
        self._covered = covered
        self._sources = sources or {}
        self.written = None
        self.verdict_rows = []

    def daily_mentions(self, *, start, end):
        return tuple(self.daily)

    def covered_dates(self, *, start, end):
        if self._covered is not None:
            return tuple(self._covered)
        return tuple({(domain, day) for _, domain, day, _ in self.daily})

    def daily_volume(self, *, start, end):
        totals = {}
        for _, domain, day, mentions in self.daily:
            totals[(domain, day)] = totals.get((domain, day), 0) + mentions
        return tuple((domain, day, total) for (domain, day), total in totals.items())

    def period_sources(self, *, start, end):
        return dict(self._sources)

    def write(self, **kwargs):
        self.written = kwargs
        return None

    def log_verdict(self, rows):
        self.verdict_rows = list(rows)
        return len(rows)


def daily(keyword_id: int, day: date, mentions: int, *, domain: str = "fashion"):
    return (keyword_id, domain, day, mentions)


def days_before(count: int) -> date:
    return D - timedelta(days=count)


# --- 원자료 읽기 -----------------------------------------------------------


def test_같은_키워드의_여러_행을_더한다():
    """병합이 반쯤 된 상태면 `(keyword_id, 날짜)` 가 둘일 수 있다. 하나만 세지 않는다."""
    sink = FakeSink([daily(1, D, 3), daily(1, D, 2)])
    series = batch.load_series(sink, history_window(D, 7))
    assert series[1].daily[D] == 5


# --- 날짜별 추이 -----------------------------------------------------------


def test_언급이_없던_날은_0_행이_된다():
    series = {1: Series(1, "fashion", {D: 3})}
    covered = {("fashion", day) for day in history_window(D, 3).dates()}
    rows, gaps = batch.history_rows(
        series, window=history_window(D, 3), active_window=history_window(D, 7), covered=covered
    )
    assert [row[3] for row in rows] == [0, 0, 3]
    assert gaps == 0


def test_수집이_없던_날은_행_자체가_없다():
    """행의 유무가 "0" 과 "데이터 없음" 을 가른다 ([07 §3]). 프론트가 구멍으로 그린다."""
    series = {1: Series(1, "fashion", {D: 3})}
    covered = {("fashion", D), ("fashion", days_before(1))}
    rows, gaps = batch.history_rows(
        series, window=history_window(D, 3), active_window=history_window(D, 7), covered=covered
    )
    assert [row[1] for row in rows] == ["2026-09-08 00:00:00+09:00", "2026-09-09 00:00:00+09:00"]
    assert gaps == 1


def test_활성_집합_밖의_키워드는_0_행을_받지_않는다():
    """정규 키워드 전체 × W 를 매 실행 갱신하면 0 인 행을 대량으로 쓰게 된다."""
    series = {
        1: Series(1, "fashion", {D: 3}),
        2: Series(2, "fashion", {days_before(60): 9}),  # 오래전에만 언급
    }
    covered = {("fashion", day) for day in history_window(D, 7).dates()}
    rows, _ = batch.history_rows(
        series, window=history_window(D, 7), active_window=history_window(D, 7), covered=covered
    )
    assert {row[0] for row in rows} == {1}


def test_버킷은_하루다():
    series = {1: Series(1, "fashion", {D: 1})}
    covered = {("fashion", D)}
    rows, _ = batch.history_rows(
        series, window=history_window(D, 1), active_window=history_window(D, 7), covered=covered
    )
    assert rows == [(1, "2026-09-09 00:00:00+09:00", "2026-09-10 00:00:00+09:00", 1)]


# --- 기간별 지표 -----------------------------------------------------------


def test_두_구간_다_0_이면_행을_만들지_않는다():
    series = {1: Series(1, "fashion", {days_before(30): 9})}
    assert batch.metric_rows(series, period="24H", reference=D) == []


def test_직전에만_있던_키워드도_행을_갖는다():
    """하락을 표현하기 위해서다. 행이 없으면 화면에서 그냥 사라진다 ([07 §5])."""
    series = {1: Series(1, "fashion", {days_before(1): 100})}
    rows = batch.metric_rows(series, period="24H", reference=D)
    assert (rows[0].mention_count, rows[0].previous_mention_count) == (0, 100)
    assert rows[0].growth_amount == -100
    assert rows[0].mention_rank is None


def test_구간_합이_반열린_경계를_지킨다():
    """`7D` 의 현재는 `[D−6, D+1)` 이라 `D−7` 은 직전 구간이다."""
    series = {1: Series(1, "fashion", {days_before(6): 1, days_before(7): 1, D: 1})}
    rows = batch.metric_rows(series, period="7D", reference=D)
    assert (rows[0].mention_count, rows[0].previous_mention_count) == (2, 1)


# --- 판별 근거 -------------------------------------------------------------


def test_조용함_창은_현재_구간을_포함하지_않는다():
    series = {1: Series(1, "fashion", {D: 9, days_before(3): 2})}
    rows = batch.metric_rows(series, period="24H", reference=D)
    found = batch.evidence_for(
        series, rows, period="24H", reference=D, sources={1: 2}, volume={},
        thresholds=thresholds(),
    )
    assert found[(1, "24H")].quiet_mentions == 2


def test_소스_수를_못_구하면_0_이다():
    """조용히 통과시키지 않는다 — `MIN_SOURCES` 에 걸려 `NEW`·`RISING` 에서 빠진다."""
    series = {1: Series(1, "fashion", {D: 9})}
    rows = batch.metric_rows(series, period="24H", reference=D)
    found = batch.evidence_for(
        series, rows, period="24H", reference=D, sources={}, volume={},
        thresholds=thresholds(),
    )
    assert found[(1, "24H")].sources == 0


# --- 한 바퀴 --------------------------------------------------------------


def rising_series() -> list[tuple]:
    """직전 3건 → 오늘 9건. 조용하지 않아 `NEW` 는 아니고 `RISING` 이다."""
    rows = [daily(1, days_before(1), 3), daily(1, D, 9)]
    rows += [daily(1, days_before(offset), 1) for offset in range(2, 8)]
    return rows


# `keyword_metrics` 스테이징 한 줄의 자리 — `io/metrics.METRIC_COLUMNS` 와 같은 차례다.
PERIOD = 1
TREND_TYPES = 9


def test_한_바퀴_돌면_두_표의_행이_나온다():
    sink = FakeSink(rising_series(), sources={1: 2})
    result = batch.run(sink, thresholds(), today=TODAY, run_id="R1")
    assert result.reference_day == D
    assert result.keywords == 1
    assert sink.written["metrics"][0][PERIOD] == "24H"
    assert sink.written["history"]
    assert "trends" not in sink.written


def test_배지가_그_기간의_지표_행에_실린다():
    """기간을 합치지 않으므로 어느 기간의 판정인지가 행 자체에 남는다 ([07 §6])."""
    sink = FakeSink(rising_series(), sources={1: 2})
    batch.run(sink, thresholds(), today=TODAY, run_id="R1")
    assert sink.written["metrics"][0][TREND_TYPES] == ["CURRENT", "RISING"]


def test_판별_이력이_회차별로_남는다():
    sink = FakeSink(rising_series(), sources={1: 2})
    batch.run(sink, thresholds(), today=TODAY, run_id="R1")
    assert sink.verdict_rows == [("R1", 1, "24H", ["CURRENT", "RISING"], "2026-09-09")]


def test_유형을_못_받은_행에는_빈_배열이_실린다():
    """**그 빈 배열이 배지를 뗀다.** 지표 행과 배지가 한 줄이라, 지금 배지를 든 키워드를 따로
    읽어 비우는 단계가 없다 ([07 §6]). 여기서는 직전 구간에만 언급이 있어 순위도 유형도 없다.
    """
    sink = FakeSink([daily(9, days_before(1), 5)], sources={9: 2})
    batch.run(sink, thresholds(), today=TODAY, run_id="R1")
    assert sink.written["metrics"][0][TREND_TYPES] == []


def test_같은_날짜로_두_번_돌려도_같은_행이_나온다():
    """[07 §7] 멱등성. 계산이 순수하므로 원자료가 같으면 결과가 같다."""
    first = FakeSink(rising_series(), sources={1: 2})
    second = FakeSink(rising_series(), sources={1: 2})
    batch.run(first, thresholds(), today=TODAY, run_id="R1")
    batch.run(second, thresholds(), today=TODAY, run_id="R2")
    assert first.written == second.written


def test_재계산_구간이_적재_범위로_넘어간다():
    """삭제 범위가 W 와 같아야 병합으로 사라져야 할 행이 실제로 사라진다 ([07 §7])."""
    sink = FakeSink(rising_series(), sources={1: 2})
    batch.run(sink, thresholds(recompute_window_days=7), today=TODAY, run_id="R1")
    window = history_window(D, 7)
    assert sink.written["history_window"] == (window.start_ts, window.end_ts)


def test_승격된_키워드가_없으면_아무것도_쓰지_않는다():
    """`keywords` 가 비어 있는 것이 지금의 선행 차단이다 ([10 §7.5])."""
    sink = FakeSink([])
    result = batch.run(sink, thresholds(), today=TODAY, run_id="R1")
    assert (result.keywords, result.history_rows, result.metric_rows) == (0, 0, 0)
    assert sink.written is None


def test_dry_run_은_쓰지_않는다():
    sink = FakeSink(rising_series(), sources={1: 2})
    result = batch.run(sink, thresholds(), today=TODAY, run_id="R1", dry_run=True)
    assert sink.written is None
    assert result.metric_rows == 1


def test_기간_지표의_구간이_백엔드_조회와_같다():
    sink = FakeSink(rising_series(), sources={1: 2})
    batch.run(sink, thresholds(), today=TODAY, run_id="R1")
    row = sink.written["metrics"][0]
    window = current_window("24H", D)
    assert (row[2], row[3]) == (window.start_ts, window.end_ts)


# --- 무정보어 제거 (z-score 의 분모) ----------------------------------------


def volume_rows(daily_docs: dict[date, int]) -> dict[tuple[str, date], int]:
    return {("fashion", day): total for day, total in daily_docs.items()}


def test_코퍼스가_커진_것을_급증으로_보지_않는다():
    """`요즘` 처럼 늘 일정한 몫으로 나오는 말. 문서량이 열 배가 되어도 z 는 0 근처다.

    2026-09-09 실데이터에서 발행일별 문서량이 6월 하루 1~2건 → 9월 첫 주 10~50건이었다.
    원자료를 그대로 배경과 견주면 최근 구간의 **거의 모든 키워드**가 함께 튄다.
    """
    background = {D - timedelta(days=offset): 10 for offset in range(2, 32)}
    volume = volume_rows({**background, D: 100})
    series = Series(1, "fashion", {**{day: 1 for day in background}, D: 10})

    from trendin.spark.metrics.trends import zscore
    from trendin.spark.metrics.windows import background_window, current_window

    current = current_window("24H", D)
    back = background_window("24H", D, 30)
    assert abs(zscore(series.rate(current, volume), series.rates(back, volume), min_days=10)) < 0.5


def test_몫이_실제로_오른_말은_튄다():
    background = {D - timedelta(days=offset): 10 for offset in range(2, 32)}
    volume = volume_rows({**background, D: 100})
    series = Series(1, "fashion", {**{day: 1 for day in background}, D: 40})

    from trendin.spark.metrics.trends import zscore
    from trendin.spark.metrics.windows import background_window, current_window

    current = current_window("24H", D)
    back = background_window("24H", D, 30)
    assert zscore(series.rate(current, volume), series.rates(back, volume), min_days=10) > 2.0


def test_수집이_없던_날은_배경에서_뺀다():
    """0 으로 채우면 수집이 멈춘 구간이 배경을 끌어내려 그 뒤 아무 값이나 급증이 된다."""
    volume = volume_rows({D - timedelta(days=1): 10, D - timedelta(days=3): 10})
    series = Series(1, "fashion", {D - timedelta(days=1): 1, D - timedelta(days=3): 1})
    from trendin.spark.metrics.windows import Window

    window = Window(D - timedelta(days=4), D)
    assert series.rates(window, volume) == [0.1, 0.1]
