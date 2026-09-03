"""MinIO 키 규칙 (설계 문서 #5.1). 순수 함수뿐이라 저장소를 모른다.

키를 어댑터가 계산하는 이유는 불변식 7 이다 — `(source, article_id)` 하나가 키 하나로
간다는 것을 저장까지 가기 전에 결정론적으로 확정해 둔다.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9), "KST")

# route 와 확장자는 1:1 이다 (#5.1). 소스 정의에 따로 두면 어긋난 조합을 적을 수 있게 된다.
ROUTE_EXT = {"rss": "xml", "listing": "html", "api": "json"}


def _prefix(domain: str, source: str, route: str, published_at: datetime, article_id: str) -> str:
    if published_at.tzinfo is None:
        raise ValueError(f"published_at 에 오프셋이 없다: {published_at!r}")
    if "/" in article_id or not article_id:
        raise ValueError(f"article_id 가 키에 못 들어간다: {article_id!r}")
    if route not in ROUTE_EXT:
        raise ValueError(f"모르는 route: {route!r}")
    # 발행일 파티션은 KST 다 (불변식 10). published_at 필드 자체는 소스 오프셋 그대로 둔다.
    day = published_at.astimezone(KST)
    return f"{domain}/{source}/{route}/{day:%Y/%m/%d}/{article_id}"


def raw_key(domain: str, source: str, route: str, published_at: datetime, article_id: str) -> str:
    return f"{_prefix(domain, source, route, published_at, article_id)}/raw.{ROUTE_EXT[route]}"


def article_key(
    domain: str, source: str, route: str, published_at: datetime, article_id: str
) -> str:
    return f"{_prefix(domain, source, route, published_at, article_id)}/article.json"
