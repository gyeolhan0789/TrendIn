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


@pytest.fixture(scope="session")
def _spark_writes_files(spark, tmp_path_factory) -> bool:
    """Spark 가 로컬 파일을 쓸 수 있는지. 세션당 한 번만 재 본다."""
    probe = tmp_path_factory.mktemp("write-probe") / "out"
    try:
        spark.createDataFrame([(1,)], "n int").write.mode("overwrite").parquet(str(probe))
    except Exception:  # noqa: BLE001 — 원인을 가리지 않는다. 못 쓰면 못 쓰는 것이다
        return False
    return True


@pytest.fixture
def writable_spark(spark, _spark_writes_files):
    """파일을 쓰는 테스트가 요청하는 픽스처. 못 쓰는 호스트에서는 건너뛴다.

    **Windows 에서 `winutils.exe` 가 없으면 Spark 는 어떤 파일도 쓰지 못한다** —
    `HADOOP_HOME and hadoop.home.dir are unset` 으로 죽는다. 로컬 개발은 컨테이너 밖
    `.venv` 에서 도는 구성이라([09 §2]) 이 호스트가 그 상태다.

    운영과 컨테이너(`compose.spark.yaml`)는 Linux 라 해당하지 않으므로, 이 테스트들은
    **건너뛰는 것이지 없는 것이 아니다.** CI 가 Linux 면 그대로 돈다.
    """
    if not _spark_writes_files:
        pytest.skip(
            "이 호스트에서는 Spark 가 파일을 쓸 수 없다 (Windows + winutils.exe 없음). "
            "Linux CI·컨테이너에서는 돈다"
        )
    return spark
