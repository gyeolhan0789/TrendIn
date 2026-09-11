#!/usr/bin/env python
"""aggregate — 일별 언급량 원자료를 읽어 지표·추이·트렌드 유형을 낸다.

```sh
spark/scripts/submit.sh aggregate --profile local                     # 어제(D)를 기준으로
spark/scripts/submit.sh aggregate --profile local --date 2026-09-09   # 그날 실행한 것처럼
spark/scripts/submit.sh aggregate --profile local --date 2026-08-01 --reaggregate
```

**하는 것** — [07] 전부. `pl_keyword_daily_stat` 을 읽어 일 버킷 시계열
(`keyword_metric_history`), 기간 지표(`keyword_metrics`, `24H`/`7D`/`30D`), 트렌드 유형
(`trends.trend_types`)을 낸다. 원자료는 **읽기만 하고** 추출 로직은 건드리지 않는다.

**기준일 D 는 어제다.** `--date` 는 "그날 실행한 것처럼" 이고, D = `--date` −
`aggregate.reference_day_offset` 이다. 진행 중인 오늘을 완결된 어제와 비교하면 증가율이
아침엔 −90%, 저녁엔 +10% 로 흐른다 ([07 §4]).

**`--reaggregate` 는 D 를 과거로 옮겨 돌리는 모드다** ([07 §7]). 백필 보정이나 임계값 변경 후
재계산이 목적이라 시계열만 고치고, `keyword_metrics` 의 "이번 구간이 아닌 행 지우기" 를
건너뛴다 — 그 실행의 `period_start` 는 옛 구간이라 그대로 두면 **최신 행을 전부 지운다.**

**🚫 승격이 백엔드에 막혀 있으면 쓸 것이 없다.** `keywords (domain, normalized_name)` UNIQUE 가
없어 [05] 가 승격을 건너뛰면 원자료의 `keyword_id` 가 전부 `NULL` 이고, 지표를 걸 대상이
없다 ([10 §7.5] 선행 차단). 그때는 크게 남기고 0 행으로 끝낸다.

**연관 키워드([06])는 여기 없다.** 문서 단위 동시출현은 원자료에 문서 정체성이 없어 리더가
두 벌이 되고, 기준 기간이 기획 답변 대기다 ([10 §7.3] B2).
"""

from __future__ import annotations

import argparse
from datetime import date, datetime

from pyspark.sql import SparkSession

from trendin.spark.common.cli import main
from trendin.spark.common.config import Config, ConfigError
from trendin.spark.common.logging import get_logger
from trendin.spark.common.run_id import default_run_id
from trendin.spark.io import stats as stats_io
from trendin.spark.io.metrics import MetricSink
from trendin.spark.metrics import batch
from trendin.spark.metrics.thresholds import AggregateThresholds
from trendin.spark.normalize.documents import KST

log = get_logger("aggregate")

JOB = "aggregate"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--date",
        default=None,
        help="실행 기준일 (YYYY-MM-DD). 없으면 오늘(KST). D = 이 날짜 − reference_day_offset",
    )
    parser.add_argument(
        "--periods",
        default=None,
        help="계산할 기간 목록 (쉼표 구분). 없으면 설정의 aggregate.periods",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="이 실행의 식별자. 없으면 지금 시각(KST). 판별 이력의 회차 키다",
    )
    parser.add_argument(
        "--reaggregate",
        action="store_true",
        help="D 를 과거로 옮겨 돌리는 모드. 옛 구간 행을 지우지 않는다 ([07 §7])",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="계산만 하고 쓰지 않는다. 임계값을 바꿔 보며 목록을 확인할 때",
    )
    parser.add_argument(
        "--allow-missing-service-tables",
        action="store_true",
        help="서비스 테이블이 없어도 진행한다 (계산만 하고 끝난다). 기본은 거부다",
    )


def _reference_date(value: str | None) -> date:
    if value is None:
        return datetime.now(KST).date()
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ConfigError(f"--date 는 YYYY-MM-DD 여야 한다: {value!r}") from None


def run(spark: SparkSession, config: Config, args: argparse.Namespace) -> None:
    """세션을 받지만 쓰지 않는다 — 집계는 PostgreSQL, 판정은 순수 파이썬이다.

    `registry/batch.py` 와 같은 이유이고, 그래서 이 Job 의 테스트가 세션 없이 돈다
    ([09 §4] 층 1).
    """
    thresholds = AggregateThresholds.from_config(config)
    if args.periods:
        chosen = tuple(part.strip() for part in args.periods.split(",") if part.strip())
        unknown = [period for period in chosen if period not in thresholds.new_windows]
        if unknown:
            raise ConfigError(
                f"--periods 에 설정이 없는 기간이 있다: {', '.join(unknown)} — "
                "aggregate.thresholds.new.windows 에 창을 먼저 채운다"
            )
        thresholds = _with_periods(thresholds, chosen)

    today = _reference_date(args.date)
    run_id = args.run_id or default_run_id()
    sink = MetricSink(config)
    sink.ensure_schema()

    dry_run = bool(args.dry_run)
    if not sink.service_tables_ready():
        # `ingest.contents.required` · `extract.registry.required` 와 같은 형태다. 없이 돌면
        # 계산은 되는데 아무 데도 안 남고, 증상이 "화면이 비었다" 로 나타난다.
        message = (
            "서비스 테이블이 없다 (keyword_metrics · keyword_metric_history · trends) — "
            "백엔드가 아직 스키마를 만들지 않았다 ([08 §5])"
        )
        allowed = args.allow_missing_service_tables
        if not (allowed or config.get("aggregate.service.required") is False):
            raise ConfigError(
                message + ". 계산만 확인하려면 --allow-missing-service-tables 또는 --dry-run"
            )
        log.warning("%s — 계산만 하고 끝낸다", message)
        dry_run = True

    if not dry_run:
        sink.warn_missing_constraints()

    result = batch.run(
        sink,
        thresholds,
        today=today,
        run_id=run_id,
        prune_metrics=not args.reaggregate,
        dry_run=dry_run,
    )
    log.info(
        "aggregate 끝: D=%s 키워드 %d · 버킷 %d · 기간지표 %d · 트렌드 %d",
        result.reference_day,
        result.keywords,
        result.history_rows,
        result.metric_rows,
        result.trend_rows,
    )

    if not dry_run:
        stats = stats_io.BatchStats(config, job=JOB)
        stats.ensure_schema()
        stats.replace(result.stats, ingest_run_id=run_id)


def _with_periods(thresholds: AggregateThresholds, periods: tuple[str, ...]):
    from dataclasses import replace

    return replace(thresholds, periods=periods)


if __name__ == "__main__":
    main(JOB, run, add_arguments=add_arguments)
