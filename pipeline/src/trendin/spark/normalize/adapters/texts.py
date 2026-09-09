"""어댑터 둘이 공유하는 정제 구현 ([03 §2·§4](../../../../../spark/docs/03-normalization-spec.md)).

**구현이 하나인 이유** — 생산자가 소스별 차이를 `article.json` 에서 이미 흡수했으므로
([03] 머리말) 남은 규칙이 "본문 → 요약 → 제목" 우선순위 하나다. 두 어댑터는 그 우선순위를
공유하고 **`expects_body` 만 다르다.**

그런데도 어댑터를 둘로 나눠 둔 이유는 [03 §7] 이다 — "본문 없는 문서 수" 가 이 묶음에서
가장 값진 지표인데, 그게 정상인지 이상인지는 소스마다 반대다. `api` 는 없는 것이 정상이고
`rss` 에서 없어지면 회원 전용 판별이 깨진 신호다. 그 판단을 함수 안에 넣으면 소스가 늘 때
`if` 가 늘고, 어댑터로 두면 값 하나가 는다.
"""

from __future__ import annotations

from typing import Any, Mapping

from trendin.spark.normalize.adapters.protocol import (
    BASIS_BODY,
    BASIS_SUMMARY,
    BASIS_TITLE,
    DocumentTexts,
)
from trendin.spark.normalize.boilerplate import strip_boilerplate
from trendin.spark.normalize.text import clean_text, clean_title, split_code


def build_texts(article: Mapping[str, Any]) -> DocumentTexts:
    """정제된 텍스트 넷과 길이 기준. 순서는 [03 §4] 그대로 — 코드 분리가 태그 제거보다 먼저다.

    **`body_text` 키가 아예 없는 것이 정상 경로다.** 생산자가 `exclude_none=True` 로
    직렬화하므로 회원 전용 기사와 `hn` 에는 그 키가 빠져 있다 ([02 §3]). `article.get()` 이
    `None` 을 주고 `split_code` 가 빈 문자열로 받는다.

    우선순위가 곧 [03 §2] 의 세 분기다. **본문이 정제 후 비면 요약으로 떨어진다** — 링크만
    있던 본문이 그 경우고, 그 문서를 버릴지는 여기서 정하지 않는다 (`normalize/filters.py`).
    다만 그 판단의 근거가 되도록 `had_raw_body` 에 "본문이 있었다" 를 남긴다 — `basis` 만
    보면 링크뿐이던 기사와 애초에 본문이 없는 `hn` 문서가 구분되지 않는다.
    """
    title = clean_title(article.get("title"))
    raw_body = article.get("body_text")
    had_raw_body = isinstance(raw_body, str) and bool(raw_body.strip())
    stripped, code = split_code(raw_body)
    # 단계 8 — 마크업이 아니라 "기사 본문이 아닌 텍스트" 를 걷는다 ([03 §4]).
    # 단계 7 뒤라야 줄 단위로 볼 수 있어서 `clean_text` 를 감싼다.
    body = strip_boilerplate(clean_text(stripped))
    # 요약은 피드가 준 발췌라 위젯·크레딧이 섞이지 않는다. 그래도 같은 규칙을 태우는 것은
    # 본문이 비어 요약이 본문 대용이 될 때(아래 `basis`) 같은 품질이어야 하기 때문이다.
    summary = strip_boilerplate(clean_text(article.get("summary")))

    if body:
        basis, length = BASIS_BODY, len(body)
    elif summary:
        basis, length = BASIS_SUMMARY, len(summary)
    else:
        basis, length = BASIS_TITLE, len(title)

    return DocumentTexts(
        title=title,
        body=body,
        body_code=code,
        summary=summary,
        content_len=length,
        basis=basis,
        had_raw_body=had_raw_body,
    )
