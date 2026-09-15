#!/usr/bin/env python
"""ingest — 수집 장부를 읽어 검증하고, 정제해 `curated` · `contents` 에 적재한다.

```sh
spark-submit --jars "$(ls spark/jars/*.jar | paste -sd,)" spark/jobs/ingest.py --profile local
```

**하는 것** — 장부 읽기, 봉투 조립, 중복 제거, MinIO 객체 조회와 checksum 대조, 처리 이력·DLQ
기록([02]), 그리고 텍스트 정제 · 중복 제거 3단계 · `curated` Parquet 쓰기 · `contents` upsert ·
`pl_batch_stat` 기록([03]). 백필 경로(`--source objects`)도 여기 있다 ([02 §6]).

**아직 안 하는 것** — 키워드 추출 ([04] 부터. `extract` Job 이 한다).

단계는 [02](../docs/02-input-contract.md) · [03](../docs/03-normalization-spec.md) 을 따른다.
"""

from __future__ import annotations

import argparse
from datetime import datetime

from pyspark.sql import SparkSession

from trendin.spark.common.cli import main
from trendin.spark.common.config import Config, ConfigError
from trendin.spark.common.exit_codes import NOTHING_NEW
from trendin.spark.common.logging import get_logger
from trendin.spark.ingest import backfill, collected
from trendin.spark.ingest.batch import ENVELOPE_COLUMNS, BatchResult, process_batch
from trendin.spark.ingest.normalize import normalizer
from trendin.spark.ingest.objects import verifier
from trendin.spark.io import jdbc
from trendin.spark.io import objects as store_io
from trendin.spark.io import stats as stats_io
from trendin.spark.io.contents import ContentsSink
from trendin.spark.io.dlq import build_dlq_sink
from trendin.spark.io.ledger import Ledger
from trendin.spark.normalize.documents import KST

log = get_logger("ingest")

JOB = "ingest"

# `ingest_run_id` 의 형식. 생산자 `run_id` 와 형식은 같고 뜻이 다르다 ([01 §3]) —
# 그쪽은 수집기가 한 번 돈 것이고 이쪽은 이 Job 이 한 번 돈 것이다.
RUN_ID_FORMAT = "%Y%m%dT%H%M%S"


def default_run_id() -> str:
    """지금 시각(KST)에서. Airflow 는 logical date 를 `--run-id` 로 넘긴다 ([01 §3]).

    KST 인 이유는 `curated` 파티션의 `published_date` 가 KST 이고(불변식 10) 둘을 나란히
    읽을 때 시간대가 갈리면 사람이 헷갈리기 때문이다.
    """
    return datetime.now(KST).strftime(RUN_ID_FORMAT)


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--source",
        choices=("ledger", "objects"),
        default="ledger",
        help=(
            "ledger: 수집 장부 뷰를 읽는 평시 경로. "
            "objects: MinIO 프리픽스 스캔으로 재처리 ([02 §6])"
        ),
    )
    # 아래 셋은 --source objects 전용이다. 배치 계약 시절의 --manifest(metadata.json
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
    parser.add_argument(
        "--run-id",
        dest="run_id",
        default=None,
        help=(
            "curated 파티션에 들어가는 이 실행의 식별자 (yyyyMMddTHHmmss, KST). "
            "없으면 지금 시각. Airflow 는 logical date 를 넘긴다 ([01 §3])"
        ),
    )
    parser.add_argument(
        "--allow-missing-contents",
        action="store_true",
        help=(
            "`contents` 테이블이 없어도 curated 까지만 쓰고 계속 돈다. 기본은 설정 "
            "`ingest.contents.required`(base.yaml 은 true, local.yaml 은 false) 를 따르며, "
            "이 플래그는 그 값을 false 로 덮는다 ([03 §8])"
        ),
    )


def _build_contents_sink(config: Config, *, require: bool) -> ContentsSink | None:
    """`contents` 싱크. 테이블이 없으면 `None` 을 주거나 죽는다.

    **🚫 `contents` 테이블이 아직 없다.** 백엔드 엔티티에 `Content` 가 없고 `ddl-auto` 가
    `create` 다. Spark 는 서비스 테이블에 DDL 을 걸지 않으므로([08 §1]) 우리가 만들 수 없다.

    **조용히 건너뛰지 않는 것이 핵심이다.** 건너뛴 배치는 `curated` 에는 쓰이고 `contents`
    에는 없어서, `extract` 가 `pl_content_id_map` 에서 그 문서를 못 찾는다. 그 증상은
    "키워드는 나오는데 관련 콘텐츠가 비어 있다" 로 [04] 에서 나타나고, 원인이 여기라는 것을
    되짚기 어렵다. 그래서 **기본은 fail-closed 다** — `ingest.contents.required` 가 `true`
    (base.yaml) 면 아예 시작하지 않는다. 로컬(local.yaml)만 `false` 고, 다른 곳에서 풀려면
    `--allow-missing-contents` 를 명시해야 한다.
    """
    sink = ContentsSink(config)
    sink.ensure_schema()
    if sink.service_table_ready():
        return sink

    message = (
        "contents 테이블이 없다 — 백엔드가 만들기 전이다 ([03 §8], [08 §5] 티어 1). "
        "curated 에는 쓰이지만 서비스 테이블과 pl_content_id_map 은 비어 있게 된다"
    )
    if require:
        raise ConfigError(message)
    log.error("%s. --allow-missing-contents 로 허용한 실행이다", message)
    return None


