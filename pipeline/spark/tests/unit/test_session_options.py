"""세션에 들어가는 옵션. SparkSession 을 만들지 않고 검사한다."""

from __future__ import annotations

import pytest

from trendin.spark.common.config import Config, ConfigError
from trendin.spark.common.session import checkpoint_dir, spark_options


def make(data: dict) -> Config:
    return Config(data, profile="test")


def test_conf_구역은_그대로_통과한다():
    options = spark_options(make({"spark": {"conf": {"spark.sql.shuffle.partitions": 8}}}))

    assert options["spark.sql.shuffle.partitions"] == "8"


def test_불린은_소문자_문자열로_나간다():
    """YAML 의 true 가 파이썬 True 를 거쳐 "True" 로 가면 Spark 가 못 읽는다."""
    options = spark_options(make({"spark": {"conf": {"spark.some.flag": True}}}))

    assert options["spark.some.flag"] == "true"


def test_minio_endpoint_가_없으면_S3A_를_건드리지_않는다():
    """MinIO 를 쓰지 않는 테스트·Job 도 있다."""
    options = spark_options(make({"minio": {"access_key": "spark"}}))

    assert not [key for key in options if "s3a" in key]


def test_경로_스타일과_리전은_MinIO_라서_필수다():
    options = spark_options(
        make({"minio": {"endpoint": "http://127.0.0.1:9000", "region": "us-east-1"}})
    )

    assert options["spark.hadoop.fs.s3a.path.style.access"] == "true"
    assert options["spark.hadoop.fs.s3a.endpoint.region"] == "us-east-1"


@pytest.mark.parametrize(
    ("endpoint", "expected"),
    [("http://127.0.0.1:9000", "false"), ("https://minio.example:9000", "true")],
)
def test_TLS_는_endpoint_스킴이_정한다(endpoint: str, expected: str):
    options = spark_options(make({"minio": {"endpoint": endpoint}}))

    assert options["spark.hadoop.fs.s3a.connection.ssl.enabled"] == expected


def test_키가_없으면_옵션도_없다():
    """빈 문자열을 넣으면 S3A 가 익명 접근이 아니라 빈 자격으로 시도해 403 이 난다."""
    options = spark_options(make({"minio": {"endpoint": "http://127.0.0.1:9000"}}))

    assert "spark.hadoop.fs.s3a.access.key" not in options
    assert "spark.hadoop.fs.s3a.secret.key" not in options


def test_추가_S3A_옵션은_코드를_고치지_않고_넣는다():
    options = spark_options(
        make(
            {
                "minio": {
                    "endpoint": "http://127.0.0.1:9000",
                    "hadoop_conf": {"fs.s3a.connection.maximum": 32},
                }
            }
        )
    )

    assert options["spark.hadoop.fs.s3a.connection.maximum"] == "32"


def test_checkpoint_는_Job_마다_갈린다():
    config = make({"checkpoint": {"root": "/var/ckpt/"}})

    assert checkpoint_dir("ingest", config) == "/var/ckpt/ingest"
    assert checkpoint_dir("extract", config) == "/var/ckpt/extract"


def test_checkpoint_root_가_없으면_죽는다():
    with pytest.raises(ConfigError, match="CHECKPOINT_ROOT"):
        checkpoint_dir("ingest", make({}))
