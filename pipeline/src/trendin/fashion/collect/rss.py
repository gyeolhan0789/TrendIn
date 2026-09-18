"""피드 어댑터 — RSS 2.0 · RSS 1.0 · Atom (설계 문서 확정 1·2, S15P21A102-284).

피드는 후보와 메타데이터(제목·발행일·분류·저자)를 준다. `discover` 는 guid 만 뽑는 값싼
경로고, 기사 페이지를 받아 본문을 뽑는 무거운 일은 `materialize` 로 미룬다. 그 사이에서
장부가 이미 받은 기사를 걸러 내면 매 주기 다시 받은 10건 중 새것만 페이지를 받는다.
raw 는 item 조각이 아니라 기사 페이지다(확정 2, S15P21A102-285).

파서는 `xml.parsers.expat` 을 네임스페이스 처리 없이 직접 쓴다. 2026-09-03 실측에서
vogue·gqkorea·allure 피드가 `xmlns:media` 선언 없이 `<media:thumbnail>` 을 써서
`ElementTree` 가 `unbound prefix` 로 파싱을 거부했다. expat 은 prefix 를 이름의 일부로
취급해 6/6 을 읽었고, `CurrentByteIndex` 가 item 의 바이트 구간까지 정확히 짚었다.

**형식은 조각의 모양으로 가른다.** `<entry>` 면 Atom, `rdf:about` 을 단 `<item>` 이면 RSS 1.0,
나머지 `<item>` 은 RSS 2.0 이다. 프로필 칸으로 두지 않는 이유는 `materialize` 가 조각만 받기
때문이다 — 피드 전체를 다시 볼 수 없다. 형식마다 필드 이름이 다른 것은 아래 `_FORMATS` 한
표가 흡수한다. article_id·발행일은 표가 아니라 프로필의 규칙이 정한다(`source-discovery.md`
#3.2) — 대체 순서를 코드에 숨기지 않는다.
"""

from __future__ import annotations

import hashlib
import logging
import re
import xml.parsers.expat as expat
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Callable
from urllib.parse import parse_qs, urlsplit

from trendin.common.collect.article import Article
from trendin.common.collect.body import decode_page, extract_body
from trendin.common.collect.contracts import Candidate, DiscoverResult, Failure, Rule, SourceDef
from trendin.common.collect.html_text import html_fragment
from trendin.common.collect.keys import raw_key
from trendin.common.collect.session import CollectSession
from trendin.common.collect.urls import clean_url

logger = logging.getLogger("trendin.collect.rss")

# 한 기사를 담는 요소. RSS 2.0 과 1.0 은 `item`, Atom 은 `entry` 다.
_ENTRY_NAMES = ("item", "entry")

GUID_HASH_LENGTH = 16


class FeedParseError(Exception):
    """피드를 파싱하지 못했다."""


def iter_item_spans(body: bytes) -> list[tuple[int, int]]:
    """응답 원본에서 `<item>`·`<entry>` 조각의 바이트 구간을 짚는다.

    파싱 후 재직렬화하면 속성 순서·공백·엔티티가 바뀌어 "받은 바이트 그대로"(불변식 8)가
    아니게 된다. 그래서 원본을 자른다.
    """
    parser = expat.ParserCreate()  # 네임스페이스 처리 없음 — 선언 없는 prefix 를 견딘다
    spans: list[tuple[int, int]] = []
    starts: list[tuple[str, int]] = []

    def on_start(name: str, _attrs: dict[str, str]) -> None:
        if name in _ENTRY_NAMES:
            starts.append((name, parser.CurrentByteIndex))

    def on_end(name: str) -> None:
        if name in _ENTRY_NAMES and starts:
            _name, begin = starts.pop()
            close_tag = f"</{name}>".encode()
            close = body.index(close_tag, parser.CurrentByteIndex)
            spans.append((begin, close + len(close_tag)))

    parser.StartElementHandler = on_start
    parser.EndElementHandler = on_end
    try:
        parser.Parse(body, True)
    except expat.ExpatError as exc:
        raise FeedParseError(f"피드 파싱 실패: {exc}") from exc
    return spans


