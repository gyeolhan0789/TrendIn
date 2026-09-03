"""RSS 소스 정의 (설계 문서 #1 표).

소스별 차이는 어댑터의 분기가 아니라 여기 열로 흡수한다. 소스를 빼는 건 한 줄 삭제다.

hypebeast 는 없다 — 약관 8조가 "automated or non-automated means" 로 "any portion of the
website" 에 접근·수집하는 것을 금지하고 RSS 예외가 없다(확정 2-1).

`guid_param` 과 `author_field` 는 지금 5소스가 모두 같은 값이지만 열로 남긴다. 2026-09-03
실측에서 소스가 하나 늘자(hypebeast) 이 둘이 `?post=` 와 `<author>` 로 갈렸다. 열을 없애면
다음 소스에서 어댑터 코드에 분기가 생긴다.
"""

from __future__ import annotations

from trendin.common.collect.contracts import SourceDef

RSS_SOURCES: tuple[SourceDef, ...] = (
    SourceDef(
        key="vogue",
        domain="fashion",
        route="rss",
        feed_url="https://www.vogue.co.kr/category/fashion/feed/",
        allowed_url_prefixes=("https://www.vogue.co.kr/",),
    ),
    SourceDef(
        key="gqkorea",
        domain="fashion",
        route="rss",
        feed_url="https://www.gqkorea.co.kr/category/style/feed/",
        allowed_url_prefixes=("https://www.gqkorea.co.kr/",),
    ),
    SourceDef(
        key="wkorea",
        domain="fashion",
        route="rss",
        feed_url="https://www.wkorea.com/category/fashion/feed/",
        allowed_url_prefixes=("https://www.wkorea.com/",),
    ),
    SourceDef(
        key="allure",
        domain="fashion",
        route="rss",
        feed_url="https://www.allurekorea.com/category/style/feed/",
        allowed_url_prefixes=("https://www.allurekorea.com/",),
    ),
    SourceDef(
        key="marieclaire",
        domain="fashion",
        route="rss",
        feed_url="https://www.marieclairekorea.com/category/fashion/feed/",
        allowed_url_prefixes=("https://www.marieclairekorea.com/",),
    ),
)

BY_KEY = {source.key: source for source in RSS_SOURCES}


def get(key: str) -> SourceDef:
    try:
        return BY_KEY[key]
    except KeyError:
        raise KeyError(f"모르는 소스다: {key!r}. 있는 것: {', '.join(sorted(BY_KEY))}") from None