def run(spark: SparkSession, config: Config, args: argparse.Namespace) -> int | None:
    """단계 호출만 한다. 로직은 `trendin.spark.*` 에 둔다.

    **새로 쓴 것이 없으면 `NOTHING_NEW` 로 끝난다** (평시 경로만, S15P21A102-247). 그러면
    Airflow 가 이 태스크를 skipped 로 두고 `curated` 자산이 갱신되지 않아 `spark_extract`
    가 깨어나지 않는다. 수집 회차마다 자산이 오는데 새 기사는 대개 없어서, 이것이 없으면
    하루에 수십 번 30일 코퍼스를 다시 돈다 — 결과는 같고 시간만 쓴다.
    """
    run_id = args.run_id or default_run_id()

    # 아무것도 하기 전에 본다. 틀린 DB 는 오류가 아니라 0건과 빈 조회로 나타나서,
    # 절반쯤 적재한 뒤에 알아채면 어디까지 어느 DB 에 갔는지 되짚어야 한다.
    jdbc.assert_producer_database(config)

    # `history` 인 이유는 `--source ledger` 의 ledger 가 수집 장부라서다. 이쪽은 처리
    # 이력(`pl_processing_ledger`)이고 둘은 다른 표다 (S15P21A102-247 코드리뷰).
    history = Ledger(config, job=JOB)
    dlq = build_dlq_sink(config, job=JOB)
    stats = stats_io.BatchStats(config, job=JOB)
    history.ensure_schema()
    dlq.ensure_schema()
    stats.ensure_schema()
    required = bool(config.get("ingest.contents.required", True))
    if args.allow_missing_contents:
        required = False
    contents = _build_contents_sink(config, require=required)

    # 통계는 배치마다 누적하고 실행 끝에 한 번 쓴다 ([03 §7], `io/stats.RunStats`).
    run_stats = stats_io.RunStats()
    normalize = normalizer(
        config,
        ingest_run_id=run_id,
        envelope_columns=ENVELOPE_COLUMNS,
        contents=contents,
        stats=run_stats,
    )

    nothing_new = False
    if args.source == "objects":
        _run_backfill(
            spark,
            config,
            args,
            run_id=run_id,
            history=history,
            dlq=dlq,
            run_stats=run_stats,
            normalize=normalize,
        )
    else:
        result = _run_ledger(
            spark, config, args, run_id=run_id, history=history, dlq=dlq, normalize=normalize
        )
        # `articles` 는 처리 이력을 통과해 정제까지 간 기사 수다. 0 이면 `curated` 가 그대로라
        # 뒤 단계가 볼 것이 없다. 정제 필터로 버려진 몫은 여기 세어져 있어서 가끔 헛걸음이
        # 생기는데, 그 반대(쓴 게 있는데 안 깨움)보다 훨씬 낫다.
        nothing_new = result.articles == 0

    # 마지막이다 — `curated` · `contents` · 처리 이력이 전부 끝난 뒤라, 쓰기가 죽은 실행의
    # 통계는 남지 않는다. 같은 run_id 의 옛 행은 지우고 다시 넣는다.
    #
    # 새로 쓴 것이 없는 회차도 적는다. 0 이 적힌 것과 아무것도 안 적힌 것은 다르다.
    stats.replace(run_stats.finalize(), ingest_run_id=run_id)

    if nothing_new:
        log.info(
            "새로 쓴 기사가 없다 — 종료 코드 %d 로 끝낸다 (뒤 단계를 깨우지 않는다)",
            NOTHING_NEW,
        )
        return NOTHING_NEW
    return None


