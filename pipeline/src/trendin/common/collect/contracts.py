"""어댑터 계약. 목록 페이지 어댑터(164)와 Hacker News 어댑터(165)가 이 모양을 그대로 쓴다.

계약이 갈리는 자리는 하나다 — 발견과 그 뒤 사이. 장부는 거기서만 끼어들어 이미 받은
기사를 거른다(설계 문서 #4). 그래서 메서드도 둘이다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:  # 순환 import 를 피한다. 런타임엔 필요 없다.
    from trendin.common.collect.article import Article


# 국가를 판정할 수 없는 소스 (S15P21A102-276). `SourceDef.country` 가 이 값을 들 수 있고,
# 발급이 장부의 국가 거울에서 소스를 못 찾았을 때 봉투에 내는 값도 이것이다.
#
# ⚠️ **장부 뷰의 `coalesce(country, 'XX')` 와 같은 값이어야 한다**(`ledger.DDL`). 봉투와 뷰가
# 같은 기사에 같은 국가를 붙인다는 약속을 지키는 장치가 두 리터럴의 일치뿐인데, SQL 쪽은
# 이 상수를 끼워 넣지 않았다 — DDL 을 f-string 으로 바꾸면 그 안의 중괄호가 전부 조용히
# 포맷 자리가 된다. 대신 `tests/common/test_ledger.py` 가 둘이 같은지 본다.
UNKNOWN_COUNTRY = "XX"


@dataclass(frozen=True, slots=True)
class Rule:
    """열거형 추출 규칙 하나. 이름과, 규칙이 받으면 파라미터.

    파라미터는 규칙마다 뜻이 다르다 — `guid_query_param` 은 쿼리 이름(문자열),
    `url_path_segment` 는 경로 조각의 위치(정수)다.
    """

    name: str
    param: str | int | None = None


@dataclass(frozen=True, slots=True)
class License:
    """라이선스를 밝힌 소스만 적는다. 검토일이 있어야 오래된 검토를 골라낼 수 있다."""

    name: str
    url: str
    reviewed_on: date


@dataclass(frozen=True, slots=True)
class SourceDef:
    """소스 하나의 정의. 설계 문서 #1 표의 한 행.

    소스별 차이는 어댑터의 분기가 아니라 이 표의 열로 흡수한다. 소스가 하나 늘어도
    어댑터 코드는 그대로다.
    """

    key: str
    domain: str  # "fashion" | "dev"
    route: str  # "rss" | "listing" | "api"
    # 발견을 시작하는 URL. 피드 소스는 피드 주소, 목록 소스는 목록 루트다.
    # route 중립 이름인 이유는 hn(165) 도 이 칸에 Algolia 질의를 넣기 때문이다.
    discover_url: str
    # 이 소스로 칠 수 있는 URL 의 전부. 어댑터가 손에 쥔 링크를 무심코 치는 걸 막는다.
    # 확정 3(hn 이 링크한 외부 원문은 v1 에서 받지 않는다)을 거는 자리이기도 하다.
    allowed_url_prefixes: tuple[str, ...]
    # 이 소스를 **발행하는 법인이 있는 나라**. 본사가 아니라 지사 기준이다 — Vogue Korea 는
    # 본사가 미국이어도 두산매거진이 한국에서 발행하므로 `KR` 이다(설계 문서 #3.2 운영 법인 표).
    # 표기는 ISO 3166-1 alpha-2 대문자이고, 판정할 수 없으면 `UNKNOWN_COUNTRY` 다.
    # `null` 을 쓰지 않는 이유는 "아직 안 붙였다"와 "붙일 수 없다"를 구분하지 못하기 때문이다.
    #
    # 기본값을 두지 않는다. 기본값이 있으면 소스를 하나 더할 때 국가를 빼먹고도 통과한다.
    country: str
    # 피드 소스가 article_id·발행일을 뽑는 규칙(`source-discovery.md` #3.2). 프로필이 채운다.
    # 목록·API 소스는 어댑터가 제 방식으로 뽑으므로 None 이다.
    article_id: Rule | None = None
    published_at: Rule | None = None
    # 피드 페이지 넘김 쿼리 파라미터. None 이면 페이지 넘김이 안 되는 피드다 — 모르는 피드에
    # `?paged=` 를 붙여 치지 않게 기본값을 두지 않는다.
    page_param: str | None = None
    author_field: str = "dc:creator"  # 저자가 실리는 항목 이름. RSS 2.0 피드에서만 쓴다
    license: License | None = None
    # 목록 루트 밑으로 함께 도는 하위 섹션 슬러그. 피드 소스는 빈 튜플이다.
    listing_sections: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Candidate:
    """발견 단계가 내놓는 기사 하나. 장부는 `(source, article_id)` 로 여기를 거른다.

    발견과 취득은 따로 부를 수 있어야 하므로(설계 문서 #4), **발견에서만 알 수 있는 것은
    전부 여기 실어 보낸다.** 어댑터 인스턴스에 들고 있으면 두 태스크로 갈렸을 때 사라진다.
    """

    source: str
    article_id: str
    url: str  # 취득이 칠 주소. article.json 의 정식 URL 과 같지 않을 수 있다
    # 발견이 이미 쥔 원문 바이트. 피드 소스는 item 조각을 쥐고, 목록 소스는 None 이다
    # (raw 가 기사 페이지라 취득에서야 받는다). 기본값을 두지 않는 건 "빠뜨린 것"과
    # "없는 것"을 구분하기 위해서다.
    raw: bytes | None
    raw_ext: str
    collected_at: datetime  # 후보를 발견한 시각 (UTC)
    published_at: datetime | None = None  # 피드 소스는 발견 때 안다. 목록 소스는 모를 수 있다.
    # 발견에서만 알 수 있는 분류. 목록 소스는 어느 섹션 목록에서 봤는지가 여기 들어간다.
    # 기사 페이지에는 이 정보가 없다(실측: `article:section` 이 8/8 상수 "FASHION").
    categories: tuple[str, ...] = ()


# 실패가 난 단계. 요약의 `failed_by_stage` 키가 된다.
Stage = Literal["discover", "materialize", "store"]


@dataclass(frozen=True, slots=True)
class Failure:
    """기사 한 건의 실패. 나머지 건은 그대로 간다(불변식 9 의 실패 단위는 기사다)."""

    source: str
    stage: Stage
    ref: str  # guid 원문이나 article_id
    reason: str


@dataclass(frozen=True, slots=True)
class FetchMeta:
    """기사 페이지를 못 받았을 때 장부 대기 행에 적어 둘 값 (S15P21A102-312).

    피드가 준 것만 들어 있다. 다시 시도해 성공하면 이 값은 쓰이지 않고, 포기할 때
    본문 없는 article.json 을 이것으로 만든다.
    """

    domain: str
    source: str
    route: str
    article_id: str
    url: str
    title: str
    published_at: datetime
    categories: tuple[str, ...] = ()


class ArticleFetchError(Exception):
    """기사 페이지를 못 받았다. 그 기사만 실패로 빠진다.

    `meta` 가 있으면 장부에 대기 행으로 남겨 다음 주기에 다시 시도한다(S15P21A102-312).
    `retryable` 이 False 면 다시 시도해도 결과가 같다 — 404·410 이다.
    `blocking` 은 403·429 다 — 대기 행을 남긴 뒤 그 실행에서 그 호스트를 멈춘다(불변식 2).
    """

    def __init__(
        self,
        reason: str,
        *,
        meta: "FetchMeta | None" = None,
        retryable: bool = True,
        blocking: bool = False,
    ):
        super().__init__(reason)
        self.reason = reason
        self.meta = meta
        self.retryable = retryable
        self.blocking = blocking


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
