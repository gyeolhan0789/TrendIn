"""소스 정의 (설계 문서 #1 표).

피드 소스는 이 폴더의 `<key>.toml` 프로필이 정본이다(`source-discovery.md` #3). 소스를 더하거나
빼는 건 파일 하나를 더하거나 지우는 일이고 코드는 그대로다.

목록 소스(허스트 2곳)만 여기 코드에 남는다(확정 5). 로그인 마스크·관련기사처럼 프로필로 적을
수 없는 소스별 규칙이 어댑터에 있어서다.

`country` 는 **발행 법인의 소재지**다(설계 문서 #3.2 운영 법인 표). vogue·gqkorea·wkorea·allure 는
두산매거진, marieclaire 는 (주)엠씨케이퍼블리싱, harpersbazaar·cosmopolitan 은 허스트중앙(유) 가
한국에서 발행한다. 본사가 아니라 발행 법인이라서 Vogue 와 Harper's Bazaar 도 미국이 아니라 한국이다.
"""

from __future__ import annotations

from pathlib import Path

from trendin.common.collect.contracts import SourceDef
from trendin.common.collect.profiles import load_profiles

RSS_SOURCES: tuple[SourceDef, ...] = load_profiles(Path(__file__).parent, domain="fashion")

# 목록 소스. 두 곳은 같은 템플릿이라(#2) 차이가 섹션 슬러그뿐이다. `atc_body`·
# `/article/{숫자}`·ld+json 은 어댑터 상수로 두고 여기 열로 만들지 않는다 — 소스가
# 늘어야 열이 생기는데, 늘 소스가 없다.
LISTING_SOURCES: tuple[SourceDef, ...] = (
    SourceDef(
        key="harpersbazaar",
        domain="fashion",
        route="listing",
        discover_url="https://www.harpersbazaar.co.kr/fashion",
        allowed_url_prefixes=("https://www.harpersbazaar.co.kr/",),
        country="KR",
        listing_sections=("news", "style", "trend", "sports", "watchnjewelry"),
    ),
    SourceDef(
        key="cosmopolitan",
        domain="fashion",
        route="listing",
        discover_url="https://www.cosmopolitan.co.kr/fashion",
        allowed_url_prefixes=("https://www.cosmopolitan.co.kr/",),
        country="KR",
        listing_sections=("trends", "item", "howto", "celebstyle", "watchandjewelry"),
    ),
)

# 소스 키 하나로 정의를 찾는 유일한 자리다. route 를 먼저 알아야 찾을 수 있으면
# probe 와 실행 흐름(167)이 각자 route 표를 들고 있게 된다.
BY_KEY = {source.key: source for source in RSS_SOURCES + LISTING_SOURCES}
if len(BY_KEY) != len(RSS_SOURCES) + len(LISTING_SOURCES):
    raise ValueError("프로필과 목록 소스에 같은 키가 있다")


def get(key: str) -> SourceDef:
    try:
        return BY_KEY[key]
    except KeyError:
        raise KeyError(f"모르는 소스다: {key!r}. 있는 것: {', '.join(sorted(BY_KEY))}") from None
