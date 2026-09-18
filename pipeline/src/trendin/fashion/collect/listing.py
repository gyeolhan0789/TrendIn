"""목록 페이지 어댑터 (설계 문서 확정 1 · Jira S15P21A102-164).

피드 소스와 갈리는 지점은 하나다 — **발견이 raw 를 쥐지 못한다.** 목록 HTML 은 후보의
article_id 만 주고, raw 로 저장할 기사 페이지는 취득에서야 받는다. 그래서 `Candidate.raw`
가 None 이고 `collected_at` 도 취득 시각이다.

2026-09-03 실측이 세 가지를 반증했고, 그 결과가 아래 상수와 판정에 그대로 박혀 있다.

1. **목록 HTML 안의 JSON 페이로드는 목록이 아니다.** `"articleId"`·`"membersYn"` 을 가진
   배열이 페이지마다 20건 들어 있지만 앵커 36건 중 34건이 거기 없다. 추천 위젯이다.
   그래서 후보는 앵커에서만 뽑는다.
2. **기사 페이지의 로그인 마스크 문구는 판정에 못 쓴다.** 8/8 전부에 들어 있다(숨은 모달).
   회원 전용 판정은 `div.membershipLine` 이고, 이건 8/8 정확히 갈랐다.
3. **`article:section` 은 상수 "FASHION" 이다.** 그래서 categories 는 기사 페이지가 아니라
   발견한 섹션 슬러그에서 온다. `Candidate.categories` 가 그걸 취득까지 실어 나른다.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Callable
from urllib.parse import urljoin

from trendin.common.collect.article import Article
from trendin.common.collect.body import find_ld_articles, is_paywalled
from trendin.common.collect.contracts import Candidate, DiscoverResult, Failure, SourceDef
from trendin.common.collect.html_text import html_fragment
from trendin.common.collect.keys import raw_key
from trendin.common.collect.session import CollectError, CollectSession, HostBlocked

logger = logging.getLogger("trendin.collect.listing")

ARTICLE_HREF = re.compile(r"/article/(\d+)")
# 본문 컨테이너. `atc_body` 는 크레딧·태그·추천까지 감싸서 넓다 (① 실측).
BODY_CLASS = "atc_body_cont"
# 본문 컨테이너 안에 섞여 있어 기사 문장이 아닌 것들 (① 실측).
BODY_DROP_CLASSES = frozenset({"atc_mask_login", "ab_related_article"})
# 회원 전용 표시. 본문 안에서 유료 구간이 시작되는 자리에 한 번 나온다 (① 실측 8/8).
MEMBERS_CLASS = "membershipLine"


class ArticleParseError(Exception):
    """기사 페이지에서 필요한 것을 못 뽑았다."""


def _same_site(href: str, allowed: tuple[str, ...]) -> bool:
    """다른 호스트를 가리키는 앵커인가.

    ID 만 뽑아 우리 호스트 URL 로 조립하므로, 걸러 내지 않으면 외부 링크의 번호가 우리
    사이트의 **다른 기사**를 가리키게 된다. 404 로 끝나면 다행이고 실재하면 조용히 엉뚱한
    기사를 수집한다. 실측 목록의 `/article/` 링크는 65개가 전부 상대경로였지만(① 2026-09-03),
    근거가 "지금은 없다" 뿐이라 문을 닫아 둔다.
    """
    if "://" not in href:
        return True
    return bool(allowed) and href.startswith(allowed)


class _AnchorIds(HTMLParser):
    """`/article/{숫자}` 앵커의 article_id 를 모은다. 순서를 지킨다."""

    def __init__(self, allowed_prefixes: tuple[str, ...] = ()) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self._allowed = allowed_prefixes
        self._seen: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href") or ""
        match = ARTICLE_HREF.search(href)
        if not match or not _same_site(href, self._allowed):
            return
        if match.group(1) not in self._seen:
            self._seen.add(match.group(1))
            self.ids.append(match.group(1))


class _HasClass(HTMLParser):
    """그 class 를 단 요소가 있는지. 정규식으로 세지 않는 이유는 #2 반증과 같다."""

    def __init__(self, name: str) -> None:
        super().__init__(convert_charrefs=True)
        self._name = name
        self.found = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if not self.found and self._name in ((dict(attrs).get("class") or "").split()):
            self.found = True


def article_ids(html: str, allowed_prefixes: tuple[str, ...] = ()) -> list[str]:
    parser = _AnchorIds(allowed_prefixes)
    parser.feed(html)
    parser.close()
    return parser.ids


def has_class(html: str, name: str) -> bool:
    parser = _HasClass(name)
    parser.feed(html)
    parser.close()
    return parser.found


def parse_ld_article(html: str) -> dict[str, Any]:
    """기사 페이지의 ld+json `NewsArticle` 을 돌려준다.

    meta 태그 대신 여기를 단일 출처로 쓴다. 발행일·url·요약은 두 곳이 8/8 같은 값을 줬고
    (① 실측), `author` 는 ld+json 에만 있다. 같은 사실을 두 자리에서 읽으면 언젠가 어긋난다.
    """
    nodes = find_ld_articles(html)
    if not nodes:
        raise ArticleParseError("ld+json NewsArticle 이 없다")
    return nodes[0]


def _author_name(value: Any) -> str | None:
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, dict):
        value = value.get("name")
    return value.strip() or None if isinstance(value, str) else None