def _run_ledger(
    spark: SparkSession,
    config: Config,
    args: argparse.Namespace,
    *,
    run_id: str,
    history: Ledger,
    dlq,
    normalize,
) -> BatchResult:
    """평시 경로 — 수집 장부의 뷰를 읽는다 (S15P21A102-247).

    **스트림이 아니다.** 창 안의 행을 한 번에 읽어 배치 하나로 돈다. 겹쳐 읽은 몫은 처리
    이력이 거르므로(`io/ledger.py` 의 중복 차단 2) 오프셋을 따로 들고 있지 않아도 된다 —
    Kafka 시절 checkpoint 가 하던 일을 이력 하나로 합쳤다. 상태가 하나면 두 상태가 어긋날
    자리도 없다.

    **계약 판별을 태운다.** 봉투를 우리가 조립했지만 그래도 `classify` 를 거친다. 도메인
    허용 목록이 거기 있기 때문이다 — 목록 밖 값이 장부에 들어오면 판별 없이는 정제 단계의
    `keywords_domain` 이 `ValueError` 를 올려 배치가 통째로 죽는다. 판별을 태우면 그 행만
    DLQ 로 가고 나머지는 처리된다 (S15P21A102-247 코드리뷰).

    백필이 판별을 건너뛰는 것과 갈리는 자리다. 그쪽 봉투는 `url`·`published_at` 이 없어
    전량이 계약 위반으로 떨어지지만, 뷰는 두 칸을 다 낸다.

    **checksum 은 요구한다.** 장부의 `article_sha256` 이 NOT NULL 이라 평시 경로에서는 늘
    있다. 없다면 장부가 깨졌다는 뜻이라 통과시킬 이유가 없다 — 메타데이터가 없는 옛 객체를
    받아 주는 모드 B 와 다른 점이다.
    """
    verify_objects = verifier(config, columns=ENVELOPE_COLUMNS)
    log.info("ingest 시작: source=%s run_id=%s force=%s", args.source, run_id, args.force)

    result: BatchResult = process_batch(
        collected.read_events(spark, config),
        job=JOB,
        ledger=history,
        dlq=dlq,
        verify_objects=verify_objects,
        normalize=normalize,
        force=args.force,
    )
    _log_totals([result])
    return result


def _run_backfill(
    spark: SparkSession,
    config: Config,
    args: argparse.Namespace,
    *,
    run_id: str,
    history: Ledger,
    dlq,
    run_stats: stats_io.RunStats,
    normalize,
) -> None:
    """모드 B — MinIO 프리픽스 스캔 ([02 §6]).

    **checkpoint 를 건드리지 않는다.** 스트림을 걸지 않으므로 오프셋이 움직이지 않고, 이
    실행이 끝난 뒤 평시 경로가 그대로 이어진다.

    **`--force` 없이도 대개 다시 처리된다.** 처리 이력 대조가 `(event_id, stage)` 인데
    171 에서 기사의 목표 단계가 `object` 에서 `normalize` 로 올라갔기 때문이다
    ([08 §3] 의 단계 승격). 이미 `normalize` 까지 적힌 구간을 다시 처리하려면 `--force` 가
    필요하다.
    """
    request = backfill.build_request(args.domain, args.date_from, args.date_to)
    store = store_io.store_config(config)
    bucket = backfill.raw_bucket(config)
    log.info(
        "백필 시작: run_id=%s bucket=%s domain=%s %s~%s force=%s",
        run_id,
        bucket,
        request.domain,
        request.date_from,
        request.date_to,
        args.force,
    )

    envelopes, listing = backfill.list_articles(store, bucket, request)
    # 목록 조회에서 이미 안 것을 [03 §7] 에 남긴다. 검증 단계까지 들고 갈 이유가 없다.
    run_stats.add(
        [
            stats_io.Stat(stats_io.BACKFILL_LISTED, stats_io.NO_DIMENSION, listing.listed),
            stats_io.Stat(
                stats_io.BACKFILL_CHECKSUM_MISSING,
                stats_io.NO_DIMENSION,
                listing.checksum_missing,
            ),
        ]
    )
    if not envelopes:
        log.warning("범위 안에 객체가 없다 — 아무것도 하지 않는다")
        return

    # 메타데이터가 없는 옛 객체는 checksum 검증을 건너뛴다 ([02 §6]). 건너뛴 건수는 위에서
    # 이미 셌다. 없는 값을 실패로 처리하면 옛 객체를 재처리에서 통째로 버린다.
    verify_objects = verifier(config, columns=ENVELOPE_COLUMNS, require_checksum=False)

    result = process_batch(
        backfill.events_frame(spark, envelopes),
        job=JOB,
        ledger=history,
        dlq=dlq,
        verify_objects=verify_objects,
        normalize=normalize,
        force=args.force,
        # 재구성한 봉투는 판별 칸이 이미 채워져 있다. 다시 `classify` 를 태우면 전부 DLQ 다.
        decided=True,
    )
    _log_totals([result])


def _log_totals(totals: list[BatchResult]) -> None:
    log.info(
        "ingest 끝: 배치 %d개 받음=%d 처리 이력에서 걸림=%d 기사=%d 요약=%d "
        "DLQ=%d 정제에서 버림=%d",
        len(totals),
        sum(r.received for r in totals),
        sum(r.duplicates for r in totals),
        sum(r.articles for r in totals),
        sum(r.summaries for r in totals),
        sum(r.rejected for r in totals),
        sum(r.filtered for r in totals),
    )


if __name__ == "__main__":
    main(JOB, run, add_arguments=add_arguments)
