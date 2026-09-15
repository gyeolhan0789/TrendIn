"""JDBC 옵션과 처리 이력 SQL ([08 §4]). DB 없이 검사한다 ([09 §4] 층 1).

주소를 틀리면 Job 이 뜨긴 하고 엉뚱한 DB 에 쓴다. 실패로 안 보인다.
"""

from __future__ import annotations

import pytest

from trendin.spark.common.config import Config, ConfigError
from trendin.spark.io import dlq, jdbc, ledger


def config(**overrides) -> Config:
    data = {
        "jdbc": {
            "url": "jdbc:postgresql://postgres:5432/trendin",
            "user": "trendin",
            "password": "pw",
        },
    }
    return Config(data | overrides, profile="test")


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


# --- 생산자와 같은 DB 를 보는가 (S15P21A102-247) -----------------------------
#
# 이 모듈 첫 줄이 적어 둔 "주소를 틀리면 Job 이 뜨긴 하고 엉뚱한 DB 에 쓴다. 실패로 안
# 보인다" 를 실제로 막는 자리다. 접속값이 두 벌(`AIRFLOW_CONN_APP_DB` · `APP_DB_URL`)이라
# 한쪽만 옮기면 그대로 갈린다.

PRODUCER = jdbc.PRODUCER_URL_ENV


def test_같은_DB_면_지나간다(monkeypatch):
    monkeypatch.setenv(PRODUCER, "postgres://someone:pw@postgres:5432/trendin")

    jdbc.assert_producer_database(config())


def test_계정이_달라도_같은_DB_면_지나간다(monkeypatch):
    """생산자는 Airflow Connection 의 계정, 소비자는 `jdbc.user` 다. 달라도 된다."""
    monkeypatch.setenv(PRODUCER, "postgres://airflow:other@postgres:5432/trendin")

    jdbc.assert_producer_database(config())


def test_포트를_안_적으면_5432_로_본다(monkeypatch):
    monkeypatch.setenv(PRODUCER, "postgres://u:p@postgres/trendin")

    jdbc.assert_producer_database(config())


@pytest.mark.parametrize(
    "producer",
    [
        "postgres://u:p@forever102:5432/trendin",  # 호스트가 다르다 (244 가 옮기는 자리)
        "postgres://u:p@postgres:5433/trendin",  # 포트가 다르다
        "postgres://u:p@postgres:5432/forever102",  # DB 이름이 다르다
    ],
)
def test_다른_DB_면_시작도_안_한다(monkeypatch, producer: str):
    """조용히 0건으로 끝나는 것이 최악이다 — 며칠 뒤 통계의 구멍으로만 드러난다."""
    monkeypatch.setenv(PRODUCER, producer)

    with pytest.raises(ConfigError, match="다르다"):
        jdbc.assert_producer_database(config())


def test_환경변수가_없으면_그냥_지나간다(monkeypatch):
    """호스트에서 `--profile local` 로 손수 돌릴 때는 Airflow Connection 이 없는 게 정상이다.

    검사를 **못 하는 것**과 검사가 **실패한 것**은 다르다. 없다고 막으면 로컬이 안 돈다.
    """
    monkeypatch.delenv(PRODUCER, raising=False)

    jdbc.assert_producer_database(config())


@pytest.mark.parametrize("producer", ['{"conn_type": "postgres"}', "postgres:///socket", "   "])
def test_읽지_못하는_값이면_막지_않는다(monkeypatch, producer: str):
    """`AIRFLOW_CONN_*` 는 URI 말고 JSON 으로도 준다. 대조가 파싱에 실패했다는 이유로
    멀쩡한 실행을 막으면, 고치는 값이 검사받는 값이 아니게 된다."""
    monkeypatch.setenv(PRODUCER, producer)

    jdbc.assert_producer_database(config())


def test_소비자_URL_이_JDBC_형식이_아니면_죽는다(monkeypatch):
    monkeypatch.setenv(PRODUCER, "postgres://u:p@postgres:5432/trendin")
    cfg = config(jdbc={"url": "postgresql://postgres:5432/trendin", "user": "trendin"})

    with pytest.raises(ConfigError, match="jdbc:postgresql"):
        jdbc.assert_producer_database(cfg)


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
