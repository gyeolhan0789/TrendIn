"""Hacker News 어댑터 (S15P21A102-165, 설계 문서 확정 3).

고정 자료 `api/hn_search_by_date.json` 은 2026-09-14 에 받은 6시간 응답(168건)에서 네 건을
고른 것이다 — 외부 링크 없는 Ask HN, 일반 링크, Show HN, 링크와 본문이 둘 다 있는 front_page.
hit 목록만 줄였고 `nbHits` 168 을 비롯한 나머지 필드는 받은 그대로다.
"""

import json
from datetime import datetime, timezone
from urllib.parse import parse_qs

import httpx
import pytest

from trendin.common.collect.session import CollectSession
from trendin.dev.collect import sources
from trendin.dev.collect.hackernews import HackerNewsAdapter

# 고정 자료를 받은 시각. 응답의 `params` 에 찍힌 창의 끝이다.
MEASURED_AT = datetime.fromtimestamp(1789360407, timezone.utc)


def adapter_for(handler, clock, *, now=MEASURED_AT):
    source = sources.get("hn")
    session = CollectSession(
        allowed_url_prefixes=source.allowed_url_prefixes,
        transport=httpx.MockTransport(handler),
        clock=clock,
        sleep=clock.sleep,
    )
    return HackerNewsAdapter(source, session, now=lambda: now), session


def recording(body: bytes):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, content=body, headers={"Content-Type": "application/json"})

    return handler, requests


def test_최근_6시간_story_를_Algolia_에만_묻는다(api_bytes, clock):
    handler, requests = recording(api_bytes("hn_search_by_date.json"))
    adapter, session = adapter_for(handler, clock)
    with session:
        result = adapter.discover()

    assert [c.article_id for c in result.candidates] == [
        "49692009",
        "49691998",
        "49691859",
        "49691343",
    ]
    assert result.failures == []
    # HN 의 HTML 은 한 번도 안 친다(확정 3). 요청은 전부 Algolia 호스트다.
    assert {r.url.host for r in requests} == {"hn.algolia.com"}
    search = [r for r in requests if r.url.path == "/api/v1/search_by_date"]
    assert len(search) == 1
    query = parse_qs(search[0].url.query.decode())
    assert query["tags"] == ["story"]
    assert query["numericFilters"] == ["created_at_i>=1789338807,created_at_i<1789360407"]
    assert query["hitsPerPage"] == ["1000"]


def test_외부_링크_없는_글은_HN_항목_URL_로_채우고_원래_링크가_없음을_남긴다(api_bytes, clock):
    handler, _ = recording(api_bytes("hn_search_by_date.json"))
    adapter, session = adapter_for(handler, clock)
    with session:
        ask = adapter.discover().candidates[0]
    raw, article = adapter.materialize(ask)

    assert article.to_json_dict() == {
        "schema_version": 1,
        "domain": "dev",
        "source": "hn",
        "route": "api",
        "article_id": "49692009",
        "url": "https://news.ycombinator.com/item?id=49692009",
        "title": "Looking for co founder in the consumer app space",
        # `created_at_i` 로 만든 UTC 시각이다. 받은 `created_at`(`...T04:30:16Z`)과 같은 순간이다.
        "published_at": "2026-09-14T04:30:16Z",
        "collected_at": "2026-09-14T04:33:27Z",
        "raw_key": "dev/hn/api/2026/09/14/49692009/raw.json",
        "content_sha256": article.content_sha256,
        "categories": ["ask_hn"],
        "author": "me_sleepy",
        "extra": {"score": 1, "descendants": 0, "by": "me_sleepy", "external_url": None},
    }
    # 본문은 raw 에만 있다 — story_text 를 body_text 로 옮기지 않는다(한계 19 는 Spark 몫).
    hit = json.loads(raw)
    assert hit["objectID"] == "49692009"
    assert "story_text" in hit and "_highlightResult" in hit


def test_링크_글은_원문_링크를_url_로_두고_front_page_는_분류에_안_싣는다(api_bytes, clock):
    handler, _ = recording(api_bytes("hn_search_by_date.json"))
    adapter, session = adapter_for(handler, clock)
    with session:
        front = adapter.discover().candidates[3]
    _raw, article = adapter.materialize(front)

    url = "https://fortune.com/2026/09/08/nike-stock-plummets-sp500-market-cap-index/"
    assert article.url == url
    assert article.extra == {
        "score": 45,
        "descendants": 27,
        "by": "andsoitis",
        "external_url": url,
    }
    assert article.categories == []
    # 링크와 story_text 가 둘 다 있는 글이다. 그래도 본문은 싣지 않는다.
    assert article.body_text is None


