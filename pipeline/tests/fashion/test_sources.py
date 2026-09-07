"""소스 레지스트리 (설계 문서 #1 표)."""

import pytest

from trendin.fashion.collect import sources

ALL_SOURCES = sources.RSS_SOURCES + sources.LISTING_SOURCES


def test_일곱_소스다():
    assert sorted(sources.BY_KEY) == [
        "allure",
        "cosmopolitan",
        "gqkorea",
        "harpersbazaar",
        "marieclaire",
        "vogue",
        "wkorea",
    ]


def test_hypebeast_는_없다():
    """약관 8조가 RSS 예외 없이 자동·수동 수집을 금지한다 (확정 2-1)."""
    assert "hypebeast" not in sources.BY_KEY
    assert not any("hypebeast" in s.discover_url for s in ALL_SOURCES)


def test_한_레지스트리가_두_route_를_다_찾는다():
    """route 를 먼저 알아야 정의를 찾을 수 있으면 probe 와 167 이 각자 표를 든다."""
    assert sources.get("vogue").route == "rss"
    assert sources.get("harpersbazaar").route == "listing"


@pytest.mark.parametrize("source", ALL_SOURCES, ids=lambda s: s.key)
def test_발견_URL_이_허용_범위_안에_있다(source):
    assert source.allowed_url_prefixes
    assert source.discover_url.startswith(source.allowed_url_prefixes)


@pytest.mark.parametrize("source", sources.RSS_SOURCES, ids=lambda s: s.key)
def test_피드_소스는_route_와_도메인이_고정이다(source):
    assert source.route == "rss"
    assert source.domain == "fashion"
    assert source.listing_sections == ()


@pytest.mark.parametrize("source", sources.LISTING_SOURCES, ids=lambda s: s.key)
def test_목록_소스는_하위_섹션_다섯을_가진다(source):
    """Jira 164 경계가 섹션을 명시한다. 루트까지 여섯 장을 돈다."""
    assert source.route == "listing"
    assert source.domain == "fashion"
    assert len(source.listing_sections) == 5
    for slug in source.listing_sections:
        assert f"{source.discover_url}/{slug}".startswith(source.allowed_url_prefixes)


def test_모르는_소스는_있는_것을_알려주며_실패한다():
    with pytest.raises(KeyError, match="vogue"):
        sources.get("hypebeast")
