"""후보 필터 ([04 §5](../../../../spark/docs/04-keyword-extraction-spec.md)).

**필터가 넷에서 둘로 줄었다** (2026-09-16). 실체 인식으로 옮기면서 불용어 사전과 노이즈
사전이 없어졌기 때문이다 — 무엇이 키워드인지를 라벨이 정의하므로 뺄 것을 따로 셀 필요가
없다 (`extract/entities.py` 의 주석).

| # | 필터 | 어디서 |
| --- | --- | --- |
| 1 | 형태 — 숫자만 · 특수문자만 · 단일 문자 · 가격 표기 | 여기 (문서 안, 순수) |
| 2 | 길이 — 문자 수 하한·상한 | 여기 |
| 3 | 라벨 — 그 언어에서 끈 유형 | `extract/adapters.py` (언어를 안다) |
| 4 | 점수 — 문턱 미만 | `extract/entities.py` (모델이 아예 돌려주지 않는다) |
| 5 | 소스 편중 | [05 §5] — 제거가 아니라 승격 보류라 여기 없다 |

**DF 하한·상한이 없어졌다.** 옛 경로는 코퍼스 문서 빈도로 잡음을 걸렀는데, 코퍼스를 7.6배
키워도 무정보어의 비율이 그대로라는 것이 측정으로 나왔다. 점수가 모델에서 오므로 DF 는
이제 기록용 칸이고 선별에 관여하지 않는다 (`extract/batch.py`).

**형태 필터를 남긴 이유** — 모델이 `2026年` · `55,000円` 같은 구간을 라벨과 함께 돌려줄 때가
있고, 이것은 사전이 아니라 정규식 두 줄이라 언어가 늘어도 늘지 않는다.

**버린 이유를 남긴다.** 사유별 건수가 [04 §9] 의 분포 모니터링으로 `pl_batch_stat` 에 간다.
값이 곧 집계 키라 이름을 바꾸면 옛 실행과 이어지지 않는다.

**pyspark 를 import 하지 않는다** ([09 §4] 층 1).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

SHAPE = "SHAPE"
LENGTH = "LENGTH"
# 그 언어에서 꺼 둔 라벨이라 빠졌다 (`adapters.AdapterSpec.allows`). 일본어의 품목·소재가
# 여기 잡힌다 — 켜고 끈 결과를 숫자로 보려면 사유가 남아야 한다.
LABEL = "LABEL"

# 글자가 하나도 없다 — 숫자 · 기호 · 밑줄뿐. 한글 · 라틴 · 가나 · 한자를 글자로 본다.
_NO_LETTER = re.compile(r"^[^A-Za-z가-힣぀-ヿ一-鿿]+$")
# 가격·비율·연도 표기. 패션 커머스 문서에서 `29,000원` · `55,000円` · `30%` · `2026年` 이
# 후보로 올라오는 것을 막는다. 통화 기호는 NFKC 뒤의 형태다.
_NUMERIC_UNIT = re.compile(
    r"^\d[\d,.]*\s*(원|만원|천원|달러|유로|엔|円|年|月|日|₩|\$|€|£|¥|%)$"
)


@dataclass(frozen=True, slots=True)
class CandidateLimits:
    """길이 필터 ([04 §5] 2번). `ExtractThresholds` 에서 온다."""

    min_chars: int = 2
    max_chars: int = 40


def rejection_reason(key: str, *, limits: CandidateLimits) -> str | None:
    """비교키 하나 → 버릴 사유. `None` 이면 통과."""
    if len(key) < 2 or _NO_LETTER.match(key) or _NUMERIC_UNIT.match(key):
        return SHAPE
    if not limits.min_chars <= len(key) <= limits.max_chars:
        return LENGTH
    return None
