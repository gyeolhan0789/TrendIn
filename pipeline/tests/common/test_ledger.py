"""수집 장부 (설계 문서 #5.4, S15P21A102-166).

Postgres 구현은 실제 DB 가 있어야 판정되므로 여기서는 계약과 메모리 구현을 겨눈다.
DDL 은 발급 봉투가 요구하는 컬럼이 빠지지 않았는지만 본다.
"""

from datetime import datetime, timedelta, timezone

import pytest

from trendin.common.collect.article import Article
from trendin.common.collect.db import Database
from trendin.common.collect.ledger import DDL, InMemoryLedger, PostgresLedger, to_pending

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 9, 3, 2, 0, tzinfo=timezone.utc)


def make_article(article_id="1", source="vogue", domain="fashion", members_only=False) -> Article:
    return Article(
        domain=domain,
        source=source,
        route="rss",
        article_id=article_id,
        url=f"https://www.vogue.co.kr/{article_id}/",
        title="제목",
        published_at=datetime(2026, 9, 3, 10, 0, tzinfo=KST),
        collected_at=NOW,
        raw_key=None if members_only else f"{domain}/{source}/rss/2026/09/03/{article_id}/raw.xml",
        content_sha256=None if members_only else "c" * 64,
        members_only=members_only or None,
    )


def record(ledger, article, key="k", sha="a" * 64) -> bool:
    return ledger.record(article, article_key=key, article_sha256=sha)


def test_같은_기사를_두_번_적어도_행이_늘지_않는다():
    """불변식 7. Postgres 쪽은 ON CONFLICT DO NOTHING 이 같은 일을 한다."""
    ledger = InMemoryLedger()
    assert record(ledger, make_article("1")) is True
    assert record(ledger, make_article("1")) is False
    assert len(ledger.pending("fashion")) == 1


def test_filter_new_는_모르는_id_만_돌려준다():
    ledger = InMemoryLedger()
    record(ledger, make_article("1"))
    assert ledger.filter_new("vogue", ["1", "2", "3"]) == {"2", "3"}


def test_소스가_다르면_같은_article_id_라도_다른_기사다():
    """유일키가 `(source, article_id)` 라서다. 매체마다 번호 체계가 따로다."""
    ledger = InMemoryLedger()
    record(ledger, make_article("1", source="vogue"))
    assert ledger.filter_new("wkorea", ["1"]) == {"1"}


def test_발급_시각을_적으면_미발급_목록에서_빠진다():
    ledger = InMemoryLedger()
    record(ledger, make_article("1"))
    ledger.mark_emitted_many([("vogue", "1")], NOW, "20260903T110000")
    assert ledger.pending("fashion") == []


def test_미발급_목록은_도메인으로_잘린다():
    ledger = InMemoryLedger()
    record(ledger, make_article("1", domain="fashion"))
    record(ledger, make_article("2", source="hn", domain="dev"))
    assert [r.article_id for r in ledger.pending("fashion")] == ["1"]
    assert [r.article_id for r in ledger.pending("dev")] == ["2"]


def test_회원_전용_행은_raw_키가_없다():
    row = to_pending(make_article("1", members_only=True), article_key="k", article_sha256="a" * 64)
    assert row.raw_key is None
    assert row.members_only is True


def test_members_only_는_None_이_아니라_불리언으로_적힌다():
    """`Article.members_only` 는 `True | None` 이다. 장부 컬럼은 NOT NULL 이라 여기서 좁힌다."""
    row = to_pending(make_article("1"), article_key="k", article_sha256="a" * 64)
    assert row.members_only is False


def test_DDL_이_발급_봉투가_쓰는_컬럼을_다_만든다():
    for column in (
        "article_sha256",
        "members_only",
        "event_emitted_at",
        "event_run_id",
        "article_key",
        "published_at_offset",
    ):
        assert column in DDL
    # 재실행에도 같아야 한다 — DAG 첫 태스크가 매번 돈다.
    # 테이블 둘 + 인덱스 둘 + 칸을 여는 ALTER 둘, 그리고 걷어내는 DROP 하나.
    assert DDL.count("IF NOT EXISTS") == 6
    assert DDL.count("DROP INDEX IF EXISTS") == 1


# --- Postgres 구현 -----------------------------------------------------------
# 진짜 DB 없이 SQL 경로를 탄다. `published_at` 오프셋 유실은 여기서만 잡힌다 —
# 메모리 구현은 `timestamptz` 를 안 거치므로 이 결함을 재현하지 못한다.


class FakeCursor:
    def __init__(self, rows) -> None:
        self.rows = rows
        self.executed: list[tuple] = []
        self.rowcount = 1

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> bool:
        return False

    def execute(self, sql, params=None) -> None:
        self.executed.append((sql, params))

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


