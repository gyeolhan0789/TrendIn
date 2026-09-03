"""robots.txt 판정 (불변식 1)."""

from trendin.common.collect.robots import RobotsCache

RULES = "User-agent: *\nDisallow: /wp-admin/\nDisallow: /search/\n"


def test_금지_경로와_허용_경로를_가른다():
    cache = RobotsCache(lambda url: RULES)
    assert cache.can_fetch("TrendInBot/0.1", "https://example.test/category/fashion/feed/") is True
    assert cache.can_fetch("TrendInBot/0.1", "https://example.test/wp-admin/x") is False


def test_robots_를_못_받으면_전부_허용으로_본다():
    cache = RobotsCache(lambda url: None)
    assert cache.can_fetch("TrendInBot/0.1", "https://example.test/anything") is True


def test_호스트당_한_번만_받는다():
    calls = []

    def fetch(url):
        calls.append(url)
        return RULES

    cache = RobotsCache(fetch)
    cache.can_fetch("TrendInBot/0.1", "https://example.test/a")
    cache.can_fetch("TrendInBot/0.1", "https://example.test/b")
    cache.can_fetch("TrendInBot/0.1", "https://other.test/a")
    assert calls == ["https://example.test/robots.txt", "https://other.test/robots.txt"]
