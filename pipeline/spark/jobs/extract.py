#!/usr/bin/env python
"""extract — MinIO `curated` 를 읽어 키워드 후보를 뽑고 점수를 매긴다.

```sh
spark/scripts/submit.sh extract --profile local                       # 새 ingest 실행분만
spark/scripts/submit.sh extract --profile local --domain fashion \\
    --from 2026-09-01 --to 2026-09-07 --force                          # 발행일 구간 재추출
```

**하는 것** — [04] 전부. 언어별 토큰화, 후보 생성, 비교키·대표 표기, 필터(형태·길이·불용어·
노이즈·DF 비율), C-value·BM25·제목 가중 결합, 문서당 상위 K 선별, 그리고 내부 테이블 적재
(`pl_document_candidate` · `pl_candidate` · `pl_keyword_daily_stat` ·
`pl_abbreviation_observation`).

**후반은 [05] 전부** — 층 1·2 자동 병합, 검수 큐, 승격 심사, `keywords` · `keyword_contents`
적재 (`registry/`, `io/keywords.py`).

**🚫 승격만 백엔드에 막혀 있다.** `keywords (domain, normalized_name)` UNIQUE 가 없으면
([09 §7] 항목 2) `--allow-missing-keyword-unique` 로 승격을 건너뛰고 나머지를 돈다 — 병합 ·
검수 큐 · 이력은 전부 `pl_` 이라 선행 조건이 없다. 기본은 fail-closed 다
(`extract.registry.required`, base.yaml `true`).

**무엇을 처리하나** — 기본은 `curated` 에 있는데 이 Job 의 처리 이력에 없는 `ingest_run_id`
파티션 전부다 ([01 §3], `extract/source.py`). `--from/--to` 를 주면 그 발행일 구간을 통째로 다시
매기며(임계값·규칙을 바꾼 뒤의 재추출, [04 §10]) 처리 이력은 건드리지 않는다.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone

from pyspark.sql import SparkSession

from trendin.spark.common.cli import main
from trendin.spark.common.config import Config, ConfigError
from trendin.spark.common.logging import get_logger
from trendin.spark.common.run_id import default_run_id
from trendin.spark.extract import batch, morphology, source
from trendin.spark.extract import tokenize as tk
from trendin.spark.extract.document import ExtractionOptions
from trendin.spark.extract.filters import CandidateLimits
from trendin.spark.extract.lexicon import load_lexicon
from trendin.spark.extract.thresholds import DomainOptions, ExtractThresholds, lexicon_dir
from trendin.spark.io import ledger as ledger_io
from trendin.spark.io import stats as stats_io
from trendin.spark.io.candidates import CandidateSink
from trendin.spark.io.contract import DOMAIN_VALUES
from trendin.spark.io.keywords import KeywordSink, RegistrySink
from trendin.spark.io.ledger import Ledger
from trendin.spark.registry import batch as registry_batch
from trendin.spark.registry.thresholds import SECTION as REGISTRY_SECTION
from trendin.spark.registry.thresholds import RegistryThresholds

log = get_logger("extract")

JOB = "extract"
# 이 Job 의 처리 이력 단위 — ingest 실행 하나. `event_shape` 로 기사·요약 이벤트와 구분한다.
STAGE = "extract"
EVENT_SHAPE = "INGEST_RUN"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--domain",
        choices=sorted(DOMAIN_VALUES),
        default=None,
        help="처리할 도메인. 없으면 전부",
    )
    parser.add_argument(
        "--ingest-run-ids",
        dest="ingest_run_ids",
        default=None,
        help="쉼표로 나눈 ingest_run_id 목록. 없으면 처리 이력에 없는 파티션 전부 ([01 §3])",
    )
    parser.add_argument(
        "--from",
        dest="date_from",
        default=None,
        help="재추출 시작 발행일 (YYYY-MM-DD). 구간 모드에서는 처리 이력을 건드리지 않는다",
    )
    parser.add_argument(
        "--to", dest="date_to", default=None, help="재추출 끝 발행일 (YYYY-MM-DD). 포함"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="처리 이력에 있는 ingest_run_id 도 다시 처리한다",
    )
    parser.add_argument(
        "--allow-missing-keyword-unique",
        dest="allow_missing_unique",
        action="store_true",
        help=(
            "keywords (domain, normalized_name) UNIQUE 가 없어도 시작한다 — **승격만** "
            "건너뛴다 ([09 §7] 항목 2). 병합·검수 큐·이력은 그대로 돈다"
        ),
    )
    parser.add_argument(
        "--run-id",
        dest="run_id",
        default=None,
        help=(
            "이 실행의 식별자 (yyyyMMddTHHmmss, KST). 없으면 지금 시각. "
            "Airflow 는 logical date 를 넘긴다"
        ),
    )


def run(spark: SparkSession, config: Config, args: argparse.Namespace) -> None:
    """단계 호출만 한다. 로직은 `trendin.spark.extract.*` 와 `io/*` 에 둔다."""
    # 임계값이 비어 있으면 여기서 죽는다 — 세션은 떴지만 아무것도 읽기 전이다.
    # [05] 의 문턱도 함께 본다. 후반에서 죽으면 전반이 이미 적재를 끝낸 상태가 된다.
    thresholds = ExtractThresholds.from_config(config)
    registry_thresholds = RegistryThresholds.from_config(config)
    run_id = args.run_id or default_run_id()
    date_from, date_to = _parse_date(args.date_from), _parse_date(args.date_to)
    if (date_from or date_to) and args.ingest_run_ids:
        raise ConfigError("--from/--to 와 --ingest-run-ids 는 함께 쓸 수 없다")

    ledger = Ledger(config, job=JOB)
    sink = CandidateSink(config)
    registry = RegistrySink(config)
    stats = stats_io.BatchStats(config, job=JOB)
    ledger.ensure_schema()
    sink.ensure_schema()
    registry.ensure_schema()
    stats.ensure_schema()
    keywords = _keyword_sink(config, allow_missing_unique=args.allow_missing_unique)

    curated = source.read_curated(spark, config)
    domains = [args.domain] if args.domain else sorted(DOMAIN_VALUES)
    run_stats: list[stats_io.Stat] = []
    log.info("extract 시작: run_id=%s domains=%s force=%s", run_id, domains, args.force)

    for domain in domains:
        run_stats.extend(
            _run_domain(
                spark,
                config,
                domain=domain,
                curated=curated,
                thresholds=thresholds,
                ledger=ledger,
                sink=sink,
                run_id=run_id,
                explicit_run_ids=_split(args.ingest_run_ids),
                date_from=date_from,
                date_to=date_to,
                force=args.force,
            )
        )
        # [05] — 전반이 새 문서를 처리하지 않았어도 돈다. 검수 승인이 반영되는 자리가
        # 여기이고([05 §7] "다음 실행부터 적용된다"), 그것은 이번 배치의 문서와 무관하다.
        run_stats.extend(
            registry_batch.registry_batch(
                domain=domain,
                domain_enum=DOMAIN_VALUES[domain],
                thresholds=registry_thresholds,
                registry=registry,
                keywords=keywords,
                extract_run_id=run_id,
            ).stats
        )

    # 마지막이다 — 적재와 처리 이력이 끝난 뒤라, 쓰기가 죽은 실행의 통계는 남지 않는다.
    stats.replace(run_stats, ingest_run_id=run_id)
    log.info("extract 끝: run_id=%s", run_id)


def _keyword_sink(config: Config, *, allow_missing_unique: bool) -> KeywordSink | None:
    """승격을 할 수 있는지 보고, 못 하면 `None`.

    **조용히 건너뛰지 않는다.** 없는 채로 돌면 병합·검수 큐는 채워지는데 `keywords` 가
    비어, 증상이 "트렌드가 하나도 안 나온다" 로 화면에서야 나타난다 —
    `ingest.contents.required` 와 같은 이유로 기본이 fail-closed 다 ([05 §5], [09 §7] 항목 2).
    """
    sink = KeywordSink(config)
    required = bool(config.get(f"{REGISTRY_SECTION}.required", True))
    missing: list[str] = []
    if not sink.service_tables_ready():
        missing.append("keywords · keyword_contents 테이블")
    elif not sink.unique_constraint_ready():
        missing.append("keywords (domain, normalized_name) UNIQUE")
    if not missing:
        return sink
    reason = " · ".join(missing)
    if required and not allow_missing_unique:
        raise ConfigError(
            f"승격 선행 조건이 없다: {reason} ([09 §7] 항목 2). 백엔드가 적용하기 전에 "
            "돌리려면 --allow-missing-keyword-unique 를 명시한다 — 그때는 승격만 건너뛴다"
        )
    log.warning(
        "🚫 승격을 건너뛴다 — %s 가 없다 ([09 §7] 항목 2). 병합·검수 큐·이력은 그대로 "
        "돌지만 keywords 와 keyword_contents 는 비어 있다",
        reason,
    )
    return None


def _run_domain(
    spark: SparkSession,
    config: Config,
    *,
    domain: str,
    curated,
    thresholds: ExtractThresholds,
    ledger: Ledger,
    sink: CandidateSink,
    run_id: str,
    explicit_run_ids: tuple[str, ...] | None,
    date_from: date | None,
    date_to: date | None,
    force: bool,
) -> list[stats_io.Stat]:
    domain_options = DomainOptions.from_config(config, domain=domain)
    directory = lexicon_dir(config)
    options = ExtractionOptions(
        lexicon=load_lexicon(directory, domain=domain),
        ngram_max=thresholds.ngram_max,
        limits=CandidateLimits(min_chars=thresholds.min_chars, max_chars=thresholds.max_chars),
        tokenize=tk.TokenizeOptions(
            code_identifiers=domain_options.code_identifiers,
            surface_policy=domain_options.surface_policy,
            # 형태소 분석기 자체가 아니라 **설정**이다. 분석기는 executor 에서 만들어진다
            # (`extract/morphology.py` — Kiwi 는 pickle 되지 않는다).
            analyzer=morphology.AnalyzerSpec(
                user_words=morphology.load_user_words(directory, domain=domain)
            ),
        ),
    )

    by_dates = date_from is not None or date_to is not None
    run_ids: tuple[str, ...] = ()
    if by_dates:
        selection = source.Selection(domain=domain, date_from=date_from, date_to=date_to)
        log.info("[%s] 발행일 구간 재추출 %s ~ %s", domain, date_from, date_to)
    else:
        run_ids = explicit_run_ids or _new_run_ids(
            spark, curated, ledger, domain=domain, force=force
        )
        if not run_ids:
            log.info("[%s] 새 ingest 실행분이 없다 — 건너뛴다", domain)
            return []
        selection = source.Selection(domain=domain, ingest_run_ids=run_ids)
        log.info("[%s] ingest 실행분 %d개: %s", domain, len(run_ids), ", ".join(run_ids))

    targets = source.target_documents(curated, selection)
    span = source.date_span(targets)
    if span is None:
        log.warning("[%s] 대상 문서가 없다 — 파티션은 있는데 행이 없다", domain)
        if run_ids:
            ledger.record(_ledger_rows(spark, domain=domain, run_ids=run_ids, documents=0))
        return []
    corpus = source.corpus_documents(
        curated, domain=domain, span=span, window_days=thresholds.corpus_window_days
    )

    result = batch.extract_batch(
        targets=targets,
        corpus=corpus,
        domain=domain,
        thresholds=thresholds,
        options=options,
        domain_options=domain_options,
        extract_run_id=run_id,
        known_keys=sink.known_keys(spark, domain=domain),
    )
    try:
        written = sink.write(
            documents=result.documents,
            document_candidates=result.document_candidates,
            abbreviations=result.abbreviations,
        )
        log.info(
            "[%s] 문서 %d · 코퍼스 %d · 문서후보 %d · 약어 %d",
            domain,
            written.documents,
            result.corpus_size,
            written.document_candidates,
            written.abbreviations,
        )
        if run_ids:
            ledger.record(
                _ledger_rows(spark, domain=domain, run_ids=run_ids, documents=result.target_count)
            )
        return result.stats
    finally:
        result.release()


def _new_run_ids(spark, curated, ledger: Ledger, *, domain: str, force: bool) -> tuple[str, ...]:
    """`curated` 에 있는데 처리 이력에 없는 `ingest_run_id`. `--force` 면 전부."""
    present = source.ingest_run_ids(curated, domain=domain)
    if force:
        return tuple(present)
    known = {
        row["event_id"]
        for row in ledger.known_event_ids(spark).where(f"stage = '{STAGE}'").collect()
    }
    return tuple(run_id for run_id in present if _event_id(domain, run_id) not in known)


def _event_id(domain: str, ingest_run_id: str) -> str:
    return f"{domain}:{ingest_run_id}"


def _ledger_rows(spark, *, domain: str, run_ids: tuple[str, ...], documents: int):
    """처리 이력 행 — ingest 실행 하나에 하나. `record_count` 는 그 실행분에서 본 문서 수의
    합이라 실행별로 나누지 않고 같은 값을 적는다."""
    from pyspark.sql.types import (
        IntegerType,
        LongType,
        StringType,
        StructField,
        StructType,
        TimestampType,
    )

    now = datetime.now(timezone.utc)
    schema = StructType(
        [
            StructField("event_id", StringType()),
            StructField("job", StringType()),
            StructField("stage", StringType()),
            StructField("event_shape", StringType()),
            StructField("status", StringType()),
            StructField("error_type", StringType()),
            StructField("detail", StringType()),
            StructField("domain", StringType()),
            StructField("source_id", StringType()),
            StructField("run_id", StringType()),
            StructField("article_id", StringType()),
            StructField("record_count", LongType()),
            StructField("collected_at", TimestampType()),
            StructField("topic_partition", IntegerType()),
            StructField("topic_offset", LongType()),
            StructField("processed_at", TimestampType()),
        ]
    )
    rows = [
        (
            _event_id(domain, run_id),
            JOB,
            STAGE,
            EVENT_SHAPE,
            "COMPLETED",
            None,
            None,
            domain,
            None,
            run_id,
            None,
            int(documents),
            None,
            None,
            None,
            now,
        )
        for run_id in run_ids
    ]
    return spark.createDataFrame(rows, schema).select(*ledger_io.COLUMNS)


def _split(value: str | None) -> tuple[str, ...] | None:
    if not value:
        return None
    items = tuple(item.strip() for item in value.split(",") if item.strip())
    return items or None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ConfigError(f"날짜는 YYYY-MM-DD 여야 한다: {value!r}") from error


if __name__ == "__main__":
    main(JOB, run, add_arguments=add_arguments)
