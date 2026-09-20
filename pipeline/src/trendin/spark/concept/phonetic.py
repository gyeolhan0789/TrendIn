"""표기 → 로마자, 그리고 로마자 → 소리키.

`샤넬` 과 `Chanel` 은 공통 글자가 하나도 없다. 글자를 아무리 비교해도 안 붙는다. 소리로 건너가는
다리가 필요해서, 양쪽을 로마자로 편 뒤 **같은 소리로 들리는 글자끼리 한 덩어리로 묶은 키**를
만들어 맞춘다.

| 단계 | 하는 일 | `샤넬` | `Chanel` |
| --- | --- | --- | --- |
| `romanize` | 한글·가나를 로마자로 편다 | `syanel` | `chanel` |
| `sound_key` | 끼워 넣은 모음을 빼고 자음을 덩어리로 접는다 | `sanir` | `sanir` |

## 모음을 버리지 않는 이유

처음에는 자음만 남겼다. 그랬더니 `까르띠에` 와 `gold` 가 같은 키(`GRD`)가 되어 후보 목록이
잡음으로 찼다. 네댓 글자 낱말에서 모음을 다 버리면 남는 것이 너무 적다. 그래서 모음은 버리지
않고 `a` · `i`(e·i) · `u`(o·u) 셋으로만 줄인다 — 음차에서 흔들리는 것은 주로 모음의 정확한
높이지 있고 없고가 아니다.

## 접는 덩어리

| 덩어리 | 묶는 소리 | 왜 |
| --- | --- | --- |
| `p` | b p f v | 한국어에 f·v 가 없어 `Ferragamo` 가 `페라가모` 가 된다 |
| `t` | d t | 종성 `ㄷ ㅅ ㅈ` 이 전부 `t` 로 적힌다 |
| `k` | k q · 뒤가 e·i·y 가 아닌 c·g | `Gucci` 와 `구찌` |
| `s` | s z j ch sh ts · 뒤가 e·i·y 인 c·g | `샤넬`(sya) 과 `Chanel`(cha), `지방시` 와 `Givenchy` |
| `r` | r l | 한국어가 둘을 안 가른다 |

`h` 와 반모음 `y` `w` 는 버린다 — `Hermès` 와 `에르메스`(ereumeseu) 가 앞글자에서 갈리지 않게
하려는 것이다. 이어진 같은 글자는 한 번으로 줄인다 (`폴로`=`pollo`=`Polo`).

**키가 세 글자보다 짧으면 빈 문자열을 준다.** 짧은 키는 사전에서 수백 개와 부딪혀 후보 목록을
잡음으로 채운다. 부른 쪽이 빈 값을 버린다.

**pyspark 를 import 하지 않는다** (층 1).
"""

from __future__ import annotations

import re

# 한글 음절 = 0xAC00 + (초성 * 21 + 중성) * 28 + 종성. 유니코드가 이 규칙을 보장한다.
_HANGUL_BASE = 0xAC00
_HANGUL_LAST = 0xD7A3

# fmt: off
_CHOSEONG = (
    "g", "kk", "n", "d", "tt", "r", "m", "b", "pp", "s",
    "ss", "", "j", "jj", "ch", "k", "t", "p", "h",
)
_JUNGSEONG = (
    "a", "ae", "ya", "yae", "eo", "e", "yeo", "ye", "o", "wa",
    "wae", "oe", "yo", "u", "wo", "we", "wi", "yu", "eu", "ui", "i",
)
_JONGSEONG = (
    "", "k", "k", "k", "n", "n", "n", "t", "l", "l",
    "l", "l", "l", "l", "l", "l", "m", "p", "p", "t",
    "t", "ng", "t", "t", "k", "t", "p", "t",
)
# fmt: on

# 히라가나를 가타카나로 옮기는 간격. 표를 한 벌만 두려고 먼저 옮긴다.
_HIRAGANA_START, _HIRAGANA_END, _KANA_GAP = 0x3041, 0x3096, 0x60

# fmt: off
_KATAKANA = {
    "ア": "a", "イ": "i", "ウ": "u", "エ": "e", "オ": "o",
    "カ": "ka", "キ": "ki", "ク": "ku", "ケ": "ke", "コ": "ko",
    "サ": "sa", "シ": "shi", "ス": "su", "セ": "se", "ソ": "so",
    "タ": "ta", "チ": "chi", "ツ": "tsu", "テ": "te", "ト": "to",
    "ナ": "na", "ニ": "ni", "ヌ": "nu", "ネ": "ne", "ノ": "no",
    "ハ": "ha", "ヒ": "hi", "フ": "fu", "ヘ": "he", "ホ": "ho",
    "マ": "ma", "ミ": "mi", "ム": "mu", "メ": "me", "モ": "mo",
    "ヤ": "ya", "ユ": "yu", "ヨ": "yo",
    "ラ": "ra", "リ": "ri", "ル": "ru", "レ": "re", "ロ": "ro",
    "ワ": "wa", "ヰ": "i", "ヱ": "e", "ヲ": "o", "ン": "n",
    "ガ": "ga", "ギ": "gi", "グ": "gu", "ゲ": "ge", "ゴ": "go",
    "ザ": "za", "ジ": "ji", "ズ": "zu", "ゼ": "ze", "ゾ": "zo",
    "ダ": "da", "ヂ": "ji", "ヅ": "zu", "デ": "de", "ド": "do",
    "バ": "ba", "ビ": "bi", "ブ": "bu", "ベ": "be", "ボ": "bo",
    "パ": "pa", "ピ": "pi", "プ": "pu", "ペ": "pe", "ポ": "po",
    "ヴ": "vu",
}
# fmt: on
_SMALL_YOUON = {"ャ": "a", "ュ": "u", "ョ": "o"}
_SMALL_VOWEL = {"ァ": "a", "ィ": "i", "ゥ": "u", "ェ": "e", "ォ": "o"}
_SOKUON = "ッ"  # 촉음 — 다음 자음을 겹친다
_CHOUON = "ー"  # 장음 — 소리키에 영향이 없어 버린다

