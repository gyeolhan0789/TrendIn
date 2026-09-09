"""텍스트 정제 ([03 §4](../../../../spark/docs/03-normalization-spec.md)).

**입력은 HTML 이다.** `body_text` 의 출처가 피드의 `content:encoded`(rss 소스)이거나 기사
페이지의 `div.atc_body_cont`(listing 소스)라 마크업이 섞여 있다. 마크다운은 오지 않는다 —
커뮤니티 소스가 없다.

순서가 중요하다. 규격의 일곱 단계를 그대로 따른다:

```
1. 코드 블록 분리        <pre>, <code> → body_code
2. HTML 태그 제거        나머지 마크업 제거. 엔티티 디코드
3. 링크 처리             앵커 텍스트만 남기고 href 는 버린다
4. URL 제거              본문에 그대로 박힌 http(s)://...
5. 유니코드 정규화        NFKC
6. 제어문자 · 이모지 제거
7. 공백 정규화           연속 공백 → 하나, 앞뒤 트림
```

**1 이 2 보다 먼저인 이유** — 태그를 먼저 지우면 `<` 가 든 코드(`if (a < b)`)가 태그로
보여 함께 사라진다. **2 안에서 태그 제거가 엔티티 디코드보다 먼저인 이유** — 뒤집으면
본문에 적힌 `&lt;script&gt;` 가 진짜 태그가 되어 다음 단계에서 지워진다. 기사가 인용한
마크업이 조용히 없어진다.

**3 은 2 에서 저절로 따라온다.** 태그를 지우면 속성이 함께 사라지므로 `href` 는 남지 않고
앵커 텍스트만 남는다. 규격이 단계를 나눠 적은 것은 의도를 밝히려는 것이고, 여기서 따로
처리할 것은 없다 — 대신 그 의도가 유지되는지를 `test_normalize_text.py` 가 고정한다.

**pyspark 를 import 하지 않는다** ([09 §4] 층 1).
"""

from __future__ import annotations

import html
import re
import unicodedata

# 코드 블록. `<pre>` 와 `<code>` 를 함께 본다 — 소스가 둘을 섞어 쓴다. `[^>]*` 로 속성을
# 흘리고, 비탐욕(`*?`)으로 가장 가까운 닫는 태그까지만 먹는다. 탐욕으로 두면 블록이 둘
# 이상일 때 사이의 본문이 통째로 코드로 넘어간다.
_CODE_BLOCK = re.compile(r"<(pre|code)\b[^>]*>(.*?)</\1\s*>", re.IGNORECASE | re.DOTALL)

# 블록 태그. 지우면서 줄바꿈을 남긴다 — 그냥 지우면 문단 끝 단어와 다음 문단 첫 단어가
# 붙어 없는 토큰이 만들어진다 ([04] 의 n-gram 이 그걸 후보로 집는다).
_BLOCK_TAG = re.compile(
    r"</?(?:p|div|br|li|ul|ol|h[1-6]|tr|td|th|table|section|article|blockquote|figure"
    r"|figcaption|header|footer|hr)\b[^>]*>",
    re.IGNORECASE,
)

# 내용까지 통째로 버리는 태그. 태그만 지우면 스크립트 본문이 텍스트로 남는다.
_DROPPED_ELEMENT = re.compile(
    r"<(script|style|noscript|iframe|svg)\b[^>]*>.*?</\1\s*>", re.IGNORECASE | re.DOTALL
)

# 주석. 소스 템플릿의 흔적이 그대로 실려 오는 경우가 있다.
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)

# 나머지 태그 전부. 여기서 속성이 사라지므로 `href` 도 함께 사라진다 (위 3 번).
_ANY_TAG = re.compile(r"<[^>]*>")

# 본문에 그대로 박힌 URL. 스킴이 있는 것만 지운다 — `www.` 로 시작하는 조각까지 지우면
# 브랜드명이 든 문장이 잘린다.
_BARE_URL = re.compile(r"https?://\S+", re.IGNORECASE)

# 제어문자. 탭·줄바꿈은 공백 정규화가 처리하므로 여기서 빼둔다.
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# 유니코드 카테고리로 지우는 것 — 서식(Cf, ZWJ·BOM 등) · 사용자 영역(Co) · 서러게이트(Cs).
# `Cn`(미할당)은 지우지 않는다. 새 유니코드 버전에서 할당된 문자를 옛 파이썬이 미할당으로
# 보는 일이 있어서, 그걸 지우면 최신 이모지가 아니라 새 문자가 사라진다.
_DROPPED_CATEGORIES = frozenset({"Cf", "Co", "Cs"})

