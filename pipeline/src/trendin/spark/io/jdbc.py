"""앱 DB 접속 — 읽기는 Spark JDBC, 쓰기는 드라이버 psycopg2.

**쓰기를 Spark JDBC 로 하지 않는 이유** ([08 §4]) — Spark 의 JDBC 쓰기는 순수 INSERT 라
upsert 를 못 하고, 무엇보다 **자기 연결에서 파티션마다 커밋한다.** 스테이징 INSERT 를 Spark 가
하고 MERGE 를 드라이버가 하면 둘은 별개 트랜잭션이라, MERGE 가 죽으면 스테이징 행이 남아
다음 실행의 MERGE 에 섞인다. 이 규모([00 §3], 하루 수백 행)에서는 행을 드라이버로 모아
**같은 psycopg2 연결에서 TRUNCATE → INSERT → MERGE 를 한 트랜잭션으로** 돌리는 것이 맞다 —
전부 반영되거나 전부 아니고, 스테이징 테이블에 남는 것이 없다.

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


# timestamp 를 문자열로 내릴 때의 형식. **오프셋을 붙인다** — `collect()` 가 주는 파이썬
# `datetime` 은 오프셋이 없어서 PostgreSQL 이 세션 시간대로 해석하고, 그 시간대가 Spark 의
# `session.timeZone` 과 같다는 보장이 없다. 문자열에 오프셋이 있으면 양쪽 설정과 무관하다.
TIMESTAMP_FORMAT = "yyyy-MM-dd HH:mm:ss.SSSSSSxxx"


def sql_rows(frame: "DataFrame", columns: tuple[str, ...]) -> list[tuple]:
    """`columns` 순서의 튜플 목록. timestamp 칸은 오프셋 붙은 문자열이 된다.

    드라이버로 모으는 것이 이 함수의 전제다 — [00 §3] 규모(배치당 수백 행)에서만 성립한다.
    행이 수만 단위가 되면 Spark JDBC 로 스테이징에 쓰고 실행별 토큰으로 격리하는 쪽으로 바꾼다.
    """
    from pyspark.sql import functions as F
    from pyspark.sql.types import TimestampType

    projected = frame.select(*columns)
    exprs = []
    for field in projected.schema.fields:
        column = F.col(field.name)
        if isinstance(field.dataType, TimestampType):
            column = F.date_format(column, TIMESTAMP_FORMAT)
        exprs.append(column.alias(field.name))
    return [tuple(row) for row in projected.select(*exprs).collect()]


def stage_and_merge(
    config: Config,
    *,
    stage_table: str,
    columns: tuple[str, ...],
    frame: "DataFrame",
    merge_sql: str,
) -> int:
    """스테이징에 넣고 병합한다 — **한 연결, 한 트랜잭션.** 넣은 행 수를 돌려준다.

    순서는 `TRUNCATE` → `INSERT` → `merge_sql` 이다. 앞의 `TRUNCATE` 는 방어다 — 이 함수가
    트랜잭션이라 실패하면 스테이징에 아무것도 남지 않지만, 다른 경로로 남은 행이 있어도 이번
    병합에 섞이지 않게 한다. `merge_sql` 은 끝에 자기 `TRUNCATE` 를 갖고 있어야 한다.

    빈 프레임이면 아무것도 하지 않는다 — 연결도 열지 않는다.
    """
    from psycopg2.extras import execute_values

    rows = sql_rows(frame, columns)
    if not rows:
        return 0
    insert = f"INSERT INTO {stage_table} ({', '.join(columns)}) VALUES %s"
    page = int(config.get("jdbc.batch_size", DEFAULT_BATCH_SIZE))
    with connection(config) as conn, conn.cursor() as cur:
        cur.execute(f"TRUNCATE {stage_table}")
        execute_values(cur, insert, rows, page_size=page)
        cur.execute(merge_sql)
    return len(rows)


def read_table(spark: Any, table_or_query: str, config: Config) -> "DataFrame":
    """JDBC 로 되읽는다. 테이블 이름 대신 괄호로 감싼 질의도 받는다."""
    options = jdbc_options(config)
    key = "query" if table_or_query.strip().lower().startswith("select") else "dbtable"
    return spark.read.format("jdbc").options(**options).option(key, table_or_query).load()
