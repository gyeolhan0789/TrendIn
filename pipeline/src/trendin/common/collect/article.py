"""article.json (설계 문서 #5.3).

필수 필드가 하나라도 비면 모델 생성이 실패한다 — 불변식 9 가 곧 pydantic 의 기본 동작이다.
검증은 어댑터의 정규화 끝에서 일어난다. 저장이 검증하면 어댑터마다 다른 수준으로 채워
보내도 통과해 버린다.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

SCHEMA_VERSION = 1

# 필수 문자열은 공백만 있어도 "비었다"로 본다.
NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class Article(BaseModel):
    """수집한 기사 하나. 어댑터의 출력이자 저장·발급의 입력."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = SCHEMA_VERSION
    domain: NonEmptyStr
    source: NonEmptyStr
    route: NonEmptyStr
    article_id: NonEmptyStr
    url: NonEmptyStr
    title: NonEmptyStr
    published_at: datetime  # 소스가 준 오프셋 그대로. UTC 로 바꾸지 않는다.
    collected_at: datetime  # UTC. 원문을 받은 시각.
    # 회원 전용·유료 표시 기사는 raw 를 저장하지 않으므로 둘 다 없다(불변식 2, 아래 검증).
    raw_key: NonEmptyStr | None = None
    content_sha256: NonEmptyStr | None = None

    modified_at: datetime | None = None
    summary: str | None = None
    body_text: str | None = None
    categories: list[str] = Field(default_factory=list)
    author: str | None = None
    members_only: bool | None = None
    # 유료 표시(`isAccessibleForFree=false`). 회원 전용과 따로 두는 이유는 둘이 다른 제한이고
    # 소비 측이 본문 없는 이유를 나눠 세기 때문이다(설계 문서 #5.3).
    # 판별은 S15P21A102-285 가 붙인다.
    paywalled: bool | None = None
    extra: dict[str, Any] | None = None

    @field_validator("published_at", "modified_at")
    @classmethod
    def _needs_offset(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            raise ValueError("오프셋 없는 시각은 받지 않는다")
        return v

    @model_validator(mode="after")
    def _raw_unless_withheld(self) -> "Article":
        """raw 는 회원 전용도 유료 표시도 아닐 때만 필수다.

        회원 전용 기사의 기사 페이지 HTML 에는 본문이 통째로 실려 온다(① 2026-09-03 실측
        8/8). 그 바이트를 raw 로 저장하면 불변식 2 의 "HTML 에 텍스트가 실려 있어도
        저장하지 않는다" 가 무의미해진다. 그래서 저장하지 않고, 여기서 필수 필드가 빈 것을
        실패가 아니라 허용으로 읽는다. 유료 표시 기사도 같은 이유로 같다(2026-09-17).

        **이것은 확정이 아니라 가역적 기본값이다** — 설계 문서 #12 열린 질문 2 가 열려 있다.
        뒤집어 저장하기로 하면 이 검증을 지우면 되고, 반대로 저장해 둔 뒤 뒤집으면 MinIO 에서
        골라 지우고 이미 나간 이벤트를 좇아야 한다. 되돌림 비용이 싼 쪽을 기본으로 뒀다.
        """
        withheld = self.members_only or self.paywalled
        if not withheld and (self.raw_key is None or self.content_sha256 is None):
            raise ValueError(
                "회원 전용·유료 표시가 아니면 raw_key·content_sha256 이 있어야 한다"
            )
        if self.members_only and self.body_text is not None:
            raise ValueError("회원 전용 기사에 body_text 를 실을 수 없다")
        if self.paywalled and self.body_text is not None:
            raise ValueError("유료 표시 기사에 body_text 를 실을 수 없다")
        return self

    @field_validator("collected_at")
    @classmethod
    def _must_be_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("collected_at 에 오프셋이 없다")
        return v.astimezone(timezone.utc)

    def to_json_dict(self) -> dict[str, Any]:
        """MinIO 에 그대로 쓸 수 있는 dict. 시각은 ISO-8601 문자열."""
        return json.loads(self.model_dump_json(exclude_none=True))
