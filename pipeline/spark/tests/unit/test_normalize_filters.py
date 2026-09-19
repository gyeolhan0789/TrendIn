"""품질 필터 ([03 §6]). 층 1 ([09 §4]).

**본문 유무 분기가 이 파일의 요점이다.** 규격의 필터 표는 `body` 가 있는 문서에만
적용되고, 그 분기를 놓치면 회원 전용 7.4% 와 dev 도메인 전량이 통째로 사라진다.
"""

from __future__ import annotations

import json
import pathlib
from datetime import date

import pytest

from trendin.spark.normalize.adapters.protocol import BASIS_BODY, BASIS_SUMMARY, BASIS_TITLE
from trendin.spark.normalize.documents import Document, build_document
from trendin.spark.normalize.filters import (
    EMPTY_BODY,
    INVALID_PUBLISHED_AT,
    KEPT,
    NO_URL,
    SHORT_BODY,
    SHORT_TITLE,
    UNKNOWN_LANG,
    URL_TOO_LONG,
    FilterThresholds,
    exclusion_reason,
)
from trendin.spark.normalize.lang import FR, IT, JA, KO, UNKNOWN, ZH
from trendin.spark.normalize.urls import URL_MAX_BYTES

LIMITS = FilterThresholds(min_body_len=100, min_title_len=5)


def document(**overrides) -> Document:
    """통과하는 문서 하나. 검사할 칸만 덮어쓴다."""
    defaults = dict(
        url_hash=b"\x00" * 32,
        source_id="vogue",
        source_document_id="854414",
        domain="fashion",
        route="rss",
        url="https://www.vogue.co.kr/a",
        url_raw="https://www.vogue.co.kr/a/",
        title="2026 F/W 런웨이가 다시 꺼낸 실루엣",
        body="가" * 200,
        body_code="",
        summary="",
        lang=KO,
        author="홍길동",
        content_len=200,
        basis=BASIS_BODY,
        had_raw_body=True,
        published_date=date(2026, 9, 3),
    )
    return Document(**(defaults | overrides))


def test_정상_문서는_통과한다():
    assert exclusion_reason(document(), LIMITS) == KEPT


# --- URL — 다른 검사보다 먼저 본다 ---------------------------------------


def test_URL_이_없으면_NO_URL():
    """`contents` 에 넣을 수 없으므로 다른 검사가 무의미하다."""
    assert exclusion_reason(document(url=None, url_hash=None), LIMITS) == NO_URL


def test_URL_이_너무_길면_제외한다():
    """`contents.url` 이 varchar UNIQUE 라 인덱스 항목 상한(약 2704바이트)을 넘으면
    `INSERT` 가 오류로 죽고 **배치 하나가 통째로 실패한다** ([03 §8]).

    드물지만 드물게 전체를 죽이는 종류라 반드시 막는다.
    """
    long_url = "https://a.com/" + "x" * URL_MAX_BYTES

    assert exclusion_reason(document(url=long_url), LIMITS) == URL_TOO_LONG


# --- 본문이 있었던 문서 --------------------------------------------------


def test_정제_후_본문이_비면_제외한다():
    """**이 줄이 이 파일에서 가장 중요하다.**

    링크만 있던 기사는 정제 후 본문이 비어 `basis` 가 요약·제목으로 떨어진다. 그러면
    "본문 없는 문서" 의 관대한 검사(제목 길이만)를 통과해버리고, [03 §6] 이 "제외" 라고
    적은 두 줄("빈 본문", "링크만 있고 텍스트가 없음")이 영영 발동하지 않는다.

    **그리고 아무 증상도 없다** — 통계에도 잡히지 않고 그 문서는 그냥 `curated` 에 들어간다.
    """
    links_only = document(body="", basis=BASIS_TITLE, content_len=30, had_raw_body=True)

    assert exclusion_reason(links_only, LIMITS) == EMPTY_BODY


def test_본문이_하한보다_짧으면_제외한다():
    """키워드를 뽑을 것이 없다."""
    short = document(body="가" * 50, content_len=50)

    assert exclusion_reason(short, LIMITS) == SHORT_BODY


def test_본문이_있는데_lang_이_unknown_이면_제외한다():
    """토크나이저를 고를 수 없다 ([04 §2]). 없는 근거로 고르면 후보가 전부 잡음이 된다."""
    assert exclusion_reason(document(lang=UNKNOWN), LIMITS) == UNKNOWN_LANG


# --- 본문이 애초에 없던 문서 ([03 §2]) ------------------------------------


@pytest.mark.parametrize("basis", [BASIS_SUMMARY, BASIS_TITLE])
def test_본문_없는_문서는_제목_길이만_본다(basis):
    """회원 전용(fashion 7.4%)과 `hn`(dev 전량). 본문 길이 하한을 타지 않는다."""
    bodyless = document(body="", basis=basis, content_len=10, had_raw_body=False)

    assert exclusion_reason(bodyless, LIMITS) == KEPT


def test_본문_없는_문서에는_lang_필터를_걸지_않는다():
    """**제목만으로는 대개 `unknown` 이 나온다**(글자 수 하한). 여기서 `lang` 을 걸면
    dev 도메인이 통째로 사라진다.

    그 문서들의 토크나이저를 무엇으로 고를지는 [00 §7] 한계 19번의 결론이 정한다 — 정제
    규격으로 덮을 문제가 아니다.
    """
    hn = document(
        body="", basis=BASIS_TITLE, content_len=20, had_raw_body=False, lang=UNKNOWN
    )

    assert exclusion_reason(hn, LIMITS) == KEPT


