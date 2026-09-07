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
        choices=("kafka", "objects"),
        default="kafka",
        help="kafka: 이벤트 소비. objects: Kafka 없이 MinIO 프리픽스 스캔으로 재처리 ([02 §6])",
    )
    # 아래 넷은 --source objects 전용이다. 배치 계약 시절의 --manifest(metadata.json
    # 목록 경로)를 대체한다 — 기사 단위로 가면서 그 파일이 없어졌다 ([02 §3]).
    parser.add_argument(
        "--domain",
        default=None,
        help="--source objects 일 때 훑을 도메인 (fashion | dev)",
    )
    parser.add_argument(
        "--from",
        dest="date_from",
        default=None,
        help="--source objects 일 때 시작 발행일 (YYYY-MM-DD). 수집일이 아니다",
    )
    parser.add_argument(
        "--to",
        dest="date_to",
        default=None,
        help="--source objects 일 때 끝 발행일 (YYYY-MM-DD). 포함",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="원장의 COMPLETED 를 무시하고 다시 처리한다 ([02 §6])",
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
