"""과거분 백필 CLI (S15P21A102-163, 상한과 거부는 S15P21A102-204, 발행일 멈춤은 S15P21A102-290).

백필이 주기 실행과 갈리는 지점 둘을 겨눈다 — 어떤 소스를 받아 주나, 어디서 멈추나.
피드는 `?paged=N` 마다 합성 RSS 를 주는 가짜 서버로 흉내 내고, 어댑터·세션·장부는 진짜를 쓴다.
"""

from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from trendin.common.collect.contracts import Rule, SourceDef
from trendin.common.collect.doubles import InMemoryObjectStore
from trendin.common.collect.ledger import InMemoryLedger
from trendin.common.collect.session import CollectSession, HostBlocked
from trendin.fashion.collect import backfill
from trendin.fashion.collect.rss import RssAdapter

SOURCE = SourceDef(
    key="synthetic",
    domain="fashion",
    route="rss",
    discover_url="https://example.test/feed/",
    allowed_url_prefixes=("https://example.test/",),
    country="XX",
    article_id=Rule("guid_query_param", "p"),
    published_at=Rule("rss_pubdate"),
    page_param="paged",
)
SINCE = datetime(2026, 3, 17, tzinfo=timezone.utc)
NEW = SINCE + timedelta(days=10)
OLD = SINCE - timedelta(days=10)


def rss(items) -> bytes:
    body = "".join(
        f"<item><title>t{post}</title><guid>https://example.test/?p={post}</guid>"
        f"<link>https://example.test/{post}/</link>"
        + (f"<pubDate>{format_datetime(published)}</pubDate>" if published else "")
        + f"<content:encoded><![CDATA[<p>본문 {post}</p>]]></content:encoded></item>"
        for post, published in items
    )
    return (
        '<?xml version="1.0"?><rss version="2.0" '
        'xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel>'
        f"{body}</channel></rss>"
    ).encode()


ARTICLE_HTML = (
    "<!doctype html><html><head><title>t</title></head>"
    "<body><article><p>본문 한 문단이다. 기사 페이지는 285 이후 매번 받는다.</p></article>"
    "</body></html>"
).encode()


class Feed:
    """`pages[N]` 을 `?paged=N` 에 준다.

    없는 페이지는 `missing_status`, 기사 주소는 기사 페이지로 답한다.
    """

    def __init__(self, pages):
        self.pages = pages
        self.seen = []
        self.missing_status = 404

    def __call__(self, request: httpx.Request) -> httpx.Response:
        query = parse_qs(urlsplit(str(request.url)).query)
        if "paged" not in query:
            # 285 부터 피드 소스도 기사 페이지를 매번 받는다.
            return httpx.Response(
                200, content=ARTICLE_HTML, headers={"content-type": "text/html; charset=utf-8"}
            )
        page = int(query["paged"][0])
        self.seen.append(page)
        if page not in self.pages:
            return httpx.Response(self.missing_status)
        return httpx.Response(200, content=rss(self.pages[page]))


def walk(feed, clock, *, ledger=None, store=None):
    with CollectSession(
        allowed_url_prefixes=SOURCE.allowed_url_prefixes,
        transport=httpx.MockTransport(feed),
        clock=clock,
        sleep=clock.sleep,
    ) as session:
        return backfill.walk_pages(
            RssAdapter(SOURCE, session), since=SINCE, ledger=ledger, store=store
        )


def test_목록_소스는_받지_않는다():
    """RssAdapter 를 붙이면 HTML 을 피드로 파싱해 0 건을 내고 성공으로 끝난다.

    목록 소스에 과거분이 없다는 건 `ListingAdapter.discover(page=...)` 가 이미 거부하는
    사실이다. CLI 가 그걸 모르고 받으면 조용한 실패가 된다.
    """
    for key in ("cosmopolitan", "harpersbazaar"):
        with pytest.raises(SystemExit) as exc:
            backfill.main([key, "--since", "2026-03-17T00:00+09:00"])
        assert "목록" in str(exc.value)


def test_rss_소스는_받는다():
    """거부가 route 로 갈리는지 본다. 파싱까지 가지 않고 인자 검사에서 갈린다."""
    assert set(backfill.BACKFILLABLE) == {
        "allure",
        "cancam",
        "fudge",
        "glamour_uk",
        "gq_us",
        "gqkorea",
        "houyhnhnm",
        "id",
        "iodonna",
        "journaldutextile",
        "luxe_co",
        "marieclaire",
        "mensnonno",
        "numero",
        "oggi",
        "theindustry",
        "vogue",
        "vogue_fr",
        "vogue_it",
        "vogue_jp",
        "vogue_uk",
        "wkorea",
    }


def test_since_는_오프셋이_필수다():
    with pytest.raises(SystemExit):
        backfill.main(["vogue", "--since", "2026-03-17T00:00"])


def test_기사가_전부_since_보다_오래된_페이지에서_멈춘다(clock):
    feed = Feed(
        {
            2: [(1, NEW), (2, NEW)],
            3: [(3, NEW), (4, OLD)],
            4: [(5, OLD), (6, OLD)],
            5: [(7, OLD)],
        }
    )
    ledger, store = InMemoryLedger(), InMemoryObjectStore()

    total, stored = walk(feed, clock, ledger=ledger, store=store)

    assert feed.seen == [2, 3, 4]
    assert (total, stored) == (3, 3)


