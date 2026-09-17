"""수집 게이트 (설계 문서 불변식 2·4, #9, `source-discovery.md` 불변식 18).

위반 넷을 여기서 잡는다 — 이름 차단 UA, 호스트 간격, 403·429 뒤 재시도, 허용 URL 밖.
robots.txt 는 2026-09-17 판정 기준에서 빠져 세션이 받지 않는다(S15P21A102-284).
실제로 자지 않으려고 시계와 sleep 을 주입한다.
"""

import httpx
import pytest

from trendin.common.collect.session import (
    BlockedUserAgent,
    CollectSession,
    FetchFailed,
    HostBlocked,
    UrlNotAllowed,
)
from trendin.common.collect.stores import InMemoryValidatorStore

FEED = "https://example.test/category/fashion/feed/"
ALLOWED = ("https://example.test/",)


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
        result = responses(request) if callable(responses) else responses
        return result

    return handler, seen


# --- 위반 넷 -------------------------------------------------------------


def test_이름으로_차단당하는_UA_로는_세션을_못_만든다():
    """두산 4곳이 Scrapy·GPTBot 등을 이름으로 전면 차단한다. 요청까지 가기 전에 막는다."""
    for blocked in ("Scrapy/2.11", "Mozilla/5.0 (compatible; GPTBot/1.1)", "CCBot/2.0"):
        with pytest.raises(BlockedUserAgent):
            CollectSession(user_agent=blocked)


def test_robots_txt_는_받지_않는다(clock):
    """판정 기준에서 뺐으니 받을 이유도 없다. 옛 코드는 호스트마다 한 번 받았다."""
    handler, seen = recorder(httpx.Response(200, content=b"x"))
    with make_session(handler, clock) as session:
        session.get("https://example.test/wp-admin/anything")
    assert seen == ["https://example.test/wp-admin/anything"]


def test_허용_URL_밖은_요청하지_않고_거부한다(clock):
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
    # 첫 요청은 안 잔다 → 둘째 요청 전에 3초
    assert clock.slept == [3.0]


@pytest.mark.parametrize("status", [403, 429])
def test_403_429_는_재시도하지_않고_그_호스트를_멈춘다(clock, status):
    handler, seen = recorder(httpx.Response(status))
    with make_session(handler, clock) as session:
        with pytest.raises(HostBlocked):
            session.get(FEED)
        assert len(seen) == 1  # 한 번뿐. 재시도가 없다.
        with pytest.raises(HostBlocked):
            session.get(FEED)  # 같은 실행에서 다시 치지 않는다
        assert len(seen) == 1


def test_5xx_는_두_번_재시도한다(clock):
    handler, seen = recorder(httpx.Response(503))
    with make_session(handler, clock) as session:
        with pytest.raises(FetchFailed):
            session.get(FEED)
    assert len([u for u in seen if u == FEED]) == 3  # 처음 + 재시도 2회


def test_네트워크_오류도_두_번_재시도한다(clock):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
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
        sent.append(request.headers.get("cookie"))
        return httpx.Response(200, content=b"x", headers={"Set-Cookie": "session=abc; Path=/"})

    with make_session(handler, clock) as session:
        session.get(FEED)
        session.get(FEED)
    assert sent == [None, None]


def test_다른_호스트로_새는_리다이렉트를_따라가지_않는다(clock):
    """허용 URL 검사를 거치지 않은 곳을 치게 된다 (불변식 18)."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "https://elsewhere.test/x"})

    with make_session(handler, clock) as session:
        response = session.get(FEED)
    assert response.status == 302
    assert response.body == b""
