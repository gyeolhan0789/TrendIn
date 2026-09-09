"""`io/jdbc.sql_rows` — 드라이버로 모은 행이 psycopg2 에 그대로 들어가는 모양인지 ([08 §4], 층 2).

`stage_and_merge` 자체는 PostgreSQL 이 필요해 층 3 이다. 여기서는 그 앞 단계 — timestamp 가
오프셋 붙은 문자열로, 바이트가 바이트로, `None` 이 `None` 으로 내려오는지만 본다.
"""

from __future__ import annotations

from datetime import datetime, timezone

from trendin.spark.io import jdbc


def test_timestamp_는_오프셋이_붙은_문자열로_내려온다(spark):
    """`collect()` 가 주는 파이썬 `datetime` 은 오프셋이 없어 PostgreSQL 이 세션 시간대로 해석한다.
    문자열에 오프셋을 붙이면 양쪽 설정과 무관하다. 테스트 세션은 UTC 다 (`conftest.py`)."""
    moment = datetime(2026, 9, 3, 2, 10, 0, tzinfo=timezone.utc)
    frame = spark.createDataFrame([("e1", moment)], "event_id string, collected_at timestamp")

    rows = jdbc.sql_rows(frame, ("event_id", "collected_at"))

    assert rows == [("e1", "2026-09-03 02:10:00.000000+00:00")]


def test_바이트와_None_은_그대로다(spark):
    frame = spark.createDataFrame(
        [(bytearray(b"\x00\x01"), None)], "url_hash binary, body_object_key string"
    )

    [(url_hash, key)] = jdbc.sql_rows(frame, ("url_hash", "body_object_key"))

    assert bytes(url_hash) == b"\x00\x01"
    assert key is None


def test_칸_순서는_받은_columns_를_따른다(spark):
    """`INSERT INTO ... (columns) VALUES %s` 가 이 순서를 그대로 쓴다.
    어긋나면 값이 옆 칸에 들어간다.
    """
    frame = spark.createDataFrame([(1, "a")], "n int, s string")

    assert jdbc.sql_rows(frame, ("s", "n")) == [("a", 1)]
