"""이벤트 계약 판별 ([02 §2](../../../../spark/docs/02-input-contract.md)).

**pyspark 를 import 하지 않는다.** 판별을 매핑 하나에 대한 순수 함수로 두는 이유는 두
가지다 — 완료 조건이 전부 "이 이벤트가 어디로 가는가" 라서 SparkSession 없이 검사할 수
있어야 하고([09 §4](../../../../spark/docs/09-dev-and-test.md) 층 1), 계약이 바뀔 때
고칠 자리가 한 곳이어야 한다.

토픽 하나에 형태가 둘 흐른다 (`pipeline/docs/web-collect.md` #6). 분기는 소비 측 책임이고
판별 기준은 `object_key` 의 유무다.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Mapping

# 아는 메시지 버전. 이보다 높으면 처리하지 않는다 (아래 `_check_schema_version`).
KNOWN_SCHEMA_VERSION = 1

# 이벤트 슬러그 → `keywords.domain` (백엔드 Java enum 상수명).
# 상위 문서 예시는 `development` 지만 실제 발행값은 `dev` 다 — `web-collect.md` #1,
# `collect/contracts.py` 의 `SourceDef.domain`. 여기가 유일한 방어선이라
# ([01 §6](../../../../spark/docs/01-architecture.md)) 목록 밖은 처리하지 않는다.
DOMAIN_VALUES = {
    "dev": "DEVELOP",
    "fashion": "FASHION",
}

# 요약 이벤트의 `status` 허용값. 생산자 `run_summary_event()` 가 이 둘만 낸다.
SUMMARY_STATUSES = frozenset({"success", "failed"})


class EventShape(str, Enum):
    """메시지의 두 형태. `object_key` 가 있으면 기사, 없으면 실행 요약이다."""

    ARTICLE = "ARTICLE"
    SUMMARY = "SUMMARY"


class ErrorType(str, Enum):
    """DLQ 사유 ([02 §5](../../../../spark/docs/02-input-contract.md)).

    배치 계약 시절의 `RECORD_COUNT_MISMATCH`·`DECOMPRESS_ERROR` 는 없다 — 기사 이벤트의
    `record_count` 는 늘 1 이라 대조 대상이 없고, `compression` 이 `none` 이다. 영영
    발생하지 않는 분기를 남겨두지 않는다.
    """

    PARSE_ERROR = "PARSE_ERROR"
    UNKNOWN_SCHEMA_VERSION = "UNKNOWN_SCHEMA_VERSION"
    CONTRACT_VIOLATION = "CONTRACT_VIOLATION"
    UNKNOWN_DOMAIN = "UNKNOWN_DOMAIN"
    OBJECT_NOT_FOUND = "OBJECT_NOT_FOUND"
    CHECKSUM_MISMATCH = "CHECKSUM_MISMATCH"
    ARTICLE_CONTRACT_VIOLATION = "ARTICLE_CONTRACT_VIOLATION"


@dataclass(frozen=True, slots=True)
class Verdict:
    """판별 결과. 통과면 `shape` 가 있고, 실패면 `error_type` 과 사유가 있다.

    둘을 한 타입에 담는 이유는 호출부가 분기를 한 번만 하게 하려는 것이다. 예외로
    올리지 않는 이유는 실패가 예외적 상황이 아니라 **정상적인 출력 경로**(DLQ)라서다.
    """

    shape: EventShape | None = None
    error_type: ErrorType | None = None
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.error_type is None

    @classmethod
    def article(cls) -> "Verdict":
        return cls(shape=EventShape.ARTICLE)

    @classmethod
    def summary(cls) -> "Verdict":
        return cls(shape=EventShape.SUMMARY)

    @classmethod
    def reject(cls, error_type: ErrorType, detail: str) -> "Verdict":
        return cls(error_type=error_type, detail=detail)


def _blank(value: Any) -> bool:
    """`None` 과 빈 문자열을 같게 본다.

    생산자는 빈 문자열을 내지 않지만(pydantic `NonEmptyStr`), 판별을 `is None` 으로만
    쓰면 공백 하나가 유효한 키로 통과해 S3A 조회가 엉뚱한 곳을 친다. 넓게 막는 쪽이 싸다.
    """
    return value is None or (isinstance(value, str) and not value.strip())


def _missing(event: Mapping[str, Any], *fields: str) -> list[str]:
    return [f for f in fields if _blank(event.get(f))]


def parse_offset_datetime(raw: Any) -> datetime | None:
    """ISO-8601 문자열을 `datetime` 으로. 못 읽으면 `None`.

    **오프셋이 없는 값은 UTC 로 보지 않고 그대로 오프셋 없이 둔다.** 조용히 UTC 로 가정하면
    한국 매체 기사가 9시간 앞으로 밀려 엉뚱한 날짜 파티션에 쌓이고, 그 오류는 날짜 경계 근처
    기사에서만 나타나 눈에 띄지 않는다. 오프셋 유무는 부른 쪽(`check_article`,
    `normalize/documents._to_kst_date`)이 본다.

    계약 판별과 정제가 **같은 파서**를 쓰는 것이 이 함수가 여기 있는 이유다 — 둘이 갈리면
    판별은 통과시키고 정제는 `None` 을 내는 값이 생기고, 그 문서는 `published_date` 가 없는
    파티션(`__HIVE_DEFAULT_PARTITION__`)에 쓰인다.
    """
    if isinstance(raw, datetime):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        return datetime.fromisoformat(raw.strip())
    except ValueError:
        return None


def classify(event: Mapping[str, Any], *, corrupt_field: str = "_corrupt_record") -> Verdict:
    """이벤트 하나가 어느 형태인지, 아니면 어떤 이유로 DLQ 인지 판별한다.

    순서가 의미를 갖는다 — 파싱 → 버전 → 공통 필드 → 형태 → 형태별 구조 → 도메인.
    도메인을 맨 뒤에 두는 이유는 구조가 깨진 이벤트의 `domain` 을 보는 것이 무의미하고,
    구조 위반이 `UNKNOWN_DOMAIN` 으로 보고되면 생산자가 엉뚱한 곳을 보게 되기 때문이다.
    """
    corrupt = event.get(corrupt_field)
    if not _blank(corrupt):
        return Verdict.reject(ErrorType.PARSE_ERROR, f"파싱 실패: {str(corrupt)[:200]}")

    verdict = _check_schema_version(event)
    if verdict is not None:
        return verdict

    if _blank(event.get("event_id")):
        return Verdict.reject(ErrorType.CONTRACT_VIOLATION, "event_id 가 없다")

    shape = EventShape.SUMMARY if _blank(event.get("object_key")) else EventShape.ARTICLE
    verdict = _check_article(event) if shape is EventShape.ARTICLE else _check_summary(event)
    if verdict is not None:
        return verdict

    domain = event.get("domain")
    if domain not in DOMAIN_VALUES:
        return Verdict.reject(
            ErrorType.UNKNOWN_DOMAIN,
            f"허용 목록에 없는 domain: {domain!r} (허용: {sorted(DOMAIN_VALUES)})",
        )

    return Verdict.article() if shape is EventShape.ARTICLE else Verdict.summary()


def _check_schema_version(event: Mapping[str, Any]) -> Verdict | None:
    """낮으면 통과, 높으면 DLQ.

    낮은 버전을 처리하는 것이 계약이다 — "필드 추가는 하위 호환, 제거·타입 변경은 값을
    올린다"(`web-collect.md` #10). 높은 값은 우리가 아는 해석이 틀렸을 수 있다는 신호라
    추측으로 처리하지 않는다.
    """
    raw = event.get("schema_version")
    if raw is None:
        return Verdict.reject(ErrorType.CONTRACT_VIOLATION, "schema_version 이 없다")
    try:
        version = int(raw)
    except (TypeError, ValueError):
        return Verdict.reject(
            ErrorType.CONTRACT_VIOLATION, f"schema_version 이 정수가 아니다: {raw!r}"
        )
    if version > KNOWN_SCHEMA_VERSION:
        return Verdict.reject(
            ErrorType.UNKNOWN_SCHEMA_VERSION,
            f"아는 것보다 높은 버전: {version} > {KNOWN_SCHEMA_VERSION}",
        )
    return None


def _check_article(event: Mapping[str, Any]) -> Verdict | None:
    """기사 이벤트의 구조. 통과면 `None`.

    `status` 가 `success` 여야 하는 이유는 기사 이벤트가 **저장 확인 뒤에만** 나가기
    때문이다(`web-collect.md` #7 불변식 5). `failed` 인 기사 이벤트는 생산자 버그다.

    `record_count` 는 검사하지 않는다. 늘 1 이라 대조할 대상이 없다 ([02 §3]).
    """
    status = event.get("status")
    if status != "success":
        return Verdict.reject(
            ErrorType.CONTRACT_VIOLATION,
            f"기사 이벤트의 status 는 success 여야 한다: {status!r}",
        )

    # url·published_at 은 저작권법 제37조 출처 명시라 항상 있다 (불변식 11).
    # bucket 이 없으면 s3a 경로를 만들 수 없다.
    missing = _missing(event, "bucket", "article_id", "url", "published_at")
    if missing:
        return Verdict.reject(
            ErrorType.CONTRACT_VIOLATION, f"기사 이벤트에 필수 필드가 없다: {missing}"
        )

    if _blank(event.get("checksum")):
        return Verdict.reject(
            ErrorType.CONTRACT_VIOLATION, "checksum 이 없다 — 검증할 수 없는 객체는 받지 않는다"
        )
    return None


def _check_summary(event: Mapping[str, Any]) -> Verdict | None:
    """실행 요약 이벤트의 구조. 통과면 `None`.

    `object_key` 가 `null` 인 것은 **계약 위반이 아니라 이 형태의 식별 표지**다. 배치 계약
    시절의 "success 인데 object_key 가 null 이면 DLQ" 를 그대로 두면 요약 이벤트를 전부
    버린다.
    """
    status = event.get("status")
    if status not in SUMMARY_STATUSES:
        return Verdict.reject(
            ErrorType.CONTRACT_VIOLATION,
            f"요약 이벤트의 status 는 {sorted(SUMMARY_STATUSES)} 중 하나다: {status!r}",
        )

    if _blank(event.get("run_id")):
        return Verdict.reject(ErrorType.CONTRACT_VIOLATION, "요약 이벤트에 run_id 가 없다")

    count = event.get("record_count")
    if count is None:
        return Verdict.reject(ErrorType.CONTRACT_VIOLATION, "요약 이벤트에 record_count 가 없다")

    if count < 0:
        return Verdict.reject(ErrorType.CONTRACT_VIOLATION, f"record_count 가 음수다: {count}")

    # `failed` 인데 `record_count > 0` 은 계약 위반이 **아니다** ([02 §2]). 생산자 `publish` 는
    # 소스 성패와 무관하게 그 도메인의 밀린 기사를 전부 내고(`flow.publish_pending`), 그 수를
    # `event_run_id` 로 세어 요약에 싣는다. 그래서 죽은 소스라도 지난 실행의 이월분이나 403·429
    # 를 맞기 전에 저장한 기사가 이번 실행 몫으로 잡힌다. 여기서 0 을 강요하면 그 요약이 DLQ 로
    # 가고 `SOURCE_FAILED` 기록이 사라진다 — 실패를 기록하려고 만든 이벤트가 실패했을 때 버려진다.
    if status == "failed" and _blank(event.get("failure_reason")):
        return Verdict.reject(ErrorType.CONTRACT_VIOLATION, "failed 인데 failure_reason 이 없다")
    return None


CHECKSUM_PREFIX = "sha256-"

# `article.json` 의 필수 필드 (`web-collect.md` #5.3, `collect/article.py`).
# 생산자가 불변식 9 로 이미 막지만, 이벤트가 다른 파일을 가리키는 경우는 checksum 이
# 잡고 못 잡는 나머지를 이게 잡는다.
ARTICLE_REQUIRED = (
    "schema_version",
    "domain",
    "source",
    "route",
    "article_id",
    "url",
    "title",
    "published_at",
    "collected_at",
)


def verify_checksum(expected: str | None, data: bytes) -> Verdict | None:
    """이벤트의 `checksum` 과 받은 **바이트**의 sha256 을 대조한다. 통과면 `None`.

    파싱한 뒤 다시 직렬화해서 해싱하면 키 순서·공백·유니코드 이스케이프가 달라져 전량
    불일치한다. 생산자가 넣는 값은 `article.model_dump_json(exclude_none=True)` 의
    바이트 해시다 (`collect/flow.py:article_bytes`).

    수집 이력의 `content_sha256`(raw 의 해시)과 이름만 비슷한 다른 값이다 ([02 §0]).
    """
    if _blank(expected):
        return Verdict.reject(ErrorType.CONTRACT_VIOLATION, "checksum 이 없다")

    want = str(expected).strip()
    if want.startswith(CHECKSUM_PREFIX):
        want = want[len(CHECKSUM_PREFIX) :]
    got = hashlib.sha256(data).hexdigest()
    if want.lower() != got:
        return Verdict.reject(
            ErrorType.CHECKSUM_MISMATCH,
            f"expected {CHECKSUM_PREFIX}{want}, got {CHECKSUM_PREFIX}{got}",
        )
    return None


def check_article(article: Mapping[str, Any], event: Mapping[str, Any]) -> Verdict | None:
    """`article.json` 이 계약을 지키는지, 그리고 이벤트와 같은 기사를 가리키는지. 통과면 `None`.

    같은 기사인지 보는 이유는 checksum 이 "내용이 온전한가" 에만 답하기 때문이다. 이벤트가
    엉뚱한 (그러나 온전한) 객체를 가리키면 체크섬은 통과하고 도메인·소스가 어긋난 문서가
    들어온다. 그 오염은 몇 주 뒤에 발견된다.
    """
    missing = _missing(article, *ARTICLE_REQUIRED)
    if missing:
        return Verdict.reject(
            ErrorType.ARTICLE_CONTRACT_VIOLATION, f"article.json 에 필수 필드가 없다: {missing}"
        )

    # 있기만 하면 안 된다 — **읽을 수 있고 오프셋이 있어야** 한다. `"invalid-date"` 를 통과시키면
    # 정제가 `published_at=None` 을 내고 `published_date` 없는 파티션에 쓰인다. `collected_at`
    # 도 같은 이유다 — 미래 시각 보정([03 §3])의 기준이라 없으면 보정이 조용히 꺼진다.
    for field in ("published_at", "collected_at"):
        moment = parse_offset_datetime(article.get(field))
        if moment is None or moment.tzinfo is None:
            return Verdict.reject(
                ErrorType.ARTICLE_CONTRACT_VIOLATION,
                f"article.json 의 {field} 가 오프셋 있는 ISO-8601 시각이 아니다: "
                f"{article.get(field)!r}",
            )

    for field in ("domain", "source", "article_id"):
        # 이벤트의 소스 필드명은 `source_id`, article.json 은 `source` 다.
        event_value = event.get("source_id" if field == "source" else field)
        if article.get(field) != event_value:
            return Verdict.reject(
                ErrorType.ARTICLE_CONTRACT_VIOLATION,
                f"이벤트와 article.json 의 {field} 가 다르다: "
                f"{event_value!r} != {article.get(field)!r}",
            )
    return None


def has_body(article: Mapping[str, Any]) -> bool:
    """본문이 있는지. 회원 전용(7.4%) · 유료 표시 · `hn`(dev 전량)은 `body_text` 가 없다.

    이벤트만으로는 판별할 수 없다 — `members_only` · `paywalled` 는 본문이 없는 이유일 뿐이고
    `hn` 은 둘 다 `false` 다. 그래서 객체를 읽어 이 함수로 본다 ([02 §3], [03 §2]).
    """
    return not _blank(article.get("body_text"))


def keywords_domain(event_domain: str) -> str:
    """이벤트 슬러그를 `keywords.domain` 값으로 바꾼다.

    `classify` 가 이미 허용 목록을 통과시킨 이벤트에만 부른다. 목록 밖이면 여기서 죽는 것이
    맞다 — 조용히 슬러그를 그대로 넣으면 `dev` 와 `DEVELOP` 이 별개 분야로 나뉜다.
    """
    try:
        return DOMAIN_VALUES[event_domain]
    except KeyError:  # pragma: no cover - classify 가 먼저 막는다
        raise ValueError(f"허용 목록에 없는 domain: {event_domain!r}") from None
