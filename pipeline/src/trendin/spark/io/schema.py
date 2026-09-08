"""Kafka 메시지와 `article.json` 의 명시 스키마 ([02 §1·§3]).

**추론하지 않는다.** `from_json` 에 스키마를 주지 않으면 필드가 하나 빠진 이벤트가 조용히
`null` 로 들어와 하류에서 터진다. 여기가 그 스키마의 단일 출처다.

판별은 이 모듈이 하지 않는다 — `contract.py` 가 한다. 스키마는 "어떤 칸이 있는가" 만
정하고 "어떤 칸이 채워져 있어야 하는가" 는 계약이 정한다. 두 형태가 같은 메시지를 쓰기
때문에 스키마로 잠글 수 없다.
"""

from __future__ import annotations

from pyspark.sql.types import (
    BooleanType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
)

# PERMISSIVE 모드가 파싱 실패를 담는 칸. 스키마에 없으면 Spark 가 채우지 않는다.
CORRUPT_FIELD = "_corrupt_record"

# `event_id` · `schema_version` 만 non-nullable 이다. 나머지가 전부 nullable 인 이유는
# 기사 이벤트와 실행 요약 이벤트가 같은 메시지를 쓰면서 안 쓰는 칸을 null 로 두기 때문이다
# (`web-collect.md` #6). 여기서 잠그면 요약 이벤트가 파싱 단계에서 통째로 깨진다.
EVENT_SCHEMA = StructType(
    [
        StructField("event_id", StringType(), False),
        StructField("schema_version", IntegerType(), False),
        StructField("bucket", StringType(), True),
        # article.json 키. 요약 이벤트는 null 이고, 그것이 두 형태의 판별 기준이다.
        StructField("object_key", StringType(), True),
        # raw.{xml|html|json}. 회원 전용 기사와 요약 이벤트는 null. 우리는 읽지 않는다.
        StructField("raw_object_key", StringType(), True),
        StructField("domain", StringType(), True),
        StructField("source_id", StringType(), True),
        StructField("article_id", StringType(), True),
        # 기사는 null — "기사는 실행에 속하지 않는다".
        StructField("run_id", StringType(), True),
        StructField("url", StringType(), True),
        StructField("title", StringType(), True),
        StructField("published_at", StringType(), True),
        StructField("collected_at", StringType(), True),
        StructField("status", StringType(), True),
        StructField("record_count", LongType(), True),
        # 늘 null. 생산자 수집 이력이 객체 크기를 들고 있지 않아 크기 대조 검증은 없다.
        StructField("size_bytes", LongType(), True),
        # article.json 바이트의 해시. 수집 이력의 content_sha256(raw 의 해시)과 다른 값이다.
        StructField("checksum", StringType(), True),
        StructField("format", StringType(), True),
        StructField("compression", StringType(), True),
        StructField("failure_reason", StringType(), True),
        StructField("members_only", BooleanType(), True),
        StructField(CORRUPT_FIELD, StringType(), True),
    ]
)

# 시각은 문자열로 받고 나중에 캐스팅한다. TimestampType 으로 바로 받으면 파싱 실패가
# null 이 되어 "값이 없음" 과 구분되지 않고, 그러면 계약 위반을 검증에서 놓친다.
#
# `extra` 는 넣지 않는다. `dict[str, Any]` 라 값 타입이 섞여 있고(hn 은 `score` int,
# `by` str) MapType 으로 받으면 한쪽이 깨진다. 170 은 검증이 일이고 `extra` 를 쓰는
# 곳이 없다 — 필요해지는 [04] 에서 소스별 struct 로 좁혀 받는다.
ARTICLE_SCHEMA = StructType(
    [
        StructField("schema_version", IntegerType(), True),
        StructField("domain", StringType(), True),
        StructField("source", StringType(), True),
        StructField("route", StringType(), True),
        StructField("article_id", StringType(), True),
        StructField("url", StringType(), True),
        StructField("title", StringType(), True),
        StructField("published_at", StringType(), True),
        StructField("collected_at", StringType(), True),
        StructField("modified_at", StringType(), True),
        # 회원 전용 기사는 둘 다 없다. exclude_none 직렬화라 키가 아예 빠진다.
        StructField("raw_key", StringType(), True),
        StructField("content_sha256", StringType(), True),
        StructField("summary", StringType(), True),
        # 회원 전용(7.4%)과 hn(dev 전량)에는 없다 ([03 §2]).
        StructField("body_text", StringType(), True),
        StructField("author", StringType(), True),
        StructField("members_only", BooleanType(), True),
        StructField(CORRUPT_FIELD, StringType(), True),
    ]
)

# `categories` 는 array<string> 인데 위 스키마에 없다 — 목록 소스가 발견한 섹션 슬러그가
# 들어오고 [03 §1] 의 표준 문서가 그 값을 쓴다. 171 에서 더한다. 170 이 검증하는 필수
# 필드에 없고, 배열 하나 때문에 스키마를 넓히면 지금 안 쓰는 칸이 는다.
