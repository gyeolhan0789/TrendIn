"""스코어링과 선별 ([04 §6](../../../../spark/docs/04-keyword-extraction-spec.md) · §7). 순수 함수.

세 축을 문서 안에서 0~1 로 정규화한 뒤 가중합한다. 원값끼리 더하면 스케일이 큰 축이 다 소비한다.

| 축 | 무엇 | 어디서 계산 |
| --- | --- | --- |
| C-value | 복합어 우선. 늘 긴 후보 안에서만 나오는 짧은 후보는 감점 | 코퍼스 빈도 (`batch.py`) |
| BM25 | 문서 내 중요도. 문서 길이 정규화가 들어 있어 TF-IDF 보다 낫다 | 문서 × 후보 |
| 위치 | 제목에 나오면 1, 아니면 0 | 문서 × 후보 |

**pyspark 를 import 하지 않는다** ([09 §4] 층 1). Spark 는 이 함수들을 컬럼식으로 옮겨 쓰거나
UDF 로 감싼다 — 어느 쪽이든 수식의 정의는 여기 한 곳이다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence


def c_value(ntokens: int, frequency: float, parent_frequencies: Iterable[float] = ()) -> float:
    """C-value(a) = log2(|a| + 1) × ( f(a) − mean f(b), b ∈ T_a ).

    **`log2(|a|)` 가 아니라 `log2(|a| + 1)` 이다.** [04 §6] 의 식은 `log2(|a|)` 인데, 그러면
    단일 토큰(|a| = 1)의 C-value 가 **항상 0** 이라 같은 절의 예시 — "`workflow` 가 독립적으로도
    500회 나오면 둘 다 살아남는다" — 가 성립하지 않는다. 식과 예시 중 예시가 의도이므로 길이
    항에 1 을 더해 단일 토큰도 빈도에 비례하게 두고, 긴 후보에 가산점을 주는 편향은 그대로
    남긴다 (1 → 1, 2 → 1.58, 3 → 2).

    `f(a) ≥ f(b)` 는 포함 관계에서 늘 성립하므로(a 가 b 안에 나올 때마다 a 도 나온다) 결과는
    0 이상이지만, 필터가 부모 일부를 걸러낸 뒤의 빈도가 들어올 수 있어 0 에서 자른다.
    """
    parents = list(parent_frequencies)
    nested = (sum(parents) / len(parents)) if parents else 0.0
    return max(0.0, math.log2(ntokens + 1) * (frequency - nested))


def bm25_idf(df: int, corpus_size: int) -> float:
    """Robertson 의 IDF. `+1` 안쪽에 있어 df 가 코퍼스의 절반을 넘어도 음수가 되지 않는다."""
    return math.log(1.0 + (corpus_size - df + 0.5) / (df + 0.5))


def bm25(
    tf: int, *, doc_len: int, avg_doc_len: float, idf: float, k1: float = 1.2, b: float = 0.75
) -> float:
    """문서 하나 · 후보 하나의 BM25. 길이 정규화 항이 소스 간 글 길이 차이를 흡수한다."""
    if tf <= 0:
        return 0.0
    ratio = (doc_len / avg_doc_len) if avg_doc_len > 0 else 1.0
    norm = k1 * (1.0 - b + b * ratio)
    return idf * (tf * (k1 + 1.0)) / (tf + norm)


def minmax(value: float, low: float, high: float) -> float:
    """문서 안 0~1 정규화. 축의 값이 전부 같으면(후보 1개, 전부 0) 1 이 아니라 **값이 있으면 1,
    0 이면 0** 이다 — 후보 하나짜리 문서에서 그 후보가 제목에 없고 C-value 0 인데 1 점을 받는
    것을 막는다."""
    if high <= low:
        return 1.0 if high > 0 else 0.0
    return (value - low) / (high - low)


@dataclass(frozen=True, slots=True)
class ScoreWeights:
    c_value: float
    bm25: float
    title: float

    @property
    def total(self) -> float:
        return self.c_value + self.bm25 + self.title


def combine(c_value_norm: float, bm25_norm: float, title: float, weights: ScoreWeights) -> float:
    """가중합. 가중치 합으로 나눠 결과도 0~1 이다 — `score_floor` 가 그 척도로 정해진다."""
    if weights.total <= 0:
        return 0.0
    total = weights.c_value * c_value_norm + weights.bm25 * bm25_norm + weights.title * title
    return total / weights.total


def title_axis(tf_title: int) -> float:
    """위치 축. 제목은 글쓴이가 주제를 압축한 자리라 있고 없고로 본다 ([04 §6])."""
    return 1.0 if tf_title > 0 else 0.0


def select(scored: Sequence[tuple[str, float]], *, top_k: int, floor: float) -> list[str]:
    """문서 하나의 `(비교키, 점수)` → `keyword_contents` 로 나갈 비교키. 상위 K **이고** 하한 이상.

    동점은 비교키 사전순 — 결정적이어야 스냅샷 테스트가 성립한다 ([04 §9]).
    """
    ranked = sorted(scored, key=lambda item: (-item[1], item[0]))
    return [key for key, score in ranked[:top_k] if score >= floor]
