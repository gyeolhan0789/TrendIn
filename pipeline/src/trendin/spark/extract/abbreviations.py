"""약어-전개형 쌍 ([05 §3](../../../../spark/docs/05-keyword-registry-spec.md) 의 결정적 증거).

`Model Context Protocol (MCP)` · `메시카(Messika)` 처럼 **한 문서 안에서 저자가 직접 두 표기를
나란히 쓴 자리**를 찾는다. 통합 층 2 가 가장 강한 증거로 꼽는 형태라 후보와 별개로 남긴다
(`pl_abbreviation_observation`).

**후보 생성과 무관하다.** 실체 인식으로 후보를 만들게 된 뒤에도 이 탐지는 그대로다 —
모델은 "이 둘이 같은 것" 이라고 말해 주지 않고, 괄호 병기는 문자열 규칙으로 정확히 잡힌다.
옛 `extract/candidates.py` 에 있던 것을 그대로 옮겼다 (2026-09-16).

**pyspark 를 import 하지 않는다** ([09 §4] 층 1).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from trendin.spark.extract.keys import normalized_key


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
