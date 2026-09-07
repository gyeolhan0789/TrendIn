"""세션 팩토리가 실제로 세션을 만드는지. 여기가 통과해야 spark-submit 이 돈다."""

from __future__ import annotations

from trendin.spark.common.config import Config
from trendin.spark.common.session import build_session


def test_인메모리_DataFrame_이_돈다(spark):
    rows = spark.createDataFrame([(1, "a"), (2, "b")], "id int, name string")

    assert rows.count() == 2
    assert rows.columns == ["id", "name"]


def test_build_session_이_설정을_세션에_넣는다():
    """이미 떠 있는 세션을 재사용하므로 master 는 픽스처가 정한 값이 남는다."""
    config = Config(
        {"spark": {"master": "local[2]", "conf": {"spark.sql.shuffle.partitions": 3}}},
        profile="test",
    )

    session = build_session("test", config)

    assert session.conf.get("spark.sql.shuffle.partitions") == "3"
