"""RSS 소스 레지스트리 (설계 문서 #1 표)."""

import pytest

from trendin.fashion.collect import sources


def test_다섯_소스다():
    assert sorted(sources.BY_KEY) == ["allure", "gqkorea", "marieclaire", "vogue", "wkorea"]


def test_hypebeast_는_없다():
    """약관 8조가 RSS 예외 없이 자동·수동 수집을 금지한다 (확정 2-1)."""
    assert "hypebeast" not in sources.BY_KEY
    assert not any("hypebeast" in s.feed_url for s in sources.RSS_SOURCES)


@pytest.mark.parametrize("source", sources.RSS_SOURCES, ids=lambda s: s.key)
def test_피드_URL_이_허용_범위_안에_있다(source):
    assert source.allowed_url_prefixes
    assert source.feed_url.startswith(source.allowed_url_prefixes)


@pytest.mark.parametrize("source", sources.RSS_SOURCES, ids=lambda s: s.key)
def test_route_와_도메인이_고정이다(source):
    assert source.route == "rss"
    assert source.domain == "fashion"


def test_모르는_소스는_있는_것을_알려주며_실패한다():
    with pytest.raises(KeyError, match="vogue"):
        sources.get("hypebeast")
