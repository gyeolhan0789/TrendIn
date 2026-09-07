"""RSS 어댑터 (설계 문서 확정 1·2).

피드 하나가 발견과 취득을 동시에 끝낸다 — item 조각이 곧 raw 다. 그래서 `discover` 는
guid 만 뽑는 값싼 경로고, HTML 을 벗기는 무거운 일은 `materialize` 로 미룬다. 그 사이에서
장부가 이미 받은 기사를 걸러 내면 매 주기 다시 받은 10건 중 새것만 정규화된다.

파서는 `xml.parsers.expat` 을 네임스페이스 처리 없이 직접 쓴다. 2026-09-03 실측에서
vogue·gqkorea·allure 피드가 `xmlns:media` 선언 없이 `<media:thumbnail>` 을 써서
`ElementTree` 가 `unbound prefix` 로 파싱을 거부했다. expat 은 prefix 를 이름의 일부로
취급해 6/6 을 읽었고, `CurrentByteIndex` 가 item 의 바이트 구간까지 정확히 짚었다.
"""

from __future__ import annotations

import hashlib
import logging
import xml.parsers.expat as expat
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Callable
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit, urlunsplit

from trendin.common.collect.article import Article
from trendin.common.collect.contracts import Candidate, DiscoverResult, Failure, SourceDef
from trendin.common.collect.html_text import html_to_text, looks_like_html
from trendin.common.collect.keys import ROUTE_EXT, raw_key
from trendin.common.collect.session import CollectSession

logger = logging.getLogger("trendin.collect.rss")

_CLOSE = b"</item>"
TRACKING_PREFIXES = ("utm_",)
TRACKING_KEYS = frozenset({"fbclid", "gclid"})


class FeedParseError(Exception):
    """피드를 파싱하지 못했다."""


def iter_item_spans(body: bytes) -> list[tuple[int, int]]:
    """응답 원본에서 `<item>`…`</item>` 의 바이트 구간을 짚는다.

    파싱 후 재직렬화하면 속성 순서·공백·엔티티가 바뀌어 "받은 바이트 그대로"(불변식 8)가
    아니게 된다. 그래서 원본을 자른다.
    """
    parser = expat.ParserCreate()  # 네임스페이스 처리 없음 — 선언 없는 prefix 를 견딘다
    spans: list[tuple[int, int]] = []
    starts: list[int] = []

    def on_start(name: str, _attrs: dict[str, str]) -> None:
        if name == "item":
            starts.append(parser.CurrentByteIndex)

    def on_end(name: str) -> None:
        if name == "item" and starts:
            begin = starts.pop()
            close = body.index(_CLOSE, parser.CurrentByteIndex)
            spans.append((begin, close + len(_CLOSE)))

    parser.StartElementHandler = on_start
    parser.EndElementHandler = on_end
    try:
        parser.Parse(body, True)
    except expat.ExpatError as exc:
        raise FeedParseError(f"피드 파싱 실패: {exc}") from exc
    return spans


def parse_item(fragment: bytes) -> dict[str, list[str]]:
    """item 조각 하나에서 직계 자식들의 텍스트를 모은다. `<category>` 처럼 반복되면 다 담는다."""
    parser = expat.ParserCreate()
    fields: dict[str, list[str]] = {}
    depth = 0
    current: str | None = None
    buffer: list[str] = []

    def on_start(name: str, _attrs: dict[str, str]) -> None:
        nonlocal depth, current, buffer
        depth += 1
        if depth == 2:
            current, buffer = name, []

    def on_chars(data: str) -> None:
        if depth >= 2 and current is not None:
            buffer.append(data)

    def on_end(_name: str) -> None:
        nonlocal depth, current
        if depth == 2 and current is not None:
            fields.setdefault(current, []).append("".join(buffer))
            current = None
        depth -= 1

    parser.StartElementHandler = on_start
    parser.CharacterDataHandler = on_chars
    parser.EndElementHandler = on_end
    try:
        parser.Parse(fragment, True)
    except expat.ExpatError as exc:
        raise FeedParseError(f"item 조각 파싱 실패: {exc}") from exc
    return fields


