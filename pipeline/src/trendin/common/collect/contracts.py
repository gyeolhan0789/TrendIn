"""어댑터 계약. 목록 페이지 어댑터(164)와 Hacker News 어댑터(165)가 이 모양을 그대로 쓴다.

계약이 갈리는 자리는 하나다 — 발견과 그 뒤 사이. 장부는 거기서만 끼어들어 이미 받은
기사를 거른다(설계 문서 #4). 그래서 메서드도 둘이다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:  # 순환 import 를 피한다. 런타임엔 필요 없다.
    from trendin.common.collect.article import Article


@dataclass(frozen=True, slots=True)
class SourceDef:
    """소스 하나의 정의. 설계 문서 #1 표의 한 행.

    소스별 차이는 어댑터의 분기가 아니라 이 표의 열로 흡수한다. 소스가 하나 늘어도
    어댑터 코드는 그대로다.
    """

    key: str
    domain: str  # "fashion" | "dev"
    route: str  # "rss" | "listing" | "api"
    feed_url: str
    # 이 소스로 칠 수 있는 URL 의 전부. 어댑터가 손에 쥔 링크를 무심코 치는 걸 막는다.
    # 확정 3(hn 이 링크한 외부 원문은 v1 에서 받지 않는다)을 거는 자리이기도 하다.
    allowed_url_prefixes: tuple[str, ...]
    guid_param: str = "p"  # guid 쿼리에서 article_id 를 담는 파라미터
    author_field: str = "dc:creator"  # 저자가 실리는 항목 이름


@dataclass(frozen=True, slots=True)
class Candidate:
    """발견 단계가 내놓는 기사 하나. 장부는 `(source, article_id)` 로 여기를 거른다."""

    source: str
    article_id: str
    url: str
    raw: bytes
    raw_ext: str
    collected_at: datetime  # raw 를 받은 시각 (UTC)
    published_at: datetime | None = None  # 피드 소스는 발견 때 안다. 목록 소스는 모를 수 있다.


@dataclass(frozen=True, slots=True)
class Failure:
    """기사 한 건의 실패. 나머지 건은 그대로 간다(불변식 9 의 실패 단위는 기사다)."""

    source: str
    stage: str  # "discover" | "materialize"
    ref: str  # guid 원문이나 article_id
    reason: str


@dataclass(frozen=True, slots=True)
class DiscoverResult:
    candidates: list[Candidate] = field(default_factory=list)
    failures: list[Failure] = field(default_factory=list)
    # 조건부 요청이 304 를 받아 아무것도 받지 않았다. "새 글 0건"과 다르다 —
    # 빈 목록으로 뭉개면 조건부 요청이 실제로 듣고 있는지 볼 수 없다.
    not_modified: bool = False


class ValidatorStore(Protocol):
    """조건부 요청용 ETag·Last-Modified 보관소. 세션에 주입한다."""

    def get(self, url: str) -> tuple[str | None, str | None] | None: ...

    def put(self, url: str, etag: str | None, last_modified: str | None) -> None: ...


class SourceAdapter(Protocol):
    """소스 어댑터. 발견은 싸고, 무거운 정규화는 취득 뒤로 미룬다."""

    source: SourceDef

    def discover(self, page: int | None = None) -> DiscoverResult:
        """후보 목록을 얻는다. article_id 만 뽑는 값싼 경로여야 한다."""
        ...

    def materialize(self, candidate: Candidate) -> tuple[bytes, "Article"]:
        """후보 하나를 raw 와 article.json 으로 만든다. 실패하면 예외를 올린다."""
        ...