def test_Show_HN_은_분류로_남는다(api_bytes, clock):
    handler, _ = recording(api_bytes("hn_search_by_date.json"))
    adapter, session = adapter_for(handler, clock)
    with session:
        show = adapter.discover().candidates[2]
    _raw, article = adapter.materialize(show)

    assert article.categories == ["show_hn"]
    assert article.url == "https://3dbae.com"


# --- 구간 조회 --------------------------------------------------------------


def test_1000건을_넘는_구간은_쪼개서_빠짐없이_받는다(clock, fake_algolia):
    start = 1_789_000_000
    # 2500건이 한 시간에 몰려 있다. 한 번에 물으면 1500건이 말없이 잘린다.
    algolia = fake_algolia([start + i for i in range(2500)])
    adapter, session = adapter_for(algolia, clock)
    with session:
        result = adapter.discover_range(
            datetime.fromtimestamp(start, timezone.utc),
            datetime.fromtimestamp(start + 3600, timezone.utc),
        )

    ids = [c.article_id for c in result.candidates]
    assert len(ids) == 2500
    assert set(ids) == {str(100000 + i) for i in range(2500)}
    assert result.failures == []
    # 잘린 응답은 버리고 반으로 다시 물었다. 결과에 쓴 창은 전부 상한 안이다.
    assert algolia.windows[0] == (start, start + 3600, 1000)


def test_구간_경계는_시작을_포함하고_끝을_뺀다(clock, fake_algolia):
    start = 1_789_000_000
    algolia = fake_algolia([start - 1, start, start + 59, start + 60])
    adapter, session = adapter_for(algolia, clock)
    with session:
        result = adapter.discover_range(
            datetime.fromtimestamp(start, timezone.utc),
            datetime.fromtimestamp(start + 60, timezone.utc),
        )

    assert sorted(c.article_id for c in result.candidates) == ["100001", "100002"]


def test_UTC_로는_전날이어도_날짜_키는_KST_로_잡는다(clock, fake_algolia):
    """2026-09-14T15:30Z 는 KST 로 09-15 00:30 이다 (불변식 10)."""
    created = int(datetime(2026, 9, 14, 15, 30, tzinfo=timezone.utc).timestamp())
    algolia = fake_algolia([created])
    adapter, session = adapter_for(algolia, clock)
    with session:
        (candidate,) = adapter.discover_range(
            datetime.fromtimestamp(created - 60, timezone.utc),
            datetime.fromtimestamp(created + 60, timezone.utc),
        ).candidates
    _raw, article = adapter.materialize(candidate)

    assert article.raw_key == "dev/hn/api/2026/09/15/100000/raw.json"
    assert article.to_json_dict()["published_at"] == "2026-09-14T15:30:00Z"


def test_1초에_상한이_차면_조용히_자르지_않고_실패한다(clock, fake_algolia):
    start = 1_789_000_000
    algolia = fake_algolia([start] * 1000)
    adapter, session = adapter_for(algolia, clock)
    with session, pytest.raises(ValueError, match="1초"):
        adapter.discover_range(
            datetime.fromtimestamp(start, timezone.utc),
            datetime.fromtimestamp(start + 1, timezone.utc),
        )


def test_구간_밖_hit_은_Algolia_가_줘도_후보로_삼지_않는다(clock, api_bytes):
    """필터를 무시한 응답이 와도 경계는 어댑터가 지킨다 — 실측 응답을 좁은 구간으로 묻는다.

    고정 자료 네 건의 `created_at_i` 는 1789354240 ~ 1789360216 이다. 그중 1789358758(Show HN)
    과 1789360063 만 드는 구간을 묻는데, 서버는 질의와 상관없이 네 건을 다 준다.
    """
    handler, _ = recording(api_bytes("hn_search_by_date.json"))
    adapter, session = adapter_for(handler, clock)
    with session:
        result = adapter.discover_range(
            datetime.fromtimestamp(1789358758, timezone.utc),
            datetime.fromtimestamp(1789360216, timezone.utc),
        )

    assert [c.article_id for c in result.candidates] == ["49691998", "49691859"]
    assert sorted(f.ref for f in result.failures) == ["49691343", "49692009"]
    assert {f.stage for f in result.failures} == {"discover"}
