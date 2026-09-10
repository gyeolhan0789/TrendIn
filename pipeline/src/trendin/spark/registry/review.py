"""검수 큐 ([05 §7]) — 층 2·3 이 자동 판별하지 못한 쌍이 모인다.

내부 테이블이며 서비스 스키마가 아니다. **검수를 안 해도 파이프라인은 정상 동작한다** —
층 1·2 자동 병합만 적용되고 층 3 후보는 각각 별개 키워드로 남는다. 의미적 동의어가 나뉘어
있는 상태이고 그건 잘못 합쳐진 것보다 훨씬 낫다.

**이 성질을 유지하는 것이 중요하다** ([05 §7]). 사람 손을 파이프라인의 의존성으로 만들면
아무도 안 볼 때 파이프라인이 멈춘다.

| 상태 | 뜻 |
| --- | --- |
| `PENDING` | 판단 대기 |
| `APPROVED` | 다음 `extract` 실행부터 병합에 반영된다 |
| `REJECTED` | **반드시 기록한다.** 없으면 같은 쌍이 매 배치마다 다시 올라와 검수자를 지치게 한다 |

우선순위는 두 후보의 문서 수 합이다 — **영향이 큰 것부터.**

## 큐에 오는 두 갈래

| 갈래 | 왜 자동이 아닌가 |
| --- | --- |
| 보류된 층 2 쌍 (`alias.resolve` 의 `parked`) | 이미 승격된 키워드가 얽혀 있다.
  [05 §1] 의 사후 병합이라 백엔드와 함께 수동으로 한다 |
| 층 3 임베딩 후보 | 유사도는 상관이지 증거가 아니다. `React`/`Vue` 를 합치면
  서비스가 망가진다 ([05 §4]) |

**pyspark 를 import 하지 않는다** ([09 §4] 층 1).
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass

from trendin.spark.registry.merge import LAYER_EVIDENCE, MergePair, signal_of

STATUS_PENDING = "PENDING"
STATUS_APPROVED = "APPROVED"
STATUS_REJECTED = "REJECTED"

# 층 3. 임베딩 유사도만 있는 쌍이다.
LAYER_EMBEDDING = 3

# 큐 항목의 출처.
ORIGIN_PARKED = "parked"
ORIGIN_EMBEDDING = "embedding"
# 검수자가 승인한 쌍을 다음 실행이 병합으로 되읽을 때의 규칙 이름.
RULE_REVIEW = "review"


@dataclass(frozen=True, slots=True)
class ReviewItem:
    """`pl_review_queue` 한 줄. 쌍은 `(대표, 흡수)` 순서로 정규화해 저장한다.

    정규화하지 않으면 `(a, b)` 와 `(b, a)` 가 별개 행이 되어 한쪽을 `REJECTED` 해도
    다른 쪽이 다음 배치에 다시 올라온다.
    """

    domain: str
    representative_key: str
    absorbed_key: str
    origin: str
    layer: int
    similarity: float | None
    npmi: float | None
    # 층 2 증거가 있는지. [05 §4] 의 표에서 "유사도 높음 + 층 2 증거 있음" 은 자동 병합이라
    # 큐에 오지 않지만, 보류된 쌍은 증거가 있는데도 오므로 그 구분이 필요하다.
    has_layer2_signal: bool
    priority: int
    signal: str


def review_items(
    *,
    parked: Iterable[MergePair] = (),
    embedding_pairs: Iterable[MergePair] = (),
    doc_counts: Mapping[str, int],
    decided: Collection[tuple[str, str, str]] = (),
) -> tuple[ReviewItem, ...]:
    """큐에 올릴 항목. **이미 판단이 끝난 쌍은 다시 올리지 않는다.**

    `decided` 는 `(domain, representative_key, absorbed_key)` 로 `APPROVED` · `REJECTED`
    가 붙은 쌍이다. `PENDING` 은 여기 넣지 않는다 — 적재가 upsert 라 우선순위가 갱신되는
    것이 맞다 (문서 수가 늘면 순서가 올라가야 한다).
    """
    seen = {tuple(item) for item in decided}
    items: dict[tuple[str, str, str], ReviewItem] = {}
    for pair, origin, layer in (
        *((pair, ORIGIN_PARKED, pair.layer) for pair in parked),
        *((pair, ORIGIN_EMBEDDING, LAYER_EMBEDDING) for pair in embedding_pairs),
    ):
        key = (pair.domain, pair.representative, pair.absorbed)
        if key in seen or key in items:
            continue
        items[key] = ReviewItem(
            domain=pair.domain,
            representative_key=pair.representative,
            absorbed_key=pair.absorbed,
            origin=origin,
            layer=layer,
            similarity=_signal_number(pair, "similarity"),
            npmi=_signal_number(pair, "npmi"),
            has_layer2_signal=pair.layer <= LAYER_EVIDENCE,
            priority=doc_counts.get(pair.representative, 0) + doc_counts.get(pair.absorbed, 0),
            signal=pair.signal,
        )
    return tuple(items[key] for key in sorted(items, key=lambda k: (-items[k].priority, k)))


def approved_pairs(
    rows: Iterable[tuple[str, str, str]],
) -> tuple[MergePair, ...]:
    """`APPROVED` 행 → 병합 쌍. **승인된 병합은 다음 `extract` 실행부터 적용된다** ([05 §7]).

    `(domain, representative_key, absorbed_key)` 를 받는다. 이미 승격된 것끼리의 승인은
    여기서 쌍이 되지만 `alias.resolve` 가 다시 보류한다 — 자동 적용하지 않는 판단이
    한 곳에만 있어야 해서 그 검사를 여기서 중복하지 않는다.
    """
    return tuple(
        MergePair(
            domain=domain,
            representative=representative,
            absorbed=absorbed,
            layer=LAYER_EMBEDDING,
            rule=RULE_REVIEW,
            # 사람이 승인한 것이라 이 층에서 가장 높다.
            confidence=1.0,
            signal=signal_of(approved=True),
        )
        for domain, representative, absorbed in sorted(rows)
        if representative != absorbed
    )


def _signal_number(pair: MergePair, name: str) -> float | None:
    """근거 JSON 에서 숫자 하나. 층 2 쌍에는 없는 칸이라 `None` 이 정상이다."""
    import json

    try:
        value = json.loads(pair.signal).get(name)
    except (ValueError, AttributeError):
        return None
    return None if value is None else float(value)
