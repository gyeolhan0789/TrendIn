"""[07] 단계 배선 — 원자료에서 두 표의 행이 나오기까지.

**DB 없이 돈다.** `MetricSink` 자리에 가짜를 끼운다 — `aggregate` 는 Spark 도 쓰지 않으므로
([09 §4] 층 1) 이 시험이 배선 전체를 덮는다.
"""

from __future__ import annotations

from datetime import date, timedelta

from trendin.spark.metrics import batch
from trendin.spark.metrics.batch import Series
from trendin.spark.metrics.concepts import ConceptRef, build_grouping
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

    def __init__(self, daily, *, covered=None, sources=None, concepts=None):
        self.daily = daily
        self._covered = covered
        self._sources = sources or {}
        self._concepts = concepts or ()
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
        # 실제 싱크는 소스 **집합**을 준다 (`io/metrics.period_sources`). 시험은 개수로 쓰는
        # 편이 읽히므로 여기서 편다 — 이름이 다르기만 하면 되는 값이다.
        return {
            keyword_id: {f"source-{index}" for index in range(count)}
            for keyword_id, count in self._sources.items()
        }

    def concept_groups(self):
        """`(keyword_id, concept_id, countable)`. 기본은 비어 있다 — 개념 표 없음."""
        return tuple(self._concepts)

    def silenced_expressions(self):
        """세지 않기로 판정된 표기의 keyword_id. 기본은 비어 있다 — 판정 표 없음."""
        return frozenset(getattr(self, "_silenced", ()))

    def judged_keywords(self, categories):
        """이름 판정이 그 분류라고 한 keyword_id. `_judged` 는 `{keyword_id: 분류}`."""
        judged = getattr(self, "_judged", {})
        return frozenset(k for k, category in judged.items() if category in set(categories))

    def keyword_keys(self):
        """`(keyword_id, normalized_name)`. 기본은 비어 있다 — 연도·시즌 접기 없음."""
        return tuple(getattr(self, "_keys", ()))

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


# --- 개념 단위 순위 --------------------------------------------------------
#
# 같은 것의 다른 언어 표기가 순위표 자리를 나눠 갖는 문제와, 세지 않을 개념을 빼는 축.
# 규칙 자체는 `metrics/concepts.py` 가 갖고 여기서는 **배선**을 본다 — 접은 결과가 지표 ·
# 이력 · 소스 수 · 배지 넷 모두에 닿는지가 이 시험의 관심사다.

MENTION_COUNT = 4
MENTION_RANK = 8


def staged(sink, keyword_id: int) -> tuple | None:
    for row in sink.written["metrics"]:
        if row[0] == keyword_id:
            return row
    return None


def two_surfaces() -> list[tuple]:
    """같은 개념의 두 표기. 1 번이 크고 2 번이 작다 — 대표는 1 번이어야 한다."""
    rows = [daily(1, D, 9), daily(2, D, 4)]
    rows += [daily(1, days_before(offset), 1) for offset in range(1, 8)]
    rows += [daily(2, days_before(offset), 1) for offset in range(1, 8)]
    return rows


def test_같은_개념의_표기는_대표_하나로_접힌다():
    """`jeans`(9) 와 `청바지`(4) 가 한 자리를 쓴다. 대표의 언급량이 둘의 합이다."""
    sink = FakeSink(
        two_surfaces(),
        sources={1: 2, 2: 2},
        concepts=[(1, 100, True), (2, 100, True)],
    )
    batch.run(sink, thresholds(), today=TODAY, run_id="r1")

    assert staged(sink, 1)[MENTION_COUNT] == 13
    assert staged(sink, 1)[MENTION_RANK] == 1
    # 흡수된 쪽은 자기 숫자를 그대로 갖되 순위표에는 오르지 않는다.
    assert staged(sink, 2)[MENTION_COUNT] == 4
    assert staged(sink, 2)[MENTION_RANK] is None
    assert staged(sink, 2)[TREND_TYPES] == []


def test_흡수된_표기도_자기_그래프를_갖는다():
    """지표 행만 남기고 이력을 빼면 `청바지` 상세 화면의 그래프가 통째로 빈다."""
    sink = FakeSink(
        two_surfaces(),
        sources={1: 2, 2: 2},
        concepts=[(1, 100, True), (2, 100, True)],
    )
    batch.run(sink, thresholds(), today=TODAY, run_id="r1")

    graphed = {row[0] for row in sink.written["history"]}
    assert graphed == {1, 2}


