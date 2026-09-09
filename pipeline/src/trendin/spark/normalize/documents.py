"""`article.json` 하나 → 표준 문서 하나.

규격은 [03 §1·§3](../../../../spark/docs/03-normalization-spec.md) 이다.

MinIO `curated` 에 Parquet 으로 쓰는 형태를 만든다. 서비스 `contents` 와 다르다 —
`contents` 에는 본문이 없고 `body_object_key` 가 이 파일을 가리킨다 ([01 §3]).

**pyspark 를 import 하지 않는다.** 매핑 하나 → 매핑 하나의 순수 함수라 SparkSession 없이
검사할 수 있다 ([09 §4] 층 1). Spark 쪽 배선은 `ingest/normalize.py` 가 UDF 로 감싼다.
Spark 스키마는 `normalize/schema.py` 에 있다.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Mapping

from trendin.spark.io.contract import parse_offset_datetime
from trendin.spark.normalize.adapters import adapter_for
from trendin.spark.normalize.lang import LangThresholds, detect_lang
from trendin.spark.normalize.simhash import simhash
from trendin.spark.normalize.urls import normalize_url, url_hash

# 발행일 파티션은 KST 다 (불변식 10, [03 §3]). `published_at` 필드 자체는 소스 오프셋을
# 그대로 보존한다 — 파티션 계산에만 변환한다.
#
# `collect/keys.KST` 와 같은 값을 여기 다시 두는 이유는 결합이다. 저쪽은 담당 1 의 수집
# 코드이고, 소비 측이 그 모듈을 import 하면 수집 쪽 리팩터링이 이쪽을 조용히 깨뜨린다.
# 상수 하나를 공유하려고 패키지 경계를 넘지 않는다.
KST = timezone(timedelta(hours=9), "KST")


@dataclass(frozen=True, slots=True)
class Document:
    """표준 문서 한 행. 컬럼과 순서는 [03 §1] 표와 같다.

    `dup_of` 는 여기서 채우지 않는다 — 근사 중복 판별이 문서 하나만 보고 되는 일이 아니라
    배치 전체를 봐야 하므로 `normalize/dedup.py` 가 나중에 채운다. 그래서 기본값이 `None` 이다.
    """

    url_hash: bytes | None
    source_id: str | None
    source_document_id: str | None
    domain: str | None
    route: str | None
    url: str | None
    url_raw: str | None
    title: str
    body: str
    body_code: str
    summary: str
    lang: str
    author: str | None
    categories: list[str] = field(default_factory=list)
    members_only: bool = False
    published_at: datetime | None = None
    published_date: date | None = None
    ingest_run_id: str = ""
    collected_at: datetime | None = None
    content_len: int = 0
    dup_of: bytes | None = None
    # --- 아래는 `curated` 로 나가지 않는다. 필터와 [03 §7] 집계가 읽는다 -------------
    # `content_len` 을 무엇의 길이로 셌는지 (`adapters/protocol.py`).
    basis: str = ""
    # 이 경로에 본문이 오기를 기대했는지. 기대했는데 없으면 [03 §7] 의 경보 대상이다.
    expects_body: bool = True
    # `article.json` 에 `body_text` 가 있었는지. 품질 필터가 "정제 후 빈 본문"(제외)과
    # "애초에 본문 없음"(통과)을 가르는 근거다 ([03 §6]).
    had_raw_body: bool = False
    # 발행 시각이 미래라 `collected_at` 으로 대체했는지 ([03 §3]).
    published_at_corrected: bool = False
    # 본문 지문. 근사 중복 3단계가 읽는다. 본문 없는 문서는 `None` 이다 ([03 §6]).
    simhash: int | None = None

    def as_row(self) -> dict[str, Any]:
        return asdict(self)


# `parse_offset_datetime` 은 `io/contract.py` 에 있다 — 계약 판별과 정제가 **같은 파서**를 써야
# 판별은 통과시키고 정제는 `None` 을 내는 값이 생기지 않는다. 여기서 다시 export 한다.
__all__ = ["Document", "build_document", "parse_offset_datetime", "resolve_published_at"]


def _to_kst_date(moment: datetime | None) -> date | None:
    """KST 로 옮긴 날짜. 오프셋이 없으면 `None` — 어느 날인지 정할 수 없다."""
    if moment is None or moment.tzinfo is None:
        return None
    return moment.astimezone(KST).date()


def resolve_published_at(
    published_at: datetime | None, collected_at: datetime | None
) -> tuple[datetime | None, bool]:
    """`(쓸 시각, 대체했는지)` — [03 §3] 의 미래 시각 방어.

    **미래 시각을 방어하는 이유** — 소스가 예약 발행이나 타임존 버그로 미래 날짜를 주는 일이
    실제로 있다. 그대로 두면 아직 오지 않은 날짜에 언급량이 쌓이고, 그 행은 프론트 그래프의
    오른쪽 끝을 이상하게 만든다.

    **"시각이 없음" 분기는 두지 않는다.** `published_at` 은 `article.json` 의 필수 필드라
    (불변식 9) 없는 기사를 생산자가 저장하지 않고, 없이 오면 `ARTICLE_CONTRACT_VIOLATION`
    으로 이미 DLQ 에서 잡힌다 ([02 §3]). 그래서 `None` 이 들어오면 `None` 을 그대로 낸다 —
    여기서 `collected_at` 으로 메우면 계약 위반이 정상 문서로 위장된다.

    기준을 `collected_at` 으로 잡는 이유는 **재현성**이다. `now()` 로 재면 같은 객체를 언제
    재처리하느냐에 따라 보정 여부가 갈리고, 그러면 백필 결과가 실행 시각에 의존한다.
    """
    if published_at is None or collected_at is None:
        return published_at, False
    if published_at.tzinfo is None or collected_at.tzinfo is None:
        # 비교할 수 없다. 오프셋 없는 값은 위 `parse_offset_datetime` 이 설명한 경로다.
        return published_at, False
    if published_at > collected_at:
        return collected_at, True
    return published_at, False


def _categories(raw: Any) -> list[str]:
    """`categories` 를 문자열 목록으로. 없으면 빈 목록.

    목록 소스가 발견한 섹션 슬러그가 들어온다 ([03 §1]). `None` 과 빈 목록을 같게 보는
    이유는 Parquet 에서 `null` 배열과 빈 배열을 가르는 값이 없기 때문이다 — 읽는 쪽이
    두 경우를 다르게 처리할 일이 없다.
    """
    if not isinstance(raw, (list, tuple)):
        return []
    return [str(item) for item in raw if item is not None and str(item).strip()]


def build_document(
    article: Mapping[str, Any],
    event: Mapping[str, Any],
    *,
    ingest_run_id: str,
    lang_thresholds: LangThresholds | None = None,
) -> Document:
    """표준 문서 하나. 정제·판별을 전부 여기서 끝낸다.

    **값의 출처를 `article.json` 으로 통일한다.** 이벤트에도 `domain`·`source_id`·`url`·
    `title` 이 있지만 그쪽을 쓰지 않는다 — 이미 `check_article` 이 둘이 같은 기사를 가리키는지
    확인했고([02 §3]), 두 출처를 섞으면 모드 B(`--source objects`)에서 값이 갈린다. 그쪽은
    이벤트를 객체 키에서 재구성하므로 `title` 같은 칸이 애초에 없다 ([02 §6]).

    예외는 `collected_at` 이다. 둘 다 있고 같은 값이지만 이벤트 쪽을 우선한다 — `contents`
    로 나가는 값이 이벤트의 `collected_at` 이라고 [03 §8] 이 못 박았다.
    """
    adapter = adapter_for(article.get("route"))
    texts = adapter.texts(article)

    raw_url = article.get("url")
    normalized = normalize_url(raw_url if isinstance(raw_url, str) else None)

    collected_at = parse_offset_datetime(
        event.get("collected_at") if event.get("collected_at") else article.get("collected_at")
    )
    published_at, corrected = resolve_published_at(
        parse_offset_datetime(article.get("published_at")), collected_at
    )

    # 길이 기준이 된 텍스트로 언어를 본다. 제목을 항상 함께 넣는 이유는 본문 없는 문서에서
    # 제목이 유일한 근거이고, 본문 있는 문서에서도 제목이 언어를 뒤집는 경우가 없기 때문이다.
    basis_text = texts.body or texts.summary
    lang = detect_lang(f"{texts.title}\n{basis_text}".strip(), lang_thresholds)

    return Document(
        url_hash=url_hash(normalized),
        source_id=_text(article.get("source")),
        source_document_id=_text(article.get("article_id")),
        domain=_text(article.get("domain")),
        route=_text(article.get("route")),
        url=normalized,
        url_raw=_text(raw_url),
        title=texts.title,
        body=texts.body,
        body_code=texts.body_code,
        summary=texts.summary,
        lang=lang,
        author=_text(article.get("author")),
        categories=_categories(article.get("categories")),
        members_only=bool(article.get("members_only") or False),
        published_at=published_at,
        published_date=_to_kst_date(published_at),
        ingest_run_id=ingest_run_id,
        collected_at=collected_at,
        content_len=texts.content_len,
        basis=texts.basis,
        expects_body=adapter.expects_body,
        had_raw_body=texts.had_raw_body,
        published_at_corrected=corrected,
        # 본문이 없으면 지문을 만들지 않는다. 제목만으로 SimHash 를 계산하면 해밍 거리가
        # 우연히 가까워지는 일이 흔해서, dev 도메인 전량이 서로 중복으로 판별될 수 있다
        # ([03 §6]).
        simhash=simhash(texts.body) if texts.has_body else None,
    )


def _text(value: Any) -> str | None:
    """문자열로. 공백만 있으면 `None` — 빈 문자열과 없음을 가르지 않는다."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None
