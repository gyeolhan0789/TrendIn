#!/usr/bin/env python
"""extract — MinIO `curated` 를 읽어 키워드를 뽑고 `keywords` · `keyword_contents` 에 넣는다.

```sh
spark-submit --jars "spark/jars/*" spark/jobs/extract.py --profile local
```

**아직 아무것도 하지 않는다.** 단계는 [04](../docs/04-keyword-extraction-spec.md) ·
[05](../docs/05-keyword-registry-spec.md) 를 따라 채운다.
"""

from __future__ import annotations

import argparse

from pyspark.sql import SparkSession

from trendin.spark.common.cli import main
from trendin.spark.common.config import Config
from trendin.spark.common.logging import get_logger

log = get_logger("extract")

JOB = "extract"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--partitions",
        default=None,
        help="다시 돌릴 curated 파티션 목록. 없으면 처리 이력이 가리키는 새 파티션만 ([01 §3])",
    )


def run(spark: SparkSession, config: Config, args: argparse.Namespace) -> None:
    log.info("extract 준비: partitions=%s", args.partitions or "(처리 이력 기준)")
    # TODO(S15P21A102): curated 읽기 → 후보 생성 → 스코어링 → 정규화·승격 → 적재.
    #   [04] 추출 · [05] 레지스트리 · [08] 적재 전략.
    log.warning("extract 는 아직 비어 있다 — 뼈대만 돌고 끝난다")


if __name__ == "__main__":
    main(JOB, run, add_arguments=add_arguments)
