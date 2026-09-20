"""트렌드 유형 판별 — `CURRENT` · `RISING` · `NEW` ([07 §6]).

세 유형은 서로 다른 질문에 답한다. **배타적이지 않다** — `trend_types` 가 배열이므로 한
키워드가 `NEW` 이면서 `RISING` 일 수 있고, 새로 등장해서 빠르게 늘고 있는 키워드에 둘 다 붙는
것이 사실에 맞다. v1 은 우선순위를 두고 하나만 골랐는데 그 제약이 없어졌다.

**판별도 저장도 기간별이다.** `keyword_metrics.trend_types` 가 생기면서([08 §5] 티어 3)
`(keyword_id, period)` 판정이 모양 그대로 자리를 찾았다. 그전에는 `trend_types` 가 `trends` 에
있었고 그 표에 `period` 가 없어서, `union_types` 가 기간을 합쳐 실었다 — `24H` 에서만
`RISING` 인 키워드가 `30D` 목록에서도 배지를 다는 상태였다. 그 합집합은 걷어냈다.

**무정보어 제거를 이 파일이 맡는다** ([07 §6]). `요즘`·`매력` 처럼 이 코퍼스에서 늘 흔한 말은
**자기 과거를 배경으로 놓으면 z ≈ 0** 이다. 사전에 손으로 올리는 대신 이 축이 거른다 — 미리
사전에 박아 넣으면 `클래식` 이 실제로 급상승한 날에도 안 보인다.

**pyspark 를 import 하지 않는다** ([09 §4] 층 1).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from trendin.spark.metrics.growth import MetricRow
from trendin.spark.metrics.thresholds import (
    MIN_SOURCES,
    AggregateThresholds,
    NewWindow,
    RisingThresholds,
    ZScoreThresholds,
)

CURRENT = "CURRENT"
RISING = "RISING"
NEW = "NEW"

# 백엔드 `TrendType` enum 과 같은 값이어야 한다. 네이티브 enum 배열이라 없는 값을 보내면
# 캐스트에서 트랜잭션이 죽는다 ([08 §4], `io/metrics.py`).
#
# **이 순서가 곧 배열에 실리는 순서다** (`judge` 의 마지막 줄). 같은 내용인데 값의 차례만
# 뒤바뀌면 `IS DISTINCT FROM` 이 참이 되어 내용 없는 UPDATE 가 나간다.
TREND_TYPES = (CURRENT, RISING, NEW)


@dataclass(frozen=True, slots=True)
class Evidence:
    """한 키워드·한 기간의 판별 근거. 지표 밖에서 오는 값들이다."""

    # 현재 구간의 **서로 다른 소스 수**. 날짜별 `source_count` 를 더해서는 알 수 없어
    # `pl_document_candidate` 에서 구간 단위로 센다 (`io/metrics.py` 의 주석).
    sources: int
    # `NEW` 의 조용함 창 언급량 — 현재 구간 바로 앞 N일 ([07 §6]).
    quiet_mentions: int
    # 배경 대비 z. 배경 표본이 모자라면 `None` 이고, 그때는 **통과시킨다**.
    zscore: float | None


def zscore(current_rate: float, background: list[float], *, min_days: int) -> float | None:
    """배경 분포 대비 몇 표준편차인가. 표본이 모자라면 `None`.

    **값은 언급량이 아니라 그날 언급 총량에 대한 몫이다** (`io/metrics.DAILY_VOLUME_SQL`).
    원자료를 그대로 견주면 발행일별 문서량 변화가 z 를 지배한다 — 실측에서 6월은 하루 1~2건,
    9월 첫 주는 10~50건이었고, 그 위에서는 최근 구간의 거의 모든 키워드가 함께 튄다.

    **배경은 일별 값이고 언급이 0 인 날을 포함한다.** 언급이 없던 날을 빼면 "가끔 한 번씩 크게
    뜨는 말" 의 배경 평균이 실제보다 높아져 급증이 묻힌다. 다만 **수집이 아예 없던 날은 부른
    쪽이 뺀다** — 그건 조용했다는 증거가 아니라 자료가 없는 것이다.

    표준편차가 0 이면(배경이 전부 같은 값, 대개 전부 0) 나눌 수 없다. 현재가 그보다 크면
    `inf` 로 본다 — "배경에 전혀 없던 것이 나타났다" 는 z 가 무한대인 경우가 맞다.
    """
    if len(background) < min_days:
        return None
    mean = sum(background) / len(background)
    variance = sum((value - mean) ** 2 for value in background) / len(background)
    deviation = math.sqrt(variance)
    if deviation == 0:
        return math.inf if current_rate > mean else 0.0
    return (current_rate - mean) / deviation


def is_current(row: MetricRow, top_n: int) -> bool:
    """**선택 기간의 언급량 TOP 5** ([07 §6] 초기 규칙).

    `mention_rank` 가 이미 그 순위이므로 판별에 계산이 없다. 향후 규칙(고정 인기 키워드
    감점)이 들어오면 순위와 갈리지만, 저장 자리는 그때도 그대로다 ([07 §6]) — 판정이 기간별로
    실리므로 순위와 배지가 따로 놀아도 어느 기간의 판정인지가 남는다.
    """
    return row.mention_rank is not None and row.mention_rank <= top_n


def is_rising(row: MetricRow, evidence: Evidence, thresholds: RisingThresholds,
              zscore_thresholds: ZScoreThresholds) -> bool:
    """`growth_amount ≥ A AND growth_rate ≥ B AND mention_count ≥ C`, 그리고 두 겹 더.

    | 조건 | 막는 것 |
    | --- | --- |
    | 증가량 · 증가율 **둘 다** | 증가율만 보면 3→9(200%)가 500→700(40%)을 앞선다 |
    | `mention_count ≥ C` | 1건 → 3건이 200% 다. 하한이 없으면 목록이 극소 표본으로 찬다 |
    | 서로 다른 소스 ≥ 2 | **한 매체에서만 쏟아진 키워드** ([07 §8]) |
    | z ≥ 최소 | `요즘`·`매력` 처럼 늘 흔한 말 ([07 §6]) |

    `previous_mention_count = 0` 이면 `growth_rate` 가 `None` 이라 여기서 탈락한다. 그런
    키워드는 `NEW` 가 담당한다.
    """
    if row.growth_rate is None:
        return False
    if row.growth_amount < thresholds.min_growth_amount:
        return False
    if row.growth_rate < thresholds.min_growth_rate:
        return False
    if row.mention_count < thresholds.min_mention_count:
        return False
    if evidence.sources < MIN_SOURCES:
        return False
    # 배경이 모자라면 통과시킨다 — 갓 뜬 키워드는 배경이 없는 것이지 흔한 것이 아니다.
    return evidence.zscore is None or evidence.zscore >= zscore_thresholds.min_z


def is_new(row: MetricRow, evidence: Evidence, window: NewWindow) -> bool:
    """**이전이 충분히 조용했고 최근이 충분히 시끄럽다** ([07 §6]).

    `keywords.first_seen_at` 없이 성립한다. 언급량 이력으로 판별하는 것이 오히려 정확하다 —
    반년 전 한 번 스친 표기가 지금 새로 뜨는 것은 사용자에게 `NEW` 이고, v1 은 최초 관측이
    반년 전이라는 이유로 그걸 놓쳤다.

    **소스 조건이 여기서 가장 중요하다.** 자동 발견에서 "새로 뜨는 것" 목록은 노이즈가 가장
    먼저 도착하는 곳이다 — 오타·봇·일회성 문자열이 정의상 전부 "처음 보는 것" 이다.
    """
    if evidence.quiet_mentions > window.quiet_max:
        return False
    if row.mention_count < window.min_mentions:
        return False
    return evidence.sources >= MIN_SOURCES


def judge(
    rows: list[MetricRow],
    evidence: dict[tuple[int, str], Evidence],
    thresholds: AggregateThresholds,
) -> dict[tuple[int, str], tuple[str, ...]]:
    """기간별 판별. `(keyword_id, period)` → 받은 유형들.

    이 결과가 `keyword_metrics.trend_types` 에 기간별로 그대로 실린다 ([07 §6]). 기간을
    합치지 않으므로 `24H` 에서만 `RISING` 인 키워드가 `7D` 목록에서 배지를 달지 않는다.

    `RISING`·`NEW` 는 조건을 넘은 것 **중 상위 N 개**만 남긴다 ([07 §6]). 자르는 순서는
    백엔드 목록 정렬과 맞춘다 — `RISING` 은 증가율, `NEW` 는 언급량이다. 순서가 다르면
    우리가 고른 5개와 백엔드가 위에 보여주는 5개가 어긋난다.

    **돌려주는 배열의 차례를 `TREND_TYPES` 로 고정한다.** 판별 차례가 이미 그 순서지만,
    조건이 하나 더 붙는 날 조용히 어긋나는 것을 막으려고 마지막에 한 번 더 세운다.

    **세 유형이 같은 키워드 집합을 본다.** 개념 분류로 어느 한 유형에서만 빼는 일은 없다
    (`metrics/concepts.py` 머리말) — 순위에서 뺀 것(`silenced`)은 셋 모두에서 빠지고, 남은
    것은 셋 모두가 조건만으로 판정한다.
    """
    verdict: dict[tuple[int, str], list[str]] = {}
    by_scope: dict[tuple[str, str], list[MetricRow]] = {}
    for row in rows:
        by_scope.setdefault((row.domain, row.period), []).append(row)

    for (_, period), scope_rows in by_scope.items():
        window = thresholds.new_windows.get(period)
        rising: list[MetricRow] = []
        fresh: list[MetricRow] = []
        for row in scope_rows:
            found = evidence.get((row.keyword_id, period))
            if found is None:
                continue
            if is_current(row, thresholds.current_top_n):
                verdict.setdefault((row.keyword_id, period), []).append(CURRENT)
            if is_rising(row, found, thresholds.rising, thresholds.zscore):
                rising.append(row)
            if window is not None and is_new(row, found, window):
                fresh.append(row)

        rising.sort(key=lambda row: (-(row.growth_rate or 0.0), -row.growth_amount, row.keyword_id))
        for row in rising[: thresholds.rising.top_n]:
            verdict.setdefault((row.keyword_id, period), []).append(RISING)
        fresh.sort(key=lambda row: (-row.mention_count, row.keyword_id))
        for row in fresh[: thresholds.new_top_n]:
            verdict.setdefault((row.keyword_id, period), []).append(NEW)

    return {
        key: tuple(name for name in TREND_TYPES if name in types)
        for key, types in verdict.items()
    }
