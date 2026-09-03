"""본문 HTML 을 평문으로 (설계 문서 #5.3 의 `body_text`).

규칙은 실측에서 나왔다 (2026-09-03, 5소스 피드 본문 태그 집계).

- `script`(8건 실재)·`style`·`svg`·`canvas` 는 안의 텍스트까지 버린다.
- `figcaption`(214건) 도 버린다. 표본 12/12 가 `Getty Images`·`@인스타핸들` 같은 사진
  크레딧이라 기사 문장이 아니고, 키워드 추출에 들어가면 통신사 이름이 트렌드로 올라온다.
  raw 에는 남아 있으니 나중에 필요하면 다시 뽑는다(불변식 8).
- `p`·`div`·`h1~h6`·`li`·`blockquote`·`br` 은 문단 경계로 본다.

목록 페이지 어댑터(164)가 기사 페이지 본문에 같은 규칙을 쓴다.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

DROP_TAGS = frozenset({"script", "style", "svg", "canvas", "figcaption"})
BLOCK_TAGS = frozenset({"p", "div", "br", "li", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6"})

_BREAK = "\x00"
_WS = re.compile(r"\s+")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._dropping: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in DROP_TAGS:
            self._dropping.append(tag)
            return
        if self._dropping:
            return
        if tag in BLOCK_TAGS:
            self.parts.append(_BREAK)

    def handle_endtag(self, tag: str) -> None:
        if self._dropping:
            # 같은 이름끼리만 닫는다. 중첩 svg 처럼 겹쳐도 어긋나지 않는다.
            if self._dropping[-1] == tag:
                self._dropping.pop()
            return
        if tag in BLOCK_TAGS:
            self.parts.append(_BREAK)

    def handle_data(self, data: str) -> None:
        if self._dropping:
            return
        self.parts.append(data)


def html_to_text(html: str) -> str:
    """태그를 벗기고 문단 경계를 빈 줄로 남긴다. 빈 입력이면 빈 문자열."""
    if not html:
        return ""
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    blocks = []
    for chunk in "".join(parser.parts).split(_BREAK):
        # \s 는 유니코드 모드라 nbsp(U+00A0) 까지 잡는다.
        text = _WS.sub(" ", chunk).strip()
        if text:
            blocks.append(text)
    return "\n\n".join(blocks)


def looks_like_html(text: str) -> bool:
    """요약 자리에 본문 사본이 들어왔는지 가른다 (설계 문서 #5.3 의 `summary`)."""
    return bool(re.search(r"<[a-zA-Z][^>]*>", text or ""))
