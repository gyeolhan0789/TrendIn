"""Kafka · JDBC 옵션 만들기 ([02 §1] · [08 §4]). 브로커도 DB 도 없이 검사한다 ([09 §4] 층 1).

주소를 틀리면 Job 이 뜨긴 하고 아무것도 안 받거나, 엉뚱한 DB 에 쓴다. 둘 다 실패로 안 보인다.
"""

from __future__ import annotations

import pytest

from trendin.spark.common.config import Config, ConfigError
from trendin.spark.io import dlq, jdbc, kafka, ledger


def config(**overrides) -> Config:
    data = {
        "kafka": {
            "bootstrap_servers": "kafka:9092",
            "group_id_prefix": "trendin-spark",
            "topics": {"raw_file_ready": "raw-file-ready"},
        },
        "jdbc": {
            "url": "jdbc:postgresql://postgres:5432/trendin",
            "user": "trendin",
            "password": "pw",
        },
    }
    return Config(data | overrides, profile="test")


# --- Kafka ---------------------------------------------------------------


def test_group_은_접두어에_job_이름을_붙인다():
    """[02 §1] 이 `trendin-spark-ingest` 로 명시했다."""
    assert kafka.group_id_prefix(config(), job="ingest") == "trendin-spark-ingest"


def test_접두어_끝의_하이픈은_겹치지_않는다():
    cfg = config(
        kafka={"group_id_prefix": "trendin-spark-", "topics": {}, "bootstrap_servers": "x"}
    )

    assert kafka.group_id_prefix(cfg, job="ingest") == "trendin-spark-ingest"


def test_옵션에_토픽과_브로커와_보장이_들어간다():
    options = kafka.kafka_options(config(), job="ingest")

    assert options["subscribe"] == "raw-file-ready"
    assert options["kafka.bootstrap.servers"] == "kafka:9092"
    assert options["startingOffsets"] == "earliest"
    # 오프셋이 사라졌을 때 조용히 건너뛰면 그 구간이 통째로 유실된다 ([02 §1]).
    assert options["failOnDataLoss"] == "true"


def test_브로커_주소가_없으면_뜨기_전에_죽는다():
    cfg = Config({"kafka": {"topics": {"raw_file_ready": "t"}}}, profile="test")

    with pytest.raises(ConfigError):
        kafka.kafka_options(cfg, job="ingest")


# --- JDBC ----------------------------------------------------------------


def test_jdbc_url_을_psycopg2_DSN_으로_바꾼다():
    assert (
        jdbc.dsn("jdbc:postgresql://postgres:5432/trendin", "trendin", "pw")
        == "postgresql://trendin:pw@postgres:5432/trendin"
    )


def test_비밀번호의_특수문자를_인코딩한다():
    """`@` 가 든 비밀번호를 그대로 끼우면 호스트 자리를 소비한다 — 오류가 "그런 호스트가
    없다" 로 나와서 인증 문제로 안 보인다."""
    got = jdbc.dsn("jdbc:postgresql://h:5432/d", "u", "p@ss:word")

    assert got == "postgresql://u:p%40ss%3Aword@h:5432/d"


def test_비밀번호가_없으면_붙이지_않는다():
    assert jdbc.dsn("jdbc:postgresql://h:5432/d", "u") == "postgresql://u@h:5432/d"


def test_jdbc_형태가_아니면_설정_오류다():
    with pytest.raises(ConfigError):
        jdbc.dsn("postgresql://h:5432/d", "u", "p")


def test_옵션에_드라이버_기본값이_붙는다():
    options = jdbc.jdbc_options(config())

    assert options["driver"] == "org.postgresql.Driver"
    assert options["password"] == "pw"


def test_비밀번호가_비어도_옵션은_만들어진다():
    """로컬 컴포즈가 trust 인증이면 빈 값이 정상이다. 여기서 막으면 개발 환경이 못 뜬다."""
    cfg = config(jdbc={"url": "jdbc:postgresql://h:5432/d", "user": "u"})

    assert jdbc.jdbc_options(cfg)["password"] == ""


# --- 처리 이력 SQL ------------------------------------------------------------


def test_job_이름이_SQL_에_그대로_들어가지_않게_막는다():
    with pytest.raises(ValueError):
        ledger.safe_job("ingest'; DROP TABLE pl_processing_ledger; --")


def test_MERGE_가_처리_이력의_모든_칸을_갱신한다():
    """컬럼을 하나 더하고 MERGE 를 안 고치면 그 칸이 조용히 안 갱신된다.

    공백을 눌러서 비교하는 이유는 SQL 을 보기 좋게 정렬해 뒀기 때문이다 — 정렬을 고쳤다고
    테스트가 깨지면 안 된다.
    """
    merge = " ".join(ledger.MERGE_SQL.split())

    for column in ledger.COLUMNS:
        if column in ("event_id", "job"):
            continue  # 충돌 키는 갱신 대상이 아니다
        assert f"{column} = EXCLUDED.{column}" in merge, column


def test_DLQ_MERGE_는_retry_count_를_덮지_않고_올린다():
    """같은 이벤트가 또 막혔을 때 몇 번째인지가 사람이 볼 신호다. EXCLUDED 로 덮으면 늘 0 이다."""
    merge = " ".join(dlq.MERGE_SQL.split())

    assert f"retry_count = {dlq.TABLE}.retry_count + 1" in merge
    assert "retry_count = EXCLUDED.retry_count" not in merge
