r"""토막 분할 — 모델이 한 번에 못 보는 길이를 나눠 넣는다 ([04 §2]).

GLiNER 는 입력을 384 토큰에서 자르고 뒤를 버린다 (`gliner/config.py` 의 `max_len`).
`curated` 전량에서 **문서의 48% 가 잘리고 전체 글자의 30.8% 가 모델에 도달하지 못했다**
(`tests/fixtures/review/extract-gliner-2026-09-17.md` §4.1).

## 왜 `max_length` 를 올리지 않았나

`GLiNER.from_pretrained(..., max_length=768)` 로 상한을 올리는 길이 있고 저자도 가능하다고
말한다. 표본 138건에서 **같은 768 범위로 두 방법을 나란히 쟀다.**

| CPU · 138건 | 초/문서 | 고유 비교키 | 384 뒤에서 얻은 구간 |
| --- | ---: | ---: | ---: |
| 상한 384 (옛 경로) | 1.58 | 1,799 | 0 |
| `max_length=768` | 2.58 | 2,035 | 671 |
| **토막 256×3** | **2.37** | **2,945** | **1,293** |

(표의 비교는 `\S+` 기준으로 쟀다. 토큰 기준으로 고친 뒤 토막이 보는 범위가 좁아졌으므로
숫자는 재실행으로 다시 확인한다.)

**토막이 더 빠르면서 더 건진다.** 384 로 학습된 모델에 768 을 한 번에 넣으면 뒤쪽에서 힘을
잃어 절반만 잡고, 고유하게 잡는 것은 `망고반팔 코튼 티셔츠` 같은 경계 오류다. 속도도 자기
주의가 길이의 제곱이라 768 한 번보다 256 세 번이 싸다.

## 무엇을 세는가

**모델의 토큰은 어절이 아니다.** `WhitespaceTokenSplitter` 의 정규식이
`\w+(?:[-_]\w+)*|\S` 라 단어와 기호를 따로 세고, 한국어 기사에서 실측하면 **어절 수의 약
1.5배**가 나온다. 처음에 `\S+` 로 셌다가 256 으로 자른 토막이 391 토큰이 되어 다시 잘렸고,
배치 예산까지 같은 비율로 어긋나 전량 재추출이 죽었다 (2026-09-17).

그래서 `count_tokens` 하나를 두고 분할과 배치 구성이 같이 쓴다.

**상한 384 를 다 채우지 않는 이유** — 한국어는 토큰 하나가 `mdeberta-v3-base` 에서 서브워드
2.9~3.2배로 부푼다 (영어는 1.47배). 상한까지 채우면 서브워드가 1,000개를 넘어 자기 주의
비용이 커진다.

**`pyspark` 도 `gliner` 도 import 하지 않는다** ([09 §4] 층 1). 문자열만 다루므로 모델 없이
전량을 테스트할 수 있다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# 토막을 끊을 자리로 삼는 토큰. **언어를 모르는 층이라 문장부호만 본다** — 한국어
# 종결어미를 알면 `adapters.py` 가 언어를 아는 유일한 곳이라는 규약이 깨진다. 일본어 `。` 와
# 영어 `.` 가 같은 규칙으로 걸린다.
_SENTENCE_END = re.compile(r"[.!?。！？]$")

# 토큰 하나. **`gliner` 의 `WhitespaceTokenSplitter` 와 글자 하나까지 같아야 한다** —
# 그 값이 384 상한과 맞붙는 수이기 때문이다.
#
# ⚠️ `\S+` 로 세면 안 된다. 이 정규식은 **단어와 기호를 따로 센다** — `2026 봄/여름` 이
# `\S+` 로는 2개지만 모델에게는 `2026`·`봄`·`/`·`여름` 4개다. 그 차이로 256 으로 자른 토막이
# 391 토큰이 되어 다시 잘렸다 (2026-09-17 전량 재추출 1차 실패).
_WORD = re.compile(r"\w+(?:[-_]\w+)*|\S")


@dataclass(frozen=True, slots=True)
class Chunk:
    """토막 하나. **원문에서 시작하는 글자 위치를 들고 간다.**

    이 값이 없으면 구간을 원문 좌표로 되돌릴 수 없고, 그러면 제목 가산
    (`document.py` 의 `span.start < title_len`)과 조사 꼬리 제거(`adapters.py`)가 둘 다
    어긋난다. 증상이 "두 번째 토막의 실체가 전부 제목에 있는 것으로 계산된다" 로 나타난다.
    """

    text: str
    offset: int


def count_tokens(text: str) -> int:
    """모델이 셀 토큰 수. **배치를 묶는 쪽도 이 함수를 써야 한다** (`entities._packed`) —
    두 곳이 다른 규칙으로 세면 예산이 어긋나 배치가 의도보다 커진다."""
    return sum(1 for _ in _WORD.finditer(text))


def split(text: str, *, budget: int, overlap: int, max_chunks: int) -> list[Chunk]:
    """원문 → 토막 목록. `budget` 과 `overlap` 은 **모델 토큰 수**다 (`count_tokens`).

    `max_chunks` 는 문서 하나가 쓸 수 있는 추론 비용의 상한이다. 옛 `max_chars` 가 하려던
    일이고, 그 값은 384 토큰보다 뒤에 있어 아무것도 하지 않았다. 기사 본문은 앞쪽에 핵심이
    몰리므로 넘는 뒷부분은 버린다.
    """
    if not text:
        return []
    words = [(m.start(), m.end()) for m in _WORD.finditer(text)]
    if not words:
        return []
    if len(words) <= budget:
        return [Chunk(text, 0)]

    chunks: list[Chunk] = []
    head = 0
    while head < len(words) and len(chunks) < max_chunks:
        tail = min(head + budget, len(words))
        if tail < len(words):
            tail = _sentence_cut(text, words, head=head, tail=tail, budget=budget)
        start, end = words[head][0], words[tail - 1][1]
        chunks.append(Chunk(text[start:end], start))
        if tail >= len(words):
            break
        # **겹침만큼 되돌린다.** 경계에 걸친 `2026 봄/여름 컬렉션` 이 어느 한쪽에는 온전히
        # 들어가야 한다. 되돌린 자리가 앞선 머리보다 뒤여야 무한 루프가 되지 않는다.
        head = max(tail - overlap, head + 1)
    return chunks


def _sentence_cut(
    text: str, words: list[tuple[int, int]], *, head: int, tail: int, budget: int
) -> int:
    """`tail` 에서 뒤로 훑어 문장이 끝나는 토큰을 찾는다. 못 찾으면 `tail` 그대로 끊는다.

    되짚는 범위를 예산의 4분의 1로 묶는다. 문장부호가 없는 문서(일본어 기사나 목록형 본문)
    에서 끝없이 되짚으면 토막이 지나치게 짧아지고, 그러면 문맥이 줄어 유형 판정이 나빠진다.
    """
    floor = max(head + 1, tail - budget // 4)
    for index in range(tail, floor, -1):
        start, end = words[index - 1]
        if _SENTENCE_END.search(text[start:end]):
            return index
    return tail
