#!/usr/bin/env python
"""완료된 기간별 트렌드를 기사 기반으로 분석해 `trend_analyses`에 저장한다."""

from __future__ import annotations

import argparse
from datetime import date, datetime
from typing import TYPE_CHECKING

from trendin.ai.articles import CuratedArticleLoader, TrendArticleRepository
from trendin.ai.runner import TopTrendAnalysisRunner
from trendin.ai.store import TrendAnalysisStore
from trendin.spark.common.cli import main
from trendin.spark.common.config import Config, ConfigError
from trendin.spark.common.logging import get_logger
from trendin.spark.metrics import windows
from trendin.spark.normalize.documents import KST

if TYPE_CHECKING:
    from pyspark.sql import SparkSession

log = get_logger("analyze")

JOB = "analyze"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--date",
        default=None,
        help="실행 기준일 (YYYY-MM-DD). 없으면 오늘(KST)",
    )
    parser.add_argument(
        "--period",
        default=None,
        choices=tuple(windows.PERIOD_DAYS),
        help="단일 분석 기간. 생략하면 24H/7D/30D를 모두 분석",
    )


def _today(value: str | None) -> date:
    if value is None:
        return datetime.now(KST).date()
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ConfigError(f"--date 는 YYYY-MM-DD 여야 한다: {value!r}") from None


def _as_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def run(spark: "SparkSession", config: Config, args: argparse.Namespace) -> None:
    reference = windows.reference_day(
        _today(args.date), int(config.get("aggregate.reference_day_offset", 1))
    )
    domains = tuple(name.upper() for name in config.section("extract.domains"))
    if not domains:
        raise ConfigError("extract.domains가 비어 있어 AI 분석 대상을 정할 수 없다")

    runner = TopTrendAnalysisRunner(
        TrendArticleRepository(config),
        CuratedArticleLoader(spark, config),
        store=TrendAnalysisStore(config),
    )
    saved = skipped = failed = 0
    periods = (args.period,) if args.period else tuple(windows.PERIOD_DAYS)
    for period in periods:
        window = windows.current_window(period, reference)
        period_start = _as_datetime(window.start_ts)
        period_end = _as_datetime(window.end_ts)
        for domain in domains:
            try:
                outcomes = runner.run(
                    domain=domain,
                    period=period,
                    period_start=period_start,
                    period_end=period_end,
                )
            except Exception:
                failed += 1
                log.exception("[%s/%s] 트렌드 대상 조회 실패", domain, period)
                continue
            for outcome in outcomes:
                if outcome.analysis is not None:
                    saved += 1
                elif outcome.skipped:
                    skipped += 1
                else:
                    failed += 1
                    log.error(
                        "[%s/%s] %s 분석·저장 실패: %s",
                        domain,
                        period,
                        outcome.target.keyword,
                        outcome.error,
                    )

    log.info(
        "AI 분석 끝: 기간=%s 저장=%d · 미분석/재사용=%d · 실패=%d",
        ",".join(periods),
        saved,
        skipped,
        failed,
    )


if __name__ == "__main__":
    main(JOB, run, add_arguments=add_arguments)