# 여러 글자가 한 소리인 것. 긴 것부터 봐야 `ch` 가 `c`+`h` 로 쪼개지지 않는다.
# fmt: off
_CLUSTERS = (
    ("tch", "s"), ("sch", "s"),
    ("ch", "s"), ("sh", "s"), ("ts", "s"), ("ph", "p"), ("th", "t"),
    ("ck", "k"), ("gh", "k"), ("kh", "k"), ("zh", "s"), ("qu", "k"),
)
_SINGLE = {
    "b": "p", "p": "p", "f": "p", "v": "p",
    "d": "t", "t": "t",
    "k": "k", "q": "k",
    "s": "s", "z": "s", "j": "s",
    "r": "r", "l": "r",
    "m": "m", "n": "n",
    "x": "ks",
    "a": "a", "e": "i", "i": "i", "o": "u", "u": "u",
    "h": "", "w": "", "y": "",
}
# fmt: on
_SOFT_VOWELS = frozenset("eiy")
_NOT_LETTER = re.compile(r"[^a-z]+")

# 로마자 단계에서 먼저 손보는 모음. 글자별로 접기 전에 해야 두 글자 모음이 두 소리가 되지 않는다.
#
# `으`(eu) 는 한국어가 외래어의 자음 뒤에 **끼워 넣는** 모음이라 통째로 버린다 — `스트라이프`
# 가 `stripe` 와 같은 키가 되는 자리다. 낱말 첫머리에서는 버리지 않는다 (`Europe`).
_EPENTHESIS = re.compile(r"(?<=.)eu")
# 가나도 자음만으로는 못 적어 `ル`(ru) 처럼 모음을 달고 끝난다. `シャネル` 이 `Chanel` 과
# 만나려면 자음 뒤의 마지막 `u` 를 뗀다. 양쪽에 똑같이 걸어 한쪽만 짧아지지 않게 한다.
_TRAILING_U = re.compile(r"(?<=[bcdfghjklmnpqrstvwxz])u$")
_VOWEL_FIXES = (("eo", "o"), ("ae", "a"), ("oe", "e"), ("ui", "i"))

MIN_SOUND_KEY = 3


def romanize(text: str) -> str:
    """한글·가나를 로마자로 편다. 이미 로마자인 글자는 그대로 둔다.

    표준 표기법을 그대로 따르지 않는다 — 여기 결과는 사람이 읽을 것이 아니라 소리키를 만드는
    중간값이라, 음절 경계의 소리 바뀜(`신라`→`silla`)까지 흉내 낼 이유가 없다.
    """
    out: list[str] = []
    pending_double = False
    for char in text:
        code = ord(char)
        if _HANGUL_BASE <= code <= _HANGUL_LAST:
            index = code - _HANGUL_BASE
            out.append(_CHOSEONG[index // 588])
            out.append(_JUNGSEONG[(index % 588) // 28])
            out.append(_JONGSEONG[index % 28])
            continue
        if _HIRAGANA_START <= code <= _HIRAGANA_END:
            char = chr(code + _KANA_GAP)
        if char == _CHOUON:
            continue
        if char == _SOKUON:
            pending_double = True
            continue
        if char in _SMALL_YOUON and out:
            out.append(_youon(out.pop(), _SMALL_YOUON[char]))
            continue
        if char in _SMALL_VOWEL and out:
            out.append(out.pop().rstrip("aiueo") + _SMALL_VOWEL[char])
            continue
        syllable = _KATAKANA.get(char, char.lower())
        if pending_double and syllable:
            syllable = syllable[0] + syllable
            pending_double = False
        out.append(syllable)
    return "".join(out)


def _youon(previous: str, vowel: str) -> str:
    """`シ`+`ャ` → `sha`. 앞 음절의 `i` 를 떼고 반모음을 붙인다."""
    stem = previous[:-1] if previous.endswith("i") else previous
    if stem.endswith(("sh", "ch", "j")):
        return stem + vowel
    return stem + "y" + vowel


def sound_key(text: str) -> str:
    """표기 → 소리키. 세 글자보다 짧으면 빈 문자열이다 — 부른 쪽이 버린다."""
    roman = _NOT_LETTER.sub("", romanize(text).lower())
    roman = _EPENTHESIS.sub("", roman)
    roman = _TRAILING_U.sub("", roman)
    for source, target in _VOWEL_FIXES:
        roman = roman.replace(source, target)
    out: list[str] = []
    i = 0
    while i < len(roman):
        for cluster, symbol in _CLUSTERS:
            if roman.startswith(cluster, i):
                out.append(symbol)
                i += len(cluster)
                break
        else:
            char = roman[i]
            if char in "cg":
                # 뒤가 e·i·y 면 `Givenchy`·`Balenciaga` 처럼 s 소리, 아니면 k 소리.
                out.append("s" if roman[i + 1 : i + 2] in _SOFT_VOWELS else "k")
            else:
                out.append(_SINGLE.get(char, ""))
            i += 1
    folded: list[str] = []
    for symbol in "".join(out):
        if not folded or folded[-1] != symbol:
            folded.append(symbol)
    result = "".join(folded)
    return result if len(result) >= MIN_SOUND_KEY else ""
