#!/usr/bin/env python
"""ingest — Kafka `raw-file-ready` 를 받아 MinIO 원문을 검증·정제하고 `contents` 에 넣는다.

```sh
spark-submit --jars "spark/jars/*" spark/jobs/ingest.py --profile local
```

**아직 아무것도 하지 않는다.** 뼈대만 있고 단계는 [02](../docs/02-input-contract.md) ·
[03](../docs/03-normalization-spec.md) 을 따라 채운다.
"""

from __future__ import annotations

import argparse

from pyspark.sql import SparkSession

from trendin.spark.common.cli import main
from trendin.spark.common.config import Config
from trendin.spark.common.logging import get_logger
from trendin.spark.common.session import checkpoint_dir

log = get_logger("ingest")

JOB = "ingest"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--source",
        choices=("kafka", "manifest"),
        default="kafka",
        help="kafka: 이벤트 소비. manifest: Kafka 없이 목록으로 재처리 ([02 §6])",
    )
    parser.add_argument(
        "--manifest",
        default=None,
        help="--source manifest 일 때 읽을 객체 키 목록 경로",
    )


def run(spark: SparkSession, config: Config, args: argparse.Namespace) -> None:
    """단계 호출만 한다. 로직은 `trendin.spark.*` 에 둔다."""
    log.info(
        "ingest 준비: source=%s checkpoint=%s",
        args.source,
        checkpoint_dir(JOB, config),
    )
    # TODO(S15P21A102): 이벤트 소비 → 원문 검증 → 정제 → curated 쓰기 → contents 적재.
    #   [02] 입력 계약 · [03] 정제 규격 · [08] 적재 전략.
    log.warning("ingest 는 아직 비어 있다 — 뼈대만 돌고 끝난다")


if __name__ == "__main__":
    main(JOB, run, add_arguments=add_arguments)
