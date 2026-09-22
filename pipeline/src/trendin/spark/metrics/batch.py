"""[07] 의 단계 배선 — `aggregate` Job 의 본체.

```
1. 기준일 D        실행일(KST) − reference_day_offset. 완결된 마지막 날이다
2. 원자료 읽기      pl_keyword_daily_stat 을 지평만큼 한 번에. 승격된 키워드만
3. 날짜별 추이      활성 키워드 × 재계산 구간 W 의 버킷. 수집이 없던 날은 행을 만들지 않는다
4. 기간별 지표      현재·직전 구간 합 → 증가량·증가율 → (domain, period) 순위
5. 판별 근거        구간 소스 수 · 조용함 창 언급량 · 배경 대비 z
6. 트렌드 유형      CURRENT · RISING · NEW 를 기간별로. 그 기간의 지표 행에 함께 싣는다
7. 적재            두 표를 한 트랜잭션. 판별 이력은 따로
```

**Spark 를 쓰지 않는다.** `registry/batch.py` 와 같은 이유다 — 입력이 이미 접힌 내부
테이블이고([08 §3]), 집계는 PostgreSQL 이 인덱스로 한다. 승격된 키워드 × 지평(121일)이 이
규모에서 수만 행이라 그 사이에 셔플이 들 자리가 없다. `jobs/aggregate.py` 가 세션을 들고
있지만 이 단계는 쓰지 않고, 그래서 테스트가 세션 없이 돈다.

**한 번 읽고 파이썬에서 여러 번 접는다.** 기간이 셋이고 창이 넷(현재·직전·조용함·배경)이라
질의로 나누면 표를 열두 번 훑는다. 지평 하나로 읽어 `keyword_id → {날짜: 언급량}` 을 만들면
그 뒤 전부가 사전 조회다.

**pyspark 를 import 하지 않는다** ([09 §4] 층 1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from trendin.spark.common.logging import get_logger
from trendin.spark.io.metrics import MetricSink
from trendin.spark.io.stats import Stat
from trendin.spark.metrics import trends as trend_rules
from trendin.spark.metrics import windows as window_rules
from trendin.spark.metrics.concepts import ConceptRef, Grouping, build_grouping
from trendin.spark.metrics.growth import MetricRow, assign_ranks, build_row
from trendin.spark.metrics.thresholds import AggregateThresholds
from trendin.spark.metrics.trends import Evidence
from trendin.spark.metrics.windows import Window

log = get_logger(__name__)

ONE_DAY = timedelta(days=1)
ONE_HOUR = timedelta(hours=1)

# --- 분포 모니터링 지표. **값이 곧 집계 키다** — 바꾸면 옛 실행과 이어지지 않는다. --------
KEYWORDS = "aggregate_keywords"  # 원자료에 언급이 있던 정규 키워드 수
HISTORY_ROWS = "history_rows"  # 쓴 버킷 행 수
HISTORY_GAPS = "history_gaps"  # 수집이 없어 건너뛴 (도메인, 날짜)
METRIC_ROWS = "metric_rows"  # 차원: 기간
# 차원: `기간:유형`. **옛 실행과 이어지지 않는다** — 배지가 `keyword_metrics` 로 옮겨오기
# 전에는 기간을 합친 뒤 세어서 차원이 유형 이름뿐이었다. 세는 대상이 키워드에서
# (키워드, 기간) 으로 바뀌었으므로 같은 키로 두면 값이 조용히 뛴 것처럼 보인다.
TREND_TYPES = "trend_types"
ZSCORE_BLOCKED = "zscore_blocked"  # z 하한에 걸려 RISING 에서 빠진 수 — 무정보어 제거의 효과
CONCEPT_FOLDED = "concept_folded"  # 개념으로 접힌 표기 수 — 순위표에서 되찾은 자리
CONCEPT_SILENCED = "concept_silenced"  # countable=false 로 순위에서 뺀 키워드 수


@dataclass
class Series:
    """한 키워드의 일별 언급량. `domain` 은 순위 범위라 함께 든다 ([07 §5])."""

    keyword_id: int
    domain: str
    daily: dict[date, int] = field(default_factory=dict)

    def total(self, window: Window) -> int:
        return sum(count for day, count in self.daily.items() if window.contains(day))

    def rates(self, window: Window, volume: dict[tuple[str, date], int]) -> list[float]:
        """구간의 일별 **몫** — 그날 언급 총량에 대한 비율 ([07 §6]).

        **언급이 없던 날은 0 으로 채우고, 수집이 아예 없던 날은 뺀다.** 앞은 "조용했다" 는
        증거이고 뒤는 자료가 없는 것이라, 섞으면 수집이 멈춘 구간이 배경을 0 으로 끌어내려
        그 뒤 아무 값이나 급증으로 보이게 한다.

        배경에서 0 인 날 자체를 빼지는 않는다 — 빼면 "가끔 한 번씩 크게 뜨는 말" 의 평균이
        실제보다 높아져 급증이 묻힌다.
        """
        rows = []
        for day in window.dates():
            total = volume.get((self.domain, day), 0)
            if total <= 0:
                continue
            rows.append(self.daily.get(day, 0) / total)
        return rows

    def rate(self, window: Window, volume: dict[tuple[str, date], int]) -> float:
        """구간 전체의 몫 — 합을 합으로 나눈다. 일별 몫의 평균이 아니다.

        평균으로 내면 문서가 한 건뿐인 날의 몫(0 또는 1)이 문서가 쉰 건인 날과 같은 무게를
        갖는다. 기간을 하나의 큰 표본으로 보는 것이 맞다.
        """
        total = sum(
            count
            for (domain, day), count in volume.items()
            if domain == self.domain and window.contains(day)
        )
        return (self.total(window) / total) if total > 0 else 0.0


@dataclass(frozen=True, slots=True)
class AggregateResult:
    reference_day: date
    keywords: int
    history_rows: int
    metric_rows: int
    # 유형을 하나라도 받은 `(키워드, 기간)` 수. 같은 키워드가 기간마다 따로 세어진다.
    trend_verdicts: int
    stats: tuple[Stat, ...]


def load_series(sink: MetricSink, horizon: Window) -> dict[int, Series]:
    """원자료 한 번 읽기 → `keyword_id → Series`."""
    series: dict[int, Series] = {}
    for keyword_id, domain, stat_date, mentions in sink.daily_mentions(
        start=horizon.start_ts, end=horizon.end_ts
    ):
        found = series.get(int(keyword_id))
        if found is None:
            found = Series(int(keyword_id), str(domain))
            series[int(keyword_id)] = found
        found.daily[stat_date] = found.daily.get(stat_date, 0) + int(mentions)
    return series


def load_grouping(
    sink: MetricSink,
    series: dict[int, Series],
    thresholds: AggregateThresholds | None = None,
) -> Grouping:
    """개념 접기 규칙을 읽는다. 개념 표가 없으면 아무것도 접지 않는 규칙이 나온다.

    대표를 고르는 무게로 **지평 전체의 언급량**을 쓴다 (`concepts.build_grouping` 의 주석).
    기간별 언급량이 아니라 한 번 정한 값이라, 같은 개념이 `24H` 와 `30D` 에서 다른 이름으로
    나오지 않는다.

    `aggregate.concepts.fold` 가 꺼져 있으면 조회조차 하지 않는다 — 끈 사람이 기대하는 것은
    "표기 단위로 돌던 때 그대로" 이고, 그때 개념 표를 읽을 이유가 없다.
    """
    fold = thresholds is None or thresholds.fold_concepts
    drop = thresholds is None or thresholds.drop_uncountable
    if not fold and not drop:
        return Grouping(representative={}, silenced=frozenset())
    
    refs = [
        ConceptRef(keyword_id, concept_id, countable if drop else True)
        for keyword_id, concept_id, countable in sink.concept_groups()
    ]
    # 개념이 아직 없지만 세지 않기로 판정된 표기. 판정 기록을 순위에 반영하는 자리다.
    silenced_keywords = sink.silenced_expressions() if drop else frozenset()
    if not fold:
        # 세지 않을 개념만 가려내고 접지는 않는다. 같은 개념의 두 표기를 서로 다른 개념
        # 번호로 흩어 놓으면 `build_grouping` 이 묶을 짝을 못 찾는다.
        refs = [ref for ref in refs if not ref.countable]
    weights = {
        keyword_id: sum(item.daily.values()) for keyword_id, item in series.items()
    }
    return build_grouping(
        refs, weights, keywords=set(series), silenced_keywords=silenced_keywords
    )


def fold_series(
    series: dict[int, Series], grouping: Grouping
) -> tuple[dict[int, Series], dict[int, Series]]:
    """개념으로 접는다 → `(세는 것, 접혀 들어간 것)`.

    **접는 자리가 여기인 이유** — 뒤따르는 전부(지표·이력·조용함 창·배경 z)가 `Series` 하나만
    보므로, 여기서 한 번 합치면 그 모두가 저절로 개념 단위가 된다. 단계마다 따로 접으면
    같은 규칙을 네 곳에 적게 되고, 그중 하나를 고치지 않는 날 지표와 그래프가 어긋난다.

    **접혀 들어간 쪽도 돌려준다.** 지표 행과 이력은 그대로 만들어야 하기 때문이다 —
    `청바지` 로 들어온 사용자가 자기 숫자와 그래프를 봐야 하고, 없애면 `keyword_contents` ·
    `keyword_relations` 가 가리키는 키워드에 지표만 비는 상태가 된다. 순위와 배지만 주지
    않는다 (`metric_rows` 의 `ranked` 인자).
    """
    counted: dict[int, Series] = {}
    absorbed: dict[int, Series] = {}
    # **원본을 복사해서 담는다.** 대표의 `Series` 에 그대로 더하면 흡수분이 원본에 섞이고,
    # 그 원본을 다시 읽는 곳(흡수된 쪽의 지표 행)이 부풀려진 값을 보게 된다.
    for keyword_id, item in series.items():
        if keyword_id in grouping.representative:
            absorbed[keyword_id] = item
        else:
            counted[keyword_id] = Series(keyword_id, item.domain, dict(item.daily))

    for keyword_id, item in absorbed.items():
        leader = grouping.representative[keyword_id]
        into = counted.get(leader)
        if into is None:
            # `build_grouping` 이 원자료가 있는 키워드만 대표로 뽑으므로 여기 오지 않는다.
            # 그래도 두는 것은 `series` 와 `grouping` 이 따로 들어오기 때문이다 — 어긋나면
            # 그 개념이 통째로 순위에서 사라지는데, 그 증상은 조용하다.
            into = Series(leader, item.domain)
            counted[leader] = into
        for day, count in item.daily.items():
            into.daily[day] = into.daily.get(day, 0) + count
    return counted, absorbed


def fold_sources(
    sources: dict[int, set[str]], grouping: Grouping
) -> dict[int, int]:
    """소스 집합을 개념으로 합치고 센다.

    **합집합이지 합이 아니다.** 같은 매체가 `가죽` 과 `leather` 를 함께 썼으면 소스 하나다.
    각자의 수를 더하면 한 매체가 여러 표기를 쓴 것만으로 "서로 다른 소스 2곳" 조건
    (`MIN_SOURCES`)을 통과하게 되는데, 그 조건이 막으려는 것이 정확히 그 형태다 ([07 §8]).
    """
    merged: dict[int, set[str]] = {}
    for keyword_id, found in sources.items():
        leader = grouping.representative.get(keyword_id, keyword_id)
        merged.setdefault(leader, set()).update(found)
    return {keyword_id: len(found) for keyword_id, found in merged.items()}


def history_rows(
    series: dict[int, Series],
    *,
    window: Window,
    active_window: Window,
    covered: set[tuple[str, date]],
) -> tuple[list[tuple], int]:
    """`keyword_metric_history` 에 쓸 버킷 행 ([07 §3]).

    **행의 유무가 "0" 과 "데이터 없음" 을 가른다.** 수집이 정상이고 언급이 없던 날은
    `mention_count = 0` 이고, 그 도메인의 문서가 하나도 없던 날은 **행 자체가 없다** — 프론트가
    그래프의 구멍으로 그린다.

    **0 행을 모든 키워드에 쓰지는 않는다.** 정규 키워드 전체 × W 를 매 실행 갱신하면 대부분이
    0 인 행을 대량으로 쓰게 된다. 최근 `active_window` 안에 한 번이라도 언급이 있었던
    키워드로 좁히면 행 수가 활성 키워드 × W 로 유지되고, 그 밖의 키워드는 애초에 그래프에
    그릴 것이 없어 행이 없는 것과 0 인 것이 화면에서 같다.
    """
    rows: list[tuple] = []
    gaps = 0
    days = window.dates()
    for series_item in series.values():
        if series_item.total(active_window) <= 0:
            continue
        for day in days:
            if (series_item.domain, day) not in covered:
                continue
            rows.append(
                (
                    series_item.keyword_id,
                    window_rules.midnight(day),
                    window_rules.midnight(day + ONE_DAY),
                    series_item.daily.get(day, 0),
                )
            )
    for domain in {item.domain for item in series.values()}:
        gaps += sum(1 for day in days if (domain, day) not in covered)
    return rows, gaps


def hourly_history_rows(
    hourly: tuple[tuple, ...], grouping: Grouping | None = None
) -> list[tuple]:
    """`keyword_metric_history` 에 쓸 **시간** 버킷 행 ([07 §3], `history_bucket: 1H`).

    일 버킷과 달리 **0 행을 만들지 않는다.** 언급이 있는 시간만 쓴다.

    일 버킷은 "행이 없음" 과 "0" 을 가르려고 수집이 있었던 날에 0 행을 깔았는데, 시간 단위로
    그러면 활성 키워드 × 720 칸이 거의 다 0 인 행이 된다. 그리고 백엔드가 버킷을 스스로
    세우고 저장 행이 없는 칸을 0 으로 그리므로(`TrendHistoryService.getHistory`) 화면에
    나타나는 결과가 같다 — 그 구분은 지금 백엔드에서 실현되지 않는다.

    **한 회차에 두 폭을 섞지 않는다.** 같은 날에 일 행과 시간 행이 함께 있으면 백엔드의
    합산이 그 날을 두 번 센다. `MetricSink.write` 의 DELETE 가 재계산 구간에서 스테이징에
    없는 행을 걷어내므로, 폭을 바꾼 첫 회차에 옛 일 행이 사라진다.

    **개념 접기를 여기서 한 번 더 한다.** 이 경로만 `Series` 를 거치지 않고 SQL 에서 바로
    오므로, `fold_series` 가 접어 둔 것이 닿지 않는다. 접지 않으면 대표의 지표는 합산인데
    그래프는 자기 것만 남아, 화면에서 "언급 426건" 아래 240건짜리 그래프가 그려진다.
    """
    buckets: dict[tuple[int, object], int] = {}
    for keyword_id, bucket_start, mentions in hourly:
        leader = int(keyword_id)
        if grouping is not None:
            leader = grouping.representative.get(leader, leader)
        key = (leader, bucket_start)
        buckets[key] = buckets.get(key, 0) + int(mentions)
        if leader != int(keyword_id):
            # 흡수된 표기도 자기 그래프를 갖는다 (`fold_series` 의 주석과 같은 이유).
            own = (int(keyword_id), bucket_start)
            buckets[own] = buckets.get(own, 0) + int(mentions)
    return [
        (keyword_id, bucket_start, bucket_start + ONE_HOUR, mentions)
        for (keyword_id, bucket_start), mentions in buckets.items()
    ]


def metric_rows(
    series: dict[int, Series], *, period: str, reference: date, ranked: bool = True
) -> list[MetricRow]:
    """`keyword_metrics` 에 쓸 행 ([07 §5]).

    **현재 구간 또는 직전 구간에 언급이 1 이상인 키워드만** 만든다. 직전만 있는 키워드를
    넣는 이유는 하락을 표현하기 위해서다 — 100 → 0 은 `growth_amount = −100` 이라는
    정보인데, 행을 안 만들면 화면에서 그냥 사라진다. 둘 다 0 이면 넣지 않는다. 넣어도 전부
    같은 값(0, 0, 0, `NULL`)이고 순위를 매길 수 없다.

    **`ranked = False` 는 "지표는 내되 순위표에는 올리지 않는다" 이다.** 개념으로 접혀 대표가
    따로 있는 표기와, `countable = false` 로 세지 않기로 한 개념이 그 대상이다
    (`metrics/concepts.py`). 행을 만드는 이유는 상세 화면과 관심 키워드가 그 숫자를 읽기
    때문이고, 순위를 비우는 이유는 같은 것이 순위표에 두 번 뜨지 않게 하기 위해서다.
    """
    current = window_rules.current_window(period, reference)
    previous = window_rules.previous_window(period, reference)
    rows = []
    for item in series.values():
        mentions = item.total(current)
        before = item.total(previous)
        if mentions == 0 and before == 0:
            continue
        rows.append(
            build_row(
                keyword_id=item.keyword_id,
                domain=item.domain,
                period=period,
                period_start=current.start,
                period_end=current.end,
                mention_count=mentions,
                previous_mention_count=before,
            )
        )
    if not ranked:
        # `build_row` 가 `mention_rank` 를 `None` 으로 두므로 비우는 손질이 따로 없다.
        # 정렬만 `assign_ranks` 와 맞춘다 — 적재 순서가 실행마다 흔들리지 않게.
        return sorted(rows, key=lambda row: (row.domain, row.period, -row.mention_count,
                                             row.keyword_id))
    return assign_ranks(rows)


def evidence_for(
    series: dict[int, Series],
    rows: list[MetricRow],
    *,
    period: str,
    reference: date,
    sources: dict[int, int],
    volume: dict[tuple[str, date], int],
    thresholds: AggregateThresholds,
) -> dict[tuple[int, str], Evidence]:
    """판별 근거 — 구간 소스 수 · 조용함 창 언급량 · 배경 대비 z ([07 §6])."""
    window = thresholds.new_windows.get(period)
    quiet = (
        window_rules.quiet_window(period, reference, window.quiet_days)
        if window is not None
        else None
    )
    background = window_rules.background_window(
        period, reference, thresholds.zscore.background_days
    )
    current = window_rules.current_window(period, reference)
    found: dict[tuple[int, str], Evidence] = {}
    for row in rows:
        item = series[row.keyword_id]
        found[(row.keyword_id, period)] = Evidence(
            sources=sources.get(row.keyword_id, 0),
            quiet_mentions=item.total(quiet) if quiet is not None else 0,
            zscore=trend_rules.zscore(
                item.rate(current, volume),
                item.rates(background, volume),
                min_days=thresholds.zscore.min_background_days,
            ),
        )
    return found


def zscore_blocked(
    rows: list[MetricRow],
    evidence: dict[tuple[int, str], Evidence],
    thresholds: AggregateThresholds,
) -> int:
    """z 하한이 없었다면 `RISING` 이었을 행의 수 — 무정보어 제거가 실제로 한 일.

    이 숫자가 0 이면 그 축이 놀고 있는 것이고, 그건 임계값이 틀렸다는 신호다 ([07 §6]).
    """
    blocked = 0
    for row in rows:
        found = evidence.get((row.keyword_id, row.period))
        if found is None or found.zscore is None:
            continue
        if found.zscore >= thresholds.zscore.min_z:
            continue
        loosened = Evidence(found.sources, found.quiet_mentions, None)
        if trend_rules.is_rising(row, loosened, thresholds.rising, thresholds.zscore):
            blocked += 1
    return blocked


# --- 실행 ------------------------------------------------------------------


def run(
    sink: MetricSink,
    thresholds: AggregateThresholds,
    *,
    today: date,
    run_id: str,
    prune_metrics: bool = True,
    dry_run: bool = False,
) -> AggregateResult:
    """[07] 전부를 한 번 돈다. `dry_run` 이면 계산만 하고 쓰지 않는다."""
    reference = window_rules.reference_day(today, thresholds.reference_day_offset)
    horizon = window_rules.Window(
        reference + timedelta(days=1 - thresholds.horizon_days()), reference + ONE_DAY
    )
    recompute = window_rules.history_window(reference, thresholds.recompute_window_days)
    active = window_rules.history_window(reference, thresholds.active_window_days)

    log.info(
        "기준일 D=%s · 재계산 [%s, %s) · 원자료 지평 [%s, %s)",
        reference,
        recompute.start,
        recompute.end,
        horizon.start,
        horizon.end,
    )

    series = load_series(sink, horizon)
    if not series:
        # 승격된 키워드가 없으면 여기서 끝난다. **조용히 0 을 쓰지 않는다** — `keywords` 가
        # 비어 있는 것이 지금의 선행 차단이고([10 §7.5]), 그걸 정상 완료로 보이게 하면
        # "트렌드가 하나도 안 나온다" 가 화면에서야 드러난다.
        log.warning(
            "원자료에 승격된 키워드가 없다 — pl_keyword_daily_stat.keyword_id 가 전부 NULL 이다. "
            "[05] 승격이 막혀 있으면 지표를 걸 대상이 없다 ([10 §7.5] 선행 차단)"
        )
        return AggregateResult(reference, 0, 0, 0, 0, (Stat(KEYWORDS, "", 0),))

    # 개념으로 접는다 ([개념층], `metrics/concepts.py`). **여기서 한 번 접으면 뒤따르는
    # 전부가 개념 단위가 된다** — 지표도 이력도 배경 z 도 `Series` 하나만 본다.
    grouping = load_grouping(sink, series, thresholds)
    counted, absorbed = fold_series(series, grouping)
    # `countable = false` 인 개념은 접지 않고 순위에서만 뺀다. 접혀 들어간 표기와 같은
    # 대접이라 한 자루에 담아 순위 없는 행으로 낸다.
    silent = {
        keyword_id: item
        for keyword_id, item in counted.items()
        if keyword_id in grouping.silenced
    }
    ranked_series = {
        keyword_id: item
        for keyword_id, item in counted.items()
        if keyword_id not in grouping.silenced
    }
    unranked_series = {**absorbed, **silent}
    if grouping.folded or silent:
        log.info(
            "개념 접기: 표기 %d개를 대표로 접고 %d개를 순위에서 뺐다 (세는 키워드 %d개)",
            grouping.folded,
            len(silent),
            len(ranked_series),
        )

    covered = {(str(domain), stat_date) for domain, stat_date in sink.covered_dates(
        start=horizon.start_ts, end=horizon.end_ts
    )}
    volume = {
        (str(domain), stat_date): int(total)
        for domain, stat_date, total in sink.daily_volume(
            start=horizon.start_ts, end=horizon.end_ts
        )
    }

    if thresholds.hourly_history:
        # 발행 시각은 `contents` 에만 남아 있다. 원자료(`pl_document_candidate`)의 보존
        # 지평 밖은 조인이 비어 돌아오므로, 그 구간의 버킷은 만들어지지 않는다 ([08 §3]).
        buckets = hourly_history_rows(
            sink.hourly_mentions(start=recompute.start_ts, end=recompute.end_ts),
            grouping,
        )
        gaps = 0
    else:
        # **접힌 것과 흡수된 것을 함께 넘긴다.** 대표는 합산 그래프를, 흡수된 표기는 자기
        # 그래프를 갖는다 — 대표만 쓰면 `청바지` 상세 화면의 그래프가 통째로 빈다.
        buckets, gaps = history_rows(
            {**counted, **absorbed},
            window=recompute,
            active_window=active,
            covered=covered,
        )

    staged_metrics: list[tuple] = []
    verdict: dict[tuple[int, str], tuple[str, ...]] = {}
    stats = [
        Stat(KEYWORDS, "", len(series)),
        Stat(HISTORY_ROWS, "", len(buckets)),
        Stat(HISTORY_GAPS, "", gaps),
    ]
    blocked = 0

    for period in thresholds.periods:
        rows = metric_rows(ranked_series, period=period, reference=reference)
        # 순위도 배지도 받지 않는 행. 지표만 그대로 낸다 (`metric_rows` 의 `ranked`).
        tail = metric_rows(
            unranked_series, period=period, reference=reference, ranked=False
        )
        current = window_rules.current_window(period, reference)
        sources = fold_sources(
            sink.period_sources(start=current.start_ts, end=current.end_ts), grouping
        )
        found = evidence_for(
            ranked_series,
            rows,
            period=period,
            reference=reference,
            sources=sources,
            volume=volume,
            thresholds=thresholds,
        )
        blocked += zscore_blocked(rows, found, thresholds)
        judged = trend_rules.judge(rows, found, thresholds)
        verdict.update(judged)
        # **유형을 못 받은 행에는 빈 배열이 실린다.** 그 값이 배지를 떼는 일까지 겸한다 —
        # 지표 행과 배지가 한 줄이라 "배지를 든 키워드를 따로 읽어 비우는" 단계가 없다
        # (`io/metrics.metrics_merge_sql`).
        staged_metrics.extend(
            (
                row.keyword_id,
                row.period,
                window_rules.midnight(row.period_start),
                window_rules.midnight(row.period_end),
                row.mention_count,
                row.previous_mention_count,
                row.growth_amount,
                row.growth_rate,
                row.mention_rank,
                list(judged.get((row.keyword_id, row.period), ())),
            )
            for row in rows
        )
        staged_metrics.extend(
            (
                row.keyword_id,
                row.period,
                window_rules.midnight(row.period_start),
                window_rules.midnight(row.period_end),
                row.mention_count,
                row.previous_mention_count,
                row.growth_amount,
                row.growth_rate,
                None,
                [],
            )
            for row in tail
        )
        stats.append(Stat(METRIC_ROWS, period, len(rows) + len(tail)))

    badged = sum(1 for types in verdict.values() if types)
    stats.append(Stat(ZSCORE_BLOCKED, "", blocked))
    stats.append(Stat(CONCEPT_FOLDED, "", grouping.folded))
    stats.append(Stat(CONCEPT_SILENCED, "", len(silent)))
    for period in thresholds.periods:
        for name in trend_rules.TREND_TYPES:
            stats.append(
                Stat(
                    TREND_TYPES,
                    f"{period}:{name}",
                    sum(
                        1
                        for (_, scope), types in verdict.items()
                        if scope == period and name in types
                    ),
                )
            )

    if dry_run:
        log.warning("--dry-run: 계산만 하고 쓰지 않는다")
        return AggregateResult(
            reference, len(series), len(buckets), len(staged_metrics), badged, tuple(stats),
        )

    sink.write(
        history=buckets,
        metrics=staged_metrics,
        history_window=(recompute.start_ts, recompute.end_ts),
        prune_metrics=prune_metrics,
    )
    sink.log_verdict(
        [
            (run_id, keyword_id, period, list(types), reference.isoformat())
            for (keyword_id, period), types in verdict.items()
        ]
    )
    return AggregateResult(
        reference, len(series), len(buckets), len(staged_metrics), badged, tuple(stats),
    )
