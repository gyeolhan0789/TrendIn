"""`curated` 읽기 (`extract/source.read_curated`). 층 2 — 실제 Parquet 을 쓴다 ([09 §4]).

**칸이 다른 세대가 한 버킷에 섞여 있다.** `source_country` 는 2026-09-17 에 들어왔고 그전
파티션에는 없다. 그 섞임을 스키마 추론에 맡기면 실행이 어떤 날은 죽고 어떤 날은 도는,
재현되지 않는 실패가 된다. 여기서 보는 것이 그것이다.
"""

from __future__ import annotations

import datetime as dt
import hashlib

from pyspark.sql import functions as F

from trendin.spark.extract import source

OLD_RUN = "20260916T000000"
NEW_RUN = "20260918T000000"

# `source_country` 가 없던 세대. 파티션 칸(`domain`·`published_date`·`source`·`ingest_run_id`)
# 은 경로에서 오므로 파일에는 들어가지 않는다.
OLD_COLUMNS = tuple(name for name in source.COLUMNS if name != "source_country")


def h(text: str) -> bytes:
    return hashlib.sha256(text.encode()).digest()


def row(url: str, *, country: str | None) -> dict:
    values = {
        "url_hash": bytearray(h(url)),
        "source_id": "vogue",
        "domain": "fashion",
        "title": "샤넬 크루즈 컬렉션",
        "body": "샤넬의 새 시즌이다.",
        "lang": "ko",
        "author": None,
        "source_country": country,
        "published_at": dt.datetime(2026, 9, 3, 9, 0),
        "published_date": dt.date(2026, 9, 3),
        "dup_of": None,
        "ingest_run_id": OLD_RUN if country is None else NEW_RUN,
    }
    return values


def write_generation(spark, root: str, *, columns: tuple[str, ...], rows: list[dict]) -> None:
    """한 세대의 파티션을 쓴다. `columns` 에 없는 칸은 파일에 들어가지 않는다."""
    fields = {field.name: field for field in source.curated_schema().fields}
    from pyspark.sql.types import StructType

    schema = StructType([fields[name] for name in columns])
    frame = spark.createDataFrame([tuple(item[name] for name in columns) for item in rows], schema)
    (
        frame.withColumn("source", F.col("source_id"))
        .write.mode("append")
        .partitionBy("domain", "published_date", "source", "ingest_run_id")
        .parquet(root)
    )


def test_국가_칸이_없던_파티션도_읽힌다(writable_spark, tmp_path):
    """옛 파티션에서는 `null` 이고, 뒤에서 `XX` 로 접힌다 (`extract/batch.py`).

    스키마를 명시하지 않으면 이 조합에서 `source_country` 를 찾지 못해 죽을 수 있다 —
    어느 파일로 스키마를 정하는지가 리스팅 순서에 달려 있기 때문이다.
    """
    root = str(tmp_path / "curated")
    write_generation(writable_spark, root, columns=OLD_COLUMNS, rows=[row("old", country=None)])
    write_generation(writable_spark, root, columns=source.COLUMNS, rows=[row("new", country="KR")])

    frame = source.read_curated(writable_spark, config=None, root=root)

    assert tuple(frame.columns) == source.COLUMNS
    countries = {bytes(r["url_hash"]): r["source_country"] for r in frame.collect()}
    assert countries[h("old")] is None
    assert countries[h("new")] == "KR"


def test_읽는_칸의_타입을_정제_스키마에서_가져온다():
    """두 정의가 한 쌍이다. 타입을 두 곳에 적으면 파케이가 조용히 다르게 읽힌다."""
    from trendin.spark.normalize.schema import DOCUMENT_SCHEMA

    declared = {field.name: field.dataType for field in DOCUMENT_SCHEMA.fields}
    for field in source.curated_schema().fields:
        assert field.dataType == declared[field.name]