def test_제목이_너무_짧으면_제외한다():
    """제목은 필수 필드라 비어 있을 수 없지만(불변식 9) 한두 글자짜리는 걸러낸다."""
    stub = document(title="속보", body="", basis=BASIS_TITLE, content_len=2, had_raw_body=False)

    assert exclusion_reason(stub, LIMITS) == SHORT_TITLE


# --- 추출하지 않는 언어 -----------------------------------------------------

CONTRACT = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "contract"


def built(**article_overrides) -> Document:
    """실제 fixture 기사로 정제한 문서. 판별부터 필터까지 정제가 실제로 타는 길을 그대로 탄다."""
    event = json.loads((CONTRACT / "article-event.json").read_text(encoding="utf-8"))
    article = json.loads((CONTRACT / "objects" / event["object_key"]).read_text(encoding="utf-8"))
    return build_document(article | article_overrides, event, ingest_run_id="20260903T000000")


def test_일본어_제목만_있는_문서도_추출한다():
    """판별은 여전히 `ja` 를 알아본다. 달라진 것은 그 뒤다 — 알아본 언어를 빼지 않는다."""
    doc = built(title="新作バッグが東京で発表された", summary=None, body_text=None)

    assert (doc.basis, doc.lang) == (BASIS_TITLE, JA)
    assert exclusion_reason(doc, LIMITS) == KEPT


def test_프랑스어_본문_문서도_추출한다():
    """`en` 으로 뒤집히지 않는 것이 여기 요점이다. 판별이 `fr` 을 맞히면 그 언어로 처리된다."""
    body = (
        "<p>La maison a présenté sa nouvelle collection à Paris. Les créations sont inspirées "
        "par les années soixante et la directrice artistique explique que cette saison est "
        "très importante pour elle et pour les clientes fidèles de la marque.</p>"
    )
    doc = built(title="La nouvelle collection de la maison", body_text=body)

    assert (doc.basis, doc.lang) == (BASIS_BODY, FR)
    assert exclusion_reason(doc, LIMITS) == KEPT


@pytest.mark.parametrize("lang", [JA, ZH, FR, IT])
@pytest.mark.parametrize("basis", [BASIS_BODY, BASIS_SUMMARY, BASIS_TITLE])
def test_다국어는_경로와_무관하게_추출한다(lang, basis):
    """2026-09-19 이전에는 이 넷이 `UNSUPPORTED_LANG` 이었다. 일본 매체 7곳·이탈리아 3곳·
    프랑스 3곳·중국 2곳이 통째로 버려지고 있었고, 그 자리가 `lang.LANGUAGES` 한 칸이다."""
    doc = document(lang=lang, basis=basis, had_raw_body=basis == BASIS_BODY)

    assert exclusion_reason(doc, LIMITS) == KEPT


def test_URL_검사가_언어보다_먼저다():
    """기존 순서를 지킨다 — `contents` 에 못 넣는 문서는 다른 사유가 무의미하다."""
    assert exclusion_reason(document(url=None, lang=FR), LIMITS) == NO_URL


# --- 저자 상한 -----------------------------------------------------------


def test_저자_상한은_여기서_보지_않는다():
    """규격이 "제외하지 않고 표시" 로 정했고([03 §6]) 그 표시는 [07 §7] 의 기여 상한이 쓴다.

    게다가 이 소스 셋에서는 저자 기반 봇 방어가 거의 의미가 없다 — 매체 기사의 저자는 소속
    기자라 문서 수가 원래 많고 `hn` 의 `author` 는 투고자다. 정상 기자를 봇으로 누르지
    않으려면 실제 분포를 재기 전까지 끄는 것이 맞다.
    """
    prolific = document(author="홍길동")

    assert exclusion_reason(prolific, LIMITS) == KEPT


# --- 문턱 ----------------------------------------------------------------


def test_문턱은_설정에서_온다():
    """[S6] 이 실데이터의 문서 길이 분포를 재고 확정한다 ([09 §7] 항목 5)."""
    doc = document(body="가" * 150, content_len=150)

    assert exclusion_reason(doc, FilterThresholds(min_body_len=100)) == KEPT
    assert exclusion_reason(doc, FilterThresholds(min_body_len=200)) == SHORT_BODY


def test_빈_구역이면_기본값이다():
    """`slots=True` 에서 `cls.min_body_len` 은 슬롯 서술자라, 기본값을 클래스에서 읽으면
    설정 구역이 빈 모든 실행이 `TypeError` 로 죽는다."""
    assert FilterThresholds.from_section({}) == FilterThresholds()


def test_설정_구역에서_읽는다():
    thresholds = FilterThresholds.from_section({"min_body_len": 42})

    assert thresholds.min_body_len == 42
    assert thresholds.min_title_len == FilterThresholds().min_title_len


def test_문턱을_주지_않으면_기본값으로_판단한다():
    """정제는 문턱이 없으면 아무 문서도 걸러지지 않고 조용히 전량 통과한다 — 04~07 의
    임계값과 달리 "없으면 거부" 로 둘 수 없는 이유다 (`conf/base.yaml`)."""
    assert exclusion_reason(document(body="가" * 3, content_len=3)) == SHORT_BODY


def test_발행일을_못_정한_문서는_제외한다():
    """`published_date` 가 없으면 `curated` 가 `__HIVE_DEFAULT_PARTITION__` 에 쓴다 — 날짜
    파티션 계약([01 §3])이 깨지고 집계에서 누락된다. 계약 판별이 먼저 막지만 여기가 마지막
    방어선이다.
    """
    assert exclusion_reason(document(published_date=None), LIMITS) == INVALID_PUBLISHED_AT
