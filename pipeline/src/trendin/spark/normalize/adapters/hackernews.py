"""`hn` — Hacker News ([03 §2](../../../../../spark/docs/03-normalization-spec.md)).

**dev 도메인 전량이 본문 없이 온다.** 있는 것은 제목 · URL · 발행일 · 점수 · 댓글수다.
점수와 댓글수는 `article.json` 의 `extra` 에 있고 `ARTICLE_SCHEMA` 가 아직 받지 않는다 —
값 타입이 섞여 있어 [04] 에서 소스별 struct 로 좁혀 받기로 했다 (`io/schema.py`).

**⚠️ 이 경로에서는 스코어링·선별이 그대로 성립하지 않는다.** 문서당 토큰이 10개 안팎이면
[04 §6] 의 위치 가중치가 사실상 제목 가중치 하나가 되고, [06] 의 동시출현은 거의 안 선다.
정제 규격으로 덮을 문제가 아니라 도메인별 추출 경로 문제이고, [00 §7] 한계 19번으로 올라가
있다. **그 결론이 나기 전에 04~07 의 임계값을 정하면 안 된다.**

**본문 경로를 닫아두지 않는 이유** — 한계 19번의 결론이 "`hn` 댓글을 받는다" 로 나면 본문이
대량으로 들어오고 코드 블록도 함께 온다. 그때 어댑터를 다시 짜는 것보다 지금 경로를 열어두고
`expects_body` 만 뒤집는 편이 싸다. 지금은 그 분기가 타지 않으므로 비용도 없다.
"""

from __future__ import annotations

from typing import Any, Mapping

from trendin.spark.normalize.adapters.protocol import DocumentTexts
from trendin.spark.normalize.adapters.texts import build_texts


class HackerNewsAdapter:
    """제목만 오는 경로. 본문이 오면 매체와 같게 처리한다."""

    name = "hackernews"
    # 본문이 없는 것이 **정상**이다. `True` 로 두면 dev 배치마다 [03 §7] 경보가 뜬다.
    expects_body = False

    def texts(self, article: Mapping[str, Any]) -> DocumentTexts:
        return build_texts(article)
