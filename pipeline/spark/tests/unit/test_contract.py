"""이벤트 계약 판정. SparkSession 없이 검사한다 ([09 §4] 층 1).

완료 조건이 전부 "이 이벤트가 어디로 가는가" 라서 이 파일이 170 의 주 검증이다.
통합 테스트(층 3)는 배선이 맞는지만 본다.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from trendin.spark.io.contract import (
    DOMAIN_VALUES,
    ErrorType,
    EventShape,
    check_article,
    classify,
    has_body,
    keywords_domain,
    verify_checksum,
)

# --- 픽스처 --------------------------------------------------------------
# 생산자 `collect/events.py` 의 `article_event()` · `run_summary_event()` 출력 모양을
# 그대로 옮겼다. 필드를 빼거나 더하면 그쪽 구현과 어긋난 것이다.


def article_event(**overrides):
    event = {
        "event_id": "vogue-854414",
        "schema_version": 1,
        "bucket": "raw-data",
        "object_key": "fashion/vogue/rss/2026/09/03/854414/article.json",
        "raw_object_key": "fashion/vogue/rss/2026/09/03/854414/raw.xml",
        "domain": "fashion",
        "source_id": "vogue",
        "article_id": "854414",
        "run_id": None,
        "url": "https://www.vogue.co.kr/2026/09/03/854414",
        "title": "제목",
        "published_at": "2026-09-03T10:00:00+09:00",
        "collected_at": "2026-09-03T11:10:00+09:00",
        "status": "success",
        "record_count": 1,
        "size_bytes": None,
        "checksum": "sha256-abc",
        "format": "json",
        "compression": "none",
        "failure_reason": None,
        "members_only": False,
    }
    event.update(overrides)
    return event


def summary_event(**overrides):
    event = {
        "event_id": "vogue-20260903T000000",
        "schema_version": 1,
        "bucket": "raw-data",
        "object_key": None,
        "raw_object_key": None,
        "domain": "fashion",
        "source_id": "vogue",
        "article_id": None,
        "run_id": "20260903T000000",
        "url": None,
        "title": None,
        "published_at": None,
        "collected_at": "2026-09-03T00:00:00+09:00",
        "status": "success",
        "record_count": 12,
        "size_bytes": None,
        "checksum": None,
        "format": None,
        "compression": None,
        "failure_reason": None,
        "members_only": None,
    }
    event.update(overrides)
    return event


# --- 두 모양 분기 ---------------------------------------------------------


def test_object_key_가_있으면_기사_이벤트다():
    assert classify(article_event()).shape is EventShape.ARTICLE


def test_object_key_가_null_이면_요약_이벤트고_계약_위반이_아니다():
    """배치 계약의 "success 인데 object_key null 이면 DLQ" 를 남겨두면 여기서 전부 버린다."""
    verdict = classify(summary_event())

    assert verdict.ok
    assert verdict.shape is EventShape.SUMMARY


@pytest.mark.parametrize("value", ["", "   "])
def test_object_key_가_공백뿐이면_기사로_보지_않는다(value):
    """공백을 유효한 키로 통과시키면 S3A 가 엉뚱한 경로를 친다.

    요약으로 분기되고, 기사 봉투에는 `run_id` 가 없으니 계약 위반으로 떨어진다. 어느
    쪽이든 **원문 조회로 가지 않는 것**이 이 테스트가 지키는 것이다.
    """
    verdict = classify(article_event(object_key=value))

    assert verdict.shape is not EventShape.ARTICLE
    assert verdict.error_type is ErrorType.CONTRACT_VIOLATION


def test_공백_object_key_에_run_id_가_있으면_요약으로_통과한다():
    """생산자가 null 대신 빈 문자열을 내게 바뀌어도 요약 경로가 살아 있어야 한다."""
    verdict = classify(summary_event(object_key=""))

    assert verdict.ok
    assert verdict.shape is EventShape.SUMMARY


# --- 완료 조건: 계약 위반 다섯 갈래 ---------------------------------------


def test_파싱_실패는_PARSE_ERROR_다():
    verdict = classify({"_corrupt_record": '{"event_id": '})

    assert verdict.error_type is ErrorType.PARSE_ERROR


@pytest.mark.parametrize("version", [2, 99])
def test_아는_것보다_높은_버전은_DLQ_다(version):
    verdict = classify(article_event(schema_version=version))

    assert verdict.error_type is ErrorType.UNKNOWN_SCHEMA_VERSION


def test_낮은_버전은_처리한다():
    """필드 추가는 하위 호환이 계약이다 (web-collect.md #10)."""
    assert classify(article_event(schema_version=0)).ok


def test_schema_version_이_없으면_계약_위반이다():
    verdict = classify(article_event(schema_version=None))

    assert verdict.error_type is ErrorType.CONTRACT_VIOLATION


def test_허용_목록에_없는_domain_은_UNKNOWN_DOMAIN_이다():
    verdict = classify(article_event(domain="beauty"))

    assert verdict.error_type is ErrorType.UNKNOWN_DOMAIN


def test_development_는_걸리고_dev_는_통과한다():
    """상위 문서 예시는 development 지만 실제 발행값은 dev 다 ([01 §6])."""
    assert classify(article_event(domain="development")).error_type is ErrorType.UNKNOWN_DOMAIN
    assert classify(article_event(domain="dev")).ok


def test_checksum_이_없는_기사_이벤트는_계약_위반이다():
    verdict = classify(article_event(checksum=None))

    assert verdict.error_type is ErrorType.CONTRACT_VIOLATION


@pytest.mark.parametrize("field", ["bucket", "article_id", "url", "published_at"])
def test_기사_이벤트의_필수_필드가_없으면_계약_위반이다(field):
    """url·published_at 은 저작권법 제37조 출처 명시라 항상 있다 (불변식 11)."""
    verdict = classify(article_event(**{field: None}))

    assert verdict.error_type is ErrorType.CONTRACT_VIOLATION
    assert field in verdict.detail


def test_기사_이벤트가_success_가_아니면_계약_위반이다():
    """기사 이벤트는 저장 확인 뒤에만 나간다 (불변식 5). failed 는 생산자 버그다."""
    verdict = classify(article_event(status="failed", failure_reason="어쩌다"))

    assert verdict.error_type is ErrorType.CONTRACT_VIOLATION


# --- 완료 조건: failed 요약 이벤트 ----------------------------------------


def test_failed_요약_이벤트는_통과하고_요약으로_분류된다():
    """원장에 SOURCE_FAILED 로 남기고 원문 조회를 건너뛰는 경로다."""
    verdict = classify(summary_event(status="failed", record_count=0, failure_reason="태스크 실패"))

    assert verdict.ok
    assert verdict.shape is EventShape.SUMMARY


def test_record_count_0_인_success_요약은_정상이다():
    """0 건도 정상 수집이면 이벤트를 낸다 (팀 발행 규약 4)."""
    assert classify(summary_event(record_count=0)).ok


def test_failed_인데_건수가_0_이_아니면_계약_위반이다():
    verdict = classify(summary_event(status="failed", record_count=3, failure_reason="x"))

    assert verdict.error_type is ErrorType.CONTRACT_VIOLATION


def test_failed_인데_사유가_없으면_계약_위반이다():
    verdict = classify(summary_event(status="failed", record_count=0, failure_reason=None))

    assert verdict.error_type is ErrorType.CONTRACT_VIOLATION


def test_모르는_status_는_계약_위반이다():
    verdict = classify(summary_event(status="partial"))

    assert verdict.error_type is ErrorType.CONTRACT_VIOLATION


def test_요약_이벤트에_run_id_가_없으면_계약_위반이다():
    verdict = classify(summary_event(run_id=None))

    assert verdict.error_type is ErrorType.CONTRACT_VIOLATION


def test_event_id_가_없으면_계약_위반이다():
    """멱등 판정 키다. 없으면 중복을 걸러낼 수 없다."""
    verdict = classify(article_event(event_id=None))

    assert verdict.error_type is ErrorType.CONTRACT_VIOLATION


def test_구조가_깨진_이벤트는_domain_보다_구조를_먼저_보고한다():
    """구조 위반이 UNKNOWN_DOMAIN 으로 보고되면 생산자가 엉뚱한 곳을 본다."""
    verdict = classify(article_event(domain="beauty", url=None))

    assert verdict.error_type is ErrorType.CONTRACT_VIOLATION


# --- checksum ------------------------------------------------------------


def test_바이트_해시가_맞으면_통과한다():
    data = b'{"title":"\xed\x95\x9c\xea\xb8\x80"}'

    assert verify_checksum(f"sha256-{hashlib.sha256(data).hexdigest()}", data) is None


def test_접두어가_없어도_대조한다():
    data = b"x"

    assert verify_checksum(hashlib.sha256(data).hexdigest(), data) is None


def test_해시가_다르면_CHECKSUM_MISMATCH_다():
    verdict = verify_checksum("sha256-" + "0" * 64, b"x")

    assert verdict.error_type is ErrorType.CHECKSUM_MISMATCH


def test_재직렬화한_바이트로_해싱하면_불일치한다():
    """받은 바이트를 먼저 해싱해야 하는 이유. 키 순서·공백만 달라도 값이 바뀐다."""
    original = b'{"b":1,"a":2}'
    expected = f"sha256-{hashlib.sha256(original).hexdigest()}"
    round_tripped = json.dumps(json.loads(original), sort_keys=True).encode()

    assert verify_checksum(expected, original) is None
    assert verify_checksum(expected, round_tripped).error_type is ErrorType.CHECKSUM_MISMATCH


# --- article.json --------------------------------------------------------


def article_json(**overrides):
    article = {
        "schema_version": 1,
        "domain": "fashion",
        "source": "vogue",
        "route": "rss",
        "article_id": "854414",
        "url": "https://www.vogue.co.kr/2026/09/03/854414",
        "title": "제목",
        "published_at": "2026-09-03T10:00:00+09:00",
        "collected_at": "2026-09-03T02:10:00+00:00",
        "raw_key": "fashion/vogue/rss/2026/09/03/854414/raw.xml",
        "content_sha256": "deadbeef",
        "body_text": "본문",
    }
    article.update(overrides)
    return article


def test_정상_article_json_은_통과한다():
    assert check_article(article_json(), article_event()) is None


@pytest.mark.parametrize("field", ["domain", "source", "route", "url", "title", "published_at"])
def test_필수_필드가_없으면_ARTICLE_CONTRACT_VIOLATION_이다(field):
    verdict = check_article(article_json(**{field: None}), article_event())

    assert verdict.error_type is ErrorType.ARTICLE_CONTRACT_VIOLATION


def test_이벤트가_다른_기사를_가리키면_잡는다():
    """checksum 은 "내용이 온전한가" 에만 답한다. 온전한 엉뚱한 객체는 여기서 걸린다."""
    verdict = check_article(article_json(article_id="999"), article_event())

    assert verdict.error_type is ErrorType.ARTICLE_CONTRACT_VIOLATION
    assert "article_id" in verdict.detail


def test_이벤트의_source_id_와_article_json_의_source_를_맞춘다():
    """필드 이름이 다르다. 그대로 비교하면 늘 불일치한다."""
    assert check_article(article_json(), article_event()) is None
    assert check_article(article_json(source="gqkorea"), article_event()) is not None


# --- 본문 유무 -----------------------------------------------------------


def test_본문이_있으면_True():
    assert has_body(article_json()) is True


@pytest.mark.parametrize("value", [None, "", "   "])
def test_본문이_없으면_False(value):
    """회원 전용 7.4% 와 hn 전량이 이 경우다. 정상 입력이므로 버리지 않는다 ([03 §2])."""
    assert has_body(article_json(body_text=value)) is False


def test_body_text_키가_아예_없어도_False():
    """exclude_none 직렬화라 값이 없으면 키가 빠진다."""
    article = article_json()
    del article["body_text"]

    assert has_body(article) is False


# --- domain 매핑 ---------------------------------------------------------


def test_슬러그를_enum_상수명으로_바꾼다():
    assert keywords_domain("dev") == "DEVELOP"
    assert keywords_domain("fashion") == "FASHION"


def test_허용_목록은_둘뿐이다():
    """소스가 늘면 사전 통보가 필요하다. 이 테스트가 그 통보를 강제한다."""
    assert set(DOMAIN_VALUES) == {"dev", "fashion"}


def test_목록_밖은_조용히_통과시키지_않는다():
    with pytest.raises(ValueError):
        keywords_domain("beauty")
