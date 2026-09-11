"""구간 경계 — 기준일 D 와 반열린 구간 ([07 §4]).

**`period_start` 는 포함, `period_end` 는 제외한다.** 두 값 다 KST 자정이다. 닫힌 구간으로
두면 `period_end` 를 `23:59:59` 로 쓸지 `24:00:00` 으로 쓸지가 매번 문제가 되고, 그 한 초에
발행된 문서가 어느 구간에도 안 들어가거나 두 구간에 들어간다.

**⚠️ 이 파일의 값이 백엔드와 한 자리라도 어긋나면 목록이 통째로 빈다.**
`backend/.../AnalysisWindow.completed` 가 같은 구간을 **독립으로** 계산하고,
`KeywordMetricRepository` 가 `period_start = :startAt AND period_end = :endAt` 로 **등호**
조회를 한다. 우리가 쓰는 값과 백엔드가 계산하는 값이 같아야 하는 것이 조건이고, 그래서
아래 대응이 회귀 시험의 대상이다 (`tests/unit/test_metrics_windows.py`).

| | 백엔드 | 여기 |
| --- | --- | --- |
| 현재 구간 끝 | `recentEnd` = **오늘 KST 자정** | `D + 1` (D = 오늘 − `reference_day_offset`) |
| 현재 구간 시작 | `recentEnd − 기간` | `D + 1 − 기간` |
| 직전 구간 | `[recentStart − 기간, recentStart)` | 같음 |

`reference_day_offset: 1` 이 그 일치를 준다. 0 으로 두면 우리 구간이 하루 앞서 백엔드 조회가
빈 목록을 받는다 — 값이 틀린 것이 아니라 **아무것도 안 나오는** 증상으로 나타난다.

**pyspark 를 import 하지 않는다** ([09 §4] 층 1).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

# 기간 이름 → 일수. 값 규약은 백엔드 `AnalysisPeriod` 의 `@EnumeratedValue` 와 같다 ([07 §4]).
PERIOD_DAYS: dict[str, int] = {"24H": 1, "7D": 7, "30D": 30}

# KST. 원자료의 `stat_date` 가 이 시간대의 날짜다 ([07 §2]).
KST_OFFSET = "+09:00"

# 버킷 폭 — 지금은 하루뿐이다 ([07 §3]). 시간 버킷을 섞으려면 원자료를 시간 단위로 세워야 한다.
HISTORY_BUCKET_DAYS = 1


class WindowError(ValueError):
    """기간 이름을 모르거나 구간이 뒤집혔다."""


@dataclass(frozen=True, slots=True)
class Window:
    """반열린 날짜 구간 `[start, end)`. 둘 다 KST 날짜다."""

    start: date
    end: date

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise WindowError(f"구간이 뒤집혔다: [{self.start}, {self.end})")

    @property
    def days(self) -> int:
        return (self.end - self.start).days

    def contains(self, day: date) -> bool:
        return self.start <= day < self.end

    def dates(self) -> list[date]:
        return [self.start + timedelta(days=offset) for offset in range(self.days)]

    @property
    def start_ts(self) -> str:
        return midnight(self.start)

    @property
    def end_ts(self) -> str:
        return midnight(self.end)


def midnight(day: date) -> str:
    """그 날짜의 KST 자정. 오프셋을 붙여 세션 시간대에 의존하지 않는다 ([08 §4])."""
    return f"{day.isoformat()} 00:00:00{KST_OFFSET}"


def timedelta_days(count: int) -> timedelta:
    """부른 쪽이 `datetime` 을 import 하지 않게 둔다 — 날짜 산술의 출처를 한 곳으로 모은다."""
    return timedelta(days=count)


def period_days(period: str) -> int:
    try:
        return PERIOD_DAYS[period]
    except KeyError:
        raise WindowError(
            f"모르는 기간이다: {period!r} — 아는 것은 {', '.join(PERIOD_DAYS)}"
        ) from None


def reference_day(today: date, offset: int) -> date:
    """D = KST 로 완결된 마지막 날. 기본은 실행일의 전날이다 ([07 §4])."""
    if offset < 0:
        raise WindowError(f"reference_day_offset 은 음수일 수 없다: {offset}")
    return today - timedelta(days=offset)


def current_window(period: str, reference: date) -> Window:
    """`24H` → `[D, D+1)` · `7D` → `[D−6, D+1)` · `30D` → `[D−29, D+1)` ([07 §4])."""
    end = reference + timedelta(days=1)
    return Window(end - timedelta(days=period_days(period)), end)


def previous_window(period: str, reference: date) -> Window:
    """현재 구간과 **길이가 같고 바로 앞에 붙는다.** 겹치지 않는다 ([07 §4])."""
    current = current_window(period, reference)
    return Window(current.start - timedelta(days=current.days), current.start)


def quiet_window(period: str, reference: date, quiet_days: int) -> Window:
    """`NEW` 가 "조용했나" 를 보는 창 — 현재 구간 **바로 앞**의 N일 ([07 §6]).

    직전 구간(`previous_window`)과 다르다. `24H` 의 직전 7일은 `[D−7, D)` 이고 직전 구간은
    `[D−1, D)` 다. `NEW` 만 자기 조건에 쓰는 별도 창이라 함수를 따로 둔다.
    """
    if quiet_days <= 0:
        raise WindowError(f"quiet_days 는 1 이상이어야 한다: {quiet_days}")
    current = current_window(period, reference)
    return Window(current.start - timedelta(days=quiet_days), current.start)


def background_window(period: str, reference: date, background_days: int) -> Window:
    """z-score 의 배경 구간 — 현재 구간 **앞쪽만** 본다 ([07 §6]).

    현재를 배경에 넣으면 자기 자신과 비교하게 되어 급증이 스스로를 희석한다.
    """
    if background_days <= 0:
        raise WindowError(f"background_days 는 1 이상이어야 한다: {background_days}")
    current = current_window(period, reference)
    return Window(current.start - timedelta(days=background_days), current.start)


def history_window(reference: date, recompute_window_days: int) -> Window:
    """다시 쓸 버킷 구간 `[D−W+1, D+1)` ([07 §2]·[07 §7]).

    삭제·갱신 범위가 소급 재계산 구간 W 와 **같아야** 병합·임계값 변경으로 사라져야 할 행이
    실제로 사라진다.
    """
    if recompute_window_days <= 0:
        raise WindowError(f"recompute_window_days 는 1 이상이어야 한다: {recompute_window_days}")
    end = reference + timedelta(days=1)
    return Window(end - timedelta(days=recompute_window_days), end)


def horizon(reference: date, windows: list[Window]) -> Window:
    """원자료를 어디까지 읽어야 하는지 — 필요한 창 전부를 덮는 하나의 구간.

    질의를 한 번으로 끝내려고 둔다. `30D`·`NEW` 가 120일(30 + 90)을 요구하므로([07 §6])
    이 값이 곧 `pl_keyword_daily_stat` 보존 지평의 하한이다 ([08 §3]).
    """
    if not windows:
        raise WindowError("덮을 구간이 없다")
    return Window(min(window.start for window in windows), max(window.end for window in windows))
