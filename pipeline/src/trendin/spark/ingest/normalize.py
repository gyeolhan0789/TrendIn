"""정제·적재 단계. 객체 검증을 통과한 기사만 탄다.

규격은 [03](../../../../spark/docs/03-normalization-spec.md) 이다.

`ingest` Job 의 후반부다. 순서만 여기서 정하고 로직은 `normalize/*` 와 `io/*` 가 들고 있다 —
`ingest/batch.py` 가 마이크로배치의 순서를 정하는 것과 같은 역할 분담이다.

```
1. 표준 문서로 접는다        normalize/documents.py (순수 함수, UDF)
2. 중복 제거 1·2·3           normalize/dedup.py
3. 통계                      io/stats.py — 버리기 **전에** 세어 실행 끝까지 누적한다
4. curated Parquet 쓰기      normalize/curated.py
5. body_object_key 회수      쓴 파일을 되읽어 얻는다 ([01 §3])
6. contents upsert           io/contents.py — id 를 pl_content_id_map 으로 회수
```

**3 이 4 보다 먼저인 이유** — 통계의 분모가 입력 건수다. 버린 뒤에 세면 생존율을 계산할 수
없다 ([03 §7]). 다만 **DB 에 쓰는 것은 실행 끝에 한 번**이다(`io/stats.RunStats`) — 배치마다
쓰면 같은 `ingest_run_id` 의 뒤 배치가 앞 배치를 덮고, 쓰기가 죽은 실행의 통계가 남는다.

**4 는 실행 안 첫 배치만 `overwrite` 다.** 뒤 배치는 `append` — 안 그러면 같은 파티션에 쓴 앞
배치의 문서가 사라진다 (`normalize/curated.write`).

**4 가 6 보다 먼저인 이유** — `contents.body_object_key` 가 4 에서 쓴 파일을 가리킨다.
뒤집으면 아직 없는 파일의 키를 넣게 된다.

**5 를 위해 되읽는 것이 낭비가 아닌 이유는 `normalize/curated.body_object_keys` 에 있다.**
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from trendin.spark.common.config import Config
from trendin.spark.common.logging import get_logger
from trendin.spark.io import contents as contents_io
from trendin.spark.io import stats as stats_io
from trendin.spark.normalize import curated
from trendin.spark.normalize.dedup import DedupThresholds, apply_dedup
from trendin.spark.normalize.documents import build_document
from trendin.spark.normalize.filters import FilterThresholds, exclusion_reason
from trendin.spark.normalize.lang import LangThresholds
from trendin.spark.normalize.schema import DOCUMENT_COLUMNS, DOCUMENT_SCHEMA
from trendin.spark.normalize.simhash import to_signed64

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

log = get_logger(__name__)

# 정제 결과가 담기는 칸. 비어 있으면 살아남았다는 뜻이다.
FILTER_REASON = "filter_reason"
# UDF 안에서만 쓰는 칸. 중복 판정(`dup_reason`)과 합쳐 `filter_reason` 이 된다.
QUALITY_REASON = "quality_reason"


@dataclass(frozen=True, slots=True)
class NormalizeThresholds:
    """[03] 의 문턱 전부. `conf/*.yaml` 의 `ingest.normalize` 에서 온다.

    **전부 잠정이다** ([09 §7] 항목 5) — [S6] 이 실데이터 분포를 재고 확정하며 그때
    `pl_config_history` 에 초기값이 기록된다. 한 곳에 모아 둔 이유는 그 재확정이 파일 하나를
    고치는 일이어야 하기 때문이다.
    """

    lang: LangThresholds
    filters: FilterThresholds
    dedup: DedupThresholds

    @classmethod
    def from_config(cls, config: Config) -> "NormalizeThresholds":
        return cls(
            lang=LangThresholds.from_section(config.section("ingest.normalize.lang")),
            filters=FilterThresholds.from_section(config.section("ingest.normalize.filters")),
            dedup=DedupThresholds.from_section(config.section("ingest.normalize.dedup")),
        )


@dataclass(frozen=True, slots=True)
class NormalizeResult:
    """정제 결과 요약. 로그와 테스트가 읽는다. 권위 있는 기록은 `pl_batch_stat` 이다."""

    received: int = 0
    kept: int = 0
    near_duplicates: int = 0
    contents_written: bool = False

    @property
    def excluded(self) -> int:
        return self.received - self.kept


def normalized_schema():
    """문서 칸 + `quality_reason`.

    품질 판정을 문서 생성과 **같은 UDF** 에서 하는 이유는 둘 다 행 하나에 대한 순수 함수라
    나눌 이유가 없고, 나누면 파이썬 왕복이 두 배가 되기 때문이다 (`ingest/batch._decision_udf`
    와 같은 판단). 중복 판정은 배치 전체를 봐야 하므로 여기 들어올 수 없다.
    """
    from pyspark.sql.types import StringType, StructField, StructType

    # **`DOCUMENT_SCHEMA.add()` 를 쓰지 않는다.** 그 메서드는 새 스키마를 만들지 않고
    # 받은 스키마를 **제자리에서 고친다.** 모듈 수준 싱글턴을 고치는 것이므로, 이 함수를 두
    # 번 부르면 `quality_reason` 이 두 번 붙고 그 뒤 `select` 가
    # `[AMBIGUOUS_REFERENCE_TO_FIELDS]` 로 죽는다. 배치 하나만 처리하는 실행에서는 드러나지
    # 않아 테스트에서 먼저 잡혔다.
    return StructType([*DOCUMENT_SCHEMA.fields, StructField(QUALITY_REASON, StringType(), True)])


def _document_udf(ingest_run_id: str, thresholds: NormalizeThresholds):
    """`article_json` 텍스트 하나 → 표준 문서 한 행 + 품질 판정.

    `article_json` 이 `None` 인 행은 여기 오지 않는다 — 부른 쪽이 객체 검증을 통과한 기사만
    보낸다. 그래도 방어하는 이유는 이 UDF 가 배치 하나를 통째로 죽일 수 있는 자리이고,
    `None` 하나 때문에 수백 건이 사라지는 것을 막는 값이 방어 세 줄보다 크기 때문이다.
    """
    from pyspark.sql import functions as F

    def _apply(article_json: str | None, envelope) -> Any:
        if not article_json:
            return None
        try:
            article = json.loads(article_json)
        except (TypeError, ValueError):
            # 객체 검증이 이미 파싱했으므로 여기 올 수 없다. 오면 그건 우리 배선이 깨진 것이고
            # 조용히 넘기면 그 문서가 이유 없이 사라진다.
            log.warning("정제 단계에서 article.json 을 다시 파싱하지 못했다")
            return None
        if not isinstance(article, dict):
            return None

        document = build_document(
            article,
            envelope.asDict() if envelope is not None else {},
            ingest_run_id=ingest_run_id,
            lang_thresholds=thresholds.lang,
        )
        row = document.as_row()
        # 부호 없는 64비트 지문은 `bigint` 에 그대로 안 들어간다 (`simhash.to_signed64`).
        row["simhash"] = to_signed64(document.simhash)
        row[QUALITY_REASON] = exclusion_reason(document, thresholds.filters) or None
        return row

    return F.udf(_apply, normalized_schema())


def build_documents(
    articles: "DataFrame",
    *,
    ingest_run_id: str,
    thresholds: NormalizeThresholds,
    envelope_columns: tuple[str, ...],
) -> "DataFrame":
    """`event_id` + 표준 문서 칸. 정제와 품질 판정이 끝난 상태다.

    봉투를 함께 넘기는 이유는 `collected_at` 이다 — [03 §8] 이 `contents.collected_at` 을
    **이벤트의** 값으로 못 박았다. 나머지 값은 `article.json` 에서 온다.
    """
    from pyspark.sql import functions as F

    from trendin.spark.ingest.objects import ARTICLE_JSON

    envelope = F.struct(*[F.col(name) for name in envelope_columns])
    udf = _document_udf(ingest_run_id, thresholds)
    built = articles.withColumn("_doc", udf(F.col(ARTICLE_JSON), envelope))
    return built.select(
        F.col("event_id"),
        *[F.col(f"_doc.{name}").alias(name) for name in DOCUMENT_COLUMNS],
        F.col(f"_doc.{QUALITY_REASON}").alias(QUALITY_REASON),
        # 정제가 통째로 실패한 행. 위 UDF 가 `None` 을 낸 경우다.
        F.col("_doc").isNull().alias("_unbuilt"),
    )


def resolve_filter_reason(documents: "DataFrame") -> "DataFrame":
    """`dup_reason` 과 `quality_reason` 을 하나의 칸으로 합친다.

    **중복이 품질보다 앞선다.** 같은 문서가 중복이면서 짧을 때 [03 §7] 집계에 중복으로
    세는 편이 진단에 쓸모 있다 — 중복은 상류(수집·재처리)의 신호이고 품질은 소스의 신호다.

    `url_hash` 가 없는 행은 `dup_reason` 이 애초에 `null` 이므로(`dedup.mark_exact_duplicates`)
    품질 사유 `NO_URL` 이 남는다. 그 경계가 두 모듈에 한 번씩 적혀 있다.
    """
    from pyspark.sql import functions as F

    return documents.withColumn(
        FILTER_REASON,
        F.coalesce(
            F.col("dup_reason"),
            F.col(QUALITY_REASON),
            # 정제 자체가 실패한 행은 살릴 수 없다. 사유를 남겨 [03 §7] 에서 보이게 한다.
            F.when(F.col("_unbuilt"), F.lit("UNBUILT")),
            F.lit(""),
        ),
    )


class NormalizeStage:
    """정제·적재 한 번. `ingest/batch.process_batch` 가 주입받아 부른다.

    클래스인 이유는 싱크 셋(`curated` · `contents` · `pl_batch_stat`)을 함께 들고 있어야
    하고, 결과 요약을 부른 쪽이 읽어야 하기 때문이다. 검증 단계(`ingest/objects.verifier`)가
    함수를 돌려주는 것과 달라지는 지점이 이것이다 — 그쪽은 부수 효과가 없다.
    """

    def __init__(
        self,
        config: Config,
        *,
        ingest_run_id: str,
        envelope_columns: tuple[str, ...],
        contents: contents_io.ContentsSink | None,
        stats: stats_io.RunStats | None,
    ) -> None:
        self._config = config
        self._run_id = ingest_run_id
        self._envelope_columns = envelope_columns
        self._contents = contents
        self._stats = stats
        self._thresholds = NormalizeThresholds.from_config(config)
        # 이 실행에서 `curated` 에 이미 썼는가. 첫 쓰기만 overwrite, 그 뒤는 append 다.
        self._wrote_curated = False
        self.last_result = NormalizeResult()

    def __call__(self, articles: "DataFrame") -> "DataFrame":
        """정제하고 적재한다. `(event_id, filter_reason)` 이 붙은 원본 프레임을 돌려준다.

        **원본 프레임의 칸을 바꾸지 않는다.** 부른 쪽이 이 결과를 요약 이벤트·거절된 이벤트와
        `unionByName` 으로 합치므로, 칸이 하나라도 달라지면 그 자리에서 죽는다.

        **판정은 드라이버로 모아 작은 프레임으로 되돌린다.** `documents` 를 lazy 하게 조인해
        돌려주면 부른 쪽의 다음 action 이 정제 UDF 를 **다시** 돌린다 — `curated` 에 쓴 문서와
        처리 이력에 적히는 판정이 서로 다른 계산에서 나오는 셈이고, 그 사이 객체가 바뀌면
        둘이 갈린다. 배치당 수백 행이라 `collect()` 가 감당된다.
        """
        documents = resolve_filter_reason(
            apply_dedup(
                build_documents(
                    articles,
                    ingest_run_id=self._run_id,
                    thresholds=self._thresholds,
                    envelope_columns=self._envelope_columns,
                ),
                self._thresholds.dedup,
            )
        ).cache()
        try:
            self.last_result = self._persist(documents)
            # 사유만 원본에 붙인다. 문서 칸을 붙이면 봉투 프레임의 스키마가 바뀐다.
            verdicts = [
                (row["event_id"], row[FILTER_REASON])
                for row in documents.select("event_id", FILTER_REASON).collect()
            ]
        finally:
            documents.unpersist()
        judged = articles.sparkSession.createDataFrame(
            verdicts, schema=f"event_id string, {FILTER_REASON} string"
        )
        return articles.join(judged, on="event_id", how="left")

    def _persist(self, documents: "DataFrame") -> NormalizeResult:
        from pyspark.sql import functions as F

        # 3 — 버리기 **전에** 센다 ([03 §7]). DB 에는 실행 끝에 한 번 쓴다 (`RunStats`).
        if self._stats is not None:
            self._stats.add_batch(documents)

        survivors = documents.where(F.col(FILTER_REASON) == "").cache()
        try:
            received = documents.count()
            kept = survivors.count()
            near = survivors.where(F.col("dup_of").isNotNull()).count()
            if not kept:
                log.info("정제 결과가 비었다 — curated·contents 를 건드리지 않는다")
                return NormalizeResult(received=received, kept=0, near_duplicates=near)

            # 4 — curated Parquet. 이 실행의 첫 배치만 overwrite, 그 뒤는 append.
            curated.write(
                survivors, self._config, mode="append" if self._wrote_curated else "overwrite"
            )
            self._wrote_curated = True

            # 5·6 — 쓴 파일의 키를 회수해 `contents` 로.
            written = False
            if self._contents is not None:
                keys = curated.body_object_keys(survivors.sparkSession, self._config, survivors)
                rows = contents_io.contents_rows(survivors.join(keys, on="url_hash", how="left"))
                self._contents.upsert(rows)
                written = True

            return NormalizeResult(
                received=received, kept=kept, near_duplicates=near, contents_written=written
            )
        finally:
            survivors.unpersist()


def normalizer(
    config: Config,
    *,
    ingest_run_id: str,
    envelope_columns: tuple[str, ...],
    contents: contents_io.ContentsSink | None,
    stats: stats_io.RunStats | None,
) -> Callable[["DataFrame"], "DataFrame"]:
    """설정에서 정제 단계를 만든다. `process_batch` 에 주입한다.

    `ingest/objects.verifier` 와 같은 형태를 유지하는 이유는 층 2 테스트가 가짜를 끼워
    넣어 MinIO·PostgreSQL 없이 배선을 검사하기 때문이다 ([09 §4]).
    """
    return NormalizeStage(
        config,
        ingest_run_id=ingest_run_id,
        envelope_columns=envelope_columns,
        contents=contents,
        stats=stats,
    )
