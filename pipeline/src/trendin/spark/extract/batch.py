"""Spark 배선 — 코퍼스를 봐야 하는 단계만 여기 있다 ([04 §1] 의 뒷부분).

```
1. UDF                     문서마다 extract/document.extract_document (층 1 로직, 감싸기만)
2. 코퍼스 통계             비교키별 DF · 빈도 · 대표 표기 · 포함 관계의 부모 빈도
3. DF 필터                  비율 → 문서 수 (extract/filters.df_bounds)
4. 스코어링                 C-value(코퍼스) · BM25(문서×후보) · 위치 → 문서 안 0~1 정규화 → 가중합
5. 선별                     문서당 순위 → 상위 K 이고 하한 이상 = selected
6. 프레임                   pl_document_candidate · 처리 문서 · 약어 관측 · [04 §9] 통계
```

**대상과 코퍼스가 다르다** (`extract/source.py`). 통계는 코퍼스 전체에서, 점수와 적재는 대상
문서에서만. 그래서 UDF 는 코퍼스 전체에 돌고 — 대상만 돌리면 DF 가 "이번 배치 안의 문서 빈도" 가
되어 배치 크기에 따라 결과가 흔들린다.

**수식은 `extract/scoring.py` 한 곳이다.** 여기서는 그 함수를 UDF 로 감싸 컬럼에 적용한다. Spark
컬럼식으로 다시 쓰면 빠르지만 정의가 두 곳이 되고, [00 §3] 규모(문서 × 후보 수만 행)에서 파이썬
UDF 의 비용은 배치 시작 비용에 묻힌다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from trendin.spark.common.logging import get_logger
from trendin.spark.extract import filters, scoring
from trendin.spark.extract import tokenize as tk
from trendin.spark.extract.document import ExtractionOptions, extract_document
from trendin.spark.extract.thresholds import DomainOptions, ExtractThresholds
from trendin.spark.io import candidates as candidates_io
from trendin.spark.io.stats import Stat

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

log = get_logger(__name__)

# --- [04 §9] 분포 모니터링 지표. 값이 곧 집계 키다 — 바꾸면 옛 실행과 이어지지 않는다. ---------
DOCUMENTS = "documents"
CORPUS_SIZE = "corpus_size"
CANDIDATES = "candidates"  # 필터를 전부 통과한 문서×후보 행
CANDIDATES_PER_DOC_AVG = "candidates_per_doc_avg"
SELECTED_PER_DOC_AVG = "selected_per_doc_avg"
DOCUMENTS_WITHOUT_CANDIDATES = "documents_without_candidates"
DROPPED = "dropped"  # 차원: {domain}/{사유}. 문서 안 필터 + DF 필터
DF_DROP_RATIO = "df_drop_ratio"  # DF 하한·상한에 걸린 비교키 비율
NEW_CANDIDATE_RATE = "new_candidate_rate"  # 이번에 처음 관측된 비교키 비율
CANDIDATE_NTOKENS = "candidate_ntokens"  # 차원: {domain}/{토큰 수}. 후보 길이 분포


def extraction_schema():
    """UDF 반환 스키마. `document.DocumentExtraction.as_row` 와 한 쌍이다 — 칸 이름이 어긋나면
    Spark 는 오류 대신 `null` 을 채운다."""
    from pyspark.sql.types import (
        ArrayType,
        BooleanType,
        IntegerType,
        MapType,
        StringType,
        StructField,
        StructType,
    )

    candidate = StructType(
        [
            StructField("key", StringType()),
            StructField("surface", StringType()),
            StructField("kind", StringType()),
            StructField("ntokens", IntegerType()),
            StructField("tf", IntegerType()),
            StructField("tf_title", IntegerType()),
            StructField("parents", ArrayType(StringType())),
            StructField("is_proper", BooleanType()),
        ]
    )
    abbreviation = StructType(
        [
            StructField("abbreviation", StringType()),
            StructField("expansion", StringType()),
            StructField("abbreviation_key", StringType()),
            StructField("expansion_key", StringType()),
            StructField("initials_match", BooleanType()),
        ]
    )
    return StructType(
        [
            StructField("candidates", ArrayType(candidate)),
            StructField("abbreviations", ArrayType(abbreviation)),
            StructField("doc_len", IntegerType()),
            StructField("dropped", MapType(StringType(), IntegerType())),
        ]
    )


def extraction_udf(options: ExtractionOptions):
    """`(title, body, lang)` → 후보 묶음. 옵션(사전 포함)은 클로저로 executor 에 간다 — 작다."""
    from pyspark.sql import functions as F

    def _apply(title: str | None, body: str | None, lang: str | None) -> dict[str, Any]:
        return extract_document(title, body, lang, options=options).as_row()

    return F.udf(_apply, extraction_schema())


@dataclass
class ExtractResult:
    """배치 하나의 산출물. 프레임은 lazy 라 `release()` 전에 써야 한다."""

    document_candidates: "DataFrame"
    documents: "DataFrame"
    abbreviations: "DataFrame"
    stats: list[Stat]
    corpus_size: int
    target_count: int
    _cached: tuple = ()

    def release(self) -> None:
        for frame in self._cached:
            frame.unpersist()


def extract_batch(
    *,
    targets: "DataFrame",
    corpus: "DataFrame",
    domain: str,
    thresholds: ExtractThresholds,
    options: ExtractionOptions,
    domain_options: DomainOptions,
    extract_run_id: str,
    known_keys: "DataFrame | None" = None,
) -> ExtractResult:
    """대상 문서의 후보를 코퍼스 통계로 점수 매긴다. `targets ⊆ corpus` 를 전제한다."""
    from pyspark.sql import Window
    from pyspark.sql import functions as F
    from pyspark.sql.types import DoubleType

    udf = extraction_udf(options)
    extracted = corpus.withColumn("_x", udf(F.col("title"), F.col("body"), F.col("lang"))).cache()
    corpus_size = extracted.count()
    avg_doc_len = float(extracted.agg(F.avg(F.col("_x.doc_len"))).collect()[0][0] or 0.0)
    log.info("코퍼스 %d건, 평균 길이 %.1f 토큰", corpus_size, avg_doc_len)

    # 1 — 문서 × 후보 출현 (코퍼스 전체).
    occurrences = (
        extracted.select(
            "url_hash",
            F.col("_x.doc_len").alias("doc_len"),
            F.explode("_x.candidates").alias("c"),
        )
        .select(
            "url_hash",
            "doc_len",
            F.col("c.key").alias("normalized_key"),
            F.col("c.surface").alias("doc_surface"),
            F.col("c.kind").alias("doc_kind"),
            F.col("c.ntokens").alias("ntokens"),
            F.col("c.tf").alias("tf"),
            F.col("c.tf_title").alias("tf_title"),
            F.col("c.parents").alias("parents"),
            F.col("c.is_proper").alias("is_proper"),
        )
        .cache()
    )

    # 2 — 비교키별 코퍼스 통계.
    bounds = filters.df_bounds(
        corpus_size, min_ratio=thresholds.df_min_ratio, max_ratio=thresholds.df_max_ratio
    )
    key_stats = (
        occurrences.groupBy("normalized_key")
        .agg(
            F.countDistinct("url_hash").alias("df"),
            F.sum("tf").alias("freq"),
            F.min("ntokens").alias("ntokens"),
        )
        .withColumn(
            "df_reason",
            F.when(F.col("df") < F.lit(bounds.low), F.lit(filters.DF_LOW)).when(
                F.col("df") > F.lit(bounds.high), F.lit(filters.DF_HIGH)
            ),
        )
    )
    kept_keys = key_stats.where(F.col("df_reason").isNull())

    # 대표 표기 — 코퍼스에서 가장 빈번한 원표기 ([04 §4]). 동률은 사전순으로 결정적이게.
    surface_order = Window.partitionBy("normalized_key").orderBy(
        F.col("n").desc(), F.col("doc_surface").asc(), F.col("doc_kind").asc()
    )
    representatives = (
        occurrences.groupBy("normalized_key", "doc_surface", "doc_kind")
        .agg(F.sum("tf").alias("n"))
        .withColumn("_r", F.row_number().over(surface_order))
        .where(F.col("_r") == 1)
        .select(
            "normalized_key", F.col("doc_surface").alias("surface"), F.col("doc_kind").alias("kind")
        )
    )

    # C-value 의 T_a — 살아남은 부모의 코퍼스 빈도 평균 ([04 §6]).
    edges = occurrences.select("normalized_key", F.explode("parents").alias("parent")).distinct()
    nested = (
        edges.join(
            kept_keys.select(
                F.col("normalized_key").alias("parent"), F.col("freq").alias("parent_freq")
            ),
            on="parent",
        )
        .groupBy("normalized_key")
        .agg(F.avg("parent_freq").alias("nested_freq"))
    )

    c_value_udf = F.udf(
        lambda ntokens, freq, nested_freq: float(
            scoring.c_value(
                int(ntokens), float(freq), [] if nested_freq is None else [float(nested_freq)]
            )
        ),
        DoubleType(),
    )
    idf_udf = F.udf(lambda df: float(scoring.bm25_idf(int(df), corpus_size)), DoubleType())
    scored_keys = (
        kept_keys.join(nested, on="normalized_key", how="left")
        .join(representatives, on="normalized_key")
        .withColumn("c_value", c_value_udf(F.col("ntokens"), F.col("freq"), F.col("nested_freq")))
        .withColumn("idf", idf_udf(F.col("df")))
        .select("normalized_key", "df", "c_value", "idf", "surface", "kind")
    )

    # 3·4 — 대상 문서의 행만 점수 매긴다.
    target_meta = targets.select(
        "url_hash", "source_id", "author", "published_date", "dup_of", "ingest_run_id"
    )
    k1, b = thresholds.bm25_k1, thresholds.bm25_b
    bm25_udf = F.udf(
        lambda tf, doc_len, idf: float(
            scoring.bm25(
                int(tf), doc_len=int(doc_len), avg_doc_len=avg_doc_len, idf=float(idf), k1=k1, b=b
            )
        ),
        DoubleType(),
    )
    minmax_udf = F.udf(
        lambda value, low, high: float(scoring.minmax(float(value), float(low), float(high))),
        DoubleType(),
    )
    weights = scoring.ScoreWeights(
        c_value=thresholds.weight_c_value,
        bm25=thresholds.weight_bm25,
        title=thresholds.weight_title,
        latin=thresholds.weight_latin,
        proper=thresholds.weight_proper,
    )
    combine_udf = F.udf(
        lambda c, bm, title, latin, proper: float(
            scoring.combine(float(c), float(bm), float(title), weights, float(latin), float(proper))
        ),
        DoubleType(),
    )
    # 라틴 문자는 **코퍼스 대표 표기**에서 본다 ([04 §4]). 문서 안 표기로 보면 같은 키워드가
    # 문서마다 다른 축 값을 받는다.
    latin_udf = F.udf(lambda surface: float(scoring.latin_axis(surface)), DoubleType())
    per_doc = Window.partitionBy("url_hash")
    rank_order = Window.partitionBy("url_hash").orderBy(
        F.col("score").desc(), F.col("normalized_key").asc()
    )

    rows = (
        occurrences.join(target_meta, on="url_hash")
        .join(scored_keys, on="normalized_key")
        .withColumn("bm25", bm25_udf(F.col("tf"), F.col("doc_len"), F.col("idf")))
        .withColumn("title_axis", F.when(F.col("tf_title") > 0, F.lit(1.0)).otherwise(F.lit(0.0)))
        .withColumn("latin_axis", latin_udf(F.col("surface")))
        .withColumn(
            "proper_axis", F.when(F.col("is_proper"), F.lit(1.0)).otherwise(F.lit(0.0))
        )
        .withColumn(
            "c_norm",
            minmax_udf(
                F.col("c_value"), F.min("c_value").over(per_doc), F.max("c_value").over(per_doc)
            ),
        )
        .withColumn(
            "bm25_norm",
            minmax_udf(F.col("bm25"), F.min("bm25").over(per_doc), F.max("bm25").over(per_doc)),
        )
        .withColumn(
            "score_raw",
            combine_udf(
                F.col("c_norm"),
                F.col("bm25_norm"),
                F.col("title_axis"),
                F.col("latin_axis"),
                F.col("proper_axis"),
            ),
        )
        # 해시태그 가중 ([04 §8]). 1 을 넘지 않게 — score_floor 가 0~1 척도다.
        .withColumn(
            "score",
            F.least(
                F.lit(1.0),
                F.when(
                    F.col("kind") == tk.HASHTAG,
                    F.col("score_raw") * F.lit(domain_options.hashtag_weight),
                ).otherwise(F.col("score_raw")),
            ),
        )
        .withColumn("rank", F.row_number().over(rank_order))
        .withColumn(
            "selected",
            (F.col("rank") <= F.lit(thresholds.per_document_top_k))
            & (F.col("score") >= F.lit(thresholds.score_floor)),
        )
    ).cache()

    extracted_at = datetime.now(timezone.utc)
    document_candidates = rows.select(
        F.lit(domain).alias("domain"),
        F.col("url_hash"),
        F.col("normalized_key"),
        F.col("surface"),
        F.col("kind"),
        F.col("ntokens"),
        F.col("tf"),
        F.col("tf_title"),
        (F.col("tf_title") > 0).alias("in_title"),
        (F.col("latin_axis") > 0).alias("is_latin"),
        F.col("is_proper"),
        F.col("df"),
        F.col("c_value"),
        F.col("bm25"),
        F.col("score"),
        F.col("rank"),
        F.col("selected"),
        F.col("published_date").alias("stat_date"),
        F.col("source_id"),
        F.col("author"),
        F.col("dup_of").isNotNull().alias("is_dup"),
        F.col("ingest_run_id"),
        F.lit(extract_run_id).alias("extract_run_id"),
        F.lit(extracted_at).alias("extracted_at"),
    ).select(*candidates_io.DOCUMENT_CANDIDATE_COLUMNS)

    documents = targets.select(F.lit(domain).alias("domain"), F.col("url_hash"))

    abbreviations = (
        # 대상 문서로 좁힌다. `extracted` 가 이미 source_id · published_date 를 들고 있어
        # 키만 조인한다.
        extracted.join(target_meta.select("url_hash"), on="url_hash")
        .select("url_hash", "source_id", "published_date", F.explode("_x.abbreviations").alias("a"))
        .select(
            F.lit(domain).alias("domain"),
            F.col("url_hash"),
            F.col("a.abbreviation_key").alias("abbreviation_key"),
            F.col("a.expansion_key").alias("expansion_key"),
            F.col("a.abbreviation").alias("abbreviation"),
            F.col("a.expansion").alias("expansion"),
            F.col("a.initials_match").alias("initials_match"),
            F.col("source_id"),
            F.col("published_date").alias("stat_date"),
            F.lit(extract_run_id).alias("extract_run_id"),
            F.lit(extracted_at).alias("observed_at"),
        )
        .select(*candidates_io.ABBREVIATION_COLUMNS)
    )

    stats = _stats(
        domain=domain,
        extracted=extracted,
        targets=targets,
        key_stats=key_stats,
        rows=rows,
        corpus_size=corpus_size,
        known_keys=known_keys,
    )
    return ExtractResult(
        document_candidates=document_candidates,
        documents=documents,
        abbreviations=abbreviations,
        stats=stats,
        corpus_size=corpus_size,
        target_count=targets.count(),
        _cached=(extracted, occurrences, rows),
    )


def _stats(
    *,
    domain: str,
    extracted: "DataFrame",
    targets: "DataFrame",
    key_stats: "DataFrame",
    rows: "DataFrame",
    corpus_size: int,
    known_keys: "DataFrame | None",
) -> list[Stat]:
    """[04 §9] 의 분포 모니터링. 급변하면 사람이 본다 — 그래서 실행마다 `pl_batch_stat` 에
    남긴다."""
    from pyspark.sql import functions as F

    target_ids = targets.select("url_hash")
    n_docs = target_ids.count()
    stats: list[Stat] = [Stat(DOCUMENTS, domain, n_docs), Stat(CORPUS_SIZE, domain, corpus_size)]

    n_rows = rows.count()
    docs_with = rows.select("url_hash").distinct().count()
    n_selected = rows.where(F.col("selected")).count()
    stats.append(Stat(CANDIDATES, domain, n_rows))
    stats.append(Stat(CANDIDATES_PER_DOC_AVG, domain, (n_rows / n_docs) if n_docs else 0.0))
    stats.append(Stat(SELECTED_PER_DOC_AVG, domain, (n_selected / n_docs) if n_docs else 0.0))
    stats.append(Stat(DOCUMENTS_WITHOUT_CANDIDATES, domain, n_docs - docs_with))

    # 문서 안 필터가 버린 것 — 대상 문서의 사유별 합.
    dropped = (
        extracted.join(target_ids, on="url_hash")
        .select(F.explode("_x.dropped").alias("reason", "n"))
        .groupBy("reason")
        .agg(F.sum("n").alias("n"))
        .collect()
    )
    for row in sorted(dropped, key=lambda r: r["reason"]):
        stats.append(Stat(DROPPED, f"{domain}/{row['reason']}", int(row["n"])))

    # DF 필터 — 비교키 단위.
    total_keys = key_stats.count()
    by_reason = {
        row["df_reason"]: int(row["n"])
        for row in key_stats.groupBy("df_reason").agg(F.count(F.lit(1)).alias("n")).collect()
        if row["df_reason"] is not None
    }
    for reason in filters.CORPUS_REASONS:
        stats.append(Stat(DROPPED, f"{domain}/{reason}", by_reason.get(reason, 0)))
    df_dropped = sum(by_reason.values())
    stats.append(Stat(DF_DROP_RATIO, domain, (df_dropped / total_keys) if total_keys else 0.0))

    # 후보 길이 분포와 신규 유입률 — 대상 문서에서 살아남은 비교키 기준.
    kept = rows.select("normalized_key", "ntokens").distinct()
    kept_count = kept.count()
    for row in kept.groupBy("ntokens").agg(F.count(F.lit(1)).alias("n")).collect():
        stats.append(Stat(CANDIDATE_NTOKENS, f"{domain}/{row['ntokens']}", int(row["n"])))
    if known_keys is not None and kept_count:
        new_count = kept.join(
            known_keys.select("normalized_key"), on="normalized_key", how="left_anti"
        ).count()
        stats.append(Stat(NEW_CANDIDATE_RATE, domain, new_count / kept_count))
    return stats