def _parse_dt(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ArticleParseError(f"{field} 이 없다")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ArticleParseError(f"{field} 을 못 읽었다: {value!r}") from exc
    if parsed.tzinfo is None:
        raise ArticleParseError(f"{field} 에 오프셋이 없다: {value!r}")
    return parsed


class ListingAdapter:
    """목록 HTML 로 발견하고 기사 페이지로 취득한다. 저장·발급·중복 판정은 모른다."""

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

    def section_urls(self) -> list[tuple[str, str | None]]:
        """루트와 하위 섹션. 루트의 슬러그는 None 이다 — 분류가 아니라 목록이라서."""
        root = self.source.discover_url
        return [(root, None)] + [(f"{root}/{s}", s) for s in self.source.listing_sections]

    def discover(self, page: int | None = None) -> DiscoverResult:
        """루트와 하위 섹션을 한 번에 돌고 `article_id` 로 합친다.

        섹션을 호출자에게 노출하지 않는 이유는 설계 문서 #13 이 "소스당 태스크 하나" 로 못
        박았기 때문이다. 실행 흐름(167)이 섹션을 알 필요가 없다.
        """
        if page is not None:
            raise ValueError(f"목록 소스에 과거분은 없다. 목록에 보이는 만큼만이다: page={page!r}")

        collected_at = self._now()
        sections: dict[str, set[str]] = {}
        order: list[str] = []
        failures: list[Failure] = []
        targets = self.section_urls()
        not_modified = 0

        for url, slug in targets:
            try:
                response = self._session.get(url)
            except HostBlocked:
                # 그 실행에서 이 호스트는 끝이다(불변식 2). 삼키면 다음 섹션을 또 친다.
                raise
            except CollectError as exc:
                logger.warning("%s: 섹션을 못 받았다 — %s", self.source.key, exc)
                failures.append(Failure(self.source.key, "discover", url, str(exc)))
                continue

            if response.not_modified:
                not_modified += 1
                continue

            page_html = response.body.decode("utf-8", "replace")
            for article_id in article_ids(page_html, self.source.allowed_url_prefixes):
                if article_id not in sections:
                    sections[article_id] = set()
                    order.append(article_id)
                if slug is not None:
                    sections[article_id].add(slug)

        if not_modified == len(targets):
            logger.info("%s: 목록 %d장 전부 304", self.source.key, len(targets))
            return DiscoverResult(not_modified=True)

        candidates = [
            Candidate(
                source=self.source.key,
                article_id=article_id,
                url=urljoin(self.source.discover_url, f"/article/{article_id}"),
                raw=None,  # 기사 페이지는 취득에서 받는다
                raw_ext="html",
                collected_at=collected_at,
                published_at=None,  # 목록에는 없다. 기사 페이지 ld+json 이 준다
                categories=tuple(sorted(sections[article_id])),
            )
            for article_id in order
        ]
        logger.info(
            "%s: 목록 %d장에서 후보 %d건, 실패 %d건, 304 %d장",
            self.source.key,
            len(targets),
            len(candidates),
            len(failures),
            not_modified,
        )
        return DiscoverResult(candidates, failures)

    def materialize(self, candidate: Candidate) -> tuple[bytes, Article]:
        """기사 페이지를 받아 raw 와 article.json 을 만든다.

        조건부 요청을 걸지 않는다. 304 면 본문 바이트가 없어 raw 를 만들 수 없고, 어차피
        이미 받은 기사는 장부가 여기 오기 전에 걸러 낸다(설계 문서 #4).
        """
        response = self._session.get(candidate.url, conditional=False)
        raw = response.body
        collected_at = self._now()  # 원문을 받은 시각은 여기다 (#5.3)
        html = raw.decode("utf-8", "replace")

        data = parse_ld_article(html)
        published_at = _parse_dt(data.get("datePublished"), "datePublished")
        title = (data.get("headline") or "").strip()
        url = (data.get("url") or "").strip() or candidate.url
        members_only = has_class(html, MEMBERS_CLASS)
        # 피드 소스와 같은 판정이다 (S15P21A102-285). 2026-09-03 실측 8건엔 표시가 없었다.
        paywalled = is_paywalled(find_ld_articles(html))
        withheld = members_only or paywalled

        body_text = None
        if withheld:
            # 본문은 HTML 에 실려 와도 저장하지 않는다 (불변식 2 · 확정 8).
            logger.info(
                "%s: 회원 전용·유료 표시 — 본문 제외 %s", self.source.key, candidate.article_id
            )
        else:
            body_text = (
                html_fragment(html, within_class=BODY_CLASS, drop_classes=BODY_DROP_CLASSES) or None
            )
            if body_text is None:
                logger.warning(
                    "%s: 본문이 비었다 — article_id=%s", self.source.key, candidate.article_id
                )

        modified = data.get("dateModified")
        article = Article(
            domain=self.source.domain,
            source=self.source.key,
            route=self.source.route,
            article_id=candidate.article_id,
            url=url,
            title=title,
            published_at=published_at,
            collected_at=collected_at,
            raw_key=(
                None
                if withheld
                else raw_key(
                    self.source.domain,
                    self.source.key,
                    self.source.route,
                    published_at,
                    candidate.article_id,
                    ext="html",
                )
            ),
            content_sha256=None if withheld else hashlib.sha256(raw).hexdigest(),
            modified_at=_parse_dt(modified, "dateModified") if modified else None,
            summary=html_fragment(data.get("description") or "") or None,
            body_text=body_text,
            categories=list(candidate.categories),
            author=_author_name(data.get("author")),
            members_only=members_only or None,
            paywalled=paywalled or None,
        )
        return raw, article
