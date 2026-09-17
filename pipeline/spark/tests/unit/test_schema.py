"""메시지 스키마. SparkSession 없이 타입만 검사한다.

이 파일이 지키는 것은 **`schema.py` 와 `contract.py` 가 어긋나지 않는 것**이다. 판별이
읽는 필드가 스키마에 없으면 런타임에 조용히 `None` 이 되고, 그러면 계약 위반이 통과한다.
둘이 다른 파일이라 한쪽만 고치는 일이 실제로 생긴다.
"""

from __future__ import annotations

from trendin.spark.io import contract
from trendin.spark.io.schema import ARTICLE_SCHEMA, CORRUPT_FIELD, EVENT_SCHEMA

# 생산자 `collect/events.py` 가 내는 칸 전부. 여기가 바뀌면 그쪽도 바뀐 것이다.
ENVELOPE_FIELDS = {
    "event_id",
    "schema_version",
    "bucket",
    "object_key",
    "raw_object_key",
    "domain",
    "source_id",
    "article_id",
    "run_id",
    "url",
    "title",
    "published_at",
    "collected_at",
    "status",
    "record_count",
    "size_bytes",
    "checksum",
    "format",
    "compression",
    "failure_reason",
    "members_only",
    "paywalled",
    "source_country",
}

# 판별이 실제로 읽는 메시지 필드. `classify` 를 고칠 때 여기도 고쳐야 테스트가 통과한다.
JUDGED_FIELDS = {
    CORRUPT_FIELD,
    "event_id",
    "schema_version",
    "object_key",
    "domain",
    "source_id",
    "article_id",
    "bucket",
    "url",
    "published_at",
    "checksum",
    "status",
    "run_id",
    "record_count",
    "failure_reason",
}


def test_메시지_스키마는_생산자가_내는_칸을_전부_담는다():
    assert set(EVENT_SCHEMA.fieldNames()) == ENVELOPE_FIELDS | {CORRUPT_FIELD}


def test_판별이_읽는_필드가_스키마에_다_있다():
    """없으면 런타임에 None 이 되어 계약 위반이 조용히 통과한다."""
    assert JUDGED_FIELDS <= set(EVENT_SCHEMA.fieldNames())


def test_event_id_와_schema_version_만_non_nullable_이다():
    """나머지를 잠그면 요약 이벤트가 파싱 단계에서 통째로 깨진다.

    두 형태가 같은 메시지를 쓰면서 안 쓰는 칸을 null 로 둔다 (web-collect.md #6).
    어느 칸이 채워져 있어야 하는지는 스키마가 아니라 `contract.classify` 가 정한다.
    """
    required = {f.name for f in EVENT_SCHEMA.fields if not f.nullable}

    assert required == {"event_id", "schema_version"}


def test_시각은_문자열로_받는다():
    """TimestampType 으로 바로 받으면 파싱 실패가 null 이 되어 "값이 없음" 과 섞인다."""
    types = {f.name: f.dataType.simpleString() for f in EVENT_SCHEMA.fields}

    assert types["published_at"] == "string"
    assert types["collected_at"] == "string"


def test_corrupt_칸이_있다():
    """PERMISSIVE 모드가 파싱 실패를 여기 담는다. 스키마에 없으면 Spark 가 채우지 않는다."""
    assert CORRUPT_FIELD in EVENT_SCHEMA.fieldNames()
    assert CORRUPT_FIELD in ARTICLE_SCHEMA.fieldNames()


def test_article_json_의_필수_필드가_스키마에_다_있다():
    assert set(contract.ARTICLE_REQUIRED) <= set(ARTICLE_SCHEMA.fieldNames())


def test_본문_판별에_쓰는_칸이_있다():
    """회원 전용과 hn 을 가르는 유일한 근거다 ([03 §2])."""
    assert "body_text" in ARTICLE_SCHEMA.fieldNames()
