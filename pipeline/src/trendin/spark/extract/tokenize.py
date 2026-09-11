"""언어별 토큰화 ([04 §2](../../../../spark/docs/04-keyword-extraction-spec.md)).

**한국어는 형태소 분석기로 품사를 보고 명사만 남긴다** (`extract/morphology.py` — 분석기
선정 근거와 품사표가 거기 있다). 2026-09-09 승인된 결정이고, 그 전의 조사·어미 접미 표 ·
최소 어간 문턱 · 보호어 파일은 **없어졌다.**

```
"인트레치아토 기법을 재해석한 백과 미니멀한 실루엣의 코트가 중심이다."
 인트레치아토/NNG  기법/NNG 을/JKO  재/XPN 해석/NNG 하/XSV ᆫ/ETM  백/NNG 과/JC …
 ─────────────────────────┘        ──────────────┘              ───┘
 구간: [인트레치아토 기법] [재해석] [백] [미니멀] [실루엣] [코트] [중심]
```

**규칙표가 하려던 일을 태그가 한다.** 조사(`J*`) · 어미(`E*`) · 용언(`V*`) · 부호(`S*`) ·
의존명사(`NNB`)는 모두 **경계**이고 후보의 재료가 아니다. 그래서 `컬러의` · `힘을` ·
`더해` · `싶다면` · `스커트보` 가 구조적으로 나올 수 없다 — 어느 사전에도 항목을 넣지
않았는데 사라진다.

**표기는 원문에서 잘라 온다.** 분석기의 `form` 은 기본형이라 `부드러운` → `부드럽` 처럼
원문과 다를 수 있는데, 후보 표기는 화면에 나가는 값이다. 그래서 형태소의 위치만 쓰고
문자열은 원문에서 슬라이스한다. 붙여 쓴 복합어(`개발자경험` = `개발자`+`경험`)가 한 토큰으로
살아남는 것도 이 덕이다 — 두 형태소가 **공백 없이 붙어 있으면** 한 표기다.

**고유명사는 사용자 사전으로 지킨다.** 분석기가 모르는 브랜드는 조사째 한 덩이가 된다
(`발렌시아가와`/NNP). 옛 보호어 파일과 목적은 닮았지만 **하는 일이 다르다** — 저쪽은
"규칙이 자르지 못하게 막는" 것이었고 이쪽은 "이런 고유명사가 있다고 알려 주는" 것이라,
알려 주면 조사까지 옳게 떨어진다 (`발렌시아가` + `와`). `conf/lexicon/userdict-{domain}.txt`.

**영어는 그대로다** — 형태소 분석기를 태우지 않는다. 공백·구두점으로 나누고, 소유격을 떼고,
코드 식별자 · 버전 · 대문자 약어를 한 토큰으로 보존한다. 영어에는 조사가 없어 이번 작업이
없애려던 오류가 애초에 없고, dev 도메인 수집분이 0건이라([10 §5.1]) 바꿔도 재 볼 수가 없다.
바꾸지 않은 것이 결정이다.

`lang` 이 `en` 이 아니면(`ko` · `mixed`) 분석기를 쓴다. 한국 패션 기사는 한글 본문에 영문
브랜드명이 섞여 있고(`mixed`) `MCP는` 처럼 영문에 조사가 붙는데, 분석기가 `MCP`/SL +
`는`/JX 로 옳게 가른다. **한글이 없는 표기는 분석기가 어디를 잘랐는지와 무관하게 영문
분류기를 다시 태운다** — `ES2023` → VERSION, `os.path` → CODE.

**pyspark 를 import 하지 않는다** ([09 §4] 층 1).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Sequence

from trendin.spark.extract import morphology as mp
from trendin.spark.extract.keys import normalized_key
from trendin.spark.extract.lexicon import Lexicon
from trendin.spark.normalize.lang import EN

# 토큰 종류. 후보의 `kind` 가 여기서 나온다 (`extract/candidates.py`).
WORD = "WORD"
HANGUL = "HANGUL"
ACRONYM = "ACRONYM"
CODE = "CODE"
VERSION = "VERSION"
NUMBER = "NUMBER"
HASHTAG = "HASHTAG"

# 숫자 꼴. 단독으로는 후보가 아니고 `Python 3.12` 의 꼬리로만 살아남는다 ([04 §3]).
NUMERIC_KINDS = frozenset({NUMBER, VERSION})


@dataclass(frozen=True, slots=True)
class Token:
    surface: str
    kind: str
    # 불용어. 구간 경계이고 단독 후보가 아니다 ([04 §3]).
    is_stop: bool = False
    # 이 토큰 뒤에서 구간이 끝난다 — 명사가 아닌 형태소 · 구두점 · 줄바꿈 · 해시태그.
    boundary_after: bool = False
    # 형태소 분석기가 **고유명사(`NNP`)** 로 본 명사가 이 토큰에 들어 있나 ([04 §6] 고유명사 축).
    #
    # ⚠️ **믿을 만한 신호가 아니다.** 2026-09-10 실측에서 `디올`·`바자` 는 `NNG` 이고
    # `퍼플`·`플랫`·`데일리` 는 `NNP` 였다 — Kiwi 의 `NNP` 는 고유명사라기보다 "사전에 드물게
    # 등재된 외래어" 에 가깝다. 그래서 축으로 쓰되 **가중치를 작게** 둔다 (`score_weights.proper`).
    # 확실한 신호는 라틴 문자 표기이고 그건 `batch.py` 가 표기에서 직접 본다.
    is_proper: bool = False


@dataclass(frozen=True, slots=True)
class TokenizeOptions:
    """도메인별 토큰화 옵션 ([04 §8]). `thresholds.DomainOptions` 에서 온다.

    **`analyzer` 는 분석기가 아니라 분석기의 설정이다.** Kiwi 는 pickle 되지 않고 이 객체는
    UDF 클로저로 executor 에 직렬화된다 (`extract/morphology.py` 의 마지막 절).
    """

    code_identifiers: bool = True
    # 명사 표기를 어디까지 붙여 쓸지 (`morphology.SURFACE_*`).
    surface_policy: str = mp.SURFACE_PREFIXED
    analyzer: mp.AnalyzerSpec = field(default_factory=mp.AnalyzerSpec)


# --- 스캐너 (영문 경로) ------------------------------------------------------

# 해시태그 → 일반 토큰 → 그 밖의 비공백 한 글자(구두점). `\w` 는 유니코드라 한글을 포함한다.
# 토큰 안에 `.`·`-`·`_`·`'`·`&`·`+`·`#` 을 허용하는 이유는 `os.path` · `multi-agent` ·
# `snake_case` · `React's` · `R&D` · `C++` · `C#` 을 한 덩이로 받기 위해서다. 앞뒤에 붙은 것은
# `_clean` 이 뗀다.
_SCAN = re.compile(r"#\w+|\d[\d,.]*\w*|\w[\w.\-'’&+#]*|\S")

_LEADING_PUNCT = re.compile(r"^[.\-'’_]+")
_TRAILING_PUNCT = re.compile(r"[.\-'’_,]+$")
_POSSESSIVE = re.compile(r"['’]s$", re.IGNORECASE)

_HAS_HANGUL = re.compile(r"[가-힣]")

# --- 영문 토큰 분류 ---------------------------------------------------------

_NUMBER = re.compile(r"^\d+(,\d+)*$")
# `v2` · `3.12` · `ES2023` · `HTTP2`. 대문자+숫자 꼴은 약어보다 먼저 본다.
_VERSION = re.compile(r"^(v\d+(\.\d+)*|\d+(\.\d+)+|[A-Z]{1,4}\d{1,4})$")
# 2~6자, 전부 대문자(숫자·`&` 섞여도 됨). 글자가 둘 이상이어야 한다 — `X1` 은 약어가 아니다.
_ACRONYM = re.compile(r"^[A-Z][A-Z0-9&]{1,5}$")
_TWO_LETTERS = re.compile(r"[A-Z].*[A-Z]")
_CAMEL = re.compile(r"^[a-z]+(?:[A-Z][a-z0-9]*)+$")
_SNAKE = re.compile(r"^\w+_\w+$")
_DOTTED = re.compile(r"^[A-Za-z_][\w\-]*(?:\.[A-Za-z_][\w\-]*)+$")
_SPLIT_IDENTIFIER = re.compile(r"[._]")

# --- 표기 정책 → 붙일 수 있는 형태소 ----------------------------------------
#
# `(핵 앞에 붙일 것, 핵 뒤에 붙일 것)`. 값은 `morphology.SURFACE_*` 가 정한다 —
# **표 하나만 고치면 정책이 바뀐다.**
_GLUE: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    mp.SURFACE_CORE: (frozenset(), frozenset()),
    mp.SURFACE_PREFIXED: (mp.NOUN_PREFIX, frozenset()),
    mp.SURFACE_WORD: (mp.NOUN_PREFIX, mp.NOUN_SUFFIX),
}


# --- 토큰화 -----------------------------------------------------------------


def tokenize(
    text: str | None,
    lang: str | None,
    *,
    lexicon: Lexicon,
    options: TokenizeOptions | None = None,
) -> list[Token]:
    """텍스트 → 토큰. 순서를 유지하고, 구간 경계를 `boundary_after` 로 표시한다.

    줄바꿈은 경계다 — [03 §4] 의 정제가 문장 경계 정보로 줄바꿈 하나를 남겨 둔 이유가
    이것이다. 문단이 바뀌는 자리를 넘어 n-gram 을 만들면 문장 조각이 된다.
    """
    if not text:
        return []
    opts = options or TokenizeOptions()
    builder = _Builder(lexicon)
    if lang == EN:
        _latin_text(text, builder, options=opts)
    else:
        _korean_text(text, builder, options=opts)
    return builder.tokens()


# --- 한국어 경로 -------------------------------------------------------------


def _korean_text(text: str, builder: "_Builder", *, options: TokenizeOptions) -> None:
    analyzer = mp.analyzer_for(options.analyzer)
    lines = text.split("\n")
    for line, morphs in zip(lines, analyzer.analyze(lines)):
        _emit_line(line, morphs, builder, options=options)
        builder.boundary()


def _emit_line(
    line: str, morphs: Sequence[mp.Morph], builder: "_Builder", *, options: TokenizeOptions
) -> None:
    """형태소 목록 → 토큰. **명사 단위로 묶고, 묶이지 않은 형태소는 모두 경계다.**

    "묶이지 않은 것이 경계" 라는 한 줄이 옛 코드의 접미 표 · 문턱 · 보호어 예외를 전부
    대신한다. 조사가 남을 자리도, 어미가 어간을 남길 자리도 없다.
    """
    glue_before, glue_after = _GLUE[options.surface_policy]
    index = 0
    while index < len(morphs):
        morph = morphs[index]
        if morph.tag == mp.HASHTAG_TAG:
            builder.hashtag(line[morph.start : morph.end])
            index += 1
            continue
        if morph.tag not in mp.NOUN_CORE and morph.tag not in glue_before:
            builder.boundary()
            index += 1
            continue
        end, next_index, proper = _unit(
            morphs, index, glue_before=glue_before, glue_after=glue_after
        )
        if end is None:
            # 핵 없이 접두사만 있었다. 한 칸만 넘긴다 — 뒤를 통째로 버리면 낱말이 사라진다.
            builder.boundary()
            index += 1
            continue
        _emit_unit(line[morph.start : end], builder, options=options, proper=proper)
        index = next_index


def _unit(
    morphs: Sequence[mp.Morph],
    start: int,
    *,
    glue_before: frozenset[str],
    glue_after: frozenset[str],
) -> tuple[int | None, int, bool]:
    """`morphs[start]` 에서 시작하는 명사 단위 → `(표기의 끝, 다음 형태소 번호, 고유명사 여부)`.

    **공백이 있으면 끊는다.** 형태소가 원문에서 바로 이어 붙어 있을 때만 한 표기로 본다 —
    `개발자`+`경험` 은 `개발자경험` 이지만 `테일러드` `재킷` 은 두 토큰이고, 그 둘을 잇는
    것은 구간과 n-gram 의 일이다 ([04 §3]). 여기서 붙이면 원문에 없는 공백이 표기에 들어간다.
    """
    end: int | None = None
    proper = False
    index = start
    while index < len(morphs):
        morph = morphs[index]
        if index > start and morph.start != morphs[index - 1].end:
            break
        if morph.tag in mp.NOUN_CORE:
            end = morph.end
            proper = proper or morph.tag == mp.PROPER_NOUN
        elif end is None and morph.tag in glue_before:
            pass  # 접두사는 핵 앞에서만
        elif end is not None and morph.tag in glue_after:
            end = morph.end
        else:
            break
        index += 1
    return end, index, proper


def _emit_unit(
    surface: str, builder: "_Builder", *, options: TokenizeOptions, proper: bool = False
) -> None:
    if _HAS_HANGUL.search(surface):
        builder.token(surface, HANGUL, proper=proper)
        return
    # 한글이 없으면 영문 분류기가 종류를 정한다 — 분석기는 `SL`·`SN` 까지만 안다.
    # 라틴 표기의 고유명사 여부는 태그로 보지 않는다 — `batch.py` 가 표기에서 직접 본다.
    for token_surface, kind in _classify_latin(surface, options):
        builder.token(token_surface, kind)


# --- 영문 경로 ---------------------------------------------------------------


def _latin_text(text: str, builder: "_Builder", *, options: TokenizeOptions) -> None:
    for line in text.split("\n"):
        for match in _SCAN.finditer(line):
            raw = match.group(0)
            if raw.startswith("#") and len(raw) > 1:
                builder.hashtag(raw)
                continue
            if not (raw[0].isalnum() or raw[0] == "_"):
                # 구두점 · 기호 한 글자. 토큰이 아니고 경계다.
                builder.boundary()
                continue
            surface, trailing_punct = _clean(raw)
            if not surface:
                builder.boundary()
                continue
            for token_surface, kind in _classify_latin(surface, options):
                builder.token(token_surface, kind)
            if trailing_punct:
                builder.boundary()
        builder.boundary()


def _clean(raw: str) -> tuple[str, bool]:
    """`(표기, 꼬리 구두점을 뗐는가)`. 뗐으면 문장 부호가 토큰에 붙어 있던 것이라 경계다 —
    `build. useEffect` 에서 `build useEffect` 라는 n-gram 이 나오면 안 된다."""
    text = _LEADING_PUNCT.sub("", raw)
    trimmed = _TRAILING_PUNCT.sub("", text)
    return _POSSESSIVE.sub("", trimmed), trimmed != text


def _classify_latin(surface: str, options: TokenizeOptions) -> list[tuple[str, str]]:
    """영문·숫자 토큰 하나 → `(표기, 종류)` 목록. 코드 식별자 규칙이 꺼져 있으면 쪼개진다."""
    if _NUMBER.match(surface):
        return [(surface, NUMBER)]
    if _VERSION.match(surface):
        return [(surface, VERSION)]
    if _ACRONYM.match(surface) and _TWO_LETTERS.search(surface):
        return [(surface, ACRONYM)]
    is_identifier = bool(_CAMEL.match(surface) or _SNAKE.match(surface) or _DOTTED.match(surface))
    if is_identifier:
        if options.code_identifiers:
            return [(surface, CODE)]
        # 패션 도메인 — `.`·`_` 로 쪼개 보통 단어로 본다 ([04 §8] "잡음만 는다").
        parts = [part for part in _SPLIT_IDENTIFIER.split(surface) if part]
        if len(parts) > 1:
            return [pair for part in parts for pair in _classify_latin(part, options)]
    return [(surface, WORD)]


class _Builder:
    """토큰을 모으고 경계를 앞 토큰에 붙인다. 경계는 토큰이 아니다."""

    def __init__(self, lexicon: Lexicon) -> None:
        self._lexicon = lexicon
        # [surface, kind, is_stop, boundary_after, is_proper]
        self._tokens: list[list] = []

    def token(self, surface: str, kind: str, *, proper: bool = False) -> None:
        key = normalized_key(surface)
        # 한 글자 영문(`F/W` 의 `F`, `-f` 의 `f`)은 후보가 못 되고 n-gram 에 끼면 `w 런웨이` 같은
        # 조각을 만든다. 한글 한 음절이 경계가 되는 것과 같은 처리다.
        if not key or (len(key) < 2 and not _HAS_HANGUL.search(key)):
            self.boundary()
            return
        # **비교키 하나만 대조한다.** 옛 코드는 조사를 뗀 어간까지 두드렸는데(`컬러의` →
        # `컬러`), 이제 분석기가 조사를 떼고 나서 오므로 그럴 일이 없다 ([04 §5]).
        self._tokens.append([surface, kind, self._lexicon.is_stopword(key), False, proper])

    def hashtag(self, raw: str) -> None:
        # 해시태그는 홀로 선다 — 앞뒤 모두 경계. `new #vibecoding trend` 에서
        # `new #vibecoding` 이라는 n-gram 은 의미가 없다.
        self.boundary()
        surface, _ = _clean(raw)
        if len(surface) > 1:
            self._tokens.append([surface, HASHTAG, False, True, False])

    def boundary(self) -> None:
        if self._tokens:
            self._tokens[-1][3] = True

    def tokens(self) -> list[Token]:
        return [
            Token(surface, kind, stop, boundary, proper)
            for surface, kind, stop, boundary, proper in self._tokens
        ]


def doc_length(tokens: Sequence[Token]) -> int:
    """BM25 의 문서 길이.

    **뜻이 달라졌다.** 옛 토크나이저는 조사를 뗀 어절을 전부(불용어까지) 냈으므로 이 값이
    어절 수에 가까웠는데, 이제 명사만 남으므로 **명사 토큰 수**다. BM25 는 이 값을 코퍼스
    평균과의 비로만 쓰므로(`scoring.bm25`) 축이 같이 줄어드는 것은 문제가 아니다. 다만
    `pl_batch_stat` 의 옛 실행과 절대값을 비교하면 안 된다.
    """
    return len(tokens)
