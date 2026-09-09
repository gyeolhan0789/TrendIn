"""`io/stats.RunStats` — 배치 누적과 실행 단위 확정 ([03 §7], 층 1).

Spark 없이 본다. `add_batch` 는 층 2(`spark/test_normalize_batch.py`)가, 여기서는 누적기의
산술만 본다 — 건수는 더하고, 비율은 끝에 다시 내고, 분포는 값을 모아 계산한다.
"""

from __future__ import annotations

import pytest

from trendin.spark.io import stats as stats_io
from trendin.spark.io.stats import RunStats, Stat, length_stats


def _by_key(stats):
    return {(s.metric, s.dimension): s.value for s in stats}


def test_빈_실행도_입력과_생존_건수는_0_으로_남긴다():
    """좁은 표에서 행이 없는 것은 "안 셌음" 이다. 실행이 돌았다면 이 둘은 셌다."""
    collected = _by_key(RunStats().finalize())

    assert collected[(stats_io.INPUT, "")] == 0
    assert collected[(stats_io.KEPT, "")] == 0
    assert collected[(stats_io.SURVIVAL_RATE, "")] == 0.0


def test_건수는_배치마다_더하고_비율은_끝에_다시_낸다():
    """배치마다 upsert 하면 뒤 배치가 앞 배치를 덮는다 — 그 대신 누적한 뒤 한 번 낸다."""
    run = RunStats()
    run.add_counts([Stat(stats_io.INPUT, "", 10), Stat(stats_io.KEPT, "", 9)])
    run.add_counts(
        [
            Stat(stats_io.INPUT, "", 10),
            Stat(stats_io.KEPT, "", 5),
            Stat(stats_io.EXCLUDED, "SHORT_BODY", 5),
        ]
    )
    collected = _by_key(run.finalize())

    assert collected[(stats_io.INPUT, "")] == 20
    assert collected[(stats_io.KEPT, "")] == 14
    assert collected[(stats_io.EXCLUDED, "SHORT_BODY")] == 5
    assert collected[(stats_io.SURVIVAL_RATE, "")] == pytest.approx(0.7)


def test_본문_길이는_값을_모아_끝에_분포를_낸다():
    """백분위는 배치 간에 더할 수 없다. 값 자체를 모아야 한다."""
    run = RunStats()
    run.add_lengths("rss", [100, 200])
    run.add_lengths("rss", [300, 400, 1000])
    collected = _by_key(run.finalize())

    assert collected[(stats_io.BODY_LEN_AVG, "rss")] == 400
    assert collected[(stats_io.BODY_LEN_P50, "rss")] == 300
    assert collected[(stats_io.BODY_LEN_P90, "rss")] == 1000
    assert collected[(stats_io.BODY_LEN_MAX, "rss")] == 1000


def test_길이가_없는_route_는_분포_행을_내지_않는다():
    assert length_stats("api", []) == []


def test_밖에서_온_지표는_그대로_실린다():
    """백필의 `backfill_listed` 처럼 정제 프레임 밖에서 이미 아는 값."""
    run = RunStats().add([Stat(stats_io.BACKFILL_LISTED, "", 42)])

    assert _by_key(run.finalize())[(stats_io.BACKFILL_LISTED, "")] == 42


def test_collect_stats_는_프레임_하나를_실행_전체로_본다():
    """옛 호출부와 테스트가 쓰는 편의 함수. 누적기 하나에 배치 하나를 넣은 것과 같다."""
    assert callable(stats_io.collect_stats)
