"""[07] 의 단계 배선 — `aggregate` Job 의 본체.

```
1. 기준일 D        실행일(KST) − reference_day_offset. 완결된 마지막 날이다
2. 원자료 읽기      pl_keyword_daily_stat 을 지평만큼 한 번에. 승격된 키워드만
3. 날짜별 추이      활성 키워드 × 재계산 구간 W 의 버킷. 수집이 없던 날은 행을 만들지 않는다
4. 기간별 지표      현재·직전 구간 합 → 증가량·증가율 → (domain, period) 순위
5. 판별 근거        구간 소스 수 · 조용함 창 언급량 · 배경 대비 z
6. 트렌드 유형      CURRENT · RISING · NEW → 기간 통합 합집합
7. 적재            세 표를 한 트랜잭션. 판별 이력은 따로
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
TREND_TYPES = "trend_types"  # 차원: 유형
TRENDS_CLEARED = "trends_cleared"  # 이번에 배지를 뗀 키워드 수
ZSCORE_BLOCKED = "zscore_blocked"  # z 하한에 걸려 RISING 에서 빠진 수 — 무정보어 제거의 효과


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
    trend_rows: int
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


def hourly_history_rows(hourly: tuple[tuple, ...]) -> list[tuple]:
    """`keyword_metric_history` 에 쓸 **시간** 버킷 행 ([07 §3], `history_bucket: 1H`).

    일 버킷과 달리 **0 행을 만들지 않는다.** 언급이 있는 시간만 쓴다.

    일 버킷은 "행이 없음" 과 "0" 을 가르려고 수집이 있었던 날에 0 행을 깔았는데, 시간 단위로
    그러면 활성 키워드 × 720 칸이 거의 다 0 인 행이 된다. 그리고 백엔드가 버킷을 스스로
    세우고 저장 행이 없는 칸을 0 으로 그리므로(`TrendHistoryService.getHistory`) 화면에
    나타나는 결과가 같다 — 그 구분은 지금 백엔드에서 실현되지 않는다.

    **한 회차에 두 폭을 섞지 않는다.** 같은 날에 일 행과 시간 행이 함께 있으면 백엔드의
    합산이 그 날을 두 번 센다. `MetricSink.write` 의 DELETE 가 재계산 구간에서 스테이징에
    없는 행을 걷어내므로, 폭을 바꾼 첫 회차에 옛 일 행이 사라진다.
    """
    return [
        (keyword_id, bucket_start, bucket_start + ONE_HOUR, int(mentions))
        for keyword_id, bucket_start, mentions in hourly
    ]


def metric_rows(
    series: dict[int, Series], *, period: str, reference: date
) -> list[MetricRow]:
    """`keyword_metrics` 에 쓸 행 ([07 §5]).

    **현재 구간 또는 직전 구간에 언급이 1 이상인 키워드만** 만든다. 직전만 있는 키워드를
    넣는 이유는 하락을 표현하기 위해서다 — 100 → 0 은 `growth_amount = −100` 이라는
    정보인데, 행을 안 만들면 화면에서 그냥 사라진다. 둘 다 0 이면 넣지 않는다. 넣어도 전부
    같은 값(0, 0, 0, `NULL`)이고 순위를 매길 수 없다.
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
            sink.hourly_mentions(start=recompute.start_ts, end=recompute.end_ts)
        )
        gaps = 0
    else:
        buckets, gaps = history_rows(
            series, window=recompute, active_window=active, covered=covered
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
        rows = metric_rows(series, period=period, reference=reference)
        current = window_rules.current_window(period, reference)
        sources = sink.period_sources(start=current.start_ts, end=current.end_ts)
        found = evidence_for(
            series,
            rows,
            period=period,
            reference=reference,
            sources=sources,
            volume=volume,
            thresholds=thresholds,
        )
        blocked += zscore_blocked(rows, found, thresholds)
        verdict.update(trend_rules.judge(rows, found, thresholds))
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
            )
            for row in rows
        )
        stats.append(Stat(METRIC_ROWS, period, len(rows)))

    union = trend_rules.union_types(verdict)
    staged_trends, cleared = _trend_rows(sink, series, union, dry_run=dry_run)
    stats.append(Stat(TRENDS_CLEARED, "", cleared))
    stats.append(Stat(ZSCORE_BLOCKED, "", blocked))
    for name in trend_rules.TREND_TYPES:
        stats.append(
            Stat(TREND_TYPES, name, sum(1 for types in union.values() if name in types))
        )

    if dry_run:
        log.warning("--dry-run: 계산만 하고 쓰지 않는다")
        return AggregateResult(
            reference, len(series), len(buckets), len(staged_metrics), len(staged_trends),
            tuple(stats),
        )

    sink.write(
        history=buckets,
        metrics=staged_metrics,
        trends=staged_trends,
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
        reference, len(series), len(buckets), len(staged_metrics), len(staged_trends),
        tuple(stats),
    )


def _trend_rows(
    sink: MetricSink,
    series: dict[int, Series],
    union: dict[int, tuple[str, ...]],
    *,
    dry_run: bool,
) -> tuple[list[tuple], int]:
    """`trends` 스테이징 — 이번에 받은 유형 + **배지를 떼야 하는 키워드**.

    내려온 키워드를 빈 배열로 함께 올리지 않으면 배지가 영원히 남는다 ([07 §6]). 대상은 지금
    유형을 들고 있는 키워드 전부이고, 그 목록은 `trends` 에서 읽는다 — 이번 회차 지표에서
    아예 빠진 키워드(두 구간 다 0)까지 덮어야 하기 때문이다.
    """
    rows = [(keyword_id, list(types)) for keyword_id, types in sorted(union.items())]
    if dry_run:
        return rows, 0
    standing = sink.trending_keywords()
    cleared = sorted(standing - set(union))
    rows.extend((keyword_id, []) for keyword_id in cleared)
    return rows, len(cleared)
