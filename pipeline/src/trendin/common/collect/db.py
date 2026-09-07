"""앱 DB 접속 (설계 확정 6 — 장부는 앱 DB 에 둔다).

Airflow 의 `PostgresHook` 을 쓰지 않는다. README 규약 12 가 태스크 함수를 Airflow 없이
테스트하라고 하고, 접속값은 어차피 환경변수 하나(`AIRFLOW_CONN_APP_DB`)로 오기 때문에
훅이 줄 이점(Connection 관리)이 이 프로젝트엔 없다. 이름만 Airflow 규격이지 값은 URI 다.

접속 주소와 커넥션 여는 방법은 늘 같이 다니므로 `Database` 하나로 묶는다. 장부와 validator
보관소가 각자 `(uri, connect)` 를 들고 다니면 같은 쌍이 두 벌로 남는다.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable

from trendin.common.collect.env import require_env

URI_ENV = "AIRFLOW_CONN_APP_DB"


def _psycopg2_connect(uri: str):
    """psycopg2 는 import 시점이 아니라 쓸 때 부른다."""
    import psycopg2

    return psycopg2.connect(uri)


@dataclass(frozen=True, slots=True)
class Database:
    """앱 DB 하나. `connect` 를 갈아 끼우면 테스트가 진짜 DB 없이 SQL 경로를 탄다."""

    uri: str
    connect: Callable[[str], object] = _psycopg2_connect

    @classmethod
    def from_env(cls) -> "Database":
        return cls(require_env(URI_ENV))

    @contextmanager
    def transaction(self):
        """커넥션 하나를 열고, 빠져나오면서 커밋하고 닫는다.

        커넥션을 들고 있지 않고 호출마다 여는 이유는 태스크 하나가 수 분을 도는 동안 유휴
        커넥션을 붙잡을 이유가 없어서다. Airflow 태스크는 어차피 프로세스가 갈린다.
        """
        conn = self.connect(self.uri)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