@dataclass
class Entry:
    """조각 하나를 읽은 것. 형식을 모르는 날것이다 — 이름 풀이는 `_FORMATS` 가 한다."""

    name: str  # 조각 루트 요소 이름
    attrs: dict[str, str]  # 루트 요소의 속성 (RSS 1.0 의 `rdf:about`)
    # 직계 자식은 이름으로, 손자는 `부모/자식` 으로. `<category>` 처럼 반복되면 다 담는다.
    texts: dict[str, list[str]] = field(default_factory=dict)
    # 직계 자식의 속성. Atom 의 `<link href>`·`<category term>` 이 여기 있다.
    child_attrs: dict[str, list[dict[str, str]]] = field(default_factory=dict)

    def first(self, name: str) -> str:
        values = self.texts.get(name)
        return values[0] if values else ""


def parse_item(fragment: bytes) -> Entry:
    parser = expat.ParserCreate()
    path: list[str] = []
    buffers: list[list[str]] = []
    entry: Entry | None = None

    def on_start(name: str, attrs: dict[str, str]) -> None:
        nonlocal entry
        path.append(name)
        buffers.append([])
        if len(path) == 1:
            entry = Entry(name, dict(attrs))
        elif len(path) == 2:
            entry.child_attrs.setdefault(name, []).append(dict(attrs))

    def on_chars(data: str) -> None:
        if len(path) >= 2:
            # 손자 이하의 글자도 자식의 글자다 — 지금까지 `content:encoded` 를 읽던 방식 그대로
            for buffer in buffers[1:]:
                buffer.append(data)

    def on_end(_name: str) -> None:
        depth = len(path)
        text = "".join(buffers.pop())
        if depth in (2, 3):
            entry.texts.setdefault("/".join(path[1:]), []).append(text)
        path.pop()

    parser.StartElementHandler = on_start
    parser.CharacterDataHandler = on_chars
    parser.EndElementHandler = on_end
    try:
        parser.Parse(fragment, True)
    except expat.ExpatError as exc:
        raise FeedParseError(f"item 조각 파싱 실패: {exc}") from exc
    return entry


@dataclass(frozen=True, slots=True)
class _Format:
    guid: Callable[[Entry], str]
    link: Callable[[Entry], str]
    body: str
    summary: str
    categories: Callable[[Entry], list[str]]
    author: Callable[[Entry, SourceDef], str]


def _atom_link(entry: Entry) -> str:
    """rel 이 없거나 `alternate` 인 첫 링크가 기사 주소다 (RFC 4287 4.2.7.2)."""
    for attrs in entry.child_attrs.get("link", []):
        if attrs.get("rel", "alternate") == "alternate" and attrs.get("href"):
            return attrs["href"]
    return ""


_FORMATS = {
    "rss20": _Format(
        guid=lambda e: e.first("guid"),
        link=lambda e: e.first("link"),
        body="content:encoded",
        summary="description",
        categories=lambda e: e.texts.get("category", []),
        author=lambda e, source: e.first(source.author_field),
    ),
    "rss10": _Format(
        guid=lambda e: e.attrs.get("rdf:about", ""),
        link=lambda e: e.first("link"),
        body="content:encoded",
        summary="description",
        categories=lambda e: e.texts.get("dc:subject", []),
        author=lambda e, _source: e.first("dc:creator"),
    ),
    "atom": _Format(
        guid=lambda e: e.first("id"),
        link=_atom_link,
        body="content",
        summary="summary",
        categories=lambda e: [a.get("term", "") for a in e.child_attrs.get("category", [])],
        author=lambda e, _source: e.first("author/name"),
    ),
}


def feed_format(entry: Entry) -> str:
    if entry.name == "entry":
        return "atom"
    return "rss10" if "rdf:about" in entry.attrs else "rss20"


def article_id_from_guid(guid: str, param: str) -> str:
    """guid 는 `https://www.vogue.co.kr/?p=857991` 꼴이다.

    URL 슬러그는 쓰지 않는다 — 제목이 바뀌면 슬러그도 바뀐다.
    """
    values = parse_qs(urlsplit(guid).query).get(param, [])
    if not values or not values[0].isdigit():
        raise ValueError(f"guid 에서 {param!r} 숫자를 못 뽑았다: {guid!r}")
    return values[0]


