#!/usr/bin/env python
"""aggregate — 날짜 단위로 언급량·순위·성장률·연관 키워드를 계산한다.

```sh
spark-submit --jars "spark/jars/*" spark/jobs/aggregate.py --profile local --date 2026-09-03
```

**아직 아무것도 하지 않는다.** 단계는 [06](../docs/06-related-keyword-spec.md) ·
[07](../docs/07-metrics-and-ranking-spec.md) 을 따라 채운다.
"""

from __future__ import annotations

import argparse

from pyspark.sql import SparkSession

from trendin.spark.common.cli import main
from trendin.spark.common.config import Config
from trendin.spark.common.logging import get_logger

log = get_logger("aggregate")

JOB = "aggregate"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--date",
        default=None,
        help="집계 기준일 (YYYY-MM-DD). 없으면 오늘. 발행이 늦은 문서는 소급 재계산한다 ([07 §3])",
    )
    parser.add_argument(
        "--periods",
        default=None,
        help="계산할 기간 목록. 없으면 설정의 aggregate.periods",
    )


def run(spark: SparkSession, config: Config, args: argparse.Namespace) -> None:
    periods = args.periods or config.get("aggregate.periods")
    log.info("aggregate 준비: date=%s periods=%s", args.date or "(오늘)", periods)
    # TODO(S15P21A102): 윈도우 집계 → 순위 → 성장률 → 연관 키워드 → 적재.
    #   [06] 연관 · [07] 지표·순위 · [08] 적재 전략.
    log.warning("aggregate 는 아직 비어 있다 — 뼈대만 돌고 끝난다")


if __name__ == "__main__":
    main(JOB, run, add_arguments=add_arguments)