def test_세지_않는_개념은_순위와_배지를_받지_않는다():
    """`countable = false` — `collection` · `Vogue` · 대명사가 여기 걸린다."""
    sink = FakeSink(
        rising_series(), sources={1: 2}, concepts=[(1, 200, False)]
    )
    batch.run(sink, thresholds(), today=TODAY, run_id="r1")

    assert staged(sink, 1)[MENTION_RANK] is None
    assert staged(sink, 1)[TREND_TYPES] == []
    # 지표 자체는 그대로 남는다 — 관심 키워드로 등록해 둔 사용자가 숫자를 읽는다.
    assert staged(sink, 1)[MENTION_COUNT] == 9


def test_세지_않는_개념은_접히지도_않는다():
    """접으면 흡수된 쪽의 지표가 대표로 옮겨 가 상세 화면이 빈다. 둘 다 혼자 남아야 한다."""
    sink = FakeSink(
        two_surfaces(),
        sources={1: 2, 2: 2},
        concepts=[(1, 100, False), (2, 100, False)],
    )
    batch.run(sink, thresholds(), today=TODAY, run_id="r1")

    assert staged(sink, 1)[MENTION_COUNT] == 9
    assert staged(sink, 2)[MENTION_COUNT] == 4


def test_두_개념에_걸린_표기는_접지_않는다():
    """`크리스찬 디올` 이 designer 이자 brand 다. 어느 쪽으로 합쳐도 틀린다."""
    sink = FakeSink(
        two_surfaces(),
        sources={1: 2, 2: 2},
        concepts=[(1, 100, True), (1, 101, True), (2, 100, True)],
    )
    batch.run(sink, thresholds(), today=TODAY, run_id="r1")

    assert staged(sink, 1)[MENTION_COUNT] == 9
    assert staged(sink, 2)[MENTION_COUNT] == 4
    assert staged(sink, 2)[MENTION_RANK] is not None


def test_개념_표가_없으면_옛_동작_그대로다():
    """개념 Job 을 안 돌린 환경. 접는 것은 개선이지 선행 조건이 아니다."""
    sink = FakeSink(two_surfaces(), sources={1: 2, 2: 2})
    batch.run(sink, thresholds(), today=TODAY, run_id="r1")

    assert staged(sink, 1)[MENTION_COUNT] == 9
    assert staged(sink, 1)[MENTION_RANK] == 1
    assert staged(sink, 2)[MENTION_RANK] == 2


def test_같은_매체가_두_표기를_썼으면_소스는_하나다():
    """각자의 수를 더하면 한 매체가 뿌린 것이 "서로 다른 소스 2곳" 을 통과한다 ([07 §8])."""
    grouping = build_grouping(
        [ConceptRef(1, 100, True), ConceptRef(2, 100, True)],
        {1: 9, 2: 4},
        keywords={1, 2},
    )
    folded = batch.fold_sources({1: {"vogue"}, 2: {"vogue"}}, grouping)

    assert folded == {1: 1}


def test_접기를_끄면_표기_단위로_돌아간다():
    """사전이 잘못 묶였을 때 되돌리는 길 (`aggregate.concepts.fold`)."""
    sink = FakeSink(
        two_surfaces(),
        sources={1: 2, 2: 2},
        concepts=[(1, 100, True), (2, 100, True)],
    )
    batch.run(sink, thresholds(fold_concepts=False), today=TODAY, run_id="r1")

    assert staged(sink, 1)[MENTION_COUNT] == 9
    assert staged(sink, 2)[MENTION_RANK] == 2


def test_접기를_꺼도_세지_않을_개념은_빠진다():
    """두 축이 따로 도는지 — 접기만 끄고 무정보어 제거는 남긴다."""
    sink = FakeSink(
        rising_series(), sources={1: 2}, concepts=[(1, 200, False)]
    )
    batch.run(sink, thresholds(fold_concepts=False), today=TODAY, run_id="r1")

    assert staged(sink, 1)[MENTION_RANK] is None
    assert staged(sink, 1)[TREND_TYPES] == []


