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

import os
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Iterator, NamedTuple
from urllib.parse import quote, urlsplit

from trendin.spark.common.config import Config, ConfigError
from trendin.spark.common.logging import get_logger

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

log = get_logger(__name__)

DEFAULT_DRIVER = "org.postgresql.Driver"
DEFAULT_BATCH_SIZE = 1000
JDBC_PREFIX = "jdbc:postgresql://"
DEFAULT_PORT = 5432

# 생산자(수집 DAG)가 쓰는 접속 문자열. Airflow Connection `app_db` 의 값이다
# (`common/collect/db.URI_ENV`). Spark Job 이 Airflow 컨테이너 안에서 `submit.sh` 로 돌기
# 때문에 이 프로세스 환경에도 같이 들어온다.
PRODUCER_URL_ENV = "AIRFLOW_CONN_APP_DB"


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


class Target(NamedTuple):
    """접속 문자열이 가리키는 곳. 자격 증명과 옵션은 들어 있지 않다."""

    host: str
    port: int
    dbname: str

    def __str__(self) -> str:
        return f"{self.host}:{self.port}/{self.dbname}"


def _target(url: str) -> Target:
    """접속 문자열에서 `(host, port, dbname)` 만. 자격 증명과 옵션은 버린다.

    계정을 빼는 이유는 양쪽이 다른 계정으로 붙어도 되기 때문이다 — 생산자는 Airflow
    Connection 의 계정, 소비자는 `jdbc.user` 다. 같은 DB 인지만 본다.
    """
    parts = urlsplit(url[len("jdbc:") :] if url.startswith("jdbc:") else url)
    name = parts.path.lstrip("/")
    # `parts.port` 는 포트가 숫자가 아니면 여기서 ValueError 를 올린다. 그대로 둔다.
    if not parts.hostname or not name:
        raise ValueError(f"host·dbname 을 못 읽었다: {url!r}")
    return Target(parts.hostname, parts.port or DEFAULT_PORT, name)


