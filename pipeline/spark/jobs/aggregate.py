#!/usr/bin/env python
"""aggregate — 일별 언급량 원자료를 읽어 지표·추이·트렌드 유형을 낸다.

```sh
spark/scripts/submit.sh aggregate --profile local                     # 어제(D)를 기준으로
spark/scripts/submit.sh aggregate --profile local --date 2026-09-09   # 그날 실행한 것처럼
spark/scripts/submit.sh aggregate --profile local --date 2026-08-01 --reaggregate
```

**하는 것** — [07] 전부. `pl_keyword_daily_stat` 을 읽어 일 버킷 시계열
(`keyword_metric_history`), 기간 지표와 트렌드 유형(`keyword_metrics`, `24H`/`7D`/`30D`)을
낸다. 원자료는 **읽기만 하고** 추출 로직은 건드리지 않는다.

**배지가 기간별이다.** 트렌드 유형이 `keyword_metrics.trend_types` 에 그 기간의 지표 행과
함께 실린다 ([07 §6]). `trends` 를 쓰던 때는 그 표에 `period` 가 없어 기간을 합쳐 실었고,
`24H` 에서만 급상승한 키워드가 `30D` 목록에서도 배지를 달았다. **백엔드 목록 조회는 아직
`trends` 를 조인한다** — 그 조회가 새 칸으로 옮겨오기 전까지 화면은 옛 배지를 보여준다.

**기준일 D 는 어제다.** `--date` 는 "그날 실행한 것처럼" 이고, D = `--date` −
`aggregate.reference_day_offset` 이다. 진행 중인 오늘을 완결된 어제와 비교하면 증가율이
아침엔 −90%, 저녁엔 +10% 로 흐른다 ([07 §4]).

**`--reaggregate` 는 D 를 과거로 옮겨 돌리는 모드다** ([07 §7]). 백필 보정이나 임계값 변경 후
재계산이 목적이라 시계열만 고치고, `keyword_metrics` 의 "이번 구간이 아닌 행 지우기" 를
건너뛴다 — 그 실행의 `period_start` 는 옛 구간이라 그대로 두면 **최신 행을 전부 지운다.**

**🚫 승격이 백엔드에 막혀 있으면 쓸 것이 없다.** `keywords (domain, normalized_name)` UNIQUE 가
없어 [05] 가 승격을 건너뛰면 원자료의 `keyword_id` 가 전부 `NULL` 이고, 지표를 걸 대상이
없다 ([10 §7.5] 선행 차단). 그때는 크게 남기고 0 행으로 끝낸다.

**연관 키워드([06])가 여기 붙었다** ([10 §7.3] B2). 원자료 대신 `keyword_contents` 를 읽어
같은 문서에 함께 나온 정도를 자카드로 재고, 기준 기간은 지표의 가장 긴 `30D` 와 맞췄다.
산식과 포함 관계 제외의 근거는 `metrics/relations.py` 에 있다.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, time, timedelta

from pyspark.sql import SparkSession

from trendin.spark.common.cli import main
from trendin.spark.common.config import Config, ConfigError
from trendin.spark.common.logging import get_logger
from trendin.spark.common.run_id import default_run_id
from trendin.spark.io import stats as stats_io
from trendin.spark.io.metrics import MetricSink, country_fold_rows
from trendin.spark.metrics import batch
from trendin.spark.metrics import windows as window_rules
from trendin.spark.metrics.concepts import Grouping
from trendin.spark.metrics.relations import RelationThresholds
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
    # `ingest.contents.required` · `extract.registry.required` 와 같은 형태다. 없이 돌면
    # 계산은 되는데 아무 데도 안 남고, 증상이 "화면이 비었다" 로 나타난다.
    #
    # **표가 있어도 칸이 없을 수 있다.** 배지 자리가 `keyword_metrics.trend_types` 로 옮겨온
    # 것이 나중이라, 그전 마이그레이션까지만 올라간 DB 는 표만 있다. 두 경우를 갈라서 남기는
    # 이유는 조치가 다르기 때문이다 — 앞은 스키마를 세우는 일이고 뒤는 칸 하나를 더하는 일이다.
    if not sink.service_tables_ready():
        message = (
            "서비스 테이블이 없다 (keyword_metrics · keyword_metric_history) — "
            "백엔드가 아직 스키마를 만들지 않았다 ([08 §5])"
        )
    elif not sink.trend_column_ready():
        message = (
            "keyword_metrics.trend_types 칸이 없다 — 트렌드 배지가 이 칸으로 옮겨왔는데 "
            "([07 §6]) DB 가 그전 스키마다. 백엔드 마이그레이션이 올라가야 한다 ([08 §5])"
        )
    elif legacy := sink.legacy_trend_columns():
        message = (
            f"trends 에 채울 수 없는 NOT NULL 칸이 남아 있다 ({', '.join(legacy)}) — "
            "V7 이 이 칸들을 떼어내기 전 스키마다. 이대로 적재하면 대표 trends 행 INSERT 가 "
            "죽고 같은 트랜잭션의 지표 병합까지 롤백된다. 백엔드 마이그레이션이 올라가야 "
            "한다 ([08 §5])"
        )
    else:
        message = ""
    if message:
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
        "aggregate 끝: D=%s 키워드 %d · 버킷 %d · 기간지표 %d · 배지 %d(키워드×기간)",
        result.reference_day,
        result.keywords,
        result.history_rows,
        result.metric_rows,
        result.trend_verdicts,
    )

    # 연관 키워드 ([06]). **지표 뒤에 온다** — 재료가 `keyword_contents` 라 지표와 서로
    # 기대지 않지만, 승격이 막히면 둘 다 쓸 것이 없다는 사정이 같다.
    if not dry_run:
        _rebuild_relations(sink, config, reference_day=result.reference_day)
        _rebuild_country_metrics(
            sink, thresholds, reference_day=result.reference_day, grouping=result.grouping
        )

    if not dry_run:
        stats = stats_io.BatchStats(config, job=JOB)
        stats.ensure_schema()
        stats.replace(result.stats, ingest_run_id=run_id)


def _rebuild_country_metrics(
    sink: MetricSink,
    thresholds: AggregateThresholds,
    *,
    reference_day: date,
    grouping: Grouping | None = None,
) -> None:
    """원자료의 국가 칸을 국가 축 지표로 옮긴다 (`io/metrics.COUNTRY_SQL` 의 주석).

    **`aggregate.country.code` 설정이 없어졌다** (2026-09-18). 상류에 국가가 없던 동안 표를
    비워 두지 않으려고 전 키워드를 한 나라로 채우던 임시 값이었고, 이제 원자료가 나라를
    안다. 끊겨 있던 자리는 추출이 `curated` 에서 읽는 칸 목록 한 줄이었다.

    **창이 시계열과 같다.** 국가 축만 다른 구간을 갈아 쓰면 같은 키워드의 전국 그래프와
    나라별 그래프가 서로 다른 시기를 말한다.

    **접기·거르기도 순위와 같다** (`io/metrics.COUNTRY_SQL` 의 주석). 트렌드의 전체 언급량과
    나라별 언급량의 합이 같은 표기들을 센 숫자여야 한다.
    """
    if not sink.country_table_ready():
        log.warning("keyword_country_daily_metrics 가 없다 — 국가별 언급량을 건너뛴다")
        return
    window = window_rules.history_window(reference_day, thresholds.recompute_window_days)
    fold = (
        country_fold_rows(grouping.representative, grouping.silenced) if grouping else []
    )
    written = sink.rebuild_country_metrics(
        window_start=window.start, window_end=window.end, fold=fold
    )
    log.info(
        "국가별 일 언급량 %d행 — 재계산 [%s, %s)",
        written,
        window.start,
        window.end,
    )


def _rebuild_relations(sink: MetricSink, config: Config, *, reference_day: date) -> None:
    """창 안의 동시출현으로 `keyword_relations` 를 다시 만든다.

    **창의 끝이 D 의 자정이다.** 지표가 D 까지를 완결된 구간으로 보므로([07 §4]) 연관만
    오늘을 포함하면 둘이 다른 시기를 말하게 된다.
    """
    thresholds = RelationThresholds.from_config(config)
    if not sink.relations_ready():
        log.warning(
            "keyword_relations 또는 keyword_contents 가 없다 — 연관을 건너뛴다 ([08 §5])"
        )
        return
    since = datetime.combine(
        reference_day - timedelta(days=thresholds.window_days - 1), time.min, KST
    )
    until = datetime.combine(reference_day + timedelta(days=1), time.min, KST)
    written = sink.rebuild_relations(since=since, until=until, thresholds=thresholds)
    log.info(
        "연관 키워드 %d행 — 최근 %d일(%s~%s) · 공기 하한 %d · 키워드당 상위 %d",
        written,
        thresholds.window_days,
        since.date(),
        reference_day,
        thresholds.min_co_occurrence,
        thresholds.top_n,
    )


def _with_periods(thresholds: AggregateThresholds, periods: tuple[str, ...]):
    from dataclasses import replace

    return replace(thresholds, periods=periods)


if __name__ == "__main__":
    main(JOB, run, add_arguments=add_arguments)
