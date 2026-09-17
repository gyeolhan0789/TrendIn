"""`article.json` → 표준 문서 ([03 §1·§3]). 층 1 ([09 §4]).

**실제 fixture 를 쓴다.** 손으로 옮겨 적은 `article.json` 을 쓰면 생산자 계약이 바뀔 때
이 테스트만 계속 통과한다.
"""

from __future__ import annotations

import json
import pathlib
from datetime import date, datetime, timezone

import pytest

from trendin.spark.normalize.adapters.protocol import BASIS_BODY, BASIS_SUMMARY, BASIS_TITLE
from trendin.spark.normalize.documents import (
    KST,
    build_document,
    parse_offset_datetime,
    resolve_published_at,
)
from trendin.spark.normalize.lang import KO, MIXED

CONTRACT = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "contract"
OBJECTS = CONTRACT / "objects"
RUN_ID = "20260903T000000"


@pytest.fixture(scope="module")
def event() -> dict:
    return json.loads((CONTRACT / "article-event.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def article(event) -> dict:
    return json.loads((OBJECTS / event["object_key"]).read_text(encoding="utf-8"))


def build(article: dict, event: dict, **overrides):
    return build_document(article | overrides, event, ingest_run_id=RUN_ID)


# --- 값의 출처 ------------------------------------------------------------


def test_fixture_기사가_표준_문서가_된다(article, event):
    document = build(article, event)

    assert document.source_id == "vogue"
    assert document.source_document_id == "854414"
    assert document.domain == "fashion"
    assert document.route == "rss"
    assert document.url == "https://www.vogue.co.kr/2026/09/03/some-article"
    # 원본은 따로 보존한다 — 정규화 규칙을 바꿀 때 되짚을 근거다.
    assert document.url_raw == "https://www.vogue.co.kr/2026/09/03/some-article/"
    assert document.title == "2026 F/W 런웨이가 다시 꺼낸 실루엣"
    assert document.ingest_run_id == RUN_ID
    assert document.lang in {KO, MIXED}
    assert document.basis == BASIS_BODY
    assert document.content_len == len(document.body)
    # 3단계가 읽을 지문. 본문이 있으므로 있다.
    assert document.simhash is not None
    # `dup_of` 는 배치 전체를 봐야 정해지므로 여기서 비어 있다.
    assert document.dup_of is None


def test_유료_표시와_소스_국가를_싣는다(article, event):
    """`paywalled` 는 article.json 에서, `source_country` 는 그 파일에 없어 봉투에서 온다."""
    document = build(article, event, paywalled=True)

    assert (document.members_only, document.paywalled) == (False, True)
    assert document.source_country == "KR"


def test_백필_봉투에는_소스_국가가_없다(article, event):
    """모드 B 는 객체 키에서 봉투를 재구성해 국가를 모른다. 지어내지 않는다."""
    document = build_document(article, event | {"source_country": None}, ingest_run_id=RUN_ID)

    assert document.source_country is None
    assert document.paywalled is False


def test_categories_를_채운다(article, event):
    """[03 §1] 이 요구하는 칸이고, 이 스토리에서 `ARTICLE_SCHEMA` 에 더했다."""
    assert build(article, event).categories == ["fashion", "runway"]


@pytest.mark.parametrize("raw", [None, "not a list", []])
def test_categories_가_없으면_빈_목록(article, event, raw):
    """Parquet 에서 `null` 배열과 빈 배열을 가르는 값이 없다 — 읽는 쪽이 두 경우를 다르게
    처리할 일이 없으므로 같게 본다."""
    assert build(article, event, categories=raw).categories == []


def test_collected_at_은_이벤트에서_온다(article, event):
    """[03 §8] 이 `contents.collected_at` 을 **이벤트의** 값으로 못 박았다.

    나머지 값은 `article.json` 에서 온다 — 두 출처를 섞으면 모드 B(`--source objects`)에서
    값이 갈린다. 그쪽은 이벤트를 객체 키에서 재구성하므로 `title` 같은 칸이 애초에 없다.
    """
    document = build_document(
        article, event | {"collected_at": "2026-09-04T00:00:00Z"}, ingest_run_id=RUN_ID
    )

    assert document.collected_at == datetime(2026, 9, 4, tzinfo=timezone.utc)


# --- 본문 유무 분기 ([03 §2]) --------------------------------------------


def test_본문이_없으면_요약을_대용으로_쓴다(article, event):
    """회원 전용 기사가 이 경로다 — fashion 의 7.4%. `exclude_none` 직렬화라 키가 빠진다."""
    without_body = {k: v for k, v in article.items() if k != "body_text"}

    document = build_document(without_body, event, ingest_run_id=RUN_ID)

    assert document.body == ""
    assert document.basis == BASIS_SUMMARY
    assert document.content_len == len(document.summary)
    # 제목만으로 지문을 만들지 않는다 — dev 도메인 전량이 서로 중복으로 판별될 수 있다.
    assert document.simhash is None


def test_본문도_요약도_없으면_제목만으로_통과한다(article, event):
    """`hn` 이 이 경로다 — dev 전량. **버리지 않는다.** 제목만으로도 키워드가 나오고,
    무엇보다 dev 도메인은 이것 말고 입력이 없다 ([03 §2])."""
    bare = {k: v for k, v in article.items() if k not in {"body_text", "summary"}}

    document = build_document(bare | {"route": "api", "source": "hn"}, event, ingest_run_id=RUN_ID)

    assert document.basis == BASIS_TITLE
    assert document.content_len == len(document.title)
    assert not document.had_raw_body
    # `hn` 은 본문이 없는 것이 정상이라 [03 §7] 경보 대상이 아니다.
    assert not document.expects_body


def test_본문이_있었는지를_따로_기록한다(article, event):
    """`basis` 만 보면 링크뿐이던 기사와 애초에 본문이 없는 `hn` 문서가 구분되지 않는다.

    [03 §6] 은 앞쪽을 **제외**하고 뒤쪽을 **통과**시키라고 한다 — 그 판단의 근거가 이 값뿐이다.
    """
    links_only = build(article, event, body_text='<a href="https://x.com">https://x.com</a>')

    assert links_only.had_raw_body
    assert links_only.basis != BASIS_BODY


# --- `published_at` ([03 §3]) --------------------------------------------


def test_발행_시각은_소스_오프셋을_보존한다(article, event):
    """`published_at` 필드 자체는 원본 그대로다. 파티션 계산에만 KST 로 변환한다."""
    document = build(article, event)

    assert document.published_at == datetime(
        2026, 9, 3, 10, 0, tzinfo=timezone(KST.utcoffset(None))
    )
    assert not document.published_at_corrected


def test_발행일_파티션은_KST_다(article, event):
    """불변식 10. UTC 로 자르면 한국 매체 기사가 하루 앞 파티션으로 밀린다."""
    # UTC 로는 9/2 23:00 이지만 KST 로는 9/3 08:00 이다.
    document = build(article, event, published_at="2026-09-02T23:00:00Z")

    assert document.published_date == date(2026, 9, 3)


def test_미래_시각은_collected_at_으로_대체하고_표시한다(article, event):
    """소스가 예약 발행이나 타임존 버그로 미래 날짜를 주는 일이 실제로 있다.

    그대로 두면 아직 오지 않은 날짜에 언급량이 쌓이고, 그 행은 프론트 그래프의 오른쪽 끝을
    이상하게 만든다. 보정 건수는 [03 §7] 이 센다.
    """
    document = build(article, event, published_at="2027-01-01T00:00:00+09:00")

    assert document.published_at == document.collected_at
    assert document.published_at_corrected


def test_보정_기준은_now_가_아니라_collected_at_이다(article, event):
    """`now()` 로 재면 같은 객체를 언제 재처리하느냐에 따라 보정 여부가 갈리고, 백필 결과가
    실행 시각에 의존한다."""
    collected = "2026-09-03T02:10:00Z"
    published = "2026-09-03T02:00:00Z"  # 수집보다 이르다 — 미래가 아니다

    document = build_document(
        article | {"published_at": published},
        event | {"collected_at": collected},
        ingest_run_id=RUN_ID,
    )

    assert not document.published_at_corrected


def test_시각이_없으면_메우지_않는다(article, event):
    """**`published_at` 이 없는 기사는 오지 않는다** — 필수 필드라(불변식 9) 생산자가 저장하지
    않고, 없이 오면 `ARTICLE_CONTRACT_VIOLATION` 으로 이미 DLQ 에서 잡힌다 ([02 §3]).

    여기서 `collected_at` 으로 메우면 그 계약 위반이 정상 문서로 위장된다.
    """
    document = build(article, event, published_at=None)

    assert document.published_at is None
    assert document.published_date is None
    assert not document.published_at_corrected


# --- 시각 파싱 ------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-09-03T02:10:00Z", datetime(2026, 9, 3, 2, 10, tzinfo=timezone.utc)),
        ("2026-09-03T10:00:00+09:00", datetime(2026, 9, 3, 10, 0, tzinfo=KST)),
        (None, None),
        ("", None),
        ("어제", None),
    ],
)
def test_시각_파싱(raw, expected):
    assert parse_offset_datetime(raw) == expected


def test_오프셋이_없으면_UTC_로_가정하지_않는다():
    """조용히 UTC 로 가정하면 한국 매체 기사가 9시간 앞으로 밀려 엉뚱한 날짜 파티션에 쌓이고,
    그 오류는 날짜 경계 근처 기사에서만 나타나 눈에 띄지 않는다."""
    naive = parse_offset_datetime("2026-09-03T10:00:00")

    assert naive is not None
    assert naive.tzinfo is None


def test_오프셋_없는_시각은_비교하지_않는다():
    """비교할 수 없으므로 보정도 하지 않는다. 파티션 계산에서 `None` 으로 걸러진다."""
    naive = datetime(2027, 1, 1)
    collected = datetime(2026, 9, 3, tzinfo=timezone.utc)

    assert resolve_published_at(naive, collected) == (naive, False)
