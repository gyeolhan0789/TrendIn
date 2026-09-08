#!/usr/bin/env python
"""ingest — Kafka `raw-file-ready` 를 받아 계약대로 판별하고 처리 이력·DLQ 에 남긴다.

```sh
spark-submit --jars "$(ls spark/jars/*.jar | paste -sd,)" spark/jobs/ingest.py --profile local
```

**지금 하는 것** — 이벤트 소비, 계약 판별, 중복 제거, MinIO 객체 조회와 checksum 대조,
처리 이력 기록, DLQ 기록. `error_type` 일곱 가지가 전부 발생한다.
**아직 안 하는 것** — 정제, `curated` 쓰기, `contents` 적재 ([03] · [08]).

단계는 [02](../docs/02-input-contract.md) · [03](../docs/03-normalization-spec.md) 을 따라 채운다.
"""

from __future__ import annotations

import argparse

from pyspark.sql import SparkSession

from trendin.spark.common.cli import main
from trendin.spark.common.config import Config
from trendin.spark.common.logging import get_logger
from trendin.spark.common.session import checkpoint_dir
from trendin.spark.ingest.batch import ENVELOPE_COLUMNS, BatchResult, process_batch
from trendin.spark.ingest.objects import verifier
from trendin.spark.io.dlq import build_dlq_sink
from trendin.spark.io.kafka import read_events
from trendin.spark.io.ledger import Ledger

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
        help="처리 이력의 기록을 무시하고 다시 처리한다 ([02 §6])",
    )


def run(spark: SparkSession, config: Config, args: argparse.Namespace) -> None:
    """단계 호출만 한다. 로직은 `trendin.spark.*` 에 둔다."""
    if args.source == "objects":
        # TODO(S15P21A102): MinIO 프리픽스 스캔으로 메시지를 재구성한다 ([02 §6] 모드 B).
        log.warning("--source objects 는 아직 없다. 모드 B 는 [02 §6] 을 따라 채운다")
        return

    ledger = Ledger(config, job=JOB)
    dlq = build_dlq_sink(config, job=JOB)
    ledger.ensure_schema()
    dlq.ensure_schema()
    # 객체 검증 ([02 §3]). 메시지를 통과한 기사 이벤트만 탄다.
    verify_objects = verifier(config, columns=ENVELOPE_COLUMNS)

    checkpoint = checkpoint_dir(JOB, config)
    log.info("ingest 시작: source=%s checkpoint=%s force=%s", args.source, checkpoint, args.force)

    events = read_events(spark, config, job=JOB)
    totals: list[BatchResult] = []

    def handle(batch, batch_id: int) -> None:
        # foreachBatch 의 콜백은 드라이버에서 돈다. 배치 DataFrame 은 여러 번 쓰이므로
        # process_batch 안에서 캐시한다.
        log.info("배치 %d 시작", batch_id)
        totals.append(
            process_batch(
                batch,
                job=JOB,
                ledger=ledger,
                dlq=dlq,
                verify_objects=verify_objects,
                force=args.force,
            )
        )

    query = (
        events.writeStream.foreachBatch(handle)
        # 그때까지 쌓인 것까지 여러 마이크로배치로 나눠 소비하고 스스로 끝난다 ([01 §1]).
        .trigger(availableNow=True)
        # 오프셋의 단일 출처. 지우는 것은 [02 §6] 절차를 따를 때만 한다.
        .option("checkpointLocation", checkpoint)
        .start()
    )
    query.awaitTermination()

    log.info(
        "ingest 끝: 배치 %d개 받음=%d 처리 이력에서 걸림=%d 기사=%d 요약=%d DLQ=%d",
        len(totals),
        sum(r.received for r in totals),
        sum(r.duplicates for r in totals),
        sum(r.articles for r in totals),
        sum(r.summaries for r in totals),
        sum(r.rejected for r in totals),
    )


if __name__ == "__main__":
    main(JOB, run, add_arguments=add_arguments)
