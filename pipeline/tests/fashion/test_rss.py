"""RSS 어댑터 (설계 문서 확정 1·2, 불변식 8·9).

고정 자료는 2026-09-03 에 실제로 받은 피드를 소스당 3건으로 줄이고 본문을 자른 것이다.
구조·네임스페이스·CDATA·필드 차이는 실측 그대로다. 실측 5소스가 값이 같아 검증되지 않는
열(`article_id` 규칙의 파라미터·`author_field`)과 실측으로 안 나오는 실패는 synthetic.xml 이 맡는다.
"""

import dataclasses
import hashlib
import xml.etree.ElementTree as ET
from datetime import timezone

import httpx
import pytest

from trendin.common.collect.contracts import ArticleFetchError, Rule, SourceDef
from trendin.common.collect.keys import KST
from trendin.common.collect.session import CollectSession, HostBlocked
from trendin.common.collect.stores import InMemoryValidatorStore
from trendin.common.collect.urls import clean_url
from trendin.fashion.collect import sources
from trendin.fashion.collect.rss import (
    RssAdapter,
    article_id_by_rule,
    article_id_from_guid,
    article_id_from_path,
)

MEASURED = ["vogue", "gqkorea", "wkorea", "allure", "marieclaire"]
# 이 셋은 xmlns:media 선언 없이 <media:thumbnail> 을 쓴다 (2026-09-03 실측).
UNBOUND_PREFIX = ["vogue", "gqkorea", "allure"]

SYNTHETIC_P = SourceDef(
    key="synthetic",
    domain="fashion",
    route="rss",
    discover_url="https://example.test/feed/",
    allowed_url_prefixes=("https://example.test/",),
    country="XX",
    article_id=Rule("guid_query_param", "p"),
    published_at=Rule("rss_pubdate"),
)
SYNTHETIC_POST = SourceDef(
    key="synthetic",
    domain="fashion",
    route="rss",
    discover_url="https://example.test/feed/",
    allowed_url_prefixes=("https://example.test/",),
    country="XX",
    article_id=Rule("guid_query_param", "post"),
    published_at=Rule("rss_pubdate"),
    author_field="author",
)

ATOM = SourceDef(
    key="atomish",
    domain="fashion",
    route="rss",
    discover_url="https://atom.test/feed",
    allowed_url_prefixes=("https://atom.test/",),
    country="GB",
    article_id=Rule("guid_hash"),
    published_at=Rule("atom_published"),
)
RDF = SourceDef(
    key="rdfish",
    domain="fashion",
    route="rss",
    discover_url="https://rdf.test/index.rdf",
    allowed_url_prefixes=("https://rdf.test/",),
    country="JP",
    article_id=Rule("guid_hash"),
    published_at=Rule("dc_date"),
)


def serve(body: bytes, status: int = 200, headers: dict | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=body, headers=headers or {})

    return handler


# 본문도 ld+json 도 없는 기사 페이지. 본문은 피드 본문으로 떨어진다(확정 2 의 마지막 단계).
BLANK_PAGE = b"<html><head><title>x</title></head><body></body></html>"


def serve_pages(feed: bytes, source: SourceDef, page: bytes = BLANK_PAGE, status: int = 200):
    """피드 주소면 피드를, 나머지(기사 페이지)는 `page` 를 준다. 받은 주소는 `.requested`."""
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if str(request.url).startswith(source.discover_url):
            return httpx.Response(200, content=feed)
        return httpx.Response(status, content=page)

    handler.requested = requested
    return handler


def adapter_for(source: SourceDef, handler, clock, **kwargs):
    session = CollectSession(
        allowed_url_prefixes=source.allowed_url_prefixes,
        transport=httpx.MockTransport(handler),
        clock=clock,
        sleep=clock.sleep,
        **kwargs,
    )
    return RssAdapter(source, session), session


# --- 실측 피드 -------------------------------------------------------------


