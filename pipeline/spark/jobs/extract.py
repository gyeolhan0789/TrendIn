#!/usr/bin/env python
"""extract — MinIO `curated` 를 읽어 키워드 후보를 뽑고 점수를 매긴다.

```sh
spark/scripts/submit.sh extract --profile local                       # 새 ingest 실행분만
spark/scripts/submit.sh extract --profile local --domain fashion \\
    --from 2026-09-01 --to 2026-09-07 --force                          # 발행일 구간 재추출
spark/scripts/submit.sh extract --profile local --domain fashion \
    --force --skip-promotion                                           # 분포만 뜨고 승격 안 함
```

**하는 것** — [04] 전부. 실체 인식(GLiNER), 언어별 후처리, 비교키·대표 표기, 필터(형태·
길이·라벨), 문서당 상위 K 선별, 그리고 내부 테이블 적재 (`pl_document_candidate` ·
`pl_candidate` · `pl_keyword_daily_stat` · `pl_abbreviation_observation`).

⚠️ **2026-09-16 에 후보 생성이 문자열 통계에서 실체 인식으로 옮겨졌다** (`extract/entities.py`).
같은 표본·같은 정답에서 옛 경로가 F1 0.233, 실체 인식이 0.504 였다. 코퍼스를 따로 읽지
않게 되어 처리 시간이 대상 문서 수에만 비례한다 — 대신 추론이 문서당 약 1초다.

**후반은 [05] 전부** — 층 1·2 자동 병합, 검수 큐, 승격 심사, `keywords` · `keyword_contents`
적재 (`registry/`, `io/keywords.py`).

**🚫 승격만 백엔드에 막혀 있다.** `keywords (domain, normalized_name)` UNIQUE 가 없으면
([09 §7] 항목 2) `--allow-missing-keyword-unique` 로 승격을 건너뛰고 나머지를 돈다 — 병합 ·
검수 큐 · 이력은 전부 `pl_` 이라 선행 조건이 없다. 기본은 fail-closed 다
(`extract.registry.required`, base.yaml `true`).

**승격을 일부러 끄는 것은 `--skip-promotion` 이다.** 위가 "할 수 없는데 돌았다" 를 막는다면
이쪽은 **"보려고만 했는데 올라가 버렸다" 를 막는다.** 승격 문턱은 후보 분포를 본 뒤라야
정할 수 있는데([10 §4] S6) 승격은 되돌릴 수 없으므로([05 §1]), 분포를 뜨는 실행과 실제로
올리는 실행이 갈려 있어야 한다. 심사는 그대로 돌아 보류 사유가 `pl_batch_stat` 에 남는다
(`held` · `held_by_condition`).

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
from trendin.spark.extract import batch, source
from trendin.spark.extract.document import ExtractionOptions
from trendin.spark.extract.filters import CandidateLimits
from trendin.spark.extract.thresholds import (
    ExtractThresholds,
    adapter_spec,
    lexicon_dir,
    recognizer_spec,
)
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
# 상류 Job 의 이력 이름. `jobs/ingest.JOB` 과 같아야 하는데 그 모듈을 import 하면 ingest 의
# 의존(boto3 등)이 딸려 오므로 값을 적는다.
INGEST_JOB = "ingest"


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
        "--skip-promotion",
        dest="skip_promotion",
        action="store_true",
        help=(
            "승격만 하지 않고 나머지를 전부 돈다 — 심사·병합·검수 큐·이력은 그대로다. "
            "후보 분포와 보류 사유를 보려고 돌릴 때 쓴다 ([10 §4] S6)"
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
    keywords = _keyword_sink(
        config,
        allow_missing_unique=args.allow_missing_unique,
        skip_promotion=args.skip_promotion,
    )

    curated = source.read_curated(spark, config)
    ingested = _ingested_run_ids(spark, config)
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
                ingested=ingested,
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


def _keyword_sink(
    config: Config, *, allow_missing_unique: bool, skip_promotion: bool
) -> KeywordSink | None:
    """승격을 할 수 있는지, 하려는지 보고, 아니면 `None`.

    **조용히 건너뛰지 않는다.** 없는 채로 돌면 병합·검수 큐는 채워지는데 `keywords` 가
    비어, 증상이 "트렌드가 하나도 안 나온다" 로 화면에서야 나타난다 —
    `ingest.contents.required` 와 같은 이유로 기본이 fail-closed 다 ([05 §5], [09 §7] 항목 2).

    **`--skip-promotion` 은 그 fail-closed 와 반대 방향이다.** 저쪽은 "할 수 없는데 돌았다"
    를 막고, 이쪽은 "보려고만 했는데 올라가 버렸다" 를 막는다. 승격은 되돌릴 수 없으므로
    ([05 §1]) 문턱을 정하려고 분포를 뜨는 실행에는 끌 수단이 있어야 한다 — 없어서 2026-09-17
    실체 인식 교체 실측이 `keywords` 1,166건과 함께 나왔다.
    """
    if skip_promotion:
        # 선행 조건은 보지 않는다. 있든 없든 이 회차는 어차피 `keywords` 를 건드리지 않고,
        # 여기서 죽으면 분포를 뜨려던 실행이 백엔드 상태에 묶인다.
        log.warning(
            "🚫 --skip-promotion — 승격하지 않는다. 심사·병합·검수 큐·이력은 그대로 돌고 "
            "keywords 와 keyword_contents 만 건드리지 않는다. 보류 사유 분포는 "
            "pl_batch_stat 의 held · held_by_condition 에 남는다"
        )
        return None
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
    ingested: frozenset[str],
    explicit_run_ids: tuple[str, ...] | None,
    date_from: date | None,
    date_to: date | None,
    force: bool,
) -> list[stats_io.Stat]:
    directory = lexicon_dir(config)
    # 인식기와 분석기 자체가 아니라 **설정**이다. 둘 다 executor 에서 만들어진다
    # (`extract/entities.py` · `extract/morphology.py` — 모델과 Kiwi 는 pickle 되지 않는다).
    recognizer = recognizer_spec(config, domain=domain)
    options = ExtractionOptions(
        adapter=adapter_spec(config, domain=domain, directory=directory),
        limits=CandidateLimits(min_chars=thresholds.min_chars, max_chars=thresholds.max_chars),
    )
    log.info(
        "[%s] 인식기 %s · 라벨 %d개 · 문턱 %.2f",
        domain,
        recognizer.model,
        len(recognizer.labels),
        recognizer.threshold,
    )

    by_dates = date_from is not None or date_to is not None
    run_ids: tuple[str, ...] = ()
    if by_dates:
        # 구간 재추출도 고아 파티션은 안 본다 — `latest_per_document` 가 실행 번호가 큰 쪽을
        # 남기므로, 이력에 없는 실행이 정상 실행의 문서를 가릴 수 있다.
        selection = source.Selection(
            domain=domain, date_from=date_from, date_to=date_to, known_run_ids=ingested
        )
        log.info("[%s] 발행일 구간 재추출 %s ~ %s", domain, date_from, date_to)
    else:
        run_ids = explicit_run_ids or _new_run_ids(
            spark, curated, ledger, domain=domain, force=force, ingested=ingested
        )
        if not run_ids:
            log.info("[%s] 새 ingest 실행분이 없다 — 건너뛴다", domain)
            return []
        selection = source.Selection(domain=domain, ingest_run_ids=run_ids)
        log.info("[%s] ingest 실행분 %d개: %s", domain, len(run_ids), ", ".join(run_ids))

    targets = source.target_documents(curated, selection).cache()
    if targets.isEmpty():
        log.warning("[%s] 대상 문서가 없다 — 파티션은 있는데 행이 없다", domain)
        targets.unpersist()
        if run_ids:
            ledger.record(_ledger_rows(spark, domain=domain, run_ids=run_ids, documents=0))
        return []

    # **코퍼스를 따로 읽지 않는다** (2026-09-16). 점수를 모델이 주므로 DF·BM25 가 선별에
    # 관여하지 않고, 최근 N 일 문서에 추론을 다시 돌릴 이유가 없다 (`extract/batch.py`).
    result = batch.extract_batch(
        targets=targets,
        domain=domain,
        thresholds=thresholds,
        recognizer=recognizer,
        options=options,
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
            "[%s] 문서 %d · 문서후보 %d · 약어 %d",
            domain,
            written.documents,
            written.document_candidates,
            written.abbreviations,
        )
        # **대상이 있는데 후보가 하나도 없으면 실패다.**
        #
        # 추론이 통째로 죽어도 이 Job 은 0 으로 끝날 수 있다 — `entities._predict_chunk` 가
        # 배치 예외를 삼켜 빈 결과를 주고(문서 하나의 인코딩 문제로 하루치를 잃지 않으려는
        # 장치다), 그러면 모든 문서가 후보 0 이 되어 적재만 비고 흐름은 정상으로 끝난다.
        # 실제로 `SparkContext was shut down` 이 난 실행이 종료 코드 0 으로 끝났다
        # (2026-09-17). Airflow 는 그것을 성공으로 받아 `aggregate` 를 이어 돌리고, 증상은
        # 며칠 뒤 "화면이 비었다" 로만 나타난다.
        #
        # 대상 문서가 전부 후보 0 인 것은 정상 운영에서 관측되지 않는다 — 후보가 하나도 없는
        # 문서는 1.4% 였다 (`tests/fixtures/review/extract-gliner-2026-09-17.md` §3).
        if result.target_count and not written.document_candidates:
            raise RuntimeError(
                f"[{domain}] 대상 {result.target_count}건인데 후보가 0건이다 — 추론이 통째로"
                " 실패했을 가능성이 크다. 구간을 좁혀(`--from`/`--to`) 다시 돌리고"
                " executor 로그에서 `SparkContext was shut down` 을 확인한다"
            )
        if run_ids:
            ledger.record(
                _ledger_rows(spark, domain=domain, run_ids=run_ids, documents=result.target_count)
            )
        return result.stats
    finally:
        result.release()
        targets.unpersist()


def _ingested_run_ids(spark, config: Config) -> frozenset[str]:
    """`ingest` 가 끝까지 기록한 실행 번호 (S15P21A102-341).

    `curated` 에 파티션은 있는데 여기 없는 실행은 **적재 도중 죽은 회차의 고아**다 — 본문은
    썼지만 `contents`·처리 이력이 커밋되지 않았다. 2026-09-18 에 그런 회차 39개가 코퍼스
    전체를 한 벌씩 들고 쌓여, 이 Job 이 그것을 전부 새 실행으로 보고 죽었다. 지금은
    `ingest` 가 실패 회차의 파티션을 지우지만(`ingest/normalize.NormalizeStage.rollback`),
    프로세스가 통째로 죽으면 그 보상도 못 하므로 여기서 한 번 더 거른다.

    비어 있으면 **경고하고 아무 실행도 집지 않는다.** 2026-09-20 이전 이력은 `run_id` 가
    NULL 이라, 이 코드를 배포한 DB 에는 `spark/sql/backfill-ledger-run-id.sql` 을 한 번
    돌려야 한다. 조용히 옛 동작으로 돌아가면 그 고아를 다시 집는다.
    """
    ingested = frozenset(Ledger(config, job=INGEST_JOB).run_ids(spark))
    if not ingested:
        log.error(
            "ingest 처리 이력에 run_id 가 하나도 없다 — curated 의 어떤 실행도 대상이 되지 않는다. "
            "옛 이력이라면 spark/sql/backfill-ledger-run-id.sql 을 먼저 돌린다"
        )
    return ingested


def _new_run_ids(
    spark,
    curated,
    ledger: Ledger,
    *,
    domain: str,
    force: bool,
    ingested: frozenset[str],
) -> tuple[str, ...]:
    """`curated` 에 있는데 처리 이력에 없는 `ingest_run_id`. `--force` 면 전부.

    **`ingest` 이력에 없는 실행은 어느 쪽에서도 뺀다** — `--force` 도 고아를 집을 이유는
    없다. 뺀 실행은 경고로 남겨, 파티션은 있는데 안 도는 상황이 조용히 지나가지 않게 한다.
    """
    present = source.ingest_run_ids(curated, domain=domain)
    orphans = [run_id for run_id in present if run_id not in ingested]
    if orphans:
        log.warning(
            "[%s] ingest 이력에 없는 curated 실행 %d개를 건너뛴다 (적재 도중 죽은 회차의 고아): %s",
            domain,
            len(orphans),
            ", ".join(orphans[:10]) + (" …" if len(orphans) > 10 else ""),
        )
    present = [run_id for run_id in present if run_id in ingested]
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
