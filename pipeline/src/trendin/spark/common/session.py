"""SparkSession 팩토리. 설정을 Spark 옵션으로 옮기는 곳은 여기 하나다.

Job 안에서 `SparkSession.builder` 를 직접 부르지 않는다. 부르는 순간 S3A 설정이
Job 마다 조금씩 달라지고, 그 차이는 "왜 저 Job 만 MinIO 를 못 읽지" 로 돌아온다.
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

from trendin.spark.common.config import Config
from trendin.spark.common.logging import get_logger

if TYPE_CHECKING:  # spark-submit 밖에서 import 만 해도 죽지 않게
    from pyspark.sql import SparkSession

log = get_logger(__name__)

DEFAULT_MASTER = "local[*]"
# AWS SDK v2 는 리전을 못 찾으면 요청을 만들기 전에 죽는다. MinIO 는 리전 개념이
# 없으므로 아무 값이나 하나 박아두면 된다. hadoop-aws 3.4 부터 필요하다.
DEFAULT_REGION = "us-east-1"
_CREDENTIALS_PROVIDER = "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider"


def ensure_worker_python() -> str:
    """executor 가 드라이버와 같은 파이썬을 쓰게 한다.

    안 맞으면 세션은 멀쩡히 뜨고 **첫 파이썬 UDF 에서** 죽는다:

        [PYTHON_VERSION_MISMATCH] Python in worker has different version: 3.14
        than that in driver: 3.12

    worker 는 PATH 의 `python` 을 잡는데, 그게 .venv 의 것이라는 보장이 없다.
    `spark-submit` 을 가상환경 밖에서 부르거나 PATH 에 다른 파이썬이 앞서 있으면
    갈린다. `sys.executable` 은 지금 이 코드를 돌리는 해석기라 항상 맞다.

    이미 값이 있으면 건드리지 않는다 — 배포에서 일부러 다른 해석기를 가리키는 경우가 있다.
    """
    for name in ("PYSPARK_PYTHON", "PYSPARK_DRIVER_PYTHON"):
        if not os.environ.get(name):
            os.environ[name] = sys.executable
    return os.environ["PYSPARK_PYTHON"]


def build_session(job: str, config: Config) -> SparkSession:
    """`trendin-{job}` 이름의 세션을 만든다. 이미 있으면 그것을 준다."""
    ensure_worker_python()

    from pyspark.sql import SparkSession

    builder = (
        SparkSession.builder.master(config.get("spark.master", DEFAULT_MASTER))
        .appName(f"trendin-{job}")
    )
    for key, value in spark_options(config).items():
        builder = builder.config(key, value)

    session = builder.getOrCreate()
    session.sparkContext.setLogLevel(config.get("logging.spark_level", "WARN"))
    log.info(
        "SparkSession 준비: job=%s profile=%s master=%s spark=%s python=%s",
        job,
        config.profile,
        session.sparkContext.master,
        session.version,
        f"{sys.version_info.major}.{sys.version_info.minor}",
    )
    return session


def spark_options(config: Config) -> dict[str, str]:
    """세션에 넣을 옵션 전부. 세션 없이도 검사할 수 있게 따로 뺐다."""
    options: dict[str, str] = {}
    # conf/*.yaml 의 spark.conf 는 그대로 통과시킨다. 새 옵션을 넣으려고 코드를
    # 고칠 일이 없어야 한다.
    for key, value in config.section("spark.conf").items():
        options[str(key)] = _as_option(value)
    options.update(_s3a_options(config))
    return options


def _s3a_options(config: Config) -> dict[str, str]:
    endpoint = config.get("minio.endpoint")
    if not endpoint:
        # MinIO 를 안 쓰는 Job·테스트도 있다. 없으면 S3A 를 아예 건드리지 않는다.
        return {}
    options = {
        "spark.hadoop.fs.s3a.endpoint": str(endpoint),
        "spark.hadoop.fs.s3a.endpoint.region": str(config.get("minio.region", DEFAULT_REGION)),
        # AWS S3 가 아니므로 경로 스타일이 필수다 ([01 §7]).
        "spark.hadoop.fs.s3a.path.style.access": "true",
        "spark.hadoop.fs.s3a.connection.ssl.enabled": _as_option(
            str(endpoint).lower().startswith("https")
        ),
        "spark.hadoop.fs.s3a.aws.credentials.provider": _CREDENTIALS_PROVIDER,
    }
    access_key = config.get("minio.access_key")
    secret_key = config.get("minio.secret_key")
    if access_key:
        options["spark.hadoop.fs.s3a.access.key"] = str(access_key)
    if secret_key:
        options["spark.hadoop.fs.s3a.secret.key"] = str(secret_key)
    for key, value in config.section("minio.hadoop_conf").items():
        options[f"spark.hadoop.{key}"] = _as_option(value)
    return options


def checkpoint_dir(job: str, config: Config) -> str:
    """Job 별 checkpoint 경로. 하나를 지울 때 나머지가 말려들지 않게 나눈다 ([01 §4])."""
    root = str(config.require("checkpoint.root")).rstrip("/")
    return f"{root}/{job}"


def _as_option(value: object) -> str:
    # Spark 옵션은 전부 문자열이다. YAML 의 true 가 "True" 로 가면 Spark 가 못 읽는다.
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