@pytest.mark.parametrize("key", MEASURED)
def test_실측_피드에서_필수_필드가_찬_article_이_나온다(key, clock, feed_bytes):
    source = sources.get(key)
    body = feed_bytes(f"{key}.xml")
    adapter, session = adapter_for(source, serve_pages(body, source), clock)
    with session:
        result = adapter.discover()
        assert result.candidates and not result.failures
        for candidate in result.candidates:
            raw, article = adapter.materialize(candidate)
            # raw 는 item 조각이 아니라 받은 기사 페이지다 (확정 2).
            assert raw == BLANK_PAGE
            assert article.source == key
            assert article.route == "rss"
            assert article.domain == "fashion"
            assert article.article_id.isdigit()
            assert article.title
            assert article.raw_key.endswith(
                f"/rss/{article.published_at.astimezone(KST):%Y/%m/%d}/{article.article_id}/raw.html"
            )
            assert article.content_sha256 == hashlib.sha256(raw).hexdigest()
            assert article.published_at.tzinfo is not None
            assert article.collected_at.tzinfo == timezone.utc


@pytest.mark.parametrize("key", MEASURED)
def test_raw_는_원본에서_잘라낸_바이트_그대로다(key, clock, feed_bytes):
    """파싱 후 재직렬화하면 속성 순서·공백·엔티티가 달라진다 (불변식 8)."""
    body = feed_bytes(f"{key}.xml")
    adapter, session = adapter_for(sources.get(key), serve(body), clock)
    with session:
        for candidate in adapter.discover().candidates:
            assert candidate.raw in body
            assert candidate.raw.startswith(b"<item")
            assert candidate.raw.endswith(b"</item>")
            assert candidate.raw_ext == "xml"


@pytest.mark.parametrize("key", UNBOUND_PREFIX)
def test_ElementTree_로는_못_읽는_피드를_읽는다(key, clock, feed_bytes):
    """xmlns:media 선언 없이 <media:thumbnail> 을 쓴다. expat 으로 간 이유가 이것이다."""
    body = feed_bytes(f"{key}.xml")
    with pytest.raises(ET.ParseError, match="unbound prefix"):
        ET.fromstring(body)
    adapter, session = adapter_for(sources.get(key), serve(body), clock)
    with session:
        assert len(adapter.discover().candidates) == 3


def test_본문이_빈_기사도_저장한다(clock, feed_bytes):
    """실측 wkorea 1건. body_text 는 선택 필드라 없다고 실패시키지 않는다."""
    source = sources.get("wkorea")
    adapter, session = adapter_for(source, serve_pages(feed_bytes("wkorea.xml"), source), clock)
    with session:
        articles = [adapter.materialize(c)[1] for c in adapter.discover().candidates]
    empty = [a for a in articles if a.body_text is None]
    assert len(empty) == 1
    assert empty[0].title and empty[0].url  # 나머지 필수 필드는 다 찼다


def test_사진_크레딧과_script_는_본문에_안_들어간다(clock, feed_bytes):
    source = sources.get("allure")
    adapter, session = adapter_for(source, serve_pages(feed_bytes("allure.xml"), source), clock)
    with session:
        bodies = [adapter.materialize(c)[1].body_text or "" for c in adapter.discover().candidates]
    joined = "\n".join(bodies)
    assert joined
    for noise in ("Getty Images", "BACKGRID", "alert(", "function("):
        assert noise not in joined


# --- 합성: 갈리는 열과 실패 -------------------------------------------------


def test_guid_파라미터와_author_field_가_소스마다_갈린다(clock, feed_bytes):
    body = feed_bytes("synthetic.xml")
    adapter, session = adapter_for(SYNTHETIC_POST, serve_pages(body, SYNTHETIC_POST), clock)
    with session:
        result = adapter.discover()
        assert [c.article_id for c in result.candidates] == ["705465"]
        _raw, article = adapter.materialize(result.candidates[0])
    assert article.author == "편집부"
    # HTML 로 보이는 description 도 버리지 않고 같은 조각 규칙을 지난다 (#5.3, 2026-09-17).
    assert article.summary == "<p>요약 자리에 본문이 들어왔다</p>"
    # 사진 크레딧과 script 는 버리고 나머지 마크업은 남는다.
    assert article.body_text == (
        '<p>첫 문단.</p><figure><img src="https://example.test/a.jpg"></figure><p>둘째 문단.</p>'
    )


def test_article_id_를_못_뽑은_건만_실패로_빠지고_나머지는_간다(clock, feed_bytes):
    body = feed_bytes("synthetic.xml")
    adapter, session = adapter_for(SYNTHETIC_P, serve(body), clock)
    with session:
        result = adapter.discover()
    assert [c.article_id for c in result.candidates] == ["111", "222"]
    assert len(result.failures) == 3
    assert {f.stage for f in result.failures} == {"discover"}
    assert all(f.ref for f in result.failures)