# 이모지. NFKC 로는 사라지지 않아 범위로 지운다. 패션 매체 본문에 실제로 섞여 온다.
#
# 눈에 보이지 않는 문자(변형 선택자·키캡)는 반드시 이스케이프로 적는다. 리터럴로 두면
# 편집기에서 지워지거나 복사에서 빠져도 아무 표시가 없다.
_EMOJI = re.compile(
    "["
    "\U0001f300-\U0001faff"  # 기호·그림문자 · 확장
    "\U0001f000-\U0001f2ff"  # 마작·카드·둘러싸인 문자
    "\u2600-\u27bf"  # 기타 기호 · 딩벳
    "\ufe0f"  # 이모지 변형 선택자
    "\u20e3"  # 키캡 결합 문자
    "]",
    re.UNICODE,
)

_WHITESPACE = re.compile(r"[^\S\n]+")
_BLANK_LINES = re.compile(r"\n{2,}")


def split_code(raw: str | None) -> tuple[str, str]:
    """`(코드를 뺀 HTML, 코드 블록)`. 단계 1.

    코드를 **버리지 않고 따로 보관하는 이유** ([03 §4]) — 진짜 키워드(`kubectl`,
    `useEffect`)가 거기 있지만 변수명·경로·스택트레이스 같은 잡음이 훨씬 많아서, 본문에
    섞어두면 [04] 의 문서 빈도 통계가 오염된다. 다시 만들려면 객체부터 다시 읽어야 하므로
    버리지도 않는다.

    **지금 이 단계는 사실상 놀고 있다** — dev 도메인이 `hn` 하나이고 본문이 없다
    ([03 §2]). 패션 기사에 `<pre>` 가 있을 일은 드물다.
    """
    if raw is None or not raw.strip():
        return "", ""

    blocks: list[str] = []

    def _take(match: re.Match[str]) -> str:
        blocks.append(match.group(2))
        # 자리에 줄바꿈을 남긴다. 지워버리면 코드 앞뒤 문장이 붙는다.
        return "\n"

    body = _CODE_BLOCK.sub(_take, raw)
    # 코드 안의 마크업·엔티티도 씻는다. 안 하면 `&lt;div&gt;` 가 그대로 남아 [04] 에서
    # 후보로 올라온다.
    code = "\n".join(clean_text(block) for block in blocks if block.strip())
    return body, code


def strip_html(raw: str) -> str:
    """단계 2 — 태그를 지우고 엔티티를 디코드한다.

    순서: 내용까지 버릴 요소 → 주석 → 블록 태그(줄바꿈으로) → 나머지 태그 → 엔티티 디코드.
    디코드가 맨 뒤인 이유는 위 docstring 에 있다.
    """
    text = _DROPPED_ELEMENT.sub(" ", raw)
    text = _COMMENT.sub(" ", text)
    text = _BLOCK_TAG.sub("\n", text)
    text = _ANY_TAG.sub(" ", text)
    return html.unescape(text)


def _strip_marks(text: str) -> str:
    """단계 6 — 제어문자 · 서식 문자 · 이모지 제거."""
    text = _CONTROL.sub("", text)
    text = _EMOJI.sub("", text)
    return "".join(ch for ch in text if unicodedata.category(ch) not in _DROPPED_CATEGORIES)


def collapse_whitespace(text: str) -> str:
    """단계 7 — 연속 공백을 하나로, 앞뒤를 트림한다.

    줄바꿈은 하나까지 남긴다. 문장 경계 정보라 [04 §6] 의 위치 가중치가 쓴다 — 전부 공백
    하나로 접으면 제목 다음 첫 문단이 어디까지인지 알 수 없다.
    """
    text = _WHITESPACE.sub(" ", text)
    text = _BLANK_LINES.sub("\n", text)
    return "\n".join(line.strip() for line in text.split("\n")).strip()


def clean_text(raw: str | None) -> str:
    """단계 2~7. 코드 분리(단계 1)는 `split_code` 가 먼저 한다.

    **빈 문자열을 돌려주는 것이 정상 경로다.** 링크만 있고 텍스트가 없는 본문은 정제 후
    비고, 그건 [03 §6] 의 품질 필터가 걸러낸다 — 여기서 예외를 올리지 않는다.
    """
    if raw is None or not raw.strip():
        return ""

    text = strip_html(raw)
    text = _BARE_URL.sub(" ", text)
    # NFKC 가 전각 영문·호환 문자를 접는다. 이걸 안 하면 `ＡＩ` 와 `AI` 가 다른 후보가 된다.
    text = unicodedata.normalize("NFKC", text)
    text = _strip_marks(text)
    return collapse_whitespace(text)


def clean_title(raw: str | None) -> str:
    """제목 정제. 본문과 같은 규칙이되 줄바꿈을 공백으로 접는다.

    제목에 줄바꿈이 남으면 `contents.title` 이 화면에서 두 줄로 깨진다. 그리고 제목은
    문장 경계 정보가 필요 없다 — 통째로 하나의 위치 가중 단위다 ([04 §6]).
    """
    return clean_text(raw).replace("\n", " ").strip()
