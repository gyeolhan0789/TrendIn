"""앱 DB 접속 — Spark JDBC 와 드라이버 psycopg2 두 경로.

**두 경로가 필요한 이유** ([08 §4]) — Spark 의 JDBC 쓰기는 순수 INSERT 라 upsert 를 못
한다. 그래서 Spark 는 스테이징 테이블에 넣고, 실제 병합은 드라이버가 한 트랜잭션으로
서버에서 돌린다. 파티션마다 커밋하는 `foreachPartition` 은 중간에 죽으면 절반만 반영되고,
절반만 반영된 상태가 가장 나쁘다 — 재실행이 곧 이중 반영이다.

접속값의 출처는 하나다. `conf/*.yaml` 의 `jdbc.*` 를 Spark 옵션과 psycopg2 DSN 양쪽으로
번역할 뿐이고, 이 모듈 밖에서 URL 을 다시 조립하지 않는다.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Iterator
from urllib.parse import quote

from trendin.spark.common.config import Config, ConfigError
from trendin.spark.common.logging import get_logger

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

log = get_logger(__name__)

DEFAULT_DRIVER = "org.postgresql.Driver"
DEFAULT_BATCH_SIZE = 1000
JDBC_PREFIX = "jdbc:postgresql://"


def jdbc_options(config: Config) -> dict[str, str]:
    """Spark 의 `format("jdbc")` 에 그대로 넣는 옵션.

    비밀번호는 `require` 하지 않는다. 로컬 컴포즈가 trust 인증이면 빈 값이 정상이고,
    여기서 막으면 개발 환경이 못 뜬다. 진짜로 필요한 곳에서는 DB 가 거절한다.
    """
    return {
        "url": str(config.require("jdbc.url")),
        "user": str(config.require("jdbc.user")),
        "password": str(config.get("jdbc.password", "") or ""),
        "driver": str(config.get("jdbc.driver", DEFAULT_DRIVER)),
    }


def write_options(config: Config) -> dict[str, str]:
    options = jdbc_options(config)
    options["batchsize"] = str(config.get("jdbc.batch_size", DEFAULT_BATCH_SIZE))
    return options


def dsn(url: str, user: str, password: str = "") -> str:
    """JDBC URL 을 psycopg2 DSN 으로. `jdbc:` 접두어를 떼고 자격을 끼운다.

    사용자·비밀번호를 퍼센트 인코딩하는 이유는 `@` 나 `:` 가 든 비밀번호가 호스트 자리를
    소비해버리기 때문이다. 그러면 오류가 "인증 실패" 가 아니라 "그런 호스트가 없다" 로 나와
    원인을 엉뚱한 데서 찾게 된다.
    """
    if not url.startswith(JDBC_PREFIX):
        raise ConfigError(f"jdbc.url 이 {JDBC_PREFIX}... 형태가 아니다: {url!r}")
    rest = url[len(JDBC_PREFIX) :]
    credential = quote(user, safe="")
    if password:
        credential += f":{quote(password, safe='')}"
    return f"postgresql://{credential}@{rest}"


def dsn_from_config(config: Config) -> str:
    options = jdbc_options(config)
    return dsn(options["url"], options["user"], options["password"])


@contextmanager
def connection(config: Config) -> Iterator[Any]:
    """드라이버에서 커넥션 하나. 빠져나오면서 커밋하고 닫는다.

    `collect/db.py` 의 `Database.transaction` 과 같은 형태가다. 유휴 커넥션을 들고 있지
    않는 이유도 같다 — Job 하나가 수 분을 도는 동안 붙잡을 이유가 없다.
    """
    import psycopg2

    conn = psycopg2.connect(dsn_from_config(config))
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def execute(config: Config, statements: str) -> None:
    """SQL 을 한 트랜잭션으로 돌린다. DDL 과 서버사이드 MERGE 가 쓴다."""
    with connection(config) as conn, conn.cursor() as cur:
        cur.execute(statements)


def append(frame: "DataFrame", table: str, config: Config) -> None:
    """스테이징 테이블에 순수 INSERT. 병합은 부른 쪽이 `execute` 로 이어서 한다."""
    frame.write.format("jdbc").options(**write_options(config)).option("dbtable", table).mode(
        "append"
    ).save()


def read_table(spark: Any, table_or_query: str, config: Config) -> "DataFrame":
    """JDBC 로 되읽는다. 테이블 이름 대신 괄호로 감싼 질의도 받는다."""
    options = jdbc_options(config)
    key = "query" if table_or_query.strip().lower().startswith("select") else "dbtable"
    return spark.read.format("jdbc").options(**options).option(key, table_or_query).load()
