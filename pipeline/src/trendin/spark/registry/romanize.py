"""한글 → 로마자 근사와 음차 유사도 — 브랜드 병기를 잇는 근거 ([05 §3]).

`메시카(Messika)` 같은 괄호 병기는 [05 §3] 이 "글쓴이가 둘은 같다고 **선언한** 것" 으로 가장
강한 증거라 부른 형태다. 그런데 그 규약의 자동 병합 조건이 **서로 다른 문서 N건**이라, 실측에서
아무것도 통과하지 못했다 — 브랜드는 괄호에 한두 번 나오고 만다 (2026-09-10: 고유 쌍 275개 중
2회 이상 관측이 8개).

**그 문턱은 "한 사람의 오기가 아님" 을 보려는 것이다.** 음차 유사도가 그 역할을 대신할 수 있다 —
`메시카` 를 로마자로 풀면 `mesika` 이고 `Messika` 와 거의 같다. 오기로 이런 일치가 나오지 않는다.
반복 관측과 문자열 근거는 서로 다른 종류의 증거라, **둘 중 하나로 문턱을 갈음하는 것이 맞다.**

## 실측 (2026-09-10, fashion 376문서 · 이름꼴 고유 쌍 275)

| | 중앙값 |
| --- | --- |
| 진짜 병기 쌍 | 0.56 |
| 무작위로 섞은 쌍 | 0.21 |

| 임계 | 진짜 통과 | 무작위 통과 |
| --- | --- | --- |
| 0.5 | 66% | **1%** |
| 0.6 | 43% | 0.4% |

## ⚠️ 통과하지 못하는 쪽이 더 중요하다

낮게 나온 쌍은 **번역**이다 — `일상의 사물들(Banal Objects)` 0.14 · `황소 가죽(Bull Leather)`
0.09 · `심장(coeur)` 0.00. 이건 결함이 아니라 **정확히 원하는 동작**이다.

> **음차는 같은 낱말의 다른 표기이고, 번역은 다른 낱말이다.**

`발레 슈즈` 와 `ballet flats` 를 한 키워드로 합치면 "어느 표기가 어디서 먼저 떴나" 를 물을
대상이 사라진다. 음차만 합치고 번역은 각자 두는 경계를 이 함수가 긋는다.

**완전한 로마자 표기법이 아니다.** 국어의 로마자 표기법의 자음 동화·구개음화를 구현하지 않고
음절을 그대로 편다 (`좋은` → `joheun` 이 아니라 `joheun` 계열로 근사). 목적이 표기 복원이
아니라 **두 문자열이 같은 소리인지 재는 것**이라 그 차이가 유사도에서 상쇄된다.

**pyspark 를 import 하지 않는다** ([09 §4] 층 1).
"""

from __future__ import annotations

from difflib import SequenceMatcher

# 한글 음절 = 0xAC00 + (초성 × 588) + (중성 × 28) + 종성.
_SYLLABLE_BASE = 0xAC00
_SYLLABLE_LAST = 0xD7A3

# 초성 19 · 중성 21 · 종성 28. 값은 개정 로마자 표기법에 가깝게 두되, 유사도 계산이 목적이라
# 자음 동화 같은 문맥 규칙은 넣지 않는다.
_INITIAL = (
    "g", "kk", "n", "d", "tt", "r", "m", "b", "pp",
    "s", "ss", "", "j", "jj", "ch", "k", "t", "p", "h",
)
_MEDIAL = (
    "a", "ae", "ya", "yae", "eo", "e", "yeo", "ye", "o", "wa", "wae", "oe", "yo",
    "u", "wo", "we", "wi", "yu", "eu", "ui", "i",
)
_FINAL = (
    "", "g", "k", "k", "n", "n", "n", "d", "l", "k", "m", "b", "l", "l", "l", "l",
    "m", "b", "s", "s", "s", "ng", "j", "c", "k", "t", "p", "h",
)
assert len(_INITIAL) == 19 and len(_MEDIAL) == 21 and len(_FINAL) == 28

# 이 값 이상이면 음차로 본다. 실측에서 무작위 쌍의 1% 만 넘는다 (모듈 docstring 의 표).
DEFAULT_SIMILARITY_FLOOR = 0.5


def romanize(text: str) -> str:
    """한글을 로마자로 편다. 한글이 아닌 글자는 소문자로 그대로 남고 기호는 빠진다."""
    out: list[str] = []
    for char in text:
        code = ord(char) - _SYLLABLE_BASE
        if 0 <= code <= _SYLLABLE_LAST - _SYLLABLE_BASE:
            out.append(_INITIAL[code // 588])
            out.append(_MEDIAL[(code % 588) // 28])
            out.append(_FINAL[code % 28])
        elif char.isalnum():
            out.append(char.lower())
    return "".join(out)


def similarity(left: str, right: str) -> float:
    """두 표기가 같은 소리인가 — 0~1.

    **양쪽을 다 로마자로 편다.** `romanize` 는 한글이 아닌 글자를 소문자로 그대로 두므로
    라틴 표기는 그대로 남고 한글만 펴진다 — 그래서 어느 쪽이 한글인지 부른 쪽이 정하지
    않아도 되고, 인자 순서를 바꿔도 같은 값이 나온다. 한쪽이라도 비면 0 이다.
    """
    first, second = romanize(left), romanize(right)
    if not first or not second:
        return 0.0
    return SequenceMatcher(None, first, second).ratio()


def is_transliteration(left: str, right: str, *, floor: float = DEFAULT_SIMILARITY_FLOOR) -> bool:
    """두 표기가 같은 이름의 음차인가. **번역은 여기서 떨어진다** (모듈 docstring)."""
    return similarity(left, right) >= floor
