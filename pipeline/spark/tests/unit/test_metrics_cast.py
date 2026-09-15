"""적재 SQL 이 붙이는 타입 캐스트 ([08 §4]). DB 없이 커서만 흉내 내 검사한다 ([09 §4] 층 1).

캐스트를 빠뜨리면 Job 이 뜨고 스테이징까지 채운 뒤 마지막 병합에서 죽는다. 그 실패가
배포한 DB 의 컬럼 타입에 달려 있어서, 로컬에서 돌던 것이 서버에서만 깨지는 모양이 된다.
"""

from __future__ import annotations

import pytest

from trendin.spark.common.config import Config
from trendin.spark.io.metrics import MetricSink, trends_merge_sql


class FakeCursor:
    """`COLUMN_TYPE_SQL` 한 줄에 정해진 타입 이름을 돌려준다."""

    def __init__(self, type_name: str | None) -> None:
        self._type_name = type_name

    def execute(self, statement: str, params: tuple) -> None:  # noqa: ARG002
        pass

    def fetchone(self) -> tuple | None:
        if self._type_name is None:
            return None
        return (self._type_name,)


def cast_for(type_name: str | None) -> str:
    cfg = Config({"jdbc": {"url": "jdbc:postgresql://h/d", "user": "u"}}, profile="test")
    sink = MetricSink(cfg)
    return sink._cast(FakeCursor(type_name), "trends", "trend_types")


def test_스칼라_varchar_는_캐스트하지_않는다():
    """`text` 를 넣어도 암묵 캐스트로 지나가므로 붙일 이유가 없다."""
    assert cast_for("character varying(255)") == ""
    assert cast_for("text") == ""


@pytest.mark.parametrize(
    "actual",
    ["character varying(255)[]", "text[]", "varchar[]"],
    ids=["varchar_길이있음", "text", "varchar_길이없음"],
)
def test_varchar_배열도_캐스트한다(actual: str):
    """**스칼라와 갈리는 지점이다.** PostgreSQL 에 `varchar[] = text[]` 연산자가 없어서,
    캐스트를 빼면 스테이징의 `text[]` 와 비교하는 순간 죽는다. 서비스 DB 의
    `trends.trend_types` 가 `varchar(255)[]` 라 실제로 걸리는 경로다.
    """
    assert cast_for(actual) == f"::{actual}"


def test_네이티브_enum_과_그_배열은_캐스트한다():
    assert cast_for("metric_period") == "::metric_period"
    assert cast_for("trend_type[]") == "::trend_type[]"


def test_컬럼이_없으면_빈_문자열이다():
    """표가 아직 없는 DB 에서 SQL 을 만들다 터지지 않게 한다."""
    assert cast_for(None) == ""


# --- MERGE 에 실제로 실리는지 -------------------------------------------------
#
# 판정이 맞아도 SQL 의 한쪽에만 붙이면 여전히 죽는다. `IS DISTINCT FROM` 은 양변의 타입이
# 맞아야 하고, `INSERT ... SELECT` 는 대상 컬럼 타입과 맞아야 한다.


def test_trends_MERGE_의_비교와_삽입_양쪽에_캐스트가_실린다():
    merge = trends_merge_sql("::character varying[]")

    assert "s.trend_types::character varying[]" in merge
    assert merge.count("::character varying[]") >= 3


def test_캐스트가_빈_문자열이면_SQL_에_아무것도_붙지_않는다():
    """옛 스키마처럼 캐스트가 필요 없는 경우에도 같은 SQL 이 만들어져야 한다."""
    assert "::" not in trends_merge_sql("")
