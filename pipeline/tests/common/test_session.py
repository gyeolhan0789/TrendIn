"""수집 게이트 (설계 문서 불변식 1·2·4, #9).

163 완료 기준이 요구하는 위반 다섯을 여기서 잡는다 — robots 금지 경로, 이름 차단 UA,
호스트 간격, 403·429 뒤 재시도, 허용 URL 밖. 실제로 자지 않으려고 시계와 sleep 을 주입한다.
"""

import httpx
import pytest

from trendin.common.collect.session import (
    BlockedUserAgent,
    CollectSession,
    FetchFailed,
    HostBlocked,
    RobotsDisallowed,
    UrlNotAllowed,
)
from trendin.common.collect.stores import InMemoryValidatorStore

FEED = "https://example.test/category/fashion/feed/"
ALLOWED = ("https://example.test/",)
ROBOTS = "User-agent: *\nDisallow: /wp-admin/\n"


def make_session(handler, clock, **kwargs):
    kwargs.setdefault("allowed_url_prefixes", ALLOWED)
    return CollectSession(
        transport=httpx.MockTransport(handler),
        clock=clock,
        sleep=clock.sleep,
        retry_wait=0.0,
        **kwargs,
    )


def recorder(responses):
    """요청 경로를 기록하면서 `responses` 가 시키는 대로 답한다."""
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=ROBOTS)
        result = responses(request) if callable(responses) else responses
        return result

    return handler, seen


# --- 위반 다섯 -------------------------------------------------------------


def test_이름으로_차단당하는_UA_로는_세션을_못_만든다():
    """두산 4곳이 Scrapy·GPTBot 등을 이름으로 전면 차단한다. 요청까지 가기 전에 막는다."""
    for blocked in ("Scrapy/2.11", "Mozilla/5.0 (compatible; GPTBot/1.1)", "CCBot/2.0"):
        with pytest.raises(BlockedUserAgent):
            CollectSession(user_agent=blocked)


def test_robots_가_금지한_경로는_요청조차_안_나간다(clock):
    handler, seen = recorder(httpx.Response(200, content=b"x"))
    with make_session(handler, clock) as session:
        with pytest.raises(RobotsDisallowed):
            session.get("https://example.test/wp-admin/secret")
    assert seen == ["https://example.test/robots.txt"]


def test_허용_URL_밖은_robots_도_안_받고_거부한다(clock):
    handler, seen = recorder(httpx.Response(200, content=b"x"))
    with make_session(handler, clock) as session:
        with pytest.raises(UrlNotAllowed):
            session.get("https://other.test/feed")
    assert seen == []


def test_같은_호스트_연속_요청은_간격을_지킨다(clock):
    handler, _ = recorder(httpx.Response(200, content=b"x"))
    with make_session(handler, clock) as session:
        session.get(FEED)
        session.get(FEED)
    # robots(첫 요청이라 안 잔다) → 피드 → 피드
    assert clock.slept == [3.0, 3.0]


def test_robots_요청도_간격에_포함된다(clock):
    """예외로 두면 소스당 요청이 3초가 아니라 0초 간격 두 번이 된다."""
    handler, seen = recorder(httpx.Response(200, content=b"x"))
    with make_session(handler, clock) as session:
        session.get(FEED)
    assert len(seen) == 2
    assert clock.slept == [3.0]


@pytest.mark.parametrize("status", [403, 429])
def test_403_429_는_재시도하지_않고_그_호스트를_멈춘다(clock, status):
    handler, seen = recorder(httpx.Response(status))
    with make_session(handler, clock) as session:
        with pytest.raises(HostBlocked):
            session.get(FEED)
        assert len(seen) == 2  # robots + 피드 한 번뿐. 재시도가 없다.
        with pytest.raises(HostBlocked):
            session.get(FEED)  # 같은 실행에서 다시 치지 않는다
        assert len(seen) == 2


def test_5xx_는_두_번_재시도한다(clock):
    handler, seen = recorder(httpx.Response(503))
    with make_session(handler, clock) as session:
        with pytest.raises(FetchFailed):
            session.get(FEED)
    assert len([u for u in seen if u == FEED]) == 3  # 처음 + 재시도 2회


def test_네트워크_오류도_두_번_재시도한다(clock):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=ROBOTS)
        calls.append(1)
        raise httpx.ConnectTimeout("끊김")

    with make_session(handler, clock) as session:
        with pytest.raises(FetchFailed):
            session.get(FEED)
    assert len(calls) == 3


# --- 조건부 요청 -----------------------------------------------------------


def test_304_는_받지_않은_것으로_돌려주고_validator_를_다시_보낸다(clock):
    sent: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=ROBOTS)
        sent.append(dict(request.headers))
        if "if-none-match" in request.headers:
            return httpx.Response(304, headers={"ETag": '"v2"'})
        return httpx.Response(200, content=b"<rss/>", headers={"ETag": '"v1"'})

    store = InMemoryValidatorStore()
    with make_session(handler, clock, validators=store) as session:
        first = session.get(FEED)
        second = session.get(FEED)

    assert first.not_modified is False and first.body == b"<rss/>"
    assert second.not_modified is True and second.body == b""
    assert sent[1]["if-none-match"] == '"v1"'
    assert store.get(FEED) == ('"v2"', None)  # 304 가 준 새 validator 로 갱신된다


def test_받은_쿠키는_다음_요청에_실리지_않는다(clock):
    """로그인·인증 경로를 만들지 않는다 (허스트중앙 약관 제5조 2항·제10조 3항)."""
    sent: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=ROBOTS)
        sent.append(request.headers.get("cookie"))
        return httpx.Response(200, content=b"x", headers={"Set-Cookie": "session=abc; Path=/"})

    with make_session(handler, clock) as session:
        session.get(FEED)
        session.get(FEED)
    assert sent == [None, None]


def test_다른_호스트로_새는_리다이렉트를_따라가지_않는다(clock):
    """robots 를 확인한 적 없는 곳을 치게 된다."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=ROBOTS)
        return httpx.Response(302, headers={"Location": "https://elsewhere.test/x"})

    with make_session(handler, clock) as session:
        response = session.get(FEED)
    assert response.status == 302
    assert response.body == b""
