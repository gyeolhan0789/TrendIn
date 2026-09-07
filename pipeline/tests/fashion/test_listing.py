"""목록 페이지 어댑터 (Jira S15P21A102-164).

완료 기준 두 줄과, 2026-09-03 실측이 반증한 함정 셋, 그리고 계약(과거분 없음·섹션 실패·
304 혼재)을 겨눈다. 함정 셋은 전부 이 MR 작업 중 실제로 빠질 뻔한 것들이라 회귀로 박는다.
"""

import re
from datetime import datetime, timezone

import httpx
import pytest

from trendin.common.collect.article import Article
from trendin.common.collect.session import CollectSession, FetchFailed, HostBlocked
from trendin.common.collect.stores import InMemoryValidatorStore
from trendin.fashion.collect import sources
from trendin.fashion.collect.listing import ListingAdapter, article_ids, parse_ld_article

BAZAAR = sources.get("harpersbazaar")
BASE = "https://www.harpersbazaar.co.kr"
NOW = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)
LATER = datetime(2026, 9, 3, 12, 30, tzinfo=timezone.utc)


@pytest.fixture
def routes(listing_bytes):
    """경로 → 응답. 없는 경로는 404 다."""
    return {
        "/fashion": (200, listing_bytes("harpersbazaar_fashion.html")),
        "/fashion/news": (200, listing_bytes("harpersbazaar_fashion_news.html")),
        "/fashion/style": (200, listing_bytes("harpersbazaar_fashion_news.html")),
        "/fashion/trend": (200, listing_bytes("harpersbazaar_fashion_news.html")),
        "/fashion/sports": (200, listing_bytes("harpersbazaar_fashion_news.html")),
        "/fashion/watchnjewelry": (200, listing_bytes("harpersbazaar_fashion_news.html")),
        "/article/1908982": (200, listing_bytes("harpersbazaar_article_1908982.html")),
        "/article/1908546": (200, listing_bytes("harpersbazaar_article_1908546_members.html")),
    }


@pytest.fixture
def make_session(mock_transport, robots_allow_all, clock):
    def build(routes, *, source=BAZAAR, seen=None):
        def handler(request):
            allowed = robots_allow_all(request)
            if allowed is not None:
                return allowed
            if seen is not None:
                seen.append(request.url.path)
            status, body = routes.get(request.url.path, (404, b""))
            if callable(status):
                return status(request)
            return httpx.Response(status, content=body)

        return CollectSession(
            allowed_url_prefixes=source.allowed_url_prefixes,
            validators=InMemoryValidatorStore(),
            transport=mock_transport(handler),
            clock=clock,
            sleep=clock.sleep,
        )

    return build


def _adapter(session, source=BAZAAR, times=(NOW, LATER)):
    it = iter(times)
    last = [times[-1]]

    def now():
        try:
            return next(it)
        except StopIteration:
            return last[0]

    return ListingAdapter(source, session, now=now)


# --- 완료 기준 -------------------------------------------------------------


def test_목록에서_후보가_나온다(make_session, routes):
    with make_session(routes) as session:
        result = _adapter(session).discover()

    assert not result.not_modified
    assert len(result.candidates) > 30
    first = result.candidates[0]
    assert first.source == "harpersbazaar"
    assert first.article_id.isdigit()
    assert first.url == f"{BASE}/article/{first.article_id}"
    assert first.raw_ext == "html"
    # 목록 소스는 발견에서 raw 를 쥐지 못한다.
    assert first.raw is None
    assert first.published_at is None