def test_앞_페이지를_이미_받았어도_멈추지_않고_이어_받는다(clock):
    """끊긴 실행을 다시 돌리거나 깊이를 늘려 다시 돌린 경우. 예전엔 2페이지에서 멈췄다."""
    pages = {
        2: [(1, NEW), (2, NEW)],
        3: [(3, NEW), (4, NEW)],
        4: [(5, NEW), (6, NEW)],
        5: [(7, OLD)],
    }
    ledger, store = InMemoryLedger(), InMemoryObjectStore()
    walk(Feed({2: pages[2], 3: pages[3], 4: [(9, OLD)]}), clock, ledger=ledger, store=store)

    feed = Feed(pages)
    total, stored = walk(feed, clock, ledger=ledger, store=store)

    assert feed.seen == [2, 3, 4, 5]
    assert (total, stored) == (2, 2)


def test_장부가_없어도_발행일로_멈춘다(clock):
    """훑기 모드(`--store` 없음)는 진단용이라 이미 받은 기사도 보이지만, 멈춤은 같다."""
    feed = Feed({2: [(1, NEW)], 3: [(2, NEW)], 4: [(3, OLD)]})

    total, stored = walk(feed, clock)

    assert feed.seen == [2, 3, 4]
    assert (total, stored) == (2, 0)


def test_앞_페이지와_같은_페이지면_중단한다(clock):
    """페이지 파라미터를 무시하는 피드(hypebeast 2026-09-03)는 발행일이 영영 안 줄어든다."""
    feed = Feed({2: [(1, NEW)], 3: [(1, NEW)], 4: [(1, NEW)]})

    with pytest.raises(backfill.WalkAborted, match="앞 페이지와 같다"):
        walk(feed, clock, ledger=InMemoryLedger(), store=InMemoryObjectStore())
    assert feed.seen == [2, 3]


def test_페이지_상한에_닿으면_중단한다(clock, monkeypatch):
    monkeypatch.setattr(backfill, "MAX_PAGES", 3)
    feed = Feed({n: [(n, NEW)] for n in range(2, 10)})

    with pytest.raises(backfill.WalkAborted, match="3 페이지를 넘겨도"):
        walk(feed, clock)
    assert feed.seen == [2, 3, 4]


@pytest.mark.parametrize("status", [404, 410])
def test_없는_페이지는_피드_끝으로_보고_정상_종료한다(clock, status):
    """역사가 6개월보다 짧은 피드. 다 받은 것이지 실패가 아니다."""
    feed = Feed({2: [(1, NEW)], 3: [(2, NEW)]})
    feed.missing_status = status

    total, stored = walk(feed, clock, ledger=InMemoryLedger(), store=InMemoryObjectStore())

    assert feed.seen == [2, 3, 4]
    assert (total, stored) == (2, 2)


def test_빈_페이지는_피드_끝으로_보고_정상_종료한다(clock):
    feed = Feed({2: [(1, NEW)], 3: []})

    total, _stored = walk(feed, clock)

    assert feed.seen == [2, 3]
    assert total == 1


def test_차단_응답은_피드_끝이_아니라_오류다(clock):
    feed = Feed({2: [(1, NEW)]})
    feed.missing_status = 403

    with pytest.raises(HostBlocked):
        walk(feed, clock)


def test_since_보다_오래된_기사는_같은_페이지에_있어도_저장하지_않는다(clock):
    feed = Feed({2: [(1, NEW), (2, OLD), (3, NEW)], 3: [(4, OLD)]})
    ledger, store = InMemoryLedger(), InMemoryObjectStore()

    total, stored = walk(feed, clock, ledger=ledger, store=store)

    assert (total, stored) == (2, 2)
    assert ledger.filter_new("synthetic", ["1", "2", "3"]) == {"2"}


def test_발행일_없는_기사는_저장_루프가_실패로_남긴다(clock, caplog):
    """주기 실행과 같은 자리에서 실패로 센다(불변식 9). 백필이 먼저 걸러 내면 셀 수 없다."""
    feed = Feed({2: [(1, NEW), (2, None)], 3: [(3, OLD)]})
    ledger, store = InMemoryLedger(), InMemoryObjectStore()

    total, stored = walk(feed, clock, ledger=ledger, store=store)

    assert (total, stored) == (2, 1)
    assert ledger.filter_new("synthetic", ["1", "2"]) == {"2"}
    assert "발행일이 없어" in caplog.text


def test_한_페이지가_전부_발행일이_없으면_중단한다(clock):
    """피드 템플릿이 바뀐 자리다. 멈추면 남은 구간이 안 채워진 채 성공으로 보인다."""
    feed = Feed({2: [(1, NEW)], 3: [(2, None), (3, None)]})

    with pytest.raises(backfill.WalkAborted, match="발행일이 하나도 없다"):
        walk(feed, clock, ledger=InMemoryLedger(), store=InMemoryObjectStore())
    assert feed.seen == [2, 3]