def _first(fields: dict[str, list[str]], name: str) -> str:
    values = fields.get(name)
    return values[0] if values else ""


def article_id_from_guid(guid: str, param: str) -> str:
    """guid 는 `https://www.vogue.co.kr/?p=857991` 꼴이다.

    URL 슬러그는 쓰지 않는다 — 제목이 바뀌면 슬러그도 바뀐다.
    """
    values = parse_qs(urlsplit(guid).query).get(param, [])
    if not values or not values[0].isdigit():
        raise ValueError(f"guid 에서 {param!r} 숫자를 못 뽑았다: {guid!r}")
    return values[0]


def clean_url(url: str) -> str:
    """추적 파라미터만 뺀다. percent-encoding 은 소스가 발행한 정식 URL 이라 그대로 둔다."""
    parts = urlsplit(url)
    if not parts.query:
        return url
    kept = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.startswith(TRACKING_PREFIXES) and key not in TRACKING_KEYS
    ]
    return urlunsplit(parts._replace(query=urlencode(kept)))


def _parse_published(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        parsed = parsedate_to_datetime(raw)
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
        self.source = source
        self._session = session
        self._now = now or (lambda: datetime.now(timezone.utc))

    def page_url(self, page: int | None) -> str:
        if page is None:
            return self.source.discover_url
        separator = "&" if "?" in self.source.discover_url else "?"
        return f"{self.source.discover_url}{separator}paged={page}"

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
            fields = parse_item(fragment)
            guid = _first(fields, "guid")
            try:
                article_id = article_id_from_guid(guid, self.source.guid_param)
            except ValueError as exc:
                logger.warning("%s: 후보가 못 됐다 — %s", self.source.key, exc)
                failures.append(Failure(self.source.key, "discover", guid or "?", str(exc)))
                continue
            candidates.append(
                Candidate(
                    source=self.source.key,
                    article_id=article_id,
                    url=clean_url(_first(fields, "link").strip()),
                    raw=fragment,
                    raw_ext=ROUTE_EXT[self.source.route],
                    collected_at=collected_at,
                    published_at=_parse_published(_first(fields, "pubDate").strip()),
                )
            )
        logger.info(
            "%s: 후보 %d건, 실패 %d건 (%s)", self.source.key, len(candidates), len(failures), url
        )
        return DiscoverResult(candidates, failures)

    def materialize(self, candidate: Candidate) -> tuple[bytes, Article]:
        if candidate.published_at is None:
            raise ValueError(f"발행일이 없어 키를 만들 수 없다: {candidate.article_id}")

        fields = parse_item(candidate.raw)
        body_text = html_to_text(_first(fields, "content:encoded")) or None
        if body_text is None:
            # 평소 0~1건이다. 갑자기 늘면 피드 구조가 바뀐 신호다 (2026-09-03 wkorea 1건).
            logger.warning(
                "%s: 본문이 비었다 — article_id=%s", self.source.key, candidate.article_id
            )

        description = _first(fields, "description").strip()
        # description 이 HTML 이면 요약이 아니라 본문 사본이다. 그때는 비운다.
        summary = description or None if description and not looks_like_html(description) else None

        article = Article(
            domain=self.source.domain,
            source=self.source.key,
            route=self.source.route,
            article_id=candidate.article_id,
            url=candidate.url,
            title=_first(fields, "title").strip(),
            published_at=candidate.published_at,
            collected_at=candidate.collected_at,
            raw_key=raw_key(
                self.source.domain,
                self.source.key,
                self.source.route,
                candidate.published_at,
                candidate.article_id,
            ),
            content_sha256=hashlib.sha256(candidate.raw).hexdigest(),
            summary=summary,
            body_text=body_text,
            categories=[c.strip() for c in fields.get("category", []) if c.strip()],
            author=_first(fields, self.source.author_field).strip() or None,
        )
        return candidate.raw, article