def test_기사_HTML_에서_article_json_이_나온다(make_session, routes):
    with make_session(routes) as session:
        adapter = _adapter(session)
        candidate = next(c for c in adapter.discover().candidates if c.article_id == "1908982")
        raw, article = adapter.materialize(candidate)

    assert isinstance(article, Article)
    assert article.route == "listing"
    assert article.article_id == "1908982"
    assert article.url == f"{BASE}/article/1908982"
    assert article.title
    assert article.published_at.isoformat() == "2026-09-01T21:56:32+09:00"
    assert article.modified_at is not None
    assert article.author
    assert article.summary
    assert article.body_text and len(article.body_text) > 500
    assert article.members_only is None
    assert article.raw_key.endswith("/1908982/raw.html")
    assert article.content_sha256 and raw


def test_회원_전용은_본문_없이_표시만_나온다(make_session, routes):
    """완료 기준: HTML 에 본문이 실려 있어도 저장하지 않는다 (불변식 2)."""
    with make_session(routes) as session:
        adapter = _adapter(session)
        candidate = next(c for c in adapter.discover().candidates if c.article_id == "1908546")
        raw, article = adapter.materialize(candidate)

    assert article.members_only is True
    assert article.body_text is None
    # 제목·URL·발행일·요약은 남는다.
    assert article.title and article.url and article.published_at and article.summary
    # raw 도 저장하지 않으므로 키와 해시가 없다 (가역적 기본값, 설계 문서 #12-2).
    assert article.raw_key is None
    assert article.content_sha256 is None
    assert "membershipLine" in raw.decode("utf-8", "replace")
    assert "raw_key" not in article.to_json_dict()


# --- 실측이 반증한 함정 셋 (회귀) -------------------------------------------


def test_내장_JSON_위젯은_후보가_아니다(listing_bytes):
    """① 목록 HTML 의 JSON 배열은 추천 위젯이다. 앵커와 거의 겹치지 않는다."""
    html = listing_bytes("synthetic_listing.html").decode("utf-8")
    found = article_ids(html)

    assert "9000001" not in found and "9000002" not in found
    assert found == ["1000001", "1000002", "1000003"]  # 중복은 한 번, 기사 아닌 링크는 제외


def test_실측_목록에서도_위젯_id_가_섞이지_않는다(listing_bytes):
    html = listing_bytes("harpersbazaar_fashion.html").decode("utf-8")
    found = set(article_ids(html))
    widget = set(re.findall(r'"articleId":"(\d+)"', html))

    assert len(found) == 36
    # 위젯 id 가 앵커에 거의 없다는 것이 이 함정의 실체다.
    assert len(widget - found) > 10


def test_마스크_문구로는_판정하지_않는다(make_session, routes):
    """② 마스크 문구는 실측 8/8 전부에 있다. 일반 기사에도 있다."""
    with make_session(routes) as session:
        adapter = _adapter(session)
        candidate = next(c for c in adapter.discover().candidates if c.article_id == "1908982")
        raw, article = adapter.materialize(candidate)

    assert "전체 페이지를 읽으시려면" in raw.decode("utf-8", "replace")
    assert article.members_only is None  # 그래도 회원 전용이 아니다


def test_위젯_memmark_를_회원_전용으로_오인하지_않는다(make_session, listing_bytes):
    """③ 기사 페이지의 관련기사 위젯에도 memmark 가 붙는다."""
    html = listing_bytes("synthetic_article.html")
    routes = {
        "/fashion": (200, listing_bytes("synthetic_listing.html")),
        "/article/1000001": (200, html),
    }
    assert b"memmark" in html and b"membershipLine" not in html

    with make_session(routes) as session:
        adapter = _adapter(session)
        candidate = next(c for c in adapter.discover().candidates if c.article_id == "1000001")
        _raw, article = adapter.materialize(candidate)

    assert article.members_only is None
    assert article.body_text is not None


