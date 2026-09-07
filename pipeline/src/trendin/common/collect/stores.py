"""조건부 요청(304)용 validator 보관소.

163 은 계약만 정하고 실제 보관은 주입받는다. `InMemory` 는 probe·백필·테스트가 쓰는 한
프로세스짜리고, 실행 사이에 남기는 `Postgres` 를 S15P21A102-167 이 끼웠다.

주기 실행이 앞 회차의 ETag 를 기억해야 304 가 실제로 듣는다 — 안 그러면 매시 같은 피드를
전부 다시 받는다. 상대 서버에 부하를 주지 않는다는 불변식 4 와 같은 방향이다.
"""

from __future__ import annotations

from datetime import datetime, timezone

from trendin.common.collect.db import Database


class InMemoryValidatorStore:
    """프로세스가 사는 동안만 기억한다."""

    def __init__(self) -> None:
        self._by_url: dict[str, tuple[str | None, str | None]] = {}

    def get(self, url: str) -> tuple[str | None, str | None] | None:
        return self._by_url.get(url)

    def put(self, url: str, etag: str | None, last_modified: str | None) -> None:
        if etag or last_modified:
            self._by_url[url] = (etag, last_modified)


class PostgresValidatorStore:
    """실행 사이에 남는 보관소. 테이블은 `ledger.DDL` 이 함께 만든다.

    발견 URL 하나에 행 하나다. 소스 7곳 × 목록 하위 섹션까지 쳐도 수십 행이라 자라지 않는다.
    """

    def __init__(self, db: Database) -> None:
        self._db = db

    def get(self, url: str) -> tuple[str | None, str | None] | None:
        with self._db.transaction() as conn, conn.cursor() as cur:
            cur.execute("SELECT etag, last_modified FROM collect_validator WHERE url = %s", (url,))
            row = cur.fetchone()
        return (row[0], row[1]) if row else None

    def put(self, url: str, etag: str | None, last_modified: str | None) -> None:
        if not (etag or last_modified):
            return
        with self._db.transaction() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO collect_validator (url, etag, last_modified, updated_at) "
                "VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (url) DO UPDATE SET etag = EXCLUDED.etag, "
                "last_modified = EXCLUDED.last_modified, updated_at = EXCLUDED.updated_at",
                (url, etag, last_modified, datetime.now(timezone.utc)),
            )
