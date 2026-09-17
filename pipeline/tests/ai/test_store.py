"""AI 분석 결과의 기간별 upsert 계약 테스트."""

from contextlib import contextmanager
from datetime import datetime, timezone

import pytest

from trendin.ai.analyzer import TrendAnalysis
from trendin.ai.articles import TrendTarget
from trendin.ai.store import (
    CURRENT_ANALYSIS_SQL,
    UPSERT_ANALYSIS_SQL,
    TrendAnalysisStore,
)
from trendin.spark.io import jdbc

UTC = timezone.utc


class FakeCursor:
    def __init__(self, rows=((101,),)):
        self.rows = iter(rows)
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, statement, params):
        self.calls.append((statement, params))

    def fetchone(self):
        return next(self.rows)


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor


def target():
    return TrendTarget(
        keyword_id=81,
        keyword="발레코어",
        domain="FASHION",
        period="7D",
        period_start=datetime(2026, 9, 8, tzinfo=UTC),
        period_end=datetime(2026, 9, 15, tzinfo=UTC),
        mention_rank=1,
        trend_types=("NEW", "RISING"),
    )


def analysis():
    return TrendAnalysis(description="설명", summary="요약", reason="상승 이유")


def install_connection(monkeypatch, cursor):
    @contextmanager
    def connection(config):
        yield FakeConnection(cursor)

    monkeypatch.setattr(jdbc, "connection", connection)


def test_분석_당시_복수_유형으로_기간별_분석만_저장한다(monkeypatch):
    cursor = FakeCursor()
    install_connection(monkeypatch, cursor)

    trend_id = TrendAnalysisStore(object()).save(target(), analysis(), "abc123")

    period_sql = " ".join(UPSERT_ANALYSIS_SQL.split())
    assert "INSERT INTO trend_analyses" in period_sql
    assert "ON CONFLICT (trend_id, period) DO UPDATE" in period_sql
    assert "keyword_metrics" not in period_sql
    assert "INSERT INTO trends" not in period_sql
    assert "UPDATE trends" not in period_sql
    assert len(cursor.calls) == 1
    assert cursor.calls[0] == (UPSERT_ANALYSIS_SQL, (
        "7D",
        ["NEW", "RISING"],
        "설명",
        "요약",
        "상승 이유",
        "abc123",
        81,
    ))
    assert trend_id == 101


def test_대표_trend가_없으면_새로_만들거나_기존_분석을_변경하지_않고_실패한다(monkeypatch):
    cursor = FakeCursor(rows=(None,))
    install_connection(monkeypatch, cursor)

    with pytest.raises(RuntimeError, match="trends 행이 없어"):
        TrendAnalysisStore(object()).save(target(), analysis(), "abc123")
    assert len(cursor.calls) == 1


def test_기간별_저장_실패도_성공으로_보고하지_않는다(monkeypatch):
    class FailingCursor(FakeCursor):
        def execute(self, statement, params):
            raise RuntimeError("DB 저장 실패")

    install_connection(monkeypatch, FailingCursor())

    with pytest.raises(RuntimeError, match="DB 저장 실패"):
        TrendAnalysisStore(object()).save(target(), analysis(), "abc123")


@pytest.mark.parametrize("found", [True, False])
def test_fingerprint가_일치할_때만_재분석을_건너뛴다(monkeypatch, found):
    cursor = FakeCursor(rows=((found,),))
    install_connection(monkeypatch, cursor)

    assert TrendAnalysisStore(object()).is_current(target(), "abc123") is found
    assert cursor.calls == [(CURRENT_ANALYSIS_SQL, (81, "7D", "abc123"))]
