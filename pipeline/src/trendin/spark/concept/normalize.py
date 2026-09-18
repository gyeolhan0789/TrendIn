"""표기 → 비교키, 그리고 표기의 문자 체계.

`extract/keys.normalized_key` 가 하는 일(NFKC · 소문자 · 하이픈·공백 접기 · 앞뒤 구두점)은
그대로 쓰고, 그 함수가 모르는 문자 체계의 접기를 **뒤에** 붙인다. 앞의 함수는 라틴·한글을
전제로 짜였고 그 전제는 지금도 옳다 — 여기서 바꾸지 않는다.

| 문자 체계 | 접는 것 | 왜 |
| --- | --- | --- |
| 아랍어 | 발음 부호 · 타트윌 · 알리프 변형 · 타 마르부타 · 알리프 마크수라 | 매체마다 갈린다 |
| 일본어 | 가운뎃점(`・`) | `ボッテガ・ヴェネタ` 와 `ボッテガヴェネタ` 는 같은 이름이다 |
| 라틴 | **키에서는 접지 않는다.** `latin_fold` 가 2차 키 | 접으면 프랑스어 단어끼리 충돌 |

**아랍어 정관사 `ال` 은 떼지 않는다.** `الموضة`(the fashion) 와 `موضة`(fashion) 는 다른 키로
남는다. 떼면 `ال` 로 시작하는 고유명사(`Alaïa` 의 아랍어 표기)까지 잘린다. 사전에 두 표기를
다 넣는 쪽이 싸고 안전하다.

**pyspark 를 import 하지 않는다** (층 1).
"""

from __future__ import annotations

import re
import unicodedata

from trendin.spark.extract.keys import normalized_key

HANGUL = "hangul"
KANA = "kana"  # 가나 · 한자. 일본어 표기로 본다
ARABIC = "arabic"
LATIN = "latin"
MIXED = "mixed"
OTHER = "other"

# 문자 체계 → 그 체계를 쓰는 언어. 라틴은 하나가 아니라서 `None` 이다 — 기사 언어가 정한다.
SCRIPT_LANG = {HANGUL: "ko", KANA: "ja", ARABIC: "ar"}
LATIN_LANGS = frozenset({"en", "fr", "it", "es", "de", "pt"})
# 라틴 표기를 언어 무관하게 조회할 때 쓰는 이름. 브랜드는 영어·프랑스어·이탈리아어 기사에서
# 같은 글자로 나오므로, 기사 언어로 가르면 같은 표기가 세 키로 갈린다.
LATIN_ANY = "la"

_RANGES = {
    HANGUL: ((0xAC00, 0xD7A3), (0x1100, 0x11FF), (0x3130, 0x318F)),
    KANA: (
        (0x3040, 0x309F),
        (0x30A0, 0x30FF),
        (0x31F0, 0x31FF),
        (0xFF66, 0xFF9F),
        (0x4E00, 0x9FFF),
    ),
    ARABIC: (
        (0x0600, 0x06FF),
        (0x0750, 0x077F),
        (0x08A0, 0x08FF),
        (0xFB50, 0xFDFF),
        (0xFE70, 0xFEFF),
    ),
}

# 아랍어 — 발음 부호(타슈킬) · 타트윌 · 위첨자 알리프. 있어도 없어도 같은 말이다.
_ARABIC_MARKS = re.compile(r"[ً-ْٰـ]")
_ARABIC_FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ة": "ه", "ى": "ي"})

# 일본어 — 가운뎃점 두 종류와 전각 공백. NFKC 가 반각 가나는 접지만 가운뎃점은 남긴다.
_JAPANESE_DOTS = re.compile(r"[・･　]")

# 라틴 — 결합 부호. NFD 로 풀면 `é` 가 `e` + U+0301 이 되고 그 부호를 뗀다.
_COMBINING = re.compile(r"[̀-ͯ]")
_LIGATURES = str.maketrans({"æ": "ae", "œ": "oe", "ß": "ss", "ø": "o", "đ": "d", "ł": "l"})


def script_of(text: str) -> str:
    """표기의 문자 체계. 글자(letter)만 세고 숫자·기호는 무시한다.

    한 체계가 글자의 전부면 그 체계, 라틴만이면 `latin`, 둘 이상이 섞이면 `mixed`,
    글자가 없으면 `other`. `MCP는` 처럼 라틴에 조사가 붙은 것은 `mixed` 다 — 비교키를 만들
    때는 형태소 분석기가 이미 조사를 떼었으므로 여기까지 오지 않는다.
    """
    seen: set[str] = set()
    for ch in text:
        if not ch.isalpha():
            continue
        code = ord(ch)
        for name, ranges in _RANGES.items():
            if any(lo <= code <= hi for lo, hi in ranges):
                seen.add(name)
                break
        else:
            seen.add(LATIN)
    if not seen:
        return OTHER
    if len(seen) == 1:
        return next(iter(seen))
    return MIXED


def lang_of_surface(surface: str, article_lang: str | None) -> str:
    """이 표기를 사전에서 **어느 언어 칸으로** 찾을지.

    한글·가나·아랍 문자는 문자 체계가 언어를 정한다 — 일본어 기사 안의 한글 표기는 없다.
    라틴 문자는 기사 언어가 라틴 언어면 그 언어, 아니면(한국·일본 기사 안의 `Bottega Veneta`)
    언어 무관 `la` 다. 조회는 어느 경우든 라틴 표기를 언어 무관 색인으로도 한 번 더 본다
    (`dictionary.Dictionary.lookup`).
    """
    script = script_of(surface)
    if script in SCRIPT_LANG:
        return SCRIPT_LANG[script]
    if script == LATIN and article_lang in LATIN_LANGS:
        return article_lang
    if script == LATIN:
        return LATIN_ANY
    return article_lang or LATIN_ANY


def concept_key(surface: str | None) -> str:
    """표기 → 비교키. 빈 문자열이면 후보가 아니다 — 부른 쪽이 버린다.

    `normalized_key` 뒤에 문자 체계별 접기를 붙인다. 순서가 중요하다 — NFKC 를 먼저 거쳐야
    반각 가나와 전각 라틴이 접힌 뒤에 우리 규칙이 본다.
    """
    key = normalized_key(surface)
    if not key:
        return ""
    script = script_of(key)
    if script == ARABIC or (script == MIXED and _has(key, ARABIC)):
        key = _ARABIC_MARKS.sub("", key).translate(_ARABIC_FOLD)
    if script == KANA or (script == MIXED and _has(key, KANA)):
        key = _JAPANESE_DOTS.sub("", key)
    return key.strip()


def latin_fold(key: str) -> str:
    """라틴 비교키의 2차 키 — 악센트와 합자를 접는다. **비교키 자체는 아니다.**

    조회가 1차 키로 못 찾았을 때만 이 키로 한 번 더 본다. `Hermès` 를 `hermes` 로 적은 기사와
    붙이기 위한 것이고, 화면에 나가는 표기는 원래대로다.
    """
    decomposed = unicodedata.normalize("NFD", key)
    stripped = _COMBINING.sub("", decomposed)
    return unicodedata.normalize("NFC", stripped).translate(_LIGATURES)


def _has(text: str, script: str) -> bool:
    ranges = _RANGES[script]
    return any(any(lo <= ord(ch) <= hi for lo, hi in ranges) for ch in text)
