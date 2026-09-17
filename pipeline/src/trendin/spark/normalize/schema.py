"""표준 문서의 Spark 스키마와 `curated` 레이아웃.

규격은 [03 §1](../../../../spark/docs/03-normalization-spec.md) 의 표와 [01 §3] 의 레이아웃이다.

`normalize/documents.Document` 의 파이썬 쪽 정의와 **한 쌍**이다. 한쪽만 고치면 UDF 가
조용히 `null` 을 채운다 — 필드가 이름으로 맞춰지기 때문에 빠진 칸이 오류가 아니라 빈 값이
된다. `test_normalize_schema.py` 가 두 정의를 대조해 그걸 막는다.

**`curated` 로 나가는 칸과 나가지 않는 칸을 여기서 가른다.** [03 §1] 표가 정한 스물하나에
유료 표시·소스 국가 둘을 더해 스물셋이고, 나머지 다섯은 필터와 [03 §7] 집계만 읽는 내부 값이다.
"""

from __future__ import annotations

from pyspark.sql.types import (
    ArrayType,
    BinaryType,
    BooleanType,
    DateType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

# [03 §1] 표의 스물한 칸에 `paywalled`·`source_country` 를 더한 스물세 칸.
# Parquet 에 이 순서로 쓴다.
CURATED_COLUMNS = (
    "url_hash",
    "source_id",
    "source_document_id",
    "domain",
    "route",
    "url",
    "url_raw",
    "title",
    "body",
    "body_code",
    "summary",
    "lang",
    "author",
    "categories",
    "members_only",
    "paywalled",
    "source_country",
    "published_at",
    "published_date",
    "ingest_run_id",
    "collected_at",
    "content_len",
    "dup_of",
)

# `curated` 로 나가지 않는 내부 칸. 필터(`normalize/filters.py`)와 통계
# (`io/stats.py`)가 읽고, Parquet 을 쓰기 전에 떨어진다.
INTERNAL_COLUMNS = (
    "basis",
    "expects_body",
    "had_raw_body",
    "published_at_corrected",
    "simhash",
)

# 파티션. `domain` / `published_date` / `source` / `ingest_run_id` 4단이다 ([01 §3]).
#
# **`source_id` 가 아니라 `source` 다.** [01 §3] 의 레이아웃이 `source=vogue` 이고
# [03 §1] 의 컬럼명은 `source_id` 라, 둘을 동시에 만족시키려면 파티션용 칸이 따로 있어야
# 한다. 파티션 컬럼은 파일 안에 저장되지 않고 경로에만 들어가므로, 데이터에는 `source_id`
# 가 남고 경로에는 `source=` 가 생긴다. 저장이 늘지 않는다.
PARTITION_SOURCE = "source"
PARTITION_COLUMNS = ("domain", "published_date", PARTITION_SOURCE, "ingest_run_id")

# `published_date` 가 `source` 보다 앞인 이유는 [07 §3] 의 소급 재계산이 날짜 범위로
# 읽기 때문이다. `ingest_run_id` 가 맨 뒤인 이유는 `--force` 재처리가 "그 실행이 쓴 것" 을
# 통째로 덮어쓸 단위를 필요로 하기 때문이다 ([02 §6]).

DOCUMENT_SCHEMA = StructType(
    [
        # `sha256(normalized_url)`. 파이프라인 내부에서의 문서 정체성 ([03 §1]).
        StructField("url_hash", BinaryType(), True),
        StructField("source_id", StringType(), True),
        StructField("source_document_id", StringType(), True),
        StructField("domain", StringType(), True),
        StructField("route", StringType(), True),
        StructField("url", StringType(), True),
        StructField("url_raw", StringType(), True),
        # 제목은 필수 필드라 `null` 이 아니다 ([03 §1]). 그래도 nullable 로 두는 이유는
        # Spark 의 non-nullable 이 값을 검사하지 않고 최적화 힌트로만 쓰이기 때문이다 —
        # 거짓이면 조용히 틀린 결과가 나온다. 계약은 `io/contract` 가 지킨다.
        StructField("title", StringType(), True),
        StructField("body", StringType(), True),
        StructField("body_code", StringType(), True),
        StructField("summary", StringType(), True),
        StructField("lang", StringType(), True),
        StructField("author", StringType(), True),
        StructField("categories", ArrayType(StringType()), True),
        StructField("members_only", BooleanType(), True),
        StructField("paywalled", BooleanType(), True),
        # 봉투에서 온다. article.json 에 없는 소스의 속성이라서다. 백필(모드 B)은 `null` 이다.
        StructField("source_country", StringType(), True),
        # 소스가 준 시각을 원본 보존한다 ([03 §3]).
        StructField("published_at", TimestampType(), True),
        # `published_at` 의 KST date. 파티션 키다.
        StructField("published_date", DateType(), True),
        StructField("ingest_run_id", StringType(), True),
        StructField("collected_at", TimestampType(), True),
        StructField("content_len", IntegerType(), True),
        # 근사 중복이면 대표 문서의 `url_hash`. `normalize/dedup.py` 가 채운다.
        StructField("dup_of", BinaryType(), True),
        # --- 내부 칸 -------------------------------------------------------
        StructField("basis", StringType(), True),
        StructField("expects_body", BooleanType(), True),
        StructField("had_raw_body", BooleanType(), True),
        StructField("published_at_corrected", BooleanType(), True),
        # 부호 있는 64비트다. 변환은 `simhash.to_signed64` 가 한다.
        StructField("simhash", LongType(), True),
    ]
)

DOCUMENT_COLUMNS = tuple(field.name for field in DOCUMENT_SCHEMA.fields)