# `url_path_segment` 가 내는 조각은 객체 키와 이벤트 id(`{source}-{article_id}`)에 그대로 들어간다.
# 퍼센트 인코딩·점·공백이 섞이면 키가 소스마다 다르게 깨지므로 좁게 받는다.
_SEGMENT = re.compile(r"[A-Za-z0-9_-]+")


def article_id_from_path(link: str, position: int) -> str:
    """link 경로를 `/` 로 나눈 빈칸 아닌 조각 중 `position` 번째다. 음수는 뒤에서 센다.

    `https://www.harpersbazaar.com/fashion/trends/a73617426/best-suede-bags/` 는 `-2` 로
    `a73617426` 이다. 경로 깊이가 섹션마다 달라도 id 가 끝에서 두 번째라 뒤에서 센다.
    """
    segments = [s for s in urlsplit(link).path.split("/") if s]
    try:
        segment = segments[position]
    except IndexError:
        raise ValueError(f"link 경로에 {position} 번째 조각이 없다: {link!r}") from None
    if not _SEGMENT.fullmatch(segment):
        raise ValueError(f"경로 조각이 id 로 못 쓰는 모양이다: {segment!r} ({link!r})")
    return segment


def article_id_by_rule(rule: Rule, guid: str, link: str) -> str:
    if rule.name == "guid_query_param":
        return article_id_from_guid(guid, rule.param)
    if rule.name == "url_path_segment":
        return article_id_from_path(link, rule.param)
    if rule.name == "guid_hash":
        # 앞뒤 공백만 벗긴다. guid 는 URL 이 아닐 수 있어 URL 정리를 하지 않는다.
        # 비었을 때 link 로 넘어가지 않는다 — 그런 소스는 규칙을 따로 둔다 (#3.2).
        stripped = guid.strip()
        if not stripped:
            raise ValueError("guid 가 비어 guid_hash 를 만들 수 없다")
        return hashlib.sha256(stripped.encode("utf-8")).hexdigest()[:GUID_HASH_LENGTH]
    raise ValueError(f"모르는 article_id 규칙이다: {rule.name!r}")


# 발행일 규칙 → (읽는 요소, 날짜 형식). 대체 순서는 없다 (#3.2).
_DATE_RULES = {
    "rss_pubdate": ("pubDate", "rfc822"),
    "dc_date": ("dc:date", "iso8601"),
    "atom_published": ("published", "iso8601"),
    "atom_updated": ("updated", "iso8601"),
}


def published_by_rule(rule: Rule, entry: Entry) -> datetime | None:
    element, form = _DATE_RULES[rule.name]
    raw = entry.first(element).strip()
    if not raw:
        return None
    try:
        if form == "rfc822":
            parsed = parsedate_to_datetime(raw)
        else:
            parsed = datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo is not None else None


