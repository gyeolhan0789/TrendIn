"""후보 생성 ([04 §3](../../../../spark/docs/04-keyword-extraction-spec.md)).

**불용어와 경계 표시 사이의 연속 토큰이 구간이다.** 구간 안에서 길이 1~N 의 모든 n-gram 을
낸다.

**경계를 누가 정하는가가 2026-09-09 에 바뀌었다.** 한국어는 이제 형태소 분석기가 명사가
아닌 것을 모두 경계로 표시해 오므로(`extract/tokenize.py`), 이 구간은 **명사 연속**이다 —
옛날처럼 "불용어 사이의 아무 토큰" 이 아니다. 그래서 `두고 활동한` · `모델로서 갖게` 같은
문장 조각이 나올 자리가 없다. 영어는 그대로 불용어·구두점이 경계다.

```
"the new agentic workflow is changing how we build"      (영어 — 불용어 경계)
 ────         ──────────────── ──                 ─────
 불용어        후보 구간         불용어              불용어
→ "new agentic workflow", "new agentic", "agentic workflow", "new", "agentic", "workflow"

"미니멀한 실루엣의 오버사이즈 테일러드 재킷"                  (한국어 — 명사 연속)
 미니멀|한  실루엣|의  오버사이즈 테일러드 재킷
 ───────┘   ───────┘   ────────────────────────
 구간: [미니멀] [실루엣] [오버사이즈 테일러드 재킷]
→ "오버사이즈 테일러드 재킷", "오버사이즈 테일러드", "테일러드 재킷", "오버사이즈", …
```

**불용어는 여전히 경계다.** 품사가 명사라도 무정보한 낱말(`컬러` · `룩`)은 명사구를 끊는다 —
`컬러의 조합` 이 후보가 되면 안 되는 이유가 품사가 아니라 무정보성이기 때문이다 ([04 §5]).

별도 규칙으로 잡는 것 — 대문자 약어 · 코드 식별자 · 해시태그 · 버전 붙은 이름은 토크나이저가
이미 한 토큰으로 보존했으므로 여기서는 **종류만 붙인다.** 약어-전개형 쌍(`Model Context
Protocol (MCP)`)만 텍스트를 다시 훑어 따로 기록한다 — [05 §3] 통합의 결정적 증거라 후보와
별개로 남긴다.

**C-value 를 위해 포함 관계를 함께 낸다.** 후보마다 같은 구간에서 그것을 포함하는 더 긴
n-gram 의 비교키를 `parents` 로 든다. 코퍼스 빈도는 `extract/batch.py` 가 Spark 로 합치지만,
"누가 누구를 포함하는가" 는 구간 안에서만 결정되므로 여기서 안다.

**pyspark 를 import 하지 않는다** ([09 §4] 층 1).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Sequence

from trendin.spark.extract import tokenize as tk
from trendin.spark.extract.keys import normalized_key
from trendin.spark.extract.tokenize import Token

# 후보 종류. 단일 토큰은 토큰 종류를 물려받고, 여럿이면 아래 둘이다.
TERM = "TERM"  # 보통 단어 하나 (WORD · HANGUL)
NGRAM = "NGRAM"
VERSIONED = "VERSIONED"  # `Python 3.12` · `React 19`. 꼬리가 숫자 꼴이다


@dataclass(frozen=True, slots=True)
class Occurrence:
    """후보의 출현 하나. 같은 문서 안에서 `document.py` 가 비교키로 합친다."""

    surface: str
    key: str
    kind: str
    ntokens: int
    in_title: bool
    # 같은 구간에서 이 후보를 포함하는 더 긴 후보의 비교키 (C-value 의 T_a).
    parents: tuple[str, ...] = ()
    # 구성 토큰 중 하나라도 고유명사 태그를 받았나 ([04 §6] 고유명사 축).
    # `제니 발레 슈즈` 처럼 이름이 낀 복합어를 잡으려면 **any** 여야 한다 — all 로 두면
    # 이름 + 일반명사 조합이 전부 떨어진다.
    is_proper: bool = False


@dataclass(frozen=True, slots=True)
class AbbreviationPair:
    """`전개형 (약어)` 패턴 하나."""

    abbreviation: str
    expansion: str
    abbreviation_key: str
    expansion_key: str
    # 약어의 각 글자가 전개형 단어들의 첫 글자와 대응하는가 ([05 §3] 조건). 한국어 전개형은
    # 대응을 볼 수 없어 `False` 로 남기고, [05] 가 다른 증거와 함께 판단한다.
    initials_match: bool


def spans(tokens: Sequence[Token]) -> list[list[Token]]:
    """불용어와 경계 표시로 자른 구간. 빈 구간은 내지 않는다.

    한국어에서 이 구간이 **명사 연속**인 것은 토크나이저가 명사가 아닌 형태소마다
    `boundary_after` 를 세워 오기 때문이다 — 이 함수는 그 표시를 읽을 뿐이고 품사를 모른다.
    영어는 같은 표시가 구두점과 줄바꿈에서 온다.
    """
    result: list[list[Token]] = []
    current: list[Token] = []
    for token in tokens:
        if token.is_stop:
            if current:
                result.append(current)
                current = []
            continue
        current.append(token)
        if token.boundary_after:
            result.append(current)
            current = []
    if current:
        result.append(current)
    return result


def ngram_candidates(
    spans_: Iterable[Sequence[Token]], *, ngram_max: int, in_title: bool
) -> list[Occurrence]:
    """구간들 → 후보 출현. 숫자 꼴은 **꼬리로만** 허용한다 — `Python 3.12` 는 되고 `3.12` ·
    `3 tips` 는 안 된다 ([04 §3] "숫자 필터에 걸리지 않게 예외 처리")."""
    result: list[Occurrence] = []
    for span in spans_:
        result.extend(_span_candidates(span, ngram_max=ngram_max, in_title=in_title))
    return result


def _span_candidates(span: Sequence[Token], *, ngram_max: int, in_title: bool) -> list[Occurrence]:
    # (start, end, key, surface, kind, is_proper)
    grams: list[tuple[int, int, str, str, str, bool]] = []
    length = len(span)
    for size in range(1, min(ngram_max, length) + 1):
        for start in range(0, length - size + 1):
            window = span[start : start + size]
            if not _valid_window(window):
                continue
            surface = " ".join(token.surface for token in window)
            key = normalized_key(surface)
            if not key:
                continue
            grams.append(
                (start, start + size, key, surface, _kind_of(window),
                 any(token.is_proper for token in window))
            )

    result: list[Occurrence] = []
    for start, end, key, surface, kind, proper in grams:
        parents = tuple(
            sorted(
                {
                    other_key
                    for o_start, o_end, other_key, _, _, _ in grams
                    if o_start <= start
                    and o_end >= end
                    and (o_end - o_start) > (end - start)
                    and other_key != key
                }
            )
        )
        result.append(Occurrence(surface, key, kind, end - start, in_title, parents, proper))
    return result


def _valid_window(window: Sequence[Token]) -> bool:
    # 첫 토큰과 가운데 토큰은 숫자 꼴이면 안 된다. 꼬리만 허용한다.
    if window[0].kind in tk.NUMERIC_KINDS:
        return False
    for token in window[1:-1]:
        if token.kind in tk.NUMERIC_KINDS:
            return False
    # 해시태그는 홀로 선다 (`tokenize._Builder.hashtag`). 여기 섞여 오면 배선이 깨진 것이다.
    if len(window) > 1 and any(token.kind == tk.HASHTAG for token in window):
        return False
    return True


def _kind_of(window: Sequence[Token]) -> str:
    if len(window) == 1:
        kind = window[0].kind
        return TERM if kind in (tk.WORD, tk.HANGUL) else kind
    if window[-1].kind in tk.NUMERIC_KINDS:
        return VERSIONED
    return NGRAM


# --- 약어-전개형 쌍 ---------------------------------------------------------

# `Model Context Protocol (MCP)` · `모델 컨텍스트 프로토콜(MCP)` · `메시카(Messika)`.
# 전개형은 괄호 앞의 단어 1~6개, 괄호 안은 **약어 또는 이름꼴**이다. 전개형 첫머리에
# 불용어(`the`)가 끼어도 아래 대응 검사가 필요한 만큼만 뒤에서 잘라 쓴다.
#
# ⚠️ **2026-09-10 에 괄호 안의 범위를 넓혔다.** 그전에는 공백 없는 대문자 약어만 받았다.
# 실측에서 fashion 코퍼스 376문서에 `한글(라틴)` 패턴이 **316건** 있는데 그중 **21건만**
# 잡히고 있었다. 나머지 288건이 `메시카(Messika)` · `아크리스(Akris)` 처럼 브랜드 음차
# 병기였고, 그게 [05 §3] 이 "가장 강한 증거" 로 꼽은 바로 그 형태다.
_ABBREVIATION = re.compile(
    r"((?:[\w\-]+[  ]+){0,5}[\w\-]+)[  ]*\(\s*([A-Za-z][A-Za-z0-9&'’.\- ]{1,30})\s*\)"
)
# 전개형 안에서 첫 글자 대응에 세지 않는 기능어.
_SKIPPED_IN_EXPANSION = frozenset({"of", "and", "the", "for", "to", "in", "on", "a", "an"})
_HANGUL = re.compile(r"[가-힣]")
# 초성 대응 검사가 성립하는 형태 — 공백 없는 대문자 약어. 이름꼴(`Messika`)은 첫 글자가
# 전개형 어절과 아무 관계가 없어 그 검사를 건너뛴다.
_ACRONYM = re.compile(r"[A-Z][A-Z0-9]{1,5}")


def abbreviation_pairs(text: str | None) -> list[AbbreviationPair]:
    """텍스트에서 `전개형 (약어)` 쌍 전부. 같은 쌍이 여러 번 나오면 여러 번 낸다 — 문서 안
    빈도는 `document.py` 가 합친다."""
    if not text:
        return []
    result: list[AbbreviationPair] = []
    for match in _ABBREVIATION.finditer(text):
        words = match.group(1).split()
        abbreviation = match.group(2)
        expansion, matched = _align(words, abbreviation)
        if expansion is None:
            continue
        result.append(
            AbbreviationPair(
                abbreviation=abbreviation,
                expansion=expansion,
                abbreviation_key=normalized_key(abbreviation),
                expansion_key=normalized_key(expansion),
                initials_match=matched,
            )
        )
    return result


# 한국어 전개형을 몇 어절까지 볼지의 상한. 넘는 이름은 실측에 없었고(최대 4어절), 상한이
# 없으면 앞 문맥을 먹던 옛 동작으로 돌아간다.
_MAX_EXPANSION_WORDS = 4


def _expansion_words(bracketed: str) -> int:
    """한국어 전개형을 뒤에서 몇 어절까지 볼지 — 괄호 안 표기가 정한다.

    **대응 방식이 둘이고 세는 단위가 다르다.**

    | 괄호 안 | 세는 것 | 왜 |
    | --- | --- | --- |
    | 약어 `MCP` | **글자 수** 3 | 초성 대응 — 글자 하나가 어절 하나다 (`모델 컨텍스트 프로토콜`) |
    | 이름꼴 `Art of Fusion` | **어절 수** 3 | 음차 대응 — 어절이 어절에 붙는다 (`아트 오브 퓨전`) |

    숫자만 있는 어절도 센다 (`System 0` 은 2어절이고 `시스템 제로` 와 대응한다).
    """
    if _ACRONYM.fullmatch(bracketed):
        return min(max(sum(1 for ch in bracketed if ch.isalpha()), 1), _MAX_EXPANSION_WORDS)
    return min(max(len(bracketed.split()), 1), _MAX_EXPANSION_WORDS)


def _align(words: list[str], abbreviation: str) -> tuple[str | None, bool]:
    """전개형 후보 단어들과 약어를 맞춘다. `(전개형, 첫 글자 대응 여부)`.

    영문이면 뒤에서부터 약어 길이만큼의 내용어를 잡아 첫 글자를 대조한다. 한국어 전개형은
    대조가 성립하지 않으므로 단어 전부를 전개형으로 두고 `False` 를 준다.
    """
    if not words:
        return None, False
    if any(_HANGUL.search(word) for word in words):
        # 괄호 바로 앞의 한글 어절 연속만. 그 앞의 영문(`MCP는 모델 컨텍스트 프로토콜(MCP)` 의
        # `MCP는`)은 전개형이 아니다.
        tail: list[str] = []
        for word in reversed(words):
            if not _HANGUL.match(word):
                break
            tail.insert(0, word)
        if not tail:
            return None, False
        # **여기서 더 잘라야 한다.** 한국어 전개형에는 초성 대응이 없어(`ASICS` ↔ `아식스`)
        # 어디까지가 이름인지 알려 주는 것이 없었고, 그래서 앞 문맥을 통째로 먹었다 —
        # `이라는 주제로 글로벌 스포츠 브랜드 아식스(ASICS)` ([05 §3] 이 후속으로 올려 둔 결함).
        # 2026-09-10 실측에서 이 한 줄이 4어절 이상 전개형을 34% → 2% 로 줄였다. 마지막
        # 1어절만 취하면 0% 지만 `아트 오브 퓨전` 이 `퓨전` 으로 깨진다.
        return " ".join(tail[-_expansion_words(abbreviation) :]), False

    # 괄호 안이 **이름꼴**(소문자가 섞였거나 공백이 있다)이면 초성 대응이 성립하지 않는다 —
    # `Messika` 의 첫 글자는 전개형 어절 수와 아무 관계가 없다. 쌍은 남기되 `initials_match`
    # 를 `False` 로 둔다. 그 값이 `True` 여야 자동 병합하는 것은 [05 §3] 의 규약이고, 이름꼴은
    # 대신 **음차 유사도**가 근거가 된다 (`registry/romanize.py`).
    if not _ACRONYM.fullmatch(abbreviation):
        return " ".join(words[-_expansion_words(abbreviation) :]), False

    letters = [ch for ch in abbreviation if ch.isalpha()]
    content = [word for word in words if word.lower() not in _SKIPPED_IN_EXPANSION]
    if len(content) < len(letters):
        return None, False
    # 뒤에서부터 약어 글자 수만큼. 그 앞의 단어(`the`, 문장 앞부분)는 전개형이 아니다.
    tail = content[-len(letters) :]
    if all(word[0].upper() == letter.upper() for word, letter in zip(tail, letters)):
        # 원문 순서를 지키되 기능어는 tail 사이의 것만 남긴다.
        first = words.index(tail[0])
        return " ".join(words[first:]), True
    return None, False