class FakeConnection:
    def __init__(self, rows=()) -> None:
        self.rows = list(rows)
        self.cursors: list[FakeCursor] = []
        self.committed = False
        self.closed = False

    def cursor(self) -> FakeCursor:
        cur = FakeCursor(self.rows)
        self.cursors.append(cur)
        return cur

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


def fake_db(rows=()) -> tuple[Database, FakeConnection]:
    conn = FakeConnection(rows)
    return Database(uri="postgres://fake", connect=lambda _uri: conn), conn


def test_저장할_때_발행일_오프셋을_따로_남긴다():
    db, conn = fake_db()
    PostgresLedger(db).record(make_article("1"), article_key="k", article_sha256="a" * 64)
    params = conn.cursors[0].executed[0][1]
    assert params["published_at_offset"] == 540  # +09:00


def test_읽을_때_소스가_준_오프셋을_되살린다():
    """`timestamptz` 는 순간만 남기고 오프셋 표기를 버린다.

    팀 시각 규약이 `published_at` 을 "소스가 준 시각을 그대로 보존" 으로 못 박아서,
    되살리지 않으면 한국 매체 기사가 `+00:00` 으로 나간다.
    """
    stored_utc = datetime(2026, 9, 3, 1, 0, tzinfo=timezone.utc)  # = 10:00 +09:00
    db, _ = fake_db(
        [
            (
                "vogue", "1", "fashion", "https://x/", "제목",
                stored_utc, 540, NOW, "k", "a" * 64, "r", False,
            )
        ]
    )
    row = PostgresLedger(db).pending("fashion")[0]
    assert row.published_at.isoformat() == "2026-09-03T10:00:00+09:00"


def test_오프셋이_없는_옛_행은_지어내지_않는다():
    """이 칸이 생기기 전에 적힌 행. 없는 값을 만들면 출처가 아니라 추측이 나간다."""
    stored_utc = datetime(2026, 9, 3, 1, 0, tzinfo=timezone.utc)
    db, _ = fake_db(
        [
            (
                "vogue", "1", "fashion", "https://x/", "제목",
                stored_utc, None, NOW, "k", "a" * 64, "r", False,
            )
        ]
    )
    assert PostgresLedger(db).pending("fashion")[0].published_at == stored_utc


def test_커밋하고_닫는다():
    db, conn = fake_db()
    PostgresLedger(db).mark_emitted_many([("vogue", "1")], NOW, "20260903T110000")
    assert conn.committed and conn.closed


def test_실패하면_되돌리고_닫는다():
    class Boom(FakeConnection):
        def cursor(self):
            raise RuntimeError("끊겼다")

    conn = Boom()
    db = Database(uri="postgres://fake", connect=lambda _uri: conn)
    with pytest.raises(RuntimeError):
        PostgresLedger(db).mark_emitted_many([("vogue", "1")], NOW, "20260903T110000")
    assert not conn.committed and conn.closed


def test_실행별_발급_건수는_그_실행_태그로만_센다():
    """완료 기준을 지탱하는 질의라 SQL 경로를 직접 탄다.

    메모리 구현은 SQL 을 안 거치므로 컬럼 이름이 틀려도 못 잡는다 — 실제로 이 브랜치에서
    `event_run_id` 를 DDL 에 안 넣고도 테스트가 통과한 적이 있다.
    """
    db, conn = fake_db([("vogue", 3), ("wkorea", 1)])
    counts = PostgresLedger(db).emitted_by_run("fashion", "20260903T110000")

    assert counts == {"vogue": 3, "wkorea": 1}
    sql, params = conn.cursors[0].executed[-1]
    assert params == ("fashion", "20260903T110000")
    # 발급 표시가 지워진 행의 옛 태그를 세면 재발행 뒤 건수가 부푼다.
    assert "event_emitted_at IS NOT NULL" in sql


def test_발급을_적을_때_실행도_같이_적는다():
    db, conn = fake_db([])
    PostgresLedger(db).mark_emitted_many([("vogue", "1"), ("wkorea", "2")], NOW, "20260903T110000")

    sql, params = conn.cursors[0].executed[-1]
    assert "event_run_id" in sql
    assert params == (NOW, "20260903T110000", (("vogue", "1"), ("wkorea", "2")))
    # 여러 행이 UPDATE 하나로 간다 — 행마다 열면 만 건에 만 번이다.
    assert len(conn.cursors[0].executed) == 1


def test_적을_행이_없으면_DB_를_열지_않는다():
    db, conn = fake_db([])
    PostgresLedger(db).mark_emitted_many([], NOW, "20260903T110000")
    assert conn.cursors == []