def test_발행일이_없으면_정규화에서_실패한다(clock, feed_bytes):
    adapter, session = adapter_for(SYNTHETIC_P, serve(feed_bytes("synthetic.xml")), clock)
    with session:
        candidates = {c.article_id: c for c in adapter.discover().candidates}
        with pytest.raises(ValueError, match="발행일"):
            adapter.materialize(candidates["111"])


def test_추적_파라미터만_빼고_평문_요약은_남긴다(clock, feed_bytes):
    handler = serve_pages(feed_bytes("synthetic.xml"), SYNTHETIC_P)
    adapter, session = adapter_for(SYNTHETIC_P, handler, clock)
    with session:
        candidates = {c.article_id: c for c in adapter.discover().candidates}
        _raw, article = adapter.materialize(candidates["222"])
    assert article.url == "https://example.test/2026/09/tracked/?keep=1"
    assert article.summary == "평문 요약이다"
    # pubDate 는 +0000 이지만 KST 로는 다음 날이라 키 날짜가 갈린다 (불변식 10).
    assert article.published_at.utcoffset().total_seconds() == 0
    assert "/2026/09/03/" in article.raw_key


# --- Atom · RSS 1.0 · 규칙 --------------------------------------------------


def test_Atom_entry_를_article_로_읽는다(clock, feed_bytes):
    body = feed_bytes("atom.xml")
    adapter, session = adapter_for(ATOM, serve_pages(body, ATOM), clock)
    with session:
        result = adapter.discover()
        first = result.candidates[0]
        raw, article = adapter.materialize(first)
    assert first.raw.startswith(b"<entry") and first.raw.endswith(b"</entry>") and first.raw in body
    assert raw == BLANK_PAGE
    assert first.article_id == hashlib.sha256(b"tag:atom.test,2026:article-1").hexdigest()[:16]
    # rel="self" 가 아니라 alternate 링크가 기사 주소다. 추적 파라미터는 뺀다.
    assert article.url == "https://atom.test/fashion/first"
    assert article.published_at.utcoffset().total_seconds() == 3600
    assert article.title == "아톰 첫 기사"
    assert article.author == "Jane Doe"
    assert article.categories == ["Fashion", "Runway"]
    assert article.summary == "짧은 요약"
    # `type="html"` 이라 엔티티로 감싼 HTML 이 한 번 풀려 조각이 된다.
    assert article.body_text == "<p>첫 문단.</p><p>둘째 문단.</p>"


def test_Atom_발행일_규칙은_대체_순서가_없다(clock, feed_bytes):
    """published 가 없으면 updated 로 넘어가지 않는다 (source-discovery.md #3.2)."""
    body = feed_bytes("atom.xml")
    adapter, session = adapter_for(ATOM, serve(body), clock)
    with session:
        second = adapter.discover().candidates[1]
        assert second.published_at is None
        with pytest.raises(ValueError, match="발행일"):
            adapter.materialize(second)

    updated = dataclasses.replace(ATOM, published_at=Rule("atom_updated"))
    adapter, session = adapter_for(updated, serve(body), clock)
    with session:
        second = adapter.discover().candidates[1]
    assert second.published_at.isoformat() == "2026-09-15T08:00:00+00:00"


def test_guid_hash_는_빈_guid_를_link_로_메우지_않고_실패시킨다(clock, feed_bytes):
    adapter, session = adapter_for(ATOM, serve(feed_bytes("atom.xml")), clock)
    with session:
        result = adapter.discover()
    assert len(result.candidates) == 2
    assert [f.stage for f in result.failures] == ["discover"]
    assert "guid" in result.failures[0].reason


def test_RSS_1_0_item_을_article_로_읽는다(clock, feed_bytes):
    body = feed_bytes("rdf.xml")
    adapter, session = adapter_for(RDF, serve_pages(body, RDF), clock)
    with session:
        (candidate,) = adapter.discover().candidates
        _raw, article = adapter.materialize(candidate)
    guid = b"https://rdf.test/main/html/rd/p/000000001.000000002.html"
    assert candidate.article_id == hashlib.sha256(guid).hexdigest()[:16]
    assert article.url == guid.decode()
    assert article.published_at.isoformat() == "2026-09-16T18:00:00+09:00"
    assert article.author == "주식회사 예시"
    assert article.categories == ["ファッション"]
    assert article.summary == "보도자료 요약"
    assert article.body_text == "<p>보도자료 본문.</p>"


