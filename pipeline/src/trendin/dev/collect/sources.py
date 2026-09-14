"""소스 정의 (설계 문서 #1 표의 dev 행).

hn 은 Algolia HN Search API 만 친다. 사이트 HTML 은 YC 약관이 스크래핑을 금지하므로
허용 범위에 아예 넣지 않는다 — 어댑터가 손에 쥔 링크를 무심코 쳐도 세션이 막는다(불변식 1).
"""

from __future__ import annotations

from trendin.common.collect.contracts import SourceDef

HN = SourceDef(
    key="hn",
    domain="dev",
    route="api",
    discover_url="https://hn.algolia.com/api/v1/search_by_date",
    allowed_url_prefixes=("https://hn.algolia.com/api/v1/",),
)

BY_KEY = {source.key: source for source in (HN,)}


def get(key: str) -> SourceDef:
    try:
        return BY_KEY[key]
    except KeyError:
        raise KeyError(f"모르는 소스다: {key!r}. 있는 것: {', '.join(sorted(BY_KEY))}") from None
