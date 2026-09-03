"""RSS 어댑터 (설계 문서 확정 1·2, 불변식 8·9).

고정 자료는 2026-09-03 에 실제로 받은 피드를 소스당 3건으로 줄이고 본문을 자른 것이다.
구조·네임스페이스·CDATA·필드 차이는 실측 그대로다. 실측 5소스가 값이 같아 검증되지 않는
열(`guid_param`·`author_field`)과 실측으로 안 나오는 실패는 synthetic.xml 이 맡는다.
"""

import hashlib
import xml.etree.ElementTree as ET
from datetime import timezone

import httpx
import pytest

from trendin.common.collect.contracts import SourceDef
from trendin.common.collect.session import CollectSession
from trendin.common.collect.stores import InMemoryValidatorStore
from trendin.fashion.collect import sources
from trendin.fashion.collect.rss import RssAdapter, article_id_from_guid, clean_url

ROBOTS = "User-agent: *\nDisallow: /wp-admin/\n"
MEASURED = ["vogue", "gqkorea", "wkorea", "allure", "marieclaire"]
# 이 셋은 xmlns:media 선언 없이 <media:thumbnail> 을 쓴다 (2026-09-03 실측).
UNBOUND_PREFIX = ["vogue", "gqkorea", "allure"]

SYNTHETIC_P = SourceDef(
    key="synthetic",
    domain="fashion",
    route="rss",
    feed_url="https://example.test/feed/",
    allowed_url_prefixes=("https://example.test/",),
)
SYNTHETIC_POST = SourceDef(
    key="synthetic",
    domain="fashion",
    route="rss",
    feed_url="https://example.test/feed/",
    allowed_url_prefixes=("https://example.test/",),
    guid_param="post",
    author_field="author",
)


def serve(body: bytes, status: int = 200, headers: dict | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=ROBOTS)
        return httpx.Response(status, content=body, headers=headers or {})

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
    adapter, session = adapter_for(source, serve(body), clock)
    with session:
        result = adapter.discover()
        assert result.candidates and not result.failures
        for candidate in result.candidates:
            raw, article = adapter.materialize(candidate)
            assert raw == candidate.raw
            assert article.source == key
            assert article.route == "rss"
            assert article.domain == "fashion"
            assert article.article_id.isdigit()
            assert article.title
            assert article.raw_key.endswith(f"/{article.article_id}/raw.xml")
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
    adapter, session = adapter_for(sources.get("wkorea"), serve(feed_bytes("wkorea.xml")), clock)
    with session:
        articles = [adapter.materialize(c)[1] for c in adapter.discover().candidates]
    empty = [a for a in articles if a.body_text is None]
    assert len(empty) == 1
    assert empty[0].title and empty[0].url  # 나머지 필수 필드는 다 찼다


def test_사진_크레딧과_script_는_본문에_안_들어간다(clock, feed_bytes):
    adapter, session = adapter_for(sources.get("allure"), serve(feed_bytes("allure.xml")), clock)
    with session:
        bodies = [adapter.materialize(c)[1].body_text or "" for c in adapter.discover().candidates]
    joined = "\n".join(bodies)
    assert joined
    for noise in ("Getty Images", "BACKGRID", "alert(", "function("):
        assert noise not in joined


# --- 합성: 갈리는 열과 실패 -------------------------------------------------


def test_guid_param_과_author_field_가_소스마다_갈린다(clock, feed_bytes):
    body = feed_bytes("synthetic.xml")
    adapter, session = adapter_for(SYNTHETIC_POST, serve(body), clock)
    with session:
        result = adapter.discover()
        assert [c.article_id for c in result.candidates] == ["705465"]
        _raw, article = adapter.materialize(result.candidates[0])
    assert article.author == "편집부"
    # description 이 HTML 이면 요약이 아니라 본문 사본이다. 비운다.
    assert article.summary is None
    assert article.body_text == "첫 문단.\n\n둘째 문단."


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
    adapter, session = adapter_for(SYNTHETIC_P, serve(feed_bytes("synthetic.xml")), clock)
    with session:
        candidates = {c.article_id: c for c in adapter.discover().candidates}
        _raw, article = adapter.materialize(candidates["222"])
    assert article.url == "https://example.test/2026/09/tracked/?keep=1"
    assert article.summary == "평문 요약이다"
    # pubDate 는 +0000 이지만 KST 로는 다음 날이라 키 날짜가 갈린다 (불변식 10).
    assert article.published_at.utcoffset().total_seconds() == 0
    assert "/2026/09/03/" in article.raw_key


# --- 페이지와 조건부 요청 ---------------------------------------------------


def test_페이지_번호가_URL_에_붙는다(clock, feed_bytes):
    adapter, session = adapter_for(sources.get("vogue"), serve(feed_bytes("vogue.xml")), clock)
    with session:
        assert adapter.page_url(None) == sources.get("vogue").feed_url
        assert adapter.page_url(2).endswith("?paged=2")


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
