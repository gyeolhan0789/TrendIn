"""어댑터가 채우는 것과 그 형태 ([03 §1·§2](../../../../../spark/docs/03-normalization-spec.md))."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

# `content_len` 을 무엇의 길이로 셌는지. [03 §2] 의 세 분기와 1:1 이고, [03 §7] 이
# 이걸로 "본문 없는 문서 수" 를 센다.
BASIS_BODY = "body"
BASIS_SUMMARY = "summary"
BASIS_TITLE = "title"


@dataclass(frozen=True, slots=True)
class DocumentTexts:
    """정제가 끝난 텍스트 넷과, 길이를 무엇으로 셌는지.

    `content_len` 을 어댑터가 세는 이유는 무엇을 본문 대용으로 썼는지가 어댑터의 결정이기
    때문이다 ([03 §2]). 호출부에서 다시 세면 그 결정과 갈릴 수 있다.
    """

    title: str
    body: str
    body_code: str
    summary: str
    content_len: int
    basis: str
    # `article.json` 에 `body_text` 가 **있었는지**. `basis` 로는 알 수 없다 —
    # 링크만 있던 본문은 정제 후 비어 `basis` 가 요약·제목으로 떨어지는데, [03 §6] 은
    # 그 문서를 "빈 본문(정제 후)" 으로 **제외**하라고 하고 애초에 본문이 없던 문서
    # (회원 전용 · `hn`)는 제목만으로 **통과**시키라고 한다. 두 경우가 갈리는 근거가 이 값뿐이다.
    had_raw_body: bool = False

    @property
    def has_body(self) -> bool:
        return self.basis == BASIS_BODY


class Adapter(Protocol):
    """소스 하나(정확히는 `route` 하나)의 정제 규칙."""

    name: str
    # 이 경로에 본문이 오기를 기대하는지. [03 §7] 의 "본문 없는 문서 수" 가 이 값으로
    # 정상과 이상을 가른다 — `api` 는 본문이 없는 것이 정상이고, `rss` 에서 없어지면
    # 회원 전용 판별(`div.membershipLine`)이 깨진 신호다.
    expects_body: bool

    def texts(self, article: Mapping[str, Any]) -> DocumentTexts:
        """`article.json` 하나에서 정제된 텍스트를 만든다."""
        ...