def test_guid_hash_는_앞뒤_공백만_벗긴다():
    rule = Rule("guid_hash")
    assert article_id_by_rule(rule, "  abc \n", "") == article_id_by_rule(rule, "abc", "")
    assert article_id_by_rule(rule, "https://x.test/?a=1", "") != article_id_by_rule(
        rule, "https://x.test/", ""
    )


def test_url_path_segment_는_link_경로의_조각을_위치로_고른다(clock, feed_bytes):
    source = dataclasses.replace(ATOM, article_id=Rule("url_path_segment", -1))
    adapter, session = adapter_for(source, serve(feed_bytes("atom.xml")), clock)
    with session:
        result = adapter.discover()
    # guid 가 빈 셋째 entry 도 link 로 id 가 나온다 — 이 규칙은 guid 를 안 본다.
    assert [c.article_id for c in result.candidates] == ["first", "second", "third"]
    assert result.failures == []


def test_경로_조각_위치는_뒤에서도_세고_깊이가_달라도_같은_자리다():
    """2026-09-16 실측의 미국 허스트 주소 모양. 섹션 깊이가 달라도 id 는 끝에서 둘째다."""
    for link in (
        "https://www.harpersbazaar.com/fashion/trends/a73617426/best-suede-bags-fall-2026/",
        "https://www.elle.com/runway/a73617426/london-fashion-week/",
    ):
        assert article_id_from_path(link, -2) == "a73617426"
    assert article_id_from_path("https://x.test/a/b/c", 0) == "a"


@pytest.mark.parametrize(
    ("link", "reason"),
    [
        ("https://x.test/only/", "조각이 없다"),
        ("https://x.test/%ED%81%B4/slug/", "모양"),
        ("https://x.test/a.b/slug/", "모양"),
    ],
)
def test_경로_조각을_못_쓰면_발견_단계에서_실패한다(link, reason):
    with pytest.raises(ValueError, match=reason):
        article_id_from_path(link, -2)


# --- 페이지와 조건부 요청 ---------------------------------------------------


def test_페이지_번호가_URL_에_붙는다(clock, feed_bytes):
    adapter, session = adapter_for(sources.get("vogue"), serve(feed_bytes("vogue.xml")), clock)
    with session:
        assert adapter.page_url(None) == sources.get("vogue").discover_url
        assert adapter.page_url(2).endswith("?paged=2")


def test_페이지_넘김이_없는_피드에는_페이지를_붙이지_않는다(clock, feed_bytes):
    adapter, session = adapter_for(SYNTHETIC_P, serve(feed_bytes("synthetic.xml")), clock)
    with session:
        assert adapter.page_url(None) == SYNTHETIC_P.discover_url
        with pytest.raises(ValueError, match="페이지 넘김"):
            adapter.page_url(2)


def test_304_는_새_글_0건과_다르다(clock, feed_bytes):
    source = sources.get("vogue")
    adapter, session = adapter_for(
        source, serve(b"", status=304), clock, validators=InMemoryValidatorStore()
    )
    with session:
        result = adapter.discover()
    assert result.not_modified is True
    assert result.candidates == [] and result.failures == []


# --- 순수 함수 -------------------------------------------------------------


def test_guid_에서_숫자만_뽑는다():
    assert article_id_from_guid("https://www.vogue.co.kr/?p=857991", "p") == "857991"
    with pytest.raises(ValueError):
        article_id_from_guid("https://www.vogue.co.kr/2026/09/03/slug/", "p")


def test_percent_encoding_은_그대로_둔다():
    url = "https://www.vogue.co.kr/2026/09/03/%ed%81%b4%eb%9e%98%ec%8b%9d/"
    assert clean_url(url) == url


# --- 기사 페이지 (확정 2, S15P21A102-285) -----------------------------------

