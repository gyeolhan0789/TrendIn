"""MinIO 키 규칙 (설계 문서 #5.1, 불변식 7·10)."""

from datetime import datetime, timedelta, timezone

import pytest

from trendin.common.collect.keys import article_key, raw_key

UTC = timezone.utc


def test_키_모양이_설계_문서와_같다():
    published = datetime(2026, 9, 3, 4, 41, 17, tzinfo=UTC)
    assert (
        raw_key("fashion", "vogue", "rss", published, "857991")
        == "fashion/vogue/rss/2026/09/03/857991/raw.xml"
    )
    assert (
        article_key("fashion", "vogue", "rss", published, "857991")
        == "fashion/vogue/rss/2026/09/03/857991/article.json"
    )


def test_날짜_파티션은_KST_라_UTC_와_갈릴_수_있다():
    """실측상 pubDate 가 전부 +0000 이라 UTC 15시 이후 발행분은 KST 로 다음 날이다."""
    published = datetime(2026, 9, 2, 23, 30, tzinfo=UTC)  # KST 로는 09-03 08:30
    assert "/2026/09/03/" in raw_key("fashion", "wkorea", "rss", published, "1")


def test_같은_기사는_언제_받아도_같은_키다():
    published = datetime(2026, 9, 3, 4, 41, 17, tzinfo=UTC)
    first = raw_key("fashion", "vogue", "rss", published, "857991")
    second = raw_key("fashion", "vogue", "rss", published, "857991")
    assert first == second


def test_route_마다_확장자가_고정이다():
    published = datetime(2026, 9, 3, tzinfo=UTC)
    assert raw_key("fashion", "x", "rss", published, "1").endswith("raw.xml")
    assert raw_key("fashion", "x", "listing", published, "1").endswith("raw.html")
    assert raw_key("dev", "hn", "api", published, "1").endswith("raw.json")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"published_at": datetime(2026, 9, 3)},  # 오프셋 없음
        {"article_id": "a/b"},  # 키 구조를 깬다
        {"article_id": ""},
        {"route": "atom"},  # 모르는 route
    ],
)
def test_키를_못_만들면_바로_실패한다(kwargs):
    base = {
        "domain": "fashion",
        "source": "vogue",
        "route": "rss",
        "published_at": datetime(2026, 9, 3, tzinfo=timezone(timedelta(hours=9))),
        "article_id": "857991",
    }
    with pytest.raises(ValueError):
        raw_key(**{**base, **kwargs})
