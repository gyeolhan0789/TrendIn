"""기간 지표의 계산 — 증가량 · 증가율 · 순위 ([07 §5]).

**`previous_mention_count` 를 이월하지 않는다.** 직전 구간을 원자료에서 **다시 계산해서**
얻는다. 지난 실행이 남긴 값을 옮겨 쓰면 그 값이 소급 재계산으로 바뀌었을 수 있고([07 §2]),
그러면 재실행이 곧 오염이 된다. 원자료에서 계산하면 같은 날 몇 번을 돌려도 결과가 같다.

**pyspark 를 import 하지 않는다** ([09 §4] 층 1).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date

# 증가율의 반올림 자리 ([07 §5]). 백엔드 `growth_rate` 가 numeric 이라 정밀도를 맞춰 둔다.
GROWTH_RATE_DIGITS = 1


@dataclass(frozen=True, slots=True)
class MetricRow:
    """`keyword_metrics` 한 줄. 키워드 × 기간에 하나다."""

    keyword_id: int
    # 순위 범위가 `(domain, period)` 다 ([07 §5]). `keywords.domain` 을 조인해 얻는 값이지만
    # 원자료가 이미 들고 있어 서비스 테이블을 읽지 않는다.
    domain: str
    period: str
    period_start: date
    period_end: date
    mention_count: int
    previous_mention_count: int
    growth_amount: int
    # **직전이 0 이면 `None` 이다.** 무한대나 큰 수로 채우지 않는다 ([07 §5]).
    growth_rate: float | None
    # **언급량이 0 이면 `None` 이다.** 하락으로 0 이 된 키워드에는 매길 순위가 없다.
    mention_rank: int | None = None


def growth_amount(mention_count: int, previous_mention_count: int) -> int:
    """음수가 될 수 있다. `bigint` 이므로 담긴다 ([07 §5])."""
    return mention_count - previous_mention_count


def growth_rate(mention_count: int, previous_mention_count: int) -> float | None:
    """`(현재 − 직전) / 직전 × 100`. **직전이 0 이면 `None`** — "계산 불가" 다.

    `None` 은 "성장률 0" 이 아니다. 프론트가 0 으로 그리면 새로 뜬 키워드가 전부 "성장 없음"
    으로 보인다 ([07 §5]) — 그 규약을 백엔드 API 문서에 남겨달라고 전달해야 한다.
    """
    if previous_mention_count == 0:
        return None
    delta = mention_count - previous_mention_count
    return round(delta / previous_mention_count * 100, GROWTH_RATE_DIGITS)


def build_row(
    *,
    keyword_id: int,
    domain: str,
    period: str,
    period_start: date,
    period_end: date,
    mention_count: int,
    previous_mention_count: int,
) -> MetricRow:
    return MetricRow(
        keyword_id=keyword_id,
        domain=domain,
        period=period,
        period_start=period_start,
        period_end=period_end,
        mention_count=mention_count,
        previous_mention_count=previous_mention_count,
        growth_amount=growth_amount(mention_count, previous_mention_count),
        growth_rate=growth_rate(mention_count, previous_mention_count),
    )


def _order_key(row: MetricRow) -> tuple:
    """[07 §5] 의 동점 처리. **공동 순위를 두지 않는다.**

    ```
    1. mention_count       DESC
    2. growth_rate         DESC NULLS LAST
    3. keyword_id          ASC
    ```

    3차 키가 `keyword_id` 인 것이 조건이다 — 데이터가 하나도 안 변했는데 실행마다 순위가
    흔들리면 그게 화면에 "순위 변동" 으로 나타난다.
    """
    rate = row.growth_rate
    return (-row.mention_count, 0 if rate is not None else 1, -(rate or 0.0), row.keyword_id)


def assign_ranks(rows: list[MetricRow]) -> list[MetricRow]:
    """`(domain, period)` 안에서 언급량 내림차순 순위를 매긴다 ([07 §5]).

    **언급량 0 인 행은 순위에서 뺀다.** 하락으로 0 이 된 키워드에 넣을 값이 없다 — 0 도
    아니고 마지막 등수도 아니다(그 등수가 매 실행 달라진다). `mention_rank` 를 `None` 으로
    두고, 그 행도 지표는 그대로 낸다 — 100 → 0 은 `growth_amount = −100` 이라는 정보다.
    """
    ranked: list[MetricRow] = []
    by_scope: dict[tuple[str, str], list[MetricRow]] = {}
    for row in rows:
        by_scope.setdefault((row.domain, row.period), []).append(row)
    for scope_rows in by_scope.values():
        position = 0
        for row in sorted(scope_rows, key=_order_key):
            if row.mention_count <= 0:
                ranked.append(replace(row, mention_rank=None))
                continue
            position += 1
            ranked.append(replace(row, mention_rank=position))
    # 부른 쪽이 무엇을 기대하든 같은 순서로 돌려준다 — 적재 순서가 실행마다 흔들리면
    # 트랜잭션 로그 비교가 어려워진다.
    return sorted(ranked, key=lambda row: (row.domain, row.period, _order_key(row)))
