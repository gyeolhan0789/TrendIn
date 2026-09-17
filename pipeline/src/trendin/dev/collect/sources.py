"""소스 정의 (설계 문서 #1 표의 dev 행).

hn 은 Algolia HN Search API 만 친다(확정 3). 사이트 HTML 은 허용 범위에 아예 넣지 않는다 —
어댑터가 손에 쥔 링크를 무심코 쳐도 세션이 막는다(`source-discovery.md` 불변식 18).

`country` 가 `XX` 인 이유는 hn 이 애그리게이터라서다. 글을 쓰는 것은 세계 각국의 사용자이고
hn 자신은 남의 글 링크를 모아 둘 뿐이라, 다른 소스에 적용하는 "발행 법인의 소재지" 기준이
여기엔 붙지 않는다. `null` 이 아니라 `XX` 인 것은 "아직 안 붙였다"와 "붙일 수 없다"를
구분하기 위해서다.
"""

from __future__ import annotations

from trendin.common.collect.contracts import SourceDef

HN = SourceDef(
    key="hn",
    domain="dev",
    route="api",
    discover_url="https://hn.algolia.com/api/v1/search_by_date",
    allowed_url_prefixes=("https://hn.algolia.com/api/v1/",),
    country="XX",
)

BY_KEY = {source.key: source for source in (HN,)}


def get(key: str) -> SourceDef:
    try:
        return BY_KEY[key]
    except KeyError:
        raise KeyError(f"모르는 소스다: {key!r}. 있는 것: {', '.join(sorted(BY_KEY))}") from None
