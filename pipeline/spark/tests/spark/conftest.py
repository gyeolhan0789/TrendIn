"""층 2 — 실제 SparkSession 을 쓰는 테스트 (09 §4).

세션 생성이 느리므로 **세션 스코프로 한 번만** 만든다. 테스트마다 만들면 전체 실행이
몇 분 단위가 되고 아무도 안 돌리게 된다.

Kafka · MinIO · PostgreSQL 은 쓰지 않는다. 입력은 인메모리 DataFrame, 출력은 임시 디렉터리다.
"""

from __future__ import annotations

import pytest

from trendin.spark.common.session import ensure_worker_python

pyspark = pytest.importorskip("pyspark", reason="pyspark 가 없으면 층 2 는 건너뛴다")


@pytest.fixture(scope="session")
def spark():
    from pyspark.sql import SparkSession

    # 드라이버와 worker 의 파이썬이 갈리면 첫 UDF 에서 죽는다. 진입점과 같은 처리를 한다.
    ensure_worker_python()
    session = (
        SparkSession.builder.master("local[2]")
        .appName("trendin-tests")
        # 테스트에서 200 개 파티션은 순수 대기 시간이다.
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    session.sparkContext.setLogLevel("ERROR")
    yield session
    session.stop()
