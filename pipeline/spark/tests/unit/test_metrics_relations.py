"""연관 키워드 설정 (`metrics/relations.py`). 층 1 ([09 §4]).

집계 자체는 SQL 이라 여기서는 **문턱과 그 거부 이유**를 본다. 산식이 맞는지는 DB 를 띄워
확인하는 일이고, 설정이 조용히 잘못 도는 것을 막는 것이 이 파일 몫이다.
"""

from __future__ import annotations

import pytest

from trendin.spark.common.config import Config, ConfigError
from trendin.spark.metrics.relations import RELATION_SQL, RelationThresholds


def config(**values) -> Config:
    return Config({"aggregate": {"relations": values}}, profile="test")


def test_defaults_when_section_is_empty():
    """구역이 없어도 돈다. 이 값들은 코퍼스가 아니라 설계에서 나온다."""
    thresholds = RelationThresholds.from_config(Config({}, profile="test"))
    assert thresholds.window_days == 30
    assert thresholds.min_co_occurrence == 2
    assert thresholds.top_n == 20


def test_reads_the_section():
    thresholds = RelationThresholds.from_config(
        config(window_days=7, min_co_occurrence=3, top_n=5)
    )
    assert (thresholds.window_days, thresholds.min_co_occurrence, thresholds.top_n) == (7, 3, 5)


def test_single_document_pairs_are_refused():
    """**1 을 허용하면 한 문서에만 함께 나온 쌍이 자카드 100 으로 상위를 먹는다.** 설정으로
    열어 둘 값이 아니라 거부한다."""
    with pytest.raises(ConfigError, match="min_co_occurrence"):
        RelationThresholds.from_config(config(min_co_occurrence=1))


@pytest.mark.parametrize("values", [{"window_days": 0}, {"top_n": 0}])
def test_nonpositive_values_are_refused(values):
    with pytest.raises(ConfigError):
        RelationThresholds.from_config(config(**values))


def test_sql_counts_each_pair_once():
    """`b.keyword_id > a.keyword_id` 가 쌍을 한 번만 세고 자기 자신과의 쌍을 뺀다. 이 조건이
    빠지면 공기 수가 두 배가 되고 모든 키워드가 자기 자신과 자카드 100 을 갖는다."""
    assert "b.keyword_id > a.keyword_id" in RELATION_SQL


def test_sql_excludes_substring_pairs():
    """포함 관계 제외 — 옛 측정에서 연관 1위의 24% 가 자기 표기의 조각이었다."""
    assert "position(klo.normalized_name IN khi.normalized_name) = 0" in RELATION_SQL
    assert "position(khi.normalized_name IN klo.normalized_name) = 0" in RELATION_SQL


def test_sql_orders_deterministically():
    """동점에서 순서가 흔들리면 같은 입력이 실행마다 다른 상위 N 을 낸다."""
    assert "ORDER BY score DESC, co DESC, tgt" in RELATION_SQL