def test_본문에_마스크와_관련기사가_섞이지_않는다(make_session, listing_bytes):
    routes = {
        "/fashion": (200, listing_bytes("synthetic_listing.html")),
        "/article/1000001": (200, listing_bytes("synthetic_article.html")),
    }
    with make_session(routes) as session:
        adapter = _adapter(session)
        candidate = next(c for c in adapter.discover().candidates if c.article_id == "1000001")
        _raw, article = adapter.materialize(candidate)

    assert "첫 문단이다." in article.body_text
    assert "둘째 문단이다." in article.body_text
    assert "전체 페이지를 읽으시려면" not in article.body_text
    assert "관련기사 제목" not in article.body_text
    assert "Getty Images" not in article.body_text  # figcaption 은 공통 규칙이 버린다
    assert "에디터 홍길동" not in article.body_text  # atc_body_cont 밖이다


# --- 계약 -------------------------------------------------------------------


def test_과거분은_없다(make_session, routes):
    with make_session(routes) as session:
        with pytest.raises(ValueError, match="과거분"):
            _adapter(session).discover(page=2)


def test_섹션_하나가_실패해도_나머지로_간다(make_session, routes):
    routes = dict(routes)
    routes["/fashion/trend"] = (500, b"")

    with make_session(routes) as session:
        result = _adapter(session).discover()

    assert result.candidates
    assert len(result.failures) == 1
    failure = result.failures[0]
    assert failure.stage == "discover"
    assert failure.ref.endswith("/fashion/trend")


def test_403_은_삼키지_않고_올린다(make_session, routes):
    """불변식 2 — 그 실행에서 그 호스트를 멈춘다."""
    routes = dict(routes)
    routes["/fashion/news"] = (lambda request: httpx.Response(403), None)

    with make_session(routes) as session:
        with pytest.raises(HostBlocked):
            _adapter(session).discover()


def test_여섯_장_전부_304_일_때만_안_바뀐_것이다(make_session, routes, listing_bytes):
    etag = {"ETag": '"v1"'}

    def always_304(request):
        return httpx.Response(304, headers=etag)

    all304 = {path: (always_304, None) for path in routes if path.startswith("/fashion")}
    with make_session(all304) as session:
        assert _adapter(session).discover().not_modified is True

    mixed = dict(all304)
    mixed["/fashion"] = (200, listing_bytes("harpersbazaar_fashion.html"))
    with make_session(mixed) as session:
        result = _adapter(session).discover()
    assert result.not_modified is False
    assert len(result.candidates) == 36


def test_categories_는_하위_섹션이고_루트는_안_들어간다(make_session, routes):
    with make_session(routes) as session:
        result = _adapter(session).discover()

    everything = {c for candidate in result.candidates for c in candidate.categories}
    assert everything <= set(BAZAAR.listing_sections)
    assert "fashion" not in everything
    assert any(candidate.categories for candidate in result.candidates)


def test_collected_at_은_기사_페이지를_받은_시각이다(make_session, routes):
    """#5.3 의 "원문을 받은 시각". 목록 소스의 원문은 기사 페이지다."""
    with make_session(routes) as session:
        adapter = _adapter(session, times=(NOW, LATER))
        candidate = next(c for c in adapter.discover().candidates if c.article_id == "1908982")
        _raw, article = adapter.materialize(candidate)

    assert candidate.collected_at == NOW
    assert article.collected_at == LATER


def test_허용_범위_밖은_치지_않는다(make_session, routes):
    with make_session(routes) as session:
        adapter = _adapter(session)
        assert adapter.section_urls()[0] == (BAZAAR.discover_url, None)
        assert adapter.section_urls()[1] == (f"{BASE}/fashion/news", "news")


def test_ld_json_이_없으면_실패한다():
    with pytest.raises(Exception, match="ld＋json|ld\\+json"):
        parse_ld_article("<html><body>없다</body></html>")


def test_기사_페이지가_404_면_취득이_실패한다(make_session, routes):
    routes = dict(routes)
    del routes["/article/1908982"]

    with make_session(routes) as session:
        adapter = _adapter(session)
        candidate = next(c for c in adapter.discover().candidates if c.article_id == "1908982")
        with pytest.raises(FetchFailed):
            adapter.materialize(candidate)
