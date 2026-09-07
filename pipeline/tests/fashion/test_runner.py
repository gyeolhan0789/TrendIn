"""DAG 이 부르는 바로 그 경로 (S15P21A102-167).

`runner.collect` 는 수집 태스크의 몸통이다. README 규약 12 가 태스크 함수를 Airflow 없이
테스트하라고 해서, 세션에 고정 응답을 끼워 발견부터 장부 기록까지 한 번에 돌린다.
"""

import httpx
import pytest

from trendin.common.collect.ledger import InMemoryLedger
from trendin.common.collect.session import CollectSession
from trendin.common.collect.stores import InMemoryValidatorStore
from trendin.fashion.collect import runner
from trendin.fashion.collect.listing import ListingAdapter
from trendin.fashion.collect.rss import RssAdapter


class FakeStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(self, key: str, body: bytes, content_type: str) -> None:
        self.objects[key] = body

    def exists(self, key: str) -> bool:
        return key in self.objects


def test_route_로_어댑터를_고른다():
    assert runner.build_adapter(runner.sources.get("vogue"), None).__class__ is RssAdapter
    assert (
        runner.build_adapter(runner.sources.get("harpersbazaar"), None).__class__ is ListingAdapter
    )


def test_모르는_route_는_거부한다():
    source = runner.sources.get("vogue").__class__(
        key="x", domain="fashion", route="ftp", discover_url="https://x/", allowed_url_prefixes=()
    )
    with pytest.raises(KeyError):
        runner.build_adapter(source, None)


def test_소스_키_목록이_소스_레지스트리와_같다():
    assert set(runner.SOURCE_KEYS) == set(runner.sources.BY_KEY)


def test_피드_한_소스를_발견부터_장부_기록까지_돈다(feed_bytes, clock, robots_allow_all):
    """DAG 태스크가 하는 일 전부다 — 다만 사이트 대신 저장해 둔 피드를 읽는다."""
    feed = feed_bytes("vogue.xml")

    def handler(request: httpx.Request) -> httpx.Response:
        allowed = robots_allow_all(request)
        if allowed is not None:
            return allowed
        return httpx.Response(200, content=feed, headers={"Content-Type": "application/xml"})

    def session_factory(**kwargs):
        return CollectSession(
            transport=httpx.MockTransport(handler),
            clock=clock,
            sleep=clock.sleep,
            **kwargs,
        )

    ledger = InMemoryLedger()
    store = FakeStore()
    outcome = runner.collect(
        "vogue",
        ledger=ledger,
        store=store,
        validators=InMemoryValidatorStore(),
        session_factory=session_factory,
    )

    assert outcome.source == "vogue"
    assert outcome.domain == "fashion"
    assert outcome.stored > 0
    assert outcome.failed == 0
    # 기사마다 raw 와 article.json 이 하나씩 (불변식 7)
    assert len(store.objects) == outcome.stored * 2
    assert len(ledger.pending("fashion")) == outcome.stored


def test_두_번_돌려도_장부와_객체가_안_는다(feed_bytes, clock, robots_allow_all):
    """불변식 12 — 장부에 있는 기사는 다시 받지도 저장하지도 않는다."""
    feed = feed_bytes("vogue.xml")

    def handler(request: httpx.Request) -> httpx.Response:
        allowed = robots_allow_all(request)
        if allowed is not None:
            return allowed
        return httpx.Response(200, content=feed, headers={"Content-Type": "application/xml"})

    def session_factory(**kwargs):
        return CollectSession(
            transport=httpx.MockTransport(handler),
            clock=clock,
            sleep=clock.sleep,
            **kwargs,
        )

    ledger = InMemoryLedger()
    store = FakeStore()
    kwargs = dict(
        ledger=ledger,
        store=store,
        validators=InMemoryValidatorStore(),
        session_factory=session_factory,
    )
    first = runner.collect("vogue", **kwargs)
    objects = dict(store.objects)
    second = runner.collect("vogue", **kwargs)

    assert second.stored == 0
    assert second.skipped == first.stored
    assert store.objects == objects
