"""MinIO 키 규칙 (설계 문서 #5.1). 순수 함수뿐이라 저장소를 모른다.

키를 어댑터가 계산하는 이유는 불변식 7 이다 — `(source, article_id)` 하나가 키 하나로
간다는 것을 저장까지 가기 전에 결정론적으로 확정해 둔다.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9), "KST")

ROUTES = frozenset({"rss", "listing", "api"})
# raw 확장자는 route 가 아니라 **raw 의 실제 내용**이 정한다 (#5.1, S15P21A102-285). 피드
# 소스도 기사 페이지를 받으므로 같은 route 에서 `html` 이 나온다. 전에는 route 와 1:1 이었다.
RAW_EXTS = frozenset({"xml", "html", "json"})


def _prefix(domain: str, source: str, route: str, published_at: datetime, article_id: str) -> str:
    if published_at.tzinfo is None:
        raise ValueError(f"published_at 에 오프셋이 없다: {published_at!r}")
    if "/" in article_id or not article_id:
        raise ValueError(f"article_id 가 키에 못 들어간다: {article_id!r}")
    if route not in ROUTES:
        raise ValueError(f"모르는 route: {route!r}")
    # 발행일 파티션은 KST 다 (불변식 10). published_at 필드 자체는 소스 오프셋 그대로 둔다.
    day = published_at.astimezone(KST)
    return f"{domain}/{source}/{route}/{day:%Y/%m/%d}/{article_id}"


def raw_key(
    domain: str, source: str, route: str, published_at: datetime, article_id: str, *, ext: str
) -> str:
    if ext not in RAW_EXTS:
        raise ValueError(f"모르는 raw 확장자: {ext!r}")
    return f"{_prefix(domain, source, route, published_at, article_id)}/raw.{ext}"


def raw_ext(key: str) -> str:
    """저장된 raw 키의 확장자. 키 규칙으로 다시 만들어 대조할 때 쓴다."""
    ext = key.rsplit(".", 1)[-1]
    if ext not in RAW_EXTS:
        raise ValueError(f"raw 키의 확장자를 모른다: {key!r}")
    return ext


def article_key(
    domain: str, source: str, route: str, published_at: datetime, article_id: str
) -> str:
    return f"{_prefix(domain, source, route, published_at, article_id)}/article.json"
