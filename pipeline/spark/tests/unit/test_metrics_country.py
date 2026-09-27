"""국가별 일 언급량 적재 (`io/metrics.COUNTRY_SQL`). DB 없이 커서만 흉내 낸다 ([09 §4] 층 1).

이 적재는 두 번 성격이 바뀌었다. 처음에는 상류에 국가가 없어 전 키워드를 설정값 한 나라로
채웠고, 그다음 원자료가 나라를 알게 되면서 그 설정이 없어졌다. 동시에 삭제 범위가 **전
기간에서 재계산 창으로** 좁아졌다 — 전자는 매 회차 화면의 옛 구간을 지웠다.

두 성질은 SQL 문자열을 읽어야만 확인된다. 실제로 틀리면 증상이 "지난달 국가 이동이
사라졌다" 이고, 그때는 이미 지워져 있다.
"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from datetime import date
from types import ModuleType

import pytest

from trendin.spark.common.config import Config
from trendin.spark.io import jdbc
from trendin.spark.io.metrics import (
    COUNTRY_FOLD_TABLE_SQL,
    COUNTRY_METRICS,
    COUNTRY_SQL,
    MetricSink,
    country_fold_rows,
)


@pytest.fixture
def recorded(monkeypatch):
    """실행된 문장과 파라미터를 모은다. `_country_stat` 행 수는 3 으로 답한다."""
    calls: list[tuple[str, object]] = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, statement, params=None):
            calls.append((statement, params))

        def fetchone(self):
            return (3,)

    class Connection:
        def cursor(self):
            return Cursor()

        def commit(self):
            pass

    @contextmanager
    def connection(_):
        yield Connection()

    extras = ModuleType("psycopg2.extras")
    extras.execute_values = lambda *_args, **_kwargs: None
    psycopg2 = ModuleType("psycopg2")
    psycopg2.extras = extras
    monkeypatch.setitem(sys.modules, "psycopg2", psycopg2)
    monkeypatch.setitem(sys.modules, "psycopg2.extras", extras)
    monkeypatch.setattr(jdbc, "connection", connection)
    return calls


def sink() -> MetricSink:
    cfg = Config({"jdbc": {"url": "jdbc:postgresql://h/d", "user": "u"}}, profile="test")
    return MetricSink(cfg)


def test_창을_파라미터로_받아_쓴_행_수를_돌려준다(recorded):
    written = sink().rebuild_country_metrics(
        window_start=date(2026, 8, 20), window_end=date(2026, 9, 19)
    )
    assert written == 3
    statements = [statement for statement, _ in recorded]
    assert COUNTRY_SQL in statements
    params = dict(next(params for statement, params in recorded if statement == COUNTRY_SQL))
    assert params == {"window_start": date(2026, 8, 20), "window_end": date(2026, 9, 19)}


def test_전_기간을_지우지_않는다(recorded):
    """전에는 `DELETE FROM keyword_country_daily_metrics` 한 줄로 시작했다.

    그 문장이 있으면 원자료 지평 밖의 옛 행이 회차마다 사라지고, 읽는 쪽이 30일을 보므로
    증상이 곧 화면에 나타난다.
    """
    sink().rebuild_country_metrics(window_start=date(2026, 8, 20), window_end=date(2026, 9, 19))
    for statement, _ in recorded:
        assert f"DELETE FROM {COUNTRY_METRICS}\n" not in statement
        assert f"DELETE FROM {COUNTRY_METRICS};" not in statement


def test_원자료의_국가_칸을_읽고_설정값을_쓰지_않는다():
    """국가가 설정에서 오던 동안에는 `%(country)s` 자리가 있었다."""
    sql = " ".join(COUNTRY_SQL.split())
    assert "source_country AS country_code" in sql
    assert "%(country)s" not in sql
    assert "GROUP BY coalesce(f.leader, s.keyword_id), s.source_country, s.stat_date" in sql


def test_창_안에서만_갈아_쓴다():
    """다른 두 표와 같은 `UPDATE → INSERT → 창 안 DELETE` 규약이다 (설계서 §6.7).

    마지막 `DELETE` 에 창 조건이 **둘 다** 있어야 한다. 하나라도 빠지면 반대쪽이 열린
    구간이 되어 전 기간 삭제로 되돌아간다.
    """
    sql = " ".join(COUNTRY_SQL.split())
    update = sql.index(f"UPDATE {COUNTRY_METRICS}")
    insert = sql.index(f"INSERT INTO {COUNTRY_METRICS}")
    delete = sql.index(f"DELETE FROM {COUNTRY_METRICS}")
    assert update < insert < delete

    tail = sql[delete:]
    assert "m.metric_date >= %(window_start)s" in tail
    assert "m.metric_date < %(window_end)s" in tail
    # 스테이징에 없는 `(키워드, 날짜, 나라)` 만 지운다.
    assert "NOT EXISTS" in tail
    assert "s.country_code = m.country_code" in tail


def test_승격된_키워드만_국가_축에_싣는다():
    """서비스 표가 `keywords` 를 참조하므로 후보는 걸 대상이 없다."""
    assert "WHERE s.keyword_id IS NOT NULL" in " ".join(COUNTRY_SQL.split())


def test_묶인_표기는_대표_줄로_합치고_뺀_키워드는_싣지_않는다():
    """순위와 같은 기준이어야 트렌드의 전체 언급량과 나라별 언급량이 같은 표기들을 센다.

    전에는 `ballet flats` 가 212건인데 나라별은 그 표기 하나의 72건만 보였다.
    """
    sql = " ".join(COUNTRY_SQL.split())
    assert "coalesce(f.leader, s.keyword_id) AS keyword_id" in sql
    assert "LEFT JOIN _country_fold f ON f.keyword_id = s.keyword_id" in sql
    assert "NOT coalesce(f.silenced, false)" in sql


def test_접기_표를_먼저_만들고_적재한다(recorded):
    """`_country_fold` 가 없으면 `COUNTRY_SQL` 의 조인이 실패한다. 빈 규칙이어도 만든다."""
    sink().rebuild_country_metrics(window_start=date(2026, 8, 20), window_end=date(2026, 9, 19))
    statements = [statement for statement, _ in recorded]
    assert statements.index(COUNTRY_FOLD_TABLE_SQL) < statements.index(COUNTRY_SQL)


def test_접기_행은_대표가_빠졌는지로_뺄지를_정한다():
    """`batch.run` 과 같은 차례 — 먼저 접고, 대표가 순위에서 빠졌는지 본다.

    11 → 10 으로 접힘(대표 10 은 셈). 21 → 20 으로 접힘(대표 20 이 빠짐).
    30 은 접히지 않고 빠짐. 11 이 따로 빠지기로 되어 있어도 대표 10 을 따라 세어진다.
    """
    rows = country_fold_rows({11: 10, 21: 20}, silenced={20, 30, 11})
    assert rows == [
        (11, 10, False),
        (20, None, True),
        (21, 20, True),
        (30, None, True),
    ]


def test_규칙이_비면_접기_행도_없다():
    """개념 층이 없는 환경 — 표기마다 그대로 싣는 옛 동작이다."""
    assert country_fold_rows({}, silenced=()) == []
