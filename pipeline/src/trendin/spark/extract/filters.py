"""후보 필터 ([04 §5](../../../../spark/docs/04-keyword-extraction-spec.md)). 순서대로, 싼 것부터.

| # | 필터 | 어디서 |
| --- | --- | --- |
| 1 | 형태 — 숫자만 · 특수문자만 · 단일 문자 · 가격 표기 | 여기 (문서 안, 순수) |
| 2 | 길이 — 문자 수 하한·상한 | 여기 |
| 3 | 불용어 — 언어별 + 도메인별 | 여기 |
| 4 | 노이즈 사전 — 확장자 · HTTP 상태 · 변수명 · 쇼핑 상투어 | 여기 |
| 5 | **DF 하한** | `batch.py` — 코퍼스를 봐야 한다. 경계 계산만 여기 |
| 6 | **DF 상한** | 같음 |
| 7 | 소스 편중 | [05 §5] — 제거가 아니라 승격 보류라 여기 없다 |

**버린 이유를 남긴다.** 사유별 건수가 [04 §9] 의 분포 모니터링으로 `pl_batch_stat` 에 간다
(`jobs/extract.py`). 값이 곧 집계 키라 이름을 바꾸면 옛 실행과 이어지지 않는다.

**pyspark 를 import 하지 않는다** ([09 §4] 층 1).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from trendin.spark.extract.lexicon import Lexicon

SHAPE = "SHAPE"
LENGTH = "LENGTH"
STOPWORD = "STOPWORD"
NOISE = "NOISE"
DF_LOW = "DF_LOW"
DF_HIGH = "DF_HIGH"

IN_DOCUMENT_REASONS = (SHAPE, LENGTH, STOPWORD, NOISE)
CORPUS_REASONS = (DF_LOW, DF_HIGH)

# 글자(라틴·한글)가 하나도 없다 — 숫자 · 기호 · 밑줄뿐.
_NO_LETTER = re.compile(r"^[^A-Za-z가-힣]+$")
# 가격·비율 표기. 패션 커머스 문서에서 `29,000원` · `30%` 가 후보로 올라오는 것을 막는다
# ([04 §8] 패션 노이즈). 통화 기호는 NFKC 뒤의 형태다.
_PRICE = re.compile(r"^\d[\d,.]*\s*(원|만원|천원|달러|유로|엔|₩|\$|€|£|%)$")


@dataclass(frozen=True, slots=True)
class CandidateLimits:
    """길이 필터 ([04 §5] 2번). `ExtractThresholds` 에서 온다."""

    min_chars: int = 2
    max_chars: int = 40


def rejection_reason(key: str, *, lexicon: Lexicon, limits: CandidateLimits) -> str | None:
    """비교키 하나 → 버릴 사유. `None` 이면 통과. 1~4 번을 순서대로 본다."""
    if len(key) < 2 or _NO_LETTER.match(key) or _PRICE.match(key):
        return SHAPE
    if not limits.min_chars <= len(key) <= limits.max_chars:
        return LENGTH
    if lexicon.is_stopword(key):
        return STOPWORD
    if lexicon.is_noise(key):
        return NOISE
    # n-gram 의 **모든** 토큰이 노이즈면 노이즈다. 하나만 노이즈인 `tmp directory` 는 살린다 —
    # 노이즈 사전은 코드 잔재를 잡는 것이고, 문장 속 단어로 쓰인 것까지 지우면 과하다.
    parts = key.split(" ")
    if len(parts) > 1 and all(lexicon.is_noise(part) for part in parts):
        return NOISE
    return None


@dataclass(frozen=True, slots=True)
class DfBounds:
    """DF 경계 — 문서 수로 환산된 값. `low ≤ df ≤ high` 가 통과다."""

    low: int
    high: int
    corpus_size: int


def df_bounds(corpus_size: int, *, min_ratio: float, max_ratio: float) -> DfBounds:
    """비율 → 문서 수. **절대값이 아니라 비율인 이유** — 하루 700건 코퍼스에서 절대값으로 걸면
    초기에는 전부 통과하고 반년 뒤에는 전부 탈락한다 ([04 §5], [10 §4] S4).

    하한은 최소 1 이다 — 0 이면 아무것도 안 걸러진다. 상한은 하한 아래로 내려가지 않는다 —
    문서 한두 건짜리 코퍼스(테스트 · 첫 실행)에서 `floor(0.5 × 1) = 0` 이 되어 전부가
    "너무 흔하다" 로 사라지는 것을 막는다. 그 규모에서는 상한이 의미가 없고, 하한만 남는 것이
    맞다.
    """
    low = max(1, math.ceil(min_ratio * corpus_size))
    high = max(low, math.floor(max_ratio * corpus_size))
    return DfBounds(low=low, high=high, corpus_size=corpus_size)


def df_reason(df: int, bounds: DfBounds) -> str | None:
    if df < bounds.low:
        return DF_LOW
    if df > bounds.high:
        return DF_HIGH
    return None