class RssAdapter:
    """소스 하나의 카테고리 피드를 읽는다. 저장·발급·중복 판정은 모른다."""

    def __init__(
        self,
        source: SourceDef,
        session: CollectSession,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if source.article_id is None or source.published_at is None:
            raise ValueError(f"{source.key}: 피드 소스에 article_id·published_at 규칙이 없다")
        self.source = source
        self._session = session
        self._now = now or (lambda: datetime.now(timezone.utc))

    def page_url(self, page: int | None) -> str:
        if page is None:
            return self.source.discover_url
        if self.source.page_param is None:
            # 모르는 피드에 페이지 파라미터를 붙여 치면, 무시당해 같은 첫 페이지를 받거나
            # 엉뚱한 응답을 받는다. 어느 쪽이든 과거분인 척 넘어간다.
            raise ValueError(f"{self.source.key}: 페이지 넘김이 안 되는 피드다 (page_param 없음)")
        separator = "&" if "?" in self.source.discover_url else "?"
        return f"{self.source.discover_url}{separator}{self.source.page_param}={page}"

    def discover(self, page: int | None = None) -> DiscoverResult:
        url = self.page_url(page)
        response = self._session.get(url)
        if response.not_modified:
            logger.info("%s: 304, 피드가 안 바뀌었다 (%s)", self.source.key, url)
            return DiscoverResult(not_modified=True)

        collected_at = self._now()
        body = response.body
        candidates: list[Candidate] = []
        failures: list[Failure] = []
        for begin, end in iter_item_spans(body):
            fragment = body[begin:end]
            entry = parse_item(fragment)
            shape = _FORMATS[feed_format(entry)]
            guid = shape.guid(entry)
            link = clean_url(shape.link(entry).strip())
            try:
                article_id = article_id_by_rule(self.source.article_id, guid, link)
            except ValueError as exc:
                logger.warning("%s: 후보가 못 됐다 — %s", self.source.key, exc)
                failures.append(Failure(self.source.key, "discover", guid or link or "?", str(exc)))
                continue
            candidates.append(
                Candidate(
                    source=self.source.key,
                    article_id=article_id,
                    url=link,
                    raw=fragment,
                    raw_ext="xml",
                    collected_at=collected_at,
                    published_at=published_by_rule(self.source.published_at, entry),
                )
            )
        logger.info(
            "%s: 후보 %d건, 실패 %d건 (%s)", self.source.key, len(candidates), len(failures), url
        )
        return DiscoverResult(candidates, failures)

    def materialize(self, candidate: Candidate) -> tuple[bytes, Article]:
        """기사 페이지를 받아 raw 와 article.json 을 만든다 (확정 2, S15P21A102-285).

        피드가 전문을 줘도 페이지를 받는다 — 전문인지 요약인지 기사마다 가를 수 없어서다
        (2026-09-16 실측: Dazed·BoF·Drapers·GlobeNewswire 가 요약을 본문 칸에 넣는다).
        제목·발행일·분류·저자는 item 조각에서 읽고, raw 는 받은 기사 페이지다.

        페이지를 못 받으면 예외를 올려 그 기사만 실패로 빠진다. 장부에 안 적혔으니 피드에
        남아 있는 동안 다음 주기에 다시 후보가 된다. 403·429 는 세션이 `HostBlocked` 로
        올려 그 실행의 소스를 멈춘다(불변식 2).
        """
        if candidate.published_at is None:
            raise ValueError(f"발행일이 없어 키를 만들 수 없다: {candidate.article_id}")
        allowed = self.source.allowed_url_prefixes
        if allowed and not candidate.url.startswith(allowed):
            # 세션도 막지만 거기선 소스 전체를 멈추는 예외다. 링크 하나로 멈추지 않게 먼저 거른다.
            raise ValueError(f"기사 링크가 허용 범위 밖이다: {candidate.url}")

        entry = parse_item(candidate.raw)
        shape = _FORMATS[feed_format(entry)]

        response = self._session.get(candidate.url, conditional=False)
        if response.status != 200:
            # 세션은 리다이렉트를 따라가지 않는다(허용 범위 검사를 건너뛰게 되므로).
            raise ValueError(f"기사 페이지가 {response.status} 다: {candidate.url}")
        raw = response.body
        collected_at = self._now()  # 원문을 받은 시각은 여기다 (#5.3)
        page = extract_body(decode_page(raw), url=candidate.url, feed_body=entry.first(shape.body))
        if page.paywalled:
            # 본문도 raw 도 저장하지 않는다. HTML 에 본문이 실려 와도 같다 (불변식 2).
            logger.info("%s: 유료 표시 — 본문 제외 %s", self.source.key, candidate.article_id)
        elif page.body_text is None:
            logger.warning(
                "%s: 본문이 비었다 — article_id=%s", self.source.key, candidate.article_id
            )

        article = Article(
            domain=self.source.domain,
            source=self.source.key,
            route=self.source.route,
            article_id=candidate.article_id,
            url=candidate.url,
            title=entry.first("title").strip(),
            published_at=candidate.published_at,
            collected_at=collected_at,
            raw_key=(
                None
                if page.paywalled
                else raw_key(
                    self.source.domain,
                    self.source.key,
                    self.source.route,
                    candidate.published_at,
                    candidate.article_id,
                    ext="html",
                )
            ),
            content_sha256=None if page.paywalled else hashlib.sha256(raw).hexdigest(),
            # HTML 로 보이는 description 도 버리지 않는다 — 본문과 같은 조각 규칙을 지난다(#5.3).
            summary=html_fragment(entry.first(shape.summary)) or None,
            body_text=page.body_text,
            categories=[c.strip() for c in shape.categories(entry) if c.strip()],
            author=shape.author(entry, self.source).strip() or None,
            paywalled=page.paywalled or None,
        )
        return raw, article