LD_PAGE = """<html><head><script type="application/ld+json">
{"@type": "NewsArticle", "headline": "x", "articleBody": "페이지 본문 <문라이트> & 끝.\\n둘째 줄."}
</script></head><body><p>무시되는 짧은 문단</p></body></html>""".encode()
PAYWALLED_PAGE = """<html><head><script type="application/ld+json">
[{"@type": "Organization"}, {"@type": "NewsArticle", "isAccessibleForFree": "False",
  "articleBody": "유료 본문"}]
</script></head><body><p>유료 본문</p></body></html>""".encode()


def _first_synthetic(page: bytes, clock, feed_bytes, status: int = 200):
    handler = serve_pages(feed_bytes("synthetic.xml"), SYNTHETIC_POST, page=page, status=status)
    adapter, session = adapter_for(SYNTHETIC_POST, handler, clock)
    return adapter, session, handler


def test_피드가_전문을_줘도_기사_페이지를_받고_페이지_본문을_쓴다(clock, feed_bytes):
    adapter, session, handler = _first_synthetic(LD_PAGE, clock, feed_bytes)
    with session:
        (candidate,) = adapter.discover().candidates
        raw, article = adapter.materialize(candidate)
    assert handler.requested[-1] == "https://example.test/2026/09/other-shape/"
    assert raw == LD_PAGE
    assert article.body_text == "<p>페이지 본문 &lt;문라이트&gt; &amp; 끝.</p><p>둘째 줄.</p>"
    assert article.raw_key.endswith("/705465/raw.html")
    assert article.content_sha256 == hashlib.sha256(LD_PAGE).hexdigest()
    assert article.paywalled is None


def test_유료_표시_기사는_본문과_raw_를_저장하지_않는다(clock, feed_bytes):
    """HTML 에 본문이 실려 와도 같다 (불변식 2)."""
    adapter, session, _handler = _first_synthetic(PAYWALLED_PAGE, clock, feed_bytes)
    with session:
        (candidate,) = adapter.discover().candidates
        _raw, article = adapter.materialize(candidate)
    assert article.paywalled is True
    assert article.body_text is None
    assert article.raw_key is None and article.content_sha256 is None
    assert article.title and article.summary  # 제목·요약은 남는다


def test_404_는_다시_시도하지_않는다(clock, feed_bytes):
    """기사가 지워진 것이라 다시 쳐도 결과가 같다 (S15P21A102-312)."""
    adapter, session, _handler = _first_synthetic(b"", clock, feed_bytes, status=404)
    with session:
        (candidate,) = adapter.discover().candidates
        with pytest.raises(ArticleFetchError, match="404") as caught:
            adapter.materialize(candidate)
    assert caught.value.retryable is False
    assert caught.value.meta.article_id == "705465"


def test_리다이렉트는_따라가지_않고_실패로_본다(clock, feed_bytes):
    adapter, session, _handler = _first_synthetic(b"", clock, feed_bytes, status=301)
    with session:
        (candidate,) = adapter.discover().candidates
        with pytest.raises(ArticleFetchError, match="301") as caught:
            adapter.materialize(candidate)
    assert caught.value.retryable is True and caught.value.blocking is False


def test_기사_페이지가_403_이면_대기로_남기고_호스트를_멈춘다(clock, feed_bytes):
    """대기 행은 남기되 그 실행에서 이 호스트는 끝이다 (불변식 2, S15P21A102-312)."""
    adapter, session, _handler = _first_synthetic(b"", clock, feed_bytes, status=403)
    with session:
        (candidate,) = adapter.discover().candidates
        with pytest.raises(ArticleFetchError) as caught:
            adapter.materialize(candidate)
    assert caught.value.blocking is True
    assert isinstance(caught.value.__cause__, HostBlocked)
    assert caught.value.meta.title and caught.value.meta.published_at


def test_허용_범위_밖_링크는_치지_않고_그_기사만_실패한다(clock, feed_bytes):
    source = dataclasses.replace(SYNTHETIC_POST, allowed_url_prefixes=("https://only.test/",))
    handler = serve_pages(feed_bytes("synthetic.xml"), SYNTHETIC_POST)
    adapter = RssAdapter(source, CollectSession(transport=httpx.MockTransport(handler)))
    (candidate,) = adapter.discover().candidates
    before = len(handler.requested)
    with pytest.raises(ValueError, match="허용 범위"):
        adapter.materialize(candidate)
    assert len(handler.requested) == before