def test_셋_다_끄면_옛_동작_그대로다():
    """끈 사람이 기대하는 것은 옛 동작 그대로다."""
    sink = FakeSink(
        two_surfaces(),
        sources={1: 2, 2: 2},
        concepts=[(1, 100, True), (2, 100, False)],
    )
    batch.run(
        sink,
        thresholds(fold_concepts=False, drop_uncountable=False, fold_editions=False),
        today=TODAY,
        run_id="r1",
    )

    assert staged(sink, 1)[MENTION_RANK] == 1
    assert staged(sink, 2)[MENTION_RANK] == 2


def test_개념이_없어도_세지_않기로_판정된_표기는_순위에서_빠진다():
    """`Vogue Italia` 처럼 개념이 아직 없는 표기는 `countable` 을 걸 자리가 없다.

    그래도 세지 않기로 **판정**됐으면 순위에서 빠져야 한다. 개념이 나중에 생기면 그쪽
    `countable=false` 가 이 일을 넘겨받는다.
    """
    sink = FakeSink(rising_series(), sources={1: 2})
    sink._silenced = {1}
    batch.run(sink, thresholds(), today=TODAY, run_id="r1")

    assert staged(sink, 1)[MENTION_RANK] is None
    assert staged(sink, 1)[TREND_TYPES] == []
    # 지표 자체는 남는다 — 세지 않는 개념과 같은 규약이다.
    assert staged(sink, 1)[MENTION_COUNT] == 9


# --- 연도·시즌 접기 (S15P21A102-385) -----------------------------------------


def vogue_world() -> list[tuple]:
    """2026-09-24 24H 순위 1~4위와 같은 모양. 그날만 몰렸고 앞의 7일은 하루 1건이다."""
    today = {1: 69, 2: 66, 3: 66, 4: 33, 5: 29}
    rows = [daily(keyword_id, D, count) for keyword_id, count in today.items()]
    rows += [
        daily(keyword_id, days_before(offset), 1)
        for keyword_id in today
        for offset in range(1, 8)
    ]
    return rows


VOGUE_KEYS = (
    (1, "vogue world"),
    (2, "vogue world 2026"),
    (3, "vogue world milano 2026"),
    (4, "vogue world milano"),
    (5, "gigi hadid"),
)


def test_연도만_다른_표기가_한_자리를_쓴다():
    """개념 사전에 아무것도 없어도 접힌다 — 개념 Job 을 안 돌린 환경에서도 돈다.
    행사인지 모르므로 이름은 무게로 고른다 — `Vogue World`(69) 가 대표다."""
    sink = FakeSink(vogue_world(), sources={keyword_id: 3 for keyword_id in range(1, 6)})
    sink._keys = VOGUE_KEYS
    batch.run(sink, thresholds(), today=TODAY, run_id="r1")

    # `Vogue World` + `Vogue World 2026` = 69 + 66
    assert staged(sink, 1)[MENTION_COUNT] == 135
    assert staged(sink, 1)[MENTION_RANK] == 1
    # `Vogue World Milano 2026` + `Vogue World: Milano` = 66 + 33
    assert staged(sink, 3)[MENTION_COUNT] == 99
    assert staged(sink, 3)[MENTION_RANK] == 2
    assert staged(sink, 5)[MENTION_RANK] == 3
    # 흡수된 표기는 자기 숫자를 갖되 순위에 오르지 않는다
    for absorbed in (2, 4):
        assert staged(sink, absorbed)[MENTION_RANK] is None
        assert staged(sink, absorbed)[TREND_TYPES] == []
    assert staged(sink, 2)[MENTION_COUNT] == 66


def test_행사_개념이면_최신_회차가_보이고_넷이_한_자리다():
    """2026-09-24 운영 DB 와 같은 모양 — `Vogue World 2026` 개념에 Milano 두 표기가 붙어 있다."""
    sink = FakeSink(
        vogue_world(),
        sources={keyword_id: 3 for keyword_id in range(1, 6)},
        concepts=[(keyword_id, 267300, True, "event") for keyword_id in (2, 3, 4)],
    )
    sink._keys = VOGUE_KEYS
    batch.run(sink, thresholds(), today=TODAY, run_id="r1")

    # 69 + 66 + 66 + 33
    assert staged(sink, 2)[MENTION_COUNT] == 234
    assert staged(sink, 2)[MENTION_RANK] == 1
    assert staged(sink, 5)[MENTION_RANK] == 2
    for absorbed in (1, 3, 4):
        assert staged(sink, absorbed)[MENTION_RANK] is None


