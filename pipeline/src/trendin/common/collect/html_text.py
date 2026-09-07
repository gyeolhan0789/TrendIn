"""본문 HTML 을 평문으로 (설계 문서 #5.3 의 `body_text`).

규칙은 실측에서 나왔다 (2026-09-03, 5소스 피드 본문 태그 집계).

- `script`(8건 실재)·`style`·`svg`·`canvas` 는 안의 텍스트까지 버린다.
- `figcaption`(214건) 도 버린다. 표본 12/12 가 `Getty Images`·`@인스타핸들` 같은 사진
  크레딧이라 기사 문장이 아니고, 키워드 추출에 들어가면 통신사 이름이 트렌드로 올라온다.
  raw 에는 남아 있으니 나중에 필요하면 다시 뽑는다(불변식 8).
- `p`·`div`·`h1~h6`·`li`·`blockquote`·`br` 은 문단 경계로 본다.

목록 페이지 어댑터(164)가 기사 페이지 본문에 같은 규칙을 쓴다 — `within_class` 로
`div.atc_body` 안만 넘긴다.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

DROP_TAGS = frozenset({"script", "style", "svg", "canvas", "figcaption"})
BLOCK_TAGS = frozenset({"p", "div", "br", "li", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6"})

_BREAK = "\x00"
_WS = re.compile(r"\s+")


class _TextExtractor(HTMLParser):
    """`within_class` 안쪽만 읽고, `drop_classes` 서브트리는 통째로 버린다.

    구간을 찾을 때 전체 깊이가 아니라 **그 요소와 같은 이름의 태그만** 센다. 실측 페이지에는
    닫히지 않은 `<p>` 가 흔한데, 전체 깊이로 세면 그런 태그 하나에 구간 끝이 밀린다.
    """

    def __init__(
        self, within_class: str | None = None, drop_classes: frozenset[str] = frozenset()
    ) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._within = within_class
        self._drop_classes = drop_classes
        self._tag: str | None = None  # 구간을 연 태그 이름
        self._open = 0  # 그 이름으로 열려 있는 개수
        self._done = False  # 구간이 닫혔다. 뒤는 안 본다
        self._drop_tag: str | None = None  # 버리는 중인 서브트리의 태그 이름
        self._drop_open = 0

    @property
    def _reading(self) -> bool:
        return (self._within is None or self._open > 0) and self._drop_tag is None

    def _count_open(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """구간 태그 세기. 버리는 중에도 세야 짝이 맞는다."""
        if self._within is None or self._done:
            return
        if self._open == 0:
            if self._within in (dict(attrs).get("class") or "").split():
                self._tag, self._open = tag, 1
        elif tag == self._tag:
            self._open += 1

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._count_open(tag, attrs)
        if self._drop_tag is not None:
            if tag == self._drop_tag:
                self._drop_open += 1
            return
        classes = (dict(attrs).get("class") or "").split()
        if tag in DROP_TAGS or self._drop_classes.intersection(classes):
            self._drop_tag, self._drop_open = tag, 1
            return
        if self._reading and tag in BLOCK_TAGS:
            self.parts.append(_BREAK)

    def handle_endtag(self, tag: str) -> None:
        if self._drop_tag is not None:
            if tag == self._drop_tag:
                self._drop_open -= 1
                if self._drop_open == 0:
                    self._drop_tag = None
        elif self._reading and tag in BLOCK_TAGS:
            self.parts.append(_BREAK)
        if self._open > 0 and tag == self._tag:
            self._open -= 1
            if self._open == 0:
                self._done = True

    def handle_data(self, data: str) -> None:
        if self._reading:
            self.parts.append(data)


def html_to_text(
    html: str,
    *,
    within_class: str | None = None,
    drop_classes: frozenset[str] = frozenset(),
) -> str:
    """태그를 벗기고 문단 경계를 빈 줄로 남긴다. 빈 입력이면 빈 문자열.

    `within_class` 는 그 class 를 단 첫 요소의 안쪽만 읽게 하고, `drop_classes` 는 그 안에
    섞인 서브트리를 통째로 버린다. 기사 페이지 전체를 넣으면 네비게이션까지 딸려 오고,
    본문 컨테이너 안에도 기사 문장이 아닌 것이 섞여 있어서 둘 다 필요하다 (① 2026-09-03
    실측: `atc_body_cont` 안에 로그인 마스크와 관련기사 목록이 들어 있다).
    """
    if not html:
        return ""
    parser = _TextExtractor(within_class, drop_classes)
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
