"""[07] 의 임계값 — `conf/*.yaml` 의 `aggregate` 구역.

`extract/thresholds.py` · `registry/thresholds.py` 와 같은 규약이다. **비어 있으면 Job 이
거부한다.** 근거 없는 문턱으로 서비스 테이블에 트렌드 배지를 다는 것보다 시작을 거부하는 것이
싸다 — 잘못 붙은 배지는 화면에 바로 나가고, 지우려면 어느 회차가 붙였는지부터 찾아야 한다.

`base.yaml` 이 측정이 필요한 값을 `null` 로 두고, `local.yaml` 이 목록을 실제로 뽑아 볼
잠정값을 채운다. 확정은 뽑힌 목록을 보고 `base.yaml` 로 옮기는 일이다 ([07 §6] "초기 규칙으로
먼저 내보내고, 실제 목록을 보고 정한다").

**`recompute_window_days` 만 사정이 다르다.** 이건 알고리즘 문턱이 아니라 실측값이고
([07 §2]), 2026-09-10 에 재서 `base.yaml` 에 30 으로 박았다
(`tests/fixtures/review/publish-lag-2026-09-10.md`). 그래도 `REQUIRED` 에 남겨 둔다 —
누군가 지우면 재계산이 그날치만 돌고 어제 숫자가 영원히 틀린 채 남는데, 그 증상은 조용하다.

**pyspark 를 import 하지 않는다** ([09 §4] 층 1).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from trendin.spark.common.config import Config, ConfigError
from trendin.spark.metrics.windows import HISTORY_BUCKET_DAYS, PERIOD_DAYS

SECTION = "aggregate"

# [07 §6] 이 못 박은 값 — `NEW`·`RISING` 은 서로 다른 소스가 둘 이상이어야 한다.
# **설정으로 낮추지 않는다.** 측정으로 정할 값이 아니라 규격의 일부라 `registry.MIN_SOURCES`
# 와 같은 자리에 둔다. 이게 "한 매체에서만 쏟아진 키워드" 를 막는 유일한 조건이다.
MIN_SOURCES = 2

# 지원하는 버킷 폭. 목록에 없는 값은 거부한다 — 조용히 하루로 떨어뜨리면 설정에 적어 둔
# 것과 다른 것을 받게 된다 ([07 §3]).
#
# `1H` 는 백엔드가 `24H` 화면에 요구하는 폭이다 (`AnalysisPeriod.getHistoryBucketDuration`).
# 일 버킷만 쓰면 하루치가 첫 한 시간에 몰리고 나머지 23칸이 0 으로 그려진다. 원자료
# (`pl_keyword_daily_stat`)에는 시각이 없지만 `contents.published_at` 에 남아 있어, 문서를
# 거쳐 되살린다 (`io/metrics.HOURLY_SQL`).
BUCKET_DAY = "1D"
BUCKET_HOUR = "1H"
SUPPORTED_HISTORY_BUCKETS = (BUCKET_DAY, BUCKET_HOUR)

# 측정 없이 정할 수 없어 `base.yaml` 이 `null` 로 두는 키. 전부 있어야 시작한다.
REQUIRED = (
    "recompute_window_days",
    "thresholds.rising.min_growth_amount",
    "thresholds.rising.min_growth_rate",
    "thresholds.rising.min_mention_count",
    "thresholds.zscore.background_days",
    "thresholds.zscore.min_background_days",
    "thresholds.zscore.min_z",
)

# `NEW` 창은 **계산하는 기간마다** 요구한다. `periods` 에서 뺀 기간의 값까지 채우게 하면
# 쓰지도 않는 숫자를 짓게 된다 (`registry` 의 `review.similarity_floor` 와 같은 이유).
NEW_WINDOW_KEYS = ("quiet_days", "quiet_max", "min_mentions")


@dataclass(frozen=True, slots=True)
class NewWindow:
    """`NEW` 판별의 기간별 창 ([07 §6]) — 이전이 조용했고 최근이 시끄럽다."""

    # 현재 구간 **바로 앞**의 며칠을 보는가. `24H` 는 7, `30D` 는 90 이다.
    quiet_days: int
    # 그 창의 언급량이 이 값 이하면 "조용했다".
    quiet_max: int
    # 현재 구간의 언급량이 이 값 이상이어야 "시끄럽다".
    min_mentions: int


@dataclass(frozen=True, slots=True)
class RisingThresholds:
    """셋을 **함께** 넘어야 한다 ([07 §6])."""

    min_growth_amount: int  # A
    min_growth_rate: float  # B — 퍼센트
    # C. **없으면 급상승 목록이 전부 극소 표본이 된다** — 1건 → 3건이 200% 다.
    min_mention_count: int
    top_n: int


@dataclass(frozen=True, slots=True)
class ZScoreThresholds:
    """무정보어 자동 제외 ([07 §6]) — 자기 과거를 배경으로 놓으면 늘 흔한 말은 z ≈ 0 이다."""

    background_days: int
    # 배경 표본이 이보다 적으면 z 를 내지 않고 **통과시킨다.** 갓 뜬 키워드는 배경이 없는
    # 것이지 흔한 것이 아니다 — 여기서 막으면 `NEW` 와 `RISING` 이 겹치는 키워드가 사라진다.
    min_background_days: int
    min_z: float


@dataclass(frozen=True, slots=True)
class AggregateThresholds:
    """[07] 의 숫자 전부. 재확정이 파일 하나를 고치는 일이어야 해서 한 곳에 모은다."""

    periods: tuple[str, ...]
    reference_day_offset: int
    recompute_window_days: int
    # 0 행을 쓸 대상 ([07 §3]) — 최근 이 며칠 안에 한 번이라도 언급이 있었던 키워드.
    active_window_days: int
    current_top_n: int
    rising: RisingThresholds
    new_windows: dict[str, NewWindow]
    new_top_n: int
    zscore: ZScoreThresholds
    # [07 §8] 저자당 일별 기여 상한. `None` = 꺼짐. **켜려면 원자료 재집계가 선행이다** —
    # `pl_keyword_daily_stat` 에 저자별 건수가 없어 지금은 적용할 근거가 없다.
    author_daily_cap: int | None
    # `keyword_metric_history` 의 버킷 폭. `1D` 또는 `1H` ([07 §3]).
    history_bucket: str = BUCKET_DAY

    @property
    def hourly_history(self) -> bool:
        return self.history_bucket == BUCKET_HOUR

    @classmethod
    def from_config(cls, config: Config) -> "AggregateThresholds":
        section = config.section(SECTION)
        missing = [key for key in REQUIRED if _lookup(section, key) is None]

        periods = tuple(section.get("periods") or ())
        if not periods:
            raise ConfigError("aggregate.periods 가 비어 있다 — 계산할 기간이 없다")
        unknown = [period for period in periods if period not in PERIOD_DAYS]
        if unknown:
            raise ConfigError(
                f"aggregate.periods 에 모르는 기간이 있다: {', '.join(unknown)} — "
                f"아는 것은 {', '.join(PERIOD_DAYS)}"
            )

        bucket = str(section.get("history_bucket", BUCKET_DAY))
        if bucket not in SUPPORTED_HISTORY_BUCKETS:
            raise ConfigError(
                f"aggregate.history_bucket 은 {', '.join(SUPPORTED_HISTORY_BUCKETS)} 만 "
                f"지원한다 (지금 {bucket!r})"
            )

        windows_config = _lookup(section, "thresholds.new.windows") or {}
        new_windows: dict[str, NewWindow] = {}
        for period in periods:
            window = windows_config.get(period) or {}
            absent = [key for key in NEW_WINDOW_KEYS if window.get(key) is None]
            missing.extend(f"thresholds.new.windows.{period}.{key}" for key in absent)
            if not absent:
                new_windows[period] = NewWindow(
                    quiet_days=int(window["quiet_days"]),
                    quiet_max=int(window["quiet_max"]),
                    min_mentions=int(window["min_mentions"]),
                )

        if missing:
            raise ConfigError(
                "aggregate 임계값이 비어 있다 — 목록을 실제로 뽑아 보기 전이면 local.yaml 의 "
                "잠정값으로 돌린다 ([07 §6]): "
                + ", ".join(f"aggregate.{key}" for key in missing)
            )

        thresholds = section.get("thresholds") or {}
        rising = thresholds.get("rising") or {}
        zscore = thresholds.get("zscore") or {}
        current = thresholds.get("current") or {}
        cap = thresholds.get("author_daily_cap")
        return cls(
            periods=periods,
            reference_day_offset=int(section.get("reference_day_offset", 1)),
            recompute_window_days=int(section["recompute_window_days"]),
            active_window_days=int(thresholds.get("active_window_days", 30)),
            current_top_n=int(current.get("top_n", 5)),
            rising=RisingThresholds(
                min_growth_amount=int(rising["min_growth_amount"]),
                min_growth_rate=float(rising["min_growth_rate"]),
                min_mention_count=int(rising["min_mention_count"]),
                top_n=int(rising.get("top_n", 5)),
            ),
            new_windows=new_windows,
            new_top_n=int((thresholds.get("new") or {}).get("top_n", 5)),
            zscore=ZScoreThresholds(
                background_days=int(zscore["background_days"]),
                min_background_days=int(zscore["min_background_days"]),
                min_z=float(zscore["min_z"]),
            ),
            author_daily_cap=None if cap is None else int(cap),
            history_bucket=bucket,
        )

    def horizon_days(self) -> int:
        """원자료를 며칠치 읽어야 하는지 — 가장 먼 창까지 ([07 §6] 의 표)."""
        needed = [self.recompute_window_days, self.active_window_days]
        for period in self.periods:
            days = PERIOD_DAYS[period]
            # 직전 구간은 현재 구간과 길이가 같고 바로 앞에 붙는다.
            needed.append(days * 2)
            window = self.new_windows.get(period)
            if window is not None:
                needed.append(days + window.quiet_days)
            needed.append(days + self.zscore.background_days)
        return max(needed) + HISTORY_BUCKET_DAYS


def _lookup(section: dict[str, Any], path: str) -> Any:
    node: Any = section
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node