def test_제외된_기준형이면_회차도_순위에서_빠진다():
    """2026-09-23 판정이 `vogue world` 를 뺐다. 회차가 그 판정을 우회해 1위로 돌아오면 안 된다."""
    sink = FakeSink(vogue_world(), sources={keyword_id: 3 for keyword_id in range(1, 6)})
    sink._keys = VOGUE_KEYS
    sink._silenced = {1}
    batch.run(sink, thresholds(), today=TODAY, run_id="r1")

    for silenced in (1, 2):
        assert staged(sink, silenced)[MENTION_RANK] is None
        assert staged(sink, silenced)[TREND_TYPES] == []
    assert staged(sink, 3)[MENTION_RANK] == 1


def test_연도_접기를_끄면_표기마다_따로_센다():
    """`aggregate.concepts.fold_editions` — 규칙이 틀렸을 때 되돌리는 길."""
    sink = FakeSink(vogue_world(), sources={keyword_id: 3 for keyword_id in range(1, 6)})
    sink._keys = VOGUE_KEYS
    batch.run(sink, thresholds(fold_editions=False), today=TODAY, run_id="r1")

    assert staged(sink, 1)[MENTION_COUNT] == 69
    assert [staged(sink, keyword_id)[MENTION_RANK] for keyword_id in range(1, 6)] == [
        1,
        2,
        3,
        4,
        5,
    ]


def test_숨길_분류의_개념은_순위에서_빠진다():
    """인물·행사는 순위에 내지 않는다 (`aggregate.concepts.hide_categories`)."""
    sink = FakeSink(
        two_surfaces(),
        sources={1: 2, 2: 2},
        concepts=[(1, 100, True, "event"), (2, 200, True, "brand")],
    )
    batch.run(sink, thresholds(hide_categories=frozenset({"person", "event"})), today=TODAY,
              run_id="r1")

    assert staged(sink, 1)[MENTION_RANK] is None
    assert staged(sink, 1)[MENTION_COUNT] == 9  # 지표 행은 남는다
    assert staged(sink, 2)[MENTION_RANK] == 1


def test_숨길_분류가_비면_분류로_거르지_않는다():
    sink = FakeSink(
        two_surfaces(), sources={1: 2, 2: 2}, concepts=[(1, 100, True, "event")]
    )
    batch.run(sink, thresholds(), today=TODAY, run_id="r1")

    assert staged(sink, 1)[MENTION_RANK] == 1


def test_접기를_다_꺼도_숨길_분류는_빠진다():
    sink = FakeSink(
        two_surfaces(), sources={1: 2, 2: 2}, concepts=[(1, 100, True, "person")]
    )
    batch.run(
        sink,
        thresholds(
            fold_concepts=False, drop_uncountable=False, fold_editions=False,
            hide_categories=frozenset({"person"}),
        ),
        today=TODAY,
        run_id="r1",
    )

    assert staged(sink, 1)[MENTION_RANK] is None
    assert staged(sink, 2)[MENTION_RANK] == 1


def test_개념에_없어도_이름_판정이_인물이면_빠진다():
    """`Zendaya` 는 개념에 `젠데이아` 만 있다 — 이름 판정 캐시의 분류로 뺀다."""
    sink = FakeSink(two_surfaces(), sources={1: 2, 2: 2})
    sink._judged = {1: "person", 2: "brand"}
    batch.run(sink, thresholds(hide_categories=frozenset({"person"})), today=TODAY, run_id="r1")

    assert staged(sink, 1)[MENTION_RANK] is None
    assert staged(sink, 2)[MENTION_RANK] == 1


def test_개념에_이어진_표기는_이름_판정보다_개념을_따른다():
    """`Tom Ford` 가 브랜드 개념에 붙어 있으면 판정이 인물이라 해도 센다."""
    sink = FakeSink(two_surfaces(), sources={1: 2, 2: 2}, concepts=[(1, 100, True, "brand")])
    sink._judged = {1: "person"}
    batch.run(sink, thresholds(hide_categories=frozenset({"person"})), today=TODAY, run_id="r1")

    assert staged(sink, 1)[MENTION_RANK] == 1


def test_hide_judged_를_끄면_이름_판정으로는_빼지_않는다():
    sink = FakeSink(two_surfaces(), sources={1: 2, 2: 2})
    sink._judged = {1: "person"}
    batch.run(
        sink,
        thresholds(hide_categories=frozenset({"person"}), hide_judged=False),
        today=TODAY,
        run_id="r1",
    )

    assert staged(sink, 1)[MENTION_RANK] == 1
