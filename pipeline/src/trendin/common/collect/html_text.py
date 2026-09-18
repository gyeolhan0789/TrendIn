"""본문 HTML 을 **HTML 조각**으로 (설계 문서 #5.3 의 `body_text`·`summary`, S15P21A102-285).

수집은 잡음만 걷어내고 나머지 마크업은 남긴다. 태그 제거·엔티티 디코드·공백 정리는 Spark 가
한다(#5.3 "본문을 누가 어디까지 정제하나"). 전에는 여기서 태그를 벗긴 평문을 냈고, Spark 가
그 평문을 HTML 로 보고 한 번 더 벗겨서 `영화 <문라이트(Moonlight)>를` 이 `영화  를` 이 됐다.
그래서 **텍스트 안의 `<` `&` 는 다시 이스케이프한다** — 파서가 읽으면서 `&lt;` 를 `<` 로
풀어 버리기 때문이다.

버리는 규칙은 실측에서 나왔다 (2026-09-03, 5소스 피드 본문 태그 집계).

- `script`(8건 실재)·`style`·`svg`·`canvas` 는 안의 텍스트까지 버린다.
- `figcaption`(214건) 도 버린다. 표본 12/12 가 `Getty Images`·`@인스타핸들` 같은 사진
  크레딧이라 기사 문장이 아니고, 키워드 추출에 들어가면 통신사 이름이 트렌드로 올라온다.
  raw 에는 남아 있으니 나중에 필요하면 다시 뽑는다(불변식 8).
- 주석·`<!DOCTYPE>` 같은 선언은 조각에 싣지 않는다.

목록 페이지 어댑터(164)가 기사 페이지 본문에 같은 규칙을 쓴다 — `within_class` 로
`div.atc_body_cont` 안만 넘긴다. 피드 본문·ld+json·trafilatura 의 조각도 모두 여기를 지난다.
"""

from __future__ import annotations

from html import escape
from html.parser import HTMLParser

DROP_TAGS = frozenset({"script", "style", "svg", "canvas", "figcaption"})
# 닫는 태그가 없는 요소. 여는 태그만 적는다.
VOID_TAGS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "source",
        "track",
        "wbr",
    }
)


class _FragmentWriter(HTMLParser):
    """`within_class` 안쪽만 다시 적고, `drop_classes` 서브트리는 통째로 버린다.

    구간을 찾을 때 전체 깊이가 아니라 **그 요소와 같은 이름의 태그만** 센다. 실측 페이지에는
    닫히지 않은 `<p>` 가 흔한데, 전체 깊이로 세면 그런 태그 하나에 구간 끝이 밀린다.
    구간을 연 요소 자신은 적지 않는다 — 조각은 그 안쪽이다.
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

    def _count_open(self, tag: str, attrs: list[tuple[str, str | None]]) -> bool:
        """구간 태그 세기. 버리는 중에도 세야 짝이 맞는다. 구간을 막 열었으면 True."""
        if self._within is None or self._done:
            return False
        if self._open == 0:
            if self._within in (dict(attrs).get("class") or "").split():
                self._tag, self._open = tag, 1
                return True
        elif tag == self._tag:
            self._open += 1
        return False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._count_open(tag, attrs):
            return
        if self._drop_tag is not None:
            if tag == self._drop_tag:
                self._drop_open += 1
            return
        classes = (dict(attrs).get("class") or "").split()
        if tag in DROP_TAGS or self._drop_classes.intersection(classes):
            if tag not in VOID_TAGS:
                self._drop_tag, self._drop_open = tag, 1
            return
        if self._reading:
            self.parts.append(_start_tag(tag, attrs))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """`<br/>` 처럼 스스로 닫은 태그. 서브트리가 없으니 버리거나 적기만 한다."""
        if self._drop_tag is not None or tag in DROP_TAGS:
            return
        if self._drop_classes.intersection((dict(attrs).get("class") or "").split()):
            return
        if self._reading:
            self.parts.append(_start_tag(tag, attrs))

    def handle_endtag(self, tag: str) -> None:
        if self._drop_tag is not None:
            if tag == self._drop_tag:
                self._drop_open -= 1
                if self._drop_open == 0:
                    self._drop_tag = None
            self._count_close(tag)
            return
        if self._open > 0 and tag == self._tag and self._open == 1:
            self._count_close(tag)  # 구간을 연 요소의 닫는 태그는 적지 않는다
            return
        if self._reading and tag not in VOID_TAGS:
            self.parts.append(f"</{tag}>")
        self._count_close(tag)

    def _count_close(self, tag: str) -> None:
        if self._open > 0 and tag == self._tag:
            self._open -= 1
            if self._open == 0:
                self._done = True

    def handle_data(self, data: str) -> None:
        if self._reading:
            self.parts.append(escape(data, quote=False))


def _start_tag(tag: str, attrs: list[tuple[str, str | None]]) -> str:
    rendered = "".join(
        f" {name}" if value is None else f' {name}="{escape(value, quote=True)}"'
        for name, value in attrs
    )
    return f"<{tag}{rendered}>"


def html_fragment(
    html: str,
    *,
    within_class: str | None = None,
    drop_classes: frozenset[str] = frozenset(),
) -> str:
    """잡음을 버린 HTML 조각. 글자가 하나도 없으면 빈 문자열.

    `within_class` 는 그 class 를 단 첫 요소의 안쪽만 적게 하고, `drop_classes` 는 그 안에
    섞인 서브트리를 통째로 버린다. 기사 페이지 전체를 넣으면 네비게이션까지 딸려 오고,
    본문 컨테이너 안에도 기사 문장이 아닌 것이 섞여 있어서 둘 다 필요하다 (① 2026-09-03
    실측: `atc_body_cont` 안에 로그인 마스크와 관련기사 목록이 들어 있다).

    평문을 넣어도 된다. `<` 뒤에 영문자가 오지 않으면 파서가 글자로 읽으므로 `<문라이트>` 는
    `&lt;문라이트&gt;` 로 남는다.
    """
    if not html:
        return ""
    parser = _FragmentWriter(within_class, drop_classes)
    parser.feed(html)
    parser.close()
    fragment = "".join(parser.parts).strip()
    return fragment if has_text(fragment) else ""


class _TextCounter(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.length = 0

    def handle_data(self, data: str) -> None:
        self.length += len("".join(data.split()))


def text_length(fragment: str) -> int:
    """조각의 글자 수. 공백은 세지 않는다."""
    counter = _TextCounter()
    counter.feed(fragment)
    counter.close()
    return counter.length


def has_text(fragment: str) -> bool:
    """태그만 있고 글자가 없는 조각(`<p></p>`)을 빈 것으로 가른다."""
    return text_length(fragment) > 0
