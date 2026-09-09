"""소스별 어댑터 ([03 §1](../../../../../spark/docs/03-normalization-spec.md)).

**입력이 이미 공통 스키마다.** 생산자가 소스별 차이를 `article.json` 에서 이미 흡수했다
(`web-collect.md` #5.3). 배치 계약 시절 이 자리는 "소스마다 다른 객체를 하나의 표준 문서로
접는" 일을 전제했는데, 그 일의 절반이 생산자 쪽으로 갔다. **남은 차이는 본문이 있는지
하나뿐이다** ([03 §2]).

그래서 어댑터가 둘이다:

| 어댑터 | 소스 | 본문 |
| --- | --- | --- |
| `media` | fashion 7 매체 (`route` = `rss` · `listing`) | 있다. 회원 전용(7.4%)만 없다 |
| `hackernews` | `hn` (`route` = `api`) | dev 전량 없다 — 제목만 온다 |

**`route` 로 고르고 소스 이름 목록으로 고르지 않는다.** 소스 이름으로 분기하면 패션 매체가
하나 늘 때마다 이 코드를 고쳐야 하고, 그때 빠뜨리면 새 소스가 조용히 `hn` 경로를 탄다.
`route` 는 계약 필수 필드라 늘 있고(불변식 9) 확장자와 1:1 이다 (`collect/keys.py`).
"""

from __future__ import annotations

from trendin.spark.normalize.adapters.hackernews import HackerNewsAdapter
from trendin.spark.normalize.adapters.media import MediaAdapter
from trendin.spark.normalize.adapters.protocol import Adapter, DocumentTexts

# `route` → 어댑터. `collect/keys.ROUTE_EXT` 의 세 값이 전부다.
_BY_ROUTE: dict[str, Adapter] = {
    "rss": MediaAdapter(),
    "listing": MediaAdapter(),
    "api": HackerNewsAdapter(),
}

# 모르는 `route` 의 기본. 매체 경로로 보내는 이유는 그쪽이 본문을 **있으면 쓰고 없으면
# 제목으로 떨어지는** 경로라서다. 반대로 두면 본문이 있는 새 소스의 본문을 버린다.
_FALLBACK: Adapter = MediaAdapter()


def adapter_for(route: str | None) -> Adapter:
    """`route` 에 맞는 어댑터. 모르는 값이면 매체 어댑터다.

    모르는 `route` 를 거절하지 않는 이유 — 여기까지 온 이벤트는 이미 계약 검증을 통과했고
    ([02 §3]), `route` 는 우리가 허용 목록으로 지키는 값이 아니다. `domain` 과 다르다
    (`io/contract.DOMAIN_VALUES` 는 목록 밖을 거절한다). 소스가 새 경로를 내면 문서를
    버리는 것보다 매체 규칙으로 정제하는 편이 낫고, 그 사실은 [03 §7] 의 `route` 별
    분포에 드러난다.
    """
    if route is None:
        return _FALLBACK
    return _BY_ROUTE.get(route.strip().lower(), _FALLBACK)


__all__ = ["Adapter", "DocumentTexts", "adapter_for"]
