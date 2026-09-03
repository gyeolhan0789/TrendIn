"""article.json (설계 문서 #5.3).

필수 필드가 하나라도 비면 모델 생성이 실패한다 — 불변식 9 가 곧 pydantic 의 기본 동작이다.
검증은 어댑터의 정규화 끝에서 일어난다. 저장이 검증하면 어댑터마다 다른 수준으로 채워
보내도 통과해 버린다.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

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
    raw_key: NonEmptyStr
    content_sha256: NonEmptyStr

    modified_at: datetime | None = None
    summary: str | None = None
    body_text: str | None = None
    categories: list[str] = Field(default_factory=list)
    author: str | None = None
    members_only: bool | None = None
    extra: dict[str, Any] | None = None

    @field_validator("published_at", "modified_at")
    @classmethod
    def _needs_offset(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            raise ValueError("오프셋 없는 시각은 받지 않는다")
        return v

    @field_validator("collected_at")
    @classmethod
    def _must_be_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("collected_at 에 오프셋이 없다")
        return v.astimezone(timezone.utc)

    def to_json_dict(self) -> dict[str, Any]:
        """MinIO 에 그대로 쓸 수 있는 dict. 시각은 ISO-8601 문자열."""
        return json.loads(self.model_dump_json(exclude_none=True))
