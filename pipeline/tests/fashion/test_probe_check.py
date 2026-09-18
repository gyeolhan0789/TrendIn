"""등록 프로브 (S15P21A102-291).

피드는 `?paged=N` 마다 합성 RSS 를 주는 가짜 서버로 흉내 내고(`test_backfill.py` 와 같은 방식),
어댑터·세션은 진짜를 쓴다. 측정 표에 붙는 요약 줄을 글자 그대로 본다.
"""

import dataclasses
import json
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from urllib.parse import parse_qs, urlsplit

import httpx

from trendin.common.collect.contracts import Rule, SourceDef
from trendin.common.collect.session import CollectSession
from trendin.fashion.collect import probe_check
from trendin.fashion.collect.rss import RssAdapter

SOURCE = SourceDef(
    key="synthetic",
    domain="fashion",
    route="rss",
    discover_url="https://example.test/feed/",
    allowed_url_prefixes=("https://example.test/",),
    country="GB",
    article_id=Rule("guid_query_param", "p"),
    published_at=Rule("rss_pubdate"),
    page_param="paged",
)
DAY = timedelta(days=1)
NEWEST = datetime(2026, 9, 16, 12, tzinfo=timezone.utc)


def rss(posts) -> bytes:
    """`posts` 는 (번호, 발행일, 저자) 목록이다. 저자가 None 이면 `dc:creator` 를 안 싣는다."""
    body = "".join(
        f"<item><title>t{post}</title><guid>https://example.test/?p={post}</guid>"
        f"<link>https://example.test/{post}/</link>"
        f"<pubDate>{format_datetime(published)}</pubDate>"
        + (f"<dc:creator>{author}</dc:creator>" if author else "")
        + f"<description>요약 {post}</description></item>"
        for post, published, author in posts
    )
    return (
        '<?xml version="1.0"?><rss version="2.0" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/"><channel>'
        f"{body}</channel></rss>"
    ).encode()


def ld_page(body: str, free: bool = True) -> bytes:
    node = {"@type": "NewsArticle", "articleBody": body, "isAccessibleForFree": free}
    return (
        f'<html><head><script type="application/ld+json">{json.dumps(node)}</script>'
        f"</head><body><p>{body}</p></body></html>"
    ).encode()


PAGE1 = [(30, NEWEST, "Kim"), (29, NEWEST - DAY, None), (28, NEWEST - 2 * DAY, "Lee")]
PAGE2 = [(27, NEWEST - 3 * DAY, "Kim"), (26, NEWEST - 4 * DAY, "Kim")]
ARTICLES = {
    30: (200, ld_page("가" * 1200)),
    29: (200, ld_page("유료 본문", free=False)),
    28: (200, ld_page("나" * 800)),
}


class Site:
    """`pages[N]` 을 `?paged=N` 에 준다. 파라미터가 없으면 1페이지다. 없는 페이지는 404."""

    def __init__(self, pages, articles=ARTICLES):
        self.pages = pages
        self.articles = articles
        self.requested: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.requested.append(url)
        parts = urlsplit(url)
        if parts.path == "/feed/":
            page = int(parse_qs(parts.query).get("paged", ["1"])[0])
            if page not in self.pages:
                return httpx.Response(404)
            content = self.pages[page]
            return httpx.Response(
                200, content=content if isinstance(content, bytes) else rss(content)
            )
        status, body = self.articles[int(parts.path.strip("/"))]
        return httpx.Response(status, content=body)


def run(site, clock, source=SOURCE):
    with CollectSession(
        allowed_url_prefixes=source.allowed_url_prefixes,
        transport=httpx.MockTransport(site),
        clock=clock,
        sleep=clock.sleep,
    ) as session:
        return probe_check.check(RssAdapter(source, session))


def test_표본_셋과_2페이지_피드_끝을_재서_측정_표_한_줄을_낸다(clock):
    report = run(Site({1: PAGE1, 2: PAGE2}), clock)
    assert probe_check.summary_row(report) == (
        "| synthetic | GB | rss20 | 3 | 2.0 | ld_json,유료,ld_json | 1000 "
        "| 1/3 | 0/3 | 2/3 | ok | 404 |"
    )
    assert probe_check.sample_lines(report) == [
        "30  2026-09-16T12:00:00+00:00  본문 ld_json 1200자  저자 있음  https://example.test/30/",
        "29  2026-09-15T12:00:00+00:00  유료  저자 없음  https://example.test/29/",
        "28  2026-09-14T12:00:00+00:00  본문 ld_json 800자  저자 있음  https://example.test/28/",
        "2p: 2건, 1p 와 겹침 0, 1p 보다 오래됨 예 → ok",
    ]


def test_2페이지가_1페이지와_같으면_same_page_이고_끝에도_기사가_있다(clock):
    """파라미터를 무시하는 피드다. hypebeast 가 `?paged=2` 에 같은 20건을 줬다(2026-09-03)."""
    site = Site({1: PAGE1, 2: PAGE1, 999: PAGE1})
    row = probe_check.summary_row(run(site, clock))
    assert row.endswith("| same_page | items |")


def test_2페이지가_더_오래되지_않으면_not_older_다(clock):
    site = Site({1: PAGE1, 2: [(31, NEWEST + DAY, None)], 999: []})
    row = probe_check.summary_row(run(site, clock))
    assert row.endswith("| not_older | empty |")


def test_피드_끝이_200_인데_피드가_아니면_파싱_실패로_찍는다(clock):
    """houyhnhnm 이 `?paged=999` 에 200 과 XML 로 못 읽는 본문을 줬다(2026-09-18)."""
    site = Site({1: PAGE1, 2: PAGE2, 999: b"<!DOCTYPE html><html><p>a & b</p></html>"})
    row = probe_check.summary_row(run(site, clock))
    assert row.endswith("| ok | 파싱 실패 |")


def test_2페이지_기사가_전부_규칙에_안_맞으면_빈_페이지가_아니다(clock):
    site = Site({1: PAGE1, 2: [("old-slug", NEWEST - 9 * DAY, None)]})
    report = run(site, clock)
    assert report.page2 == "discover_failed"
    assert report.page2_line == "2p: 후보 0건, 발견 실패 1건"


def test_기사_페이지가_403_이면_그_뒤로_아무것도_치지_않는다(clock):
    site = Site({1: PAGE1, 2: PAGE2}, articles={**ARTICLES, 29: (403, b"")})
    report = run(site, clock)
    assert probe_check.summary_row(report) == (
        "| synthetic | GB | rss20 | 3 | 2.0 | ld_json,차단 | 1200 | 0/2 | 1/2 | 1/2 | - | - |"
    )
    assert site.requested == [
        "https://example.test/feed/",
        "https://example.test/30/",
        "https://example.test/29/",
    ]


def test_페이지_넘김_파라미터가_없으면_2페이지도_끝도_재지_않는다(clock):
    site = Site({1: PAGE1})
    report = run(site, clock, dataclasses.replace(SOURCE, page_param=None))
    assert probe_check.summary_row(report).endswith("| - | - |")
    assert not any("paged" in url for url in site.requested)
