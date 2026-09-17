"""표준 문서의 파이썬 정의와 Spark 스키마가 한 쌍인지 ([03 §1]). 층 1 ([09 §4]).

**한쪽만 고치면 조용히 깨진다.** UDF 가 사전을 돌려주고 Spark 가 **이름으로** 칸을 맞추므로,
스키마에 없는 칸은 버려지고 사전에 없는 칸은 `null` 이 된다. 둘 다 오류가 아니다 — 그
문서의 그 값이 그냥 비어서 `curated` 에 들어가고, 몇 주 뒤 [04] 에서 "왜 이 칸이 비었지" 로
발견된다.

그래서 이 파일은 기능을 검사하지 않고 **두 정의의 대조**만 한다.
"""

from __future__ import annotations

import dataclasses

import pytest

from trendin.spark.io.schema import ARTICLE_SCHEMA
from trendin.spark.normalize.documents import Document
from trendin.spark.normalize.schema import (
    CURATED_COLUMNS,
    DOCUMENT_COLUMNS,
    DOCUMENT_SCHEMA,
    INTERNAL_COLUMNS,
    PARTITION_COLUMNS,
    PARTITION_SOURCE,
)


def test_스키마와_데이터클래스의_칸이_같다():
    """순서까지 같게 둔다. 이름으로 맞춰지므로 순서가 달라도 동작하지만, 두 정의를 나란히
    읽어야 하는 사람에게는 순서가 정보다."""
    assert DOCUMENT_COLUMNS == tuple(field.name for field in dataclasses.fields(Document))


def test_curated_와_내부_칸이_문서_칸_전부다():
    """빠진 칸이 있으면 그 값이 어디로도 가지 않는다 — Parquet 에도, 통계에도 없다."""
    assert set(CURATED_COLUMNS) | set(INTERNAL_COLUMNS) == set(DOCUMENT_COLUMNS)
    # 겹치면 `curated` 에 내부 판정값이 섞인다.
    assert not set(CURATED_COLUMNS) & set(INTERNAL_COLUMNS)


def test_curated_는_규격의_스물한_칸에_두_칸을_더한_것이다():
    """[03 §1] 표의 스물하나에 `paywalled`·`source_country` 를 더했다. 늘거나 줄면 규격과
    어긋난 것이므로 문서를 먼저 고쳐야 한다."""
    assert len(CURATED_COLUMNS) == 23


def test_파티션은_네_단이고_source_만_문서_칸이_아니다():
    """[01 §3] 의 레이아웃이 `source=vogue` 이고 [03 §1] 의 컬럼명은 `source_id` 다.

    둘을 동시에 만족시키려고 파티션용 칸을 따로 둔다 — 파티션 컬럼은 파일 안에 저장되지
    않고 경로에만 들어가므로 저장이 늘지 않는다.
    """
    assert PARTITION_COLUMNS == ("domain", "published_date", PARTITION_SOURCE, "ingest_run_id")

    partition_only = set(PARTITION_COLUMNS) - set(CURATED_COLUMNS)
    assert partition_only == {PARTITION_SOURCE}


def test_published_date_가_source_보다_앞이다():
    """[07 §3] 의 소급 재계산이 날짜 범위로 읽는다. 순서가 뒤집히면 그 읽기가 전체 스캔이 된다."""
    order = list(PARTITION_COLUMNS)

    assert order.index("published_date") < order.index(PARTITION_SOURCE)


def test_ingest_run_id_가_맨_뒤다():
    """`--force` 재처리가 "그 실행이 쓴 것" 을 통째로 덮어쓸 단위를 필요로 한다 ([02 §6]).

    4단을 없애고 `domain/published_date/source` 로만 자르면 재처리가 그 날짜·소스의
    **모든** 실행분을 함께 덮어쓰고, 범위 밖 문서가 딸려 사라진다 ([01 §3]).
    """
    assert PARTITION_COLUMNS[-1] == "ingest_run_id"


def test_simhash_는_bigint_다():
    """부호 없는 64비트 지문을 그대로 넣으면 조용히 `null` 이 되거나 배치가 죽는다.

    변환은 `simhash.to_signed64` 가 한다.
    """
    field = DOCUMENT_SCHEMA[DOCUMENT_SCHEMA.fieldNames().index("simhash")]

    assert field.dataType.typeName() == "long"


# `article.json` 에서 표준 문서가 읽는 키 전부 (`normalize/documents.py` ·
# `normalize/adapters/texts.py`). 여기 적힌 것이 `ARTICLE_SCHEMA` 에 없으면, 그 칸은
# 계약 문서상 존재하지 않는 값을 읽고 있는 것이다.
ARTICLE_KEYS_READ = (
    "title",
    "body_text",
    "summary",
    "url",
    "published_at",
    "collected_at",
    "source",
    "article_id",
    "domain",
    "route",
    "author",
    "categories",
    "members_only",
    "paywalled",
)


@pytest.mark.parametrize("key", ARTICLE_KEYS_READ)
def test_읽는_키는_계약_스키마에_선언돼_있다(key):
    """**`ARTICLE_SCHEMA` 를 장식으로 두지 않는다.**

    정제는 `json.loads` 로 사전을 읽으므로 그 스키마가 파싱 경로에 있지 않다. 그래서 스키마에
    없는 키를 읽어도 아무 일이 없고, 계약 문서와 코드가 조용히 갈린다. 이 테스트가 그
    스키마를 다시 하중을 받는 자리로 만든다.

    `categories` 가 이 스토리에서 더해진 칸이다 — 170 이 "171 에서 더한다" 로 남겨 뒀다.
    """
    assert key in ARTICLE_SCHEMA.fieldNames()