def assert_producer_database(config: Config) -> None:
    """생산자와 같은 DB 를 보고 있는지 본다. 아니면 시작하지 않는다 (S15P21A102-247·244).

    **틀린 DB 를 봐도 오류가 안 난다는 것이 문제다.** 장부 뷰는 수집 DAG 이 만들므로 옛 DB
    에도 남아 있고, 그러면 `collected.view_ready` 가 통과하고 창 질의가 0행을 준다 — "수집이
    0건이었다" 와 구분되지 않는다. 적재 쪽은 더 나쁘다. `curated`·`contents`·`pl_*` 가 아무도
    안 읽는 DB 에 쌓이고, 증상은 **"적재는 되는데 조회가 빈다"** 로만 나타난다.

    접속값이 두 벌인 것이 원인이다. 생산자는 `AIRFLOW_CONN_APP_DB`, 소비자는 `APP_DB_URL`
    로 각자 받는다. 한쪽만 팀 postgres 로 옮기면 그대로 갈린다.

    **환경변수가 없으면 그냥 지나간다.** 호스트에서 `--profile local` 로 손수 돌릴 때는
    Airflow Connection 이 없는 것이 정상이다 — 검사를 못 하는 것과 검사가 실패한 것은 다르다.

    **읽지 못해도 지나간다.** `AIRFLOW_CONN_APP_DB` 는 URI 말고 JSON 으로도 줄 수 있고,
    인코딩 안 된 비밀번호가 host 자리를 먹기도 한다. 검사가 파싱에 실패했다는 이유로 멀쩡한
    실행을 막지 않는다.

    ⚠️ **host 를 문자열로 비교한다.** 같은 DB 를 한쪽은 서비스 이름, 다른 쪽은 IP 로
    가리키면 멀쩡한 실행이 막힌다. 이름을 풀어서 비교하지 않는 이유는 그 풀이가 컨테이너
    안팎에서 다른 답을 주기 때문이다 — 틀린 통과보다 틀린 차단이 낫고, 차단은 오류 메시지가
    양쪽 주소를 그대로 보여 주므로 사람이 5초 안에 판정한다 (S15P21A102-247 코드리뷰).
    """
    raw = os.environ.get(PRODUCER_URL_ENV, "").strip()
    if not raw:
        log.info("%s 가 없어 생산자 DB 대조를 건너뛴다", PRODUCER_URL_ENV)
        return
    try:
        producer = _target(raw)
    except ValueError as error:
        log.warning("%s 를 읽지 못해 대조를 건너뛴다: %s", PRODUCER_URL_ENV, error)
        return

    url = str(config.require("jdbc.url"))
    if not url.startswith(JDBC_PREFIX):
        raise ConfigError(f"jdbc.url 이 {JDBC_PREFIX}... 형태가 아니다: {url!r}")
    consumer = _target(url)

    if producer != consumer:
        raise ConfigError(
            "수집이 쓰는 DB 와 Spark 가 보는 DB 가 다르다 — "
            f"수집({PRODUCER_URL_ENV})={producer}, Spark(jdbc.url)={consumer}. "
            "이대로 돌면 장부가 0건으로 보이고 적재는 아무도 안 읽는 DB 에 쌓인다. "
            "둘이 같은 DB 인데 한쪽만 IP 나 별칭으로 적혀 있다면 주소 표기를 맞춘다 "
            "(S15P21A102-247)"
        )
    log.info("생산자와 같은 DB 다: %s", consumer)


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
    conn: Any | None = None,
) -> int:
    """스테이징에 넣고 병합한다 — **한 연결, 한 트랜잭션.** 넣은 행 수를 돌려준다.

    순서는 `TRUNCATE` → `INSERT` → `merge_sql` 이다. 앞의 `TRUNCATE` 는 방어다 — 이 함수가
    트랜잭션이라 실패하면 스테이징에 아무것도 남지 않지만, 다른 경로로 남은 행이 있어도 이번
    병합에 섞이지 않게 한다. `merge_sql` 은 끝에 자기 `TRUNCATE` 를 갖고 있어야 한다.

    빈 프레임이면 아무것도 하지 않는다 — 연결도 열지 않는다.

    **`conn` 을 주면 그 연결 안에서 돌고 커밋하지 않는다.** 표 여럿을 한 트랜잭션으로 묶을
    때 쓴다 — `ingest` 가 `contents` 와 처리 이력을 그렇게 묶는다 (S15P21A102-341). 한쪽만
    커밋된 상태가 곧 다음 실행의 중복 처리라서, 트랜잭션의 주인은 부른 쪽이어야 한다.
    """
    rows = sql_rows(frame, columns)
    if not rows:
        return 0
    insert = f"INSERT INTO {stage_table} ({', '.join(columns)}) VALUES %s"
    page = int(config.get("jdbc.batch_size", DEFAULT_BATCH_SIZE))
    if conn is not None:
        _stage_and_merge(conn, stage_table, insert, rows, merge_sql, page=page)
        return len(rows)
    with connection(config) as owned:
        _stage_and_merge(owned, stage_table, insert, rows, merge_sql, page=page)
    return len(rows)


def _stage_and_merge(conn: Any, stage_table: str, insert: str, rows, merge_sql: str, *, page: int):
    from psycopg2.extras import execute_values

    with conn.cursor() as cur:
        cur.execute(f"TRUNCATE {stage_table}")
        execute_values(cur, insert, rows, page_size=page)
        cur.execute(merge_sql)


def read_table(spark: Any, table_or_query: str, config: Config) -> "DataFrame":
    """JDBC 로 되읽는다. 테이블 이름 대신 괄호로 감싼 질의도 받는다."""
    options = jdbc_options(config)
    key = "query" if table_or_query.strip().lower().startswith("select") else "dbtable"
    return spark.read.format("jdbc").options(**options).option(key, table_or_query).load()
