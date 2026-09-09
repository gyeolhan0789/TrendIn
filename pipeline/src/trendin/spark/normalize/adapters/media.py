"""패션 7 매체 ([03 §1·§2](../../../../../spark/docs/03-normalization-spec.md)).

`vogue` · `gqkorea` · `wkorea` · `allure` · `marieclaire` · `harpersbazaar` · `cosmopolitan`.
경로는 `rss`(두산 계열 4곳 — 피드 `content:encoded` 전문)와 `listing`(기사 페이지 HTML 파싱)
둘이고, **정제 규칙은 같다.** 나뉘는 것은 품질뿐이라 `route` 컬럼으로 나중에 구분해 재본다
([03 §1] "`route` 를 남기는 이유").

**본문이 없는 경우가 정상적으로 온다** — 회원 전용이 fashion 의 7.4% 다. 그때는 `summary`
를 본문 대용으로 쓰고, 그것도 없으면 제목만으로 통과시킨다. 버리지 않는 이유는 제목만으로도
키워드가 나오기 때문이다 ([03 §2]).

**⚠️ 이 경로에서 본문이 사라지면 경보다.** 회원 전용 판별은 `div.membershipLine` 이라는
CSS 선택자 하나에 달려 있고(`web-collect.md` #2) 매체가 템플릿을 바꾸면 조용히 깨진다.
깨지는 방향이 둘인데 둘 다 나쁘다 — 전부 회원 전용으로 판별하면 본문이 통째로 안 오고,
전부 일반으로 판별하면 저장하면 안 되는 본문을 저장한다. 후자는 법적 문제다(불변식 2).
그래서 `expects_body = True` 이고, 7.4% 에서 벗어나면 [03 §7] 집계에 드러난다.
"""

from __future__ import annotations

from typing import Any, Mapping

from trendin.spark.normalize.adapters.protocol import DocumentTexts
from trendin.spark.normalize.adapters.texts import build_texts


class MediaAdapter:
    """매체 기사. 본문이 있으면 쓰고, 없으면 요약, 그것도 없으면 제목."""

    name = "media"
    expects_body = True

    def texts(self, article: Mapping[str, Any]) -> DocumentTexts:
        return build_texts(article)
