"""Spark 배선 — 추론과 코퍼스 통계 ([04 §1] 의 뒷부분).

```
1. mapPartitions    파티션마다 GLiNER 배치 추론 → 문서 × 후보 행 (extract/document.py)
2. 코퍼스 통계      비교키별 DF · 대표 표기 · 대표 유형
3. 기록용 BM25      점수에 들어가지 않는다 (extract/scoring.py 의 주석)
4. 선별             문서당 순위 → 상위 K 이고 하한 이상 = selected
5. 프레임           pl_document_candidate · 처리 문서 · 약어 관측 · [04 §9] 통계
```

## 2026-09-16 에 바뀐 것 둘

**파티션 단위로 배치 추론한다.** 트랜스포머는 문서를 하나씩 넣으면 세션 비용이 문서 수만큼
곱해진다. 파티션 하나를 통째로 모델에 묶음으로 넣고, 모델은 executor 프로세스마다 한 번만
적재된다 (`entities.recognizer_for`). 행 단위 UDF 를 쓰면 이 둘을 다 잃는다.

⚠️ **`mapInPandas` 가 아니라 `rdd.mapPartitions` 다.** 배치 추론의 표준 배선은 전자이고
처음에 그렇게 썼는데, 이 조합(Spark 4.0.4 · pandas 2.3 · pyarrow 21)에서 출력 프레임이
`TypeError: Expected Array, got ChunkedArray` 로 죽었다 — 열을 하나씩 빼도 마찬가지였다.
`mapPartitions` 는 Arrow 를 거치지 않아 그 문제가 없고, **pandas·pyarrow 의존이 사라진다.**
잃는 것은 Arrow 직렬화 속도인데, 우리 병목은 문서당 약 1초인 추론이라 묻힌다.

**코퍼스 전체에 추론하지 않는다.** 옛 경로는 DF 를 재려고 최근 N 일 문서를 매번 다시
토큰화했다. 토큰화는 싸지만 추론은 문서당 약 1초라 같은 배선을 쓰면 하루치 처리가 코퍼스
크기에 비례한다. **점수가 코퍼스에 의존하지 않으므로**(모델이 준다) 대상 문서만 돌리고,
DF 는 이번 배치 안에서 세어 칸에만 적는다. 누적 관측이 필요한 곳([05] 승격 심사)은
`pl_candidate` 와 `pl_keyword_daily_stat` 의 누적을 본다.

⚠️ 그래서 **`df` 칸의 뜻이 달라졌다** — "최근 N 일 코퍼스에서의 문서 빈도" 가 아니라 "이번
배치에서의 문서 빈도" 다. 배치 크기에 따라 흔들리지만 선별에 관여하지 않는다.

## `url_hash` 를 hex 문자열로 실어 보낸다

바이트 열을 파이썬 경계로 넘기면 `bytes` · `bytearray` · `memoryview` 가 섞여 조인 키로
쓰기 나쁘다. 문서 식별자를 `F.hex` 로 문자열로 만들어 넣고 그대로 돌려받는다. 적재 프레임의
`url_hash` 는 `targets` 쪽 원본 컬럼을 쓰므로 타입이 바뀌지 않는다.

## 한 프레임에 세 가지 행이 섞이는 이유

추론은 비싸고 한 번만 해야 하는데, 한 번의 추론에서 나오는 것이 셋이다 — 후보, 문서 메타
(길이), 버린 사유별 건수. 결과 프레임은 하나이므로 `row_type` 으로 가른다. 중첩 구조체로
내면 행 종류는 하나가 되지만 스키마가 복잡해지고, 추론을 세 번 하면 비용이 세 배가 된다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Iterator

from trendin.spark.common import countries
from trendin.spark.common.config import ConfigError
from trendin.spark.common.logging import get_logger
from trendin.spark.extract import chunking as ck
from trendin.spark.extract import entities as ent
from trendin.spark.extract import scoring
from trendin.spark.extract.document import ExtractionOptions, document_text, extract_document
from trendin.spark.extract.thresholds import ExtractThresholds
from trendin.spark.io import candidates as candidates_io
from trendin.spark.io.stats import Stat

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

log = get_logger(__name__)

# --- [04 §9] 분포 모니터링 지표. 값이 곧 집계 키다 — 바꾸면 옛 실행과 이어지지 않는다. ---------
DOCUMENTS = "documents"
CANDIDATES = "candidates"  # 필터를 전부 통과한 문서×후보 행
CANDIDATES_PER_DOC_AVG = "candidates_per_doc_avg"
SELECTED_PER_DOC_AVG = "selected_per_doc_avg"
DOCUMENTS_WITHOUT_CANDIDATES = "documents_without_candidates"
DROPPED = "dropped"  # 차원: {domain}/{사유}
NEW_CANDIDATE_RATE = "new_candidate_rate"  # 이번에 처음 관측된 비교키 비율
CHUNKS_PER_DOC_AVG = "chunks_per_doc_avg"  # 문서당 토막 수. 추론 비용의 직접 지표
# 토막 상한(`chunk.max_chunks`)까지 쓴 문서 수. **여전히 뒤가 버려지는 문서다** — 이 값이
# 크면 상한을 올려 더 볼 여지가 있고, 0 에 가까우면 상한이 놀고 있다.
DOCUMENTS_AT_CHUNK_LIMIT = "documents_at_chunk_limit"
CANDIDATE_NTOKENS = "candidate_ntokens"  # 차원: {domain}/{토큰 수}. 후보 길이 분포
ENTITY_TYPES = "entity_types"  # 차원: {domain}/{유형}. 라벨별 후보 수
LANGUAGES = "languages"  # 차원: {domain}/{lang}. 언어 분포 — 다국어 확장의 모니터링

# 결과 프레임의 행 종류. `row_type` 으로 셋을 가른다 (모듈 주석).
ROW_CANDIDATE = "CANDIDATE"
ROW_DOCUMENT = "DOCUMENT"
ROW_DROPPED = "DROPPED"


def extraction_schema():
    """`_recognize` 가 내는 행의 스키마. 칸 이름과 순서가 `_COLUMNS` 와 한 쌍이다."""
    from pyspark.sql.types import (
        BooleanType,
        DoubleType,
        IntegerType,
        StringType,
        StructField,
        StructType,
    )

    return StructType(
        [
            StructField("row_type", StringType(), False),
            StructField("doc_key", StringType(), False),
            # 후보 행
            StructField("normalized_key", StringType(), True),
            StructField("doc_surface", StringType(), True),
            StructField("entity_type", StringType(), True),
            StructField("model_score", DoubleType(), True),
            StructField("ntokens", IntegerType(), True),
            StructField("tf", IntegerType(), True),
            StructField("tf_title", IntegerType(), True),
            StructField("is_proper", BooleanType(), True),
            # 문서 행
            StructField("doc_len", IntegerType(), True),
            # 이 문서가 모델에 몇 토막으로 들어갔나 ([04 §2], `extract/chunking.py`).
            StructField("chunks", IntegerType(), True),
            # 버림 행
            StructField("drop_reason", StringType(), True),
            StructField("drop_count", IntegerType(), True),
        ]
    )


# 파티션을 모델에 넣는 단위는 문서가 아니라 **토막**이고, 배치 구성은
# `RecognizerSpec.batch_words`·`batch_size` 가 정한다 (`entities.Recognizer.predict`).
def _recognize(
    rows: "Iterator",
    *,
    recognizer: ent.RecognizerSpec,
    options: ExtractionOptions,
) -> "Iterator[tuple]":
    """파티션 하나 → 후보·문서·버림 행. **executor 에서 돈다.**

    `recognizer_for` 가 프로세스 전역 캐시라 파티션이 여러 개여도 모델은 한 번만 적재된다
    (`spark.python.worker.reuse` 가 기본 참).

    **파티션을 통째로 메모리에 올린다.** 배치 추론을 하려면 문서를 모아야 하고, 하루치가
    수천 건이라 파티션 하나는 수백 건이다. 문서가 쓰는 토막이 `chunk.max_chunks` 로 묶여
    있어 상한이 있다.
    """
    partition = list(rows)
    if not partition:
        return
    model = ent.recognizer_for(recognizer)
    keys = [row["doc_key"] for row in partition]
    titles = [row["title"] for row in partition]
    bodies = [row["body"] for row in partition]
    langs = [row["lang"] for row in partition]
    texts = [document_text(title, body)[0] for title, body in zip(titles, bodies)]
    spans = model.predict(texts)
    # **토막 수를 여기서 다시 센다.** `predict` 의 계약은 문서별 구간이고 토막은 그 안에서
    # 생겼다 사라진다. 분할은 정규식 한 번이라 추론 대비 비용이 없고, 계약을 지키는 값이
    # 더 크다 ([04 §9] 의 `chunks_per_doc_avg`).
    counts = [
        len(
            ck.split(
                text,
                budget=recognizer.chunk_words,
                overlap=recognizer.chunk_overlap,
                max_chunks=recognizer.max_chunks,
            )
        )
        for text in texts
    ]

    for doc_key, title, body, lang, doc_spans, chunks in zip(
        keys, titles, bodies, langs, spans, counts
    ):
        result = extract_document(title, body, lang, doc_spans, options=options)
        yield _row(ROW_DOCUMENT, doc_key, doc_len=result.doc_len, chunks=chunks)
        for candidate in result.candidates:
            yield _row(
                ROW_CANDIDATE,
                doc_key,
                normalized_key=candidate.key,
                doc_surface=candidate.surface,
                entity_type=candidate.entity_type,
                model_score=candidate.score,
                ntokens=candidate.ntokens,
                tf=candidate.tf,
                tf_title=candidate.tf_title,
                is_proper=candidate.is_proper,
            )
        for reason, count in sorted(result.dropped.items()):
            yield _row(ROW_DROPPED, doc_key, drop_reason=reason, drop_count=count)


# 파티션 하나가 들고 갈 문서 수의 상한. 파티션을 통째로 메모리에 올리므로(`_recognize`)
# 무한정 키우지 않는다. 토막 상한(256 어절 × 3)이 문서당 약 2,800자이므로 500건이면
# 넉넉잡아 수십 MB 다.
MAX_DOCS_PER_PARTITION = 500


def _partition_count(session, frame: "DataFrame", *, recognizer: ent.RecognizerSpec) -> int:
    """추론에 쓸 파티션 수.

    **`curated` 의 파일 수를 그대로 쓰면 안 된다.** Parquet 이 실행별로 잘게 쓰여 파티션이
    수천 개가 되고, 그러면 파티션마다 문서가 한두 건이라 **배치 추론이 성립하지 않는다** —
    묶어서 넣으려고 `mapPartitions` 를 쓴 것이 무의미해진다.

    코어 수에 맞추되(모델이 코어마다 한 번 적재된다) 파티션이 너무 커지지 않게 상한을 둔다.

    **GPU 에서는 코어가 하나여야 한다.** 모델은 executor 파이썬 프로세스마다 적재되는데
    (`entities.recognizer_for`), CPU 에서 그것은 코어를 다 쓰는 길이고 GPU 에서는 **같은
    가중치를 VRAM 에 여러 벌 올리는 길이다.** 6 GB 짜리 GPU 에 209M 모델을 넷 올리면 터지고,
    죽는 자리가 `_predict_chunk` 의 `except` 안이라 **Job 은 후보 0건으로 정상 종료한다.**
    그래서 계산으로 맞추지 않고 시작 전에 거부한다.
    """
    cores = max(1, session.sparkContext.defaultParallelism)
    device = ent.resolve_device(recognizer.device)
    if device != "cpu" and cores > 1:
        raise ConfigError(
            f"extract.recognizer.device 가 {device} 인데 코어가 {cores} 개다 — 모델이 워커마다 "
            "적재되어 VRAM 을 그 수만큼 먹는다. SPARK_MASTER=local[1] 로 돌린다"
        )
    documents = frame.count()
    needed = -(-documents // MAX_DOCS_PER_PARTITION)  # 올림
    return max(1, min(documents, max(cores, needed)))


def _row(row_type: str, doc_key: str, **values) -> tuple:
    """`_COLUMNS` 순서의 튜플. **딕셔너리가 아니라 튜플인 이유** — `createDataFrame` 이
    스키마를 이미 알고 있으므로 이름을 다시 실어 보낼 필요가 없다."""
    values["row_type"] = row_type
    values["doc_key"] = doc_key
    return tuple(values.get(name) for name in _COLUMNS)


_COLUMNS = (
    "row_type",
    "doc_key",
    "normalized_key",
    "doc_surface",
    "entity_type",
    "model_score",
    "ntokens",
    "tf",
    "tf_title",
    "is_proper",
    "doc_len",
    "chunks",
    "drop_reason",
    "drop_count",
)


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
    domain: str,
    thresholds: ExtractThresholds,
    recognizer: ent.RecognizerSpec,
    options: ExtractionOptions,
    extract_run_id: str,
    known_keys: "DataFrame | None" = None,
) -> ExtractResult:
    """대상 문서에서 후보를 뽑고 점수를 매긴다.

    **코퍼스 인자가 없다.** 점수가 코퍼스에 의존하지 않으므로 대상 문서만 처리한다 (모듈
    주석).
    """
    from pyspark.sql import Window
    from pyspark.sql import functions as F
    from pyspark.sql.types import DoubleType

    # 문서 식별자를 hex 문자열로 실어 보낸다 (모듈 주석의 `url_hash` 절).
    keyed = targets.withColumn("doc_key", F.hex(F.col("url_hash")))
    session = keyed.sparkSession
    partitions = _partition_count(session, keyed, recognizer=recognizer)
    rows_rdd = (
        keyed.select("doc_key", "title", "body", "lang")
        .repartition(partitions)
        .rdd.mapPartitions(lambda it: _recognize(it, recognizer=recognizer, options=options))
    )
    recognized = session.createDataFrame(rows_rdd, extraction_schema()).cache()

    doc_meta = recognized.where(F.col("row_type") == ROW_DOCUMENT).select("doc_key", "doc_len")
    corpus_size = doc_meta.count()
    avg_doc_len = float(doc_meta.agg(F.avg("doc_len")).collect()[0][0] or 0.0)
    log.info("대상 %d건, 평균 길이 %.0f자", corpus_size, avg_doc_len)

    # 1 — 문서 × 후보 출현.
    occurrences = (
        recognized.where(F.col("row_type") == ROW_CANDIDATE)
        # 후보 행에도 `doc_len` 칸이 있다 (값은 null). 떼지 않으면 조인 뒤 이름이 겹쳐
        # `AMBIGUOUS_REFERENCE` 로 죽는다 — 한 프레임에 세 행 종류를 담은 대가다.
        .drop("doc_len")
        .join(doc_meta, on="doc_key")
        .select(
            "doc_key",
            "doc_len",
            "normalized_key",
            "doc_surface",
            "entity_type",
            "model_score",
            "ntokens",
            "tf",
            "tf_title",
            "is_proper",
        )
        .cache()
    )

    # 2 — 비교키별 통계. **거르지 않는다** — DF 상하한이 없어졌다 (모듈 주석).
    key_stats = occurrences.groupBy("normalized_key").agg(
        F.countDistinct("doc_key").alias("df"),
        F.sum("tf").alias("freq"),
        F.min("ntokens").alias("ntokens"),
    )

    # 대표 표기와 대표 유형 — 배치에서 가장 빈번한 것 ([04 §4]). 동률은 사전순으로 결정적이게.
    # **유형도 코퍼스에서 고른다.** 문서마다 다른 유형이 붙으면 화면의 유형 필터가 문서에
    # 따라 흔들린다.
    surface_order = Window.partitionBy("normalized_key").orderBy(
        F.col("n").desc(), F.col("doc_surface").asc(), F.col("entity_type").asc()
    )
    representatives = (
        occurrences.groupBy("normalized_key", "doc_surface", "entity_type")
        .agg(F.sum("tf").alias("n"))
        .withColumn("_r", F.row_number().over(surface_order))
        .where(F.col("_r") == 1)
        .select(
            "normalized_key",
            F.col("doc_surface").alias("surface"),
            F.col("entity_type").alias("kind"),
        )
    )

    # 3 — 기록용 BM25. 점수에 들어가지 않는다.
    k1, b = thresholds.bm25_k1, thresholds.bm25_b
    idf_udf = F.udf(lambda df: float(scoring.bm25_idf(int(df), corpus_size)), DoubleType())
    bm25_udf = F.udf(
        lambda tf, doc_len, idf: float(
            scoring.bm25(
                int(tf), doc_len=int(doc_len), avg_doc_len=avg_doc_len, idf=float(idf), k1=k1, b=b
            )
        ),
        DoubleType(),
    )
    scored_keys = (
        key_stats.join(representatives, on="normalized_key")
        .withColumn("idf", idf_udf(F.col("df")))
        .select("normalized_key", "df", "idf", "surface", "kind")
    )

    # 4 — 선별. 점수는 모델이 준 값 그대로다.
    target_meta = keyed.select(
        "doc_key",
        "url_hash",
        "source_id",
        "author",
        # 국가는 문서마다 하나다 (소스의 속성이라서). 여기서 접어 두면 아래 조립과
        # 일별 재집계가 같은 값을 본다.
        countries.country_column(F.col("source_country")),
        "published_date",
        "dup_of",
        "ingest_run_id",
    )
    rank_order = Window.partitionBy("doc_key").orderBy(
        F.col("score").desc(), F.col("normalized_key").asc()
    )
    rows = (
        occurrences.join(target_meta, on="doc_key")
        .join(scored_keys, on="normalized_key")
        .withColumn("bm25", bm25_udf(F.col("tf"), F.col("doc_len"), F.col("idf")))
        .withColumn("score", F.col("model_score"))
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
        # **`kind` 가 이제 실체 유형이다** (2026-09-16). 옛 경로에서는 토큰 종류
        # (`TERM` · `NGRAM` · `HASHTAG`)였고, 그 값을 만들던 토크나이저가 없어졌다.
        # 칸을 새로 만들지 않은 이유는 둘 다 "후보의 종류" 이고 쓰는 곳이 같기 때문이다.
        F.col("kind"),
        F.col("ntokens"),
        F.col("tf"),
        F.col("tf_title"),
        (F.col("tf_title") > 0).alias("in_title"),
        # 라틴 문자가 섞여 있나. **코퍼스 대표 표기에서 본다** ([04 §4]) — 문서 안 표기로 보면
        # 같은 키워드가 문서마다 다른 값을 받는다. 점수 축이 아니라 기록이다.
        F.col("surface").rlike("[A-Za-z]").alias("is_latin"),
        F.col("is_proper"),
        F.col("df"),
        # C-value 가 없어졌다. 칸은 남기고 0 을 적는다 — 옛 행과 같은 표를 쓰기 때문이다.
        F.lit(0.0).alias("c_value"),
        F.col("bm25"),
        F.col("score"),
        F.col("rank"),
        F.col("selected"),
        F.col("published_date").alias("stat_date"),
        F.col("source_id"),
        F.col("author"),
        # 발행 매체의 나라. `target_meta` 가 이미 접어 둔 값이다.
        F.col("source_country"),
        F.col("dup_of").isNotNull().alias("is_dup"),
        F.col("ingest_run_id"),
        F.lit(extract_run_id).alias("extract_run_id"),
        F.lit(extracted_at).alias("extracted_at"),
    ).select(*candidates_io.DOCUMENT_CANDIDATE_COLUMNS)

    documents = targets.select(F.lit(domain).alias("domain"), F.col("url_hash"))
    abbreviations = _abbreviations(
        targets, domain=domain, extract_run_id=extract_run_id, observed_at=extracted_at
    )

    stats = _stats(
        domain=domain,
        recognized=recognized,
        targets=targets,
        rows=rows,
        known_keys=known_keys,
        max_chunks=recognizer.max_chunks,
    )
    return ExtractResult(
        document_candidates=document_candidates,
        documents=documents,
        abbreviations=abbreviations,
        stats=stats,
        corpus_size=corpus_size,
        target_count=corpus_size,
        _cached=(recognized, occurrences, rows),
    )


def _abbreviations(
    targets: "DataFrame", *, domain: str, extract_run_id: str, observed_at: datetime
) -> "DataFrame":
    """`전개형 (약어)` 관측 ([05 §3]).

    **모델을 쓰지 않는다.** 정규식이라 행 단위 UDF 로 충분하고, 추론 경로와 떼어 두면
    약어 규칙을 고칠 때 추론을 다시 돌리지 않아도 된다.
    """
    from pyspark.sql import functions as F
    from pyspark.sql.types import ArrayType, BooleanType, StringType, StructField, StructType

    pair = StructType(
        [
            StructField("abbreviation", StringType()),
            StructField("expansion", StringType()),
            StructField("abbreviation_key", StringType()),
            StructField("expansion_key", StringType()),
            StructField("initials_match", BooleanType()),
        ]
    )

    def _pairs(title: str | None, body: str | None) -> list[dict]:
        from trendin.spark.extract.abbreviations import abbreviation_pairs
        from trendin.spark.extract.document import document_text

        text, _ = document_text(title, body)
        seen: set[tuple[str, str]] = set()
        result = []
        for item in abbreviation_pairs(text):
            marker = (item.abbreviation_key, item.expansion_key)
            if marker in seen:
                continue
            seen.add(marker)
            result.append(
                {
                    "abbreviation": item.abbreviation,
                    "expansion": item.expansion,
                    "abbreviation_key": item.abbreviation_key,
                    "expansion_key": item.expansion_key,
                    "initials_match": item.initials_match,
                }
            )
        return result

    pairs_udf = F.udf(_pairs, ArrayType(pair))
    return (
        targets.select(
            "url_hash",
            "source_id",
            "published_date",
            F.explode(pairs_udf(F.col("title"), F.col("body"))).alias("a"),
        )
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
            F.lit(observed_at).alias("observed_at"),
        )
        .select(*candidates_io.ABBREVIATION_COLUMNS)
    )


def _stats(
    *,
    domain: str,
    recognized: "DataFrame",
    targets: "DataFrame",
    rows: "DataFrame",
    known_keys: "DataFrame | None",
    max_chunks: int,
) -> list[Stat]:
    """[04 §9] 의 분포 모니터링. 급변하면 사람이 본다 — 그래서 실행마다 `pl_batch_stat` 에
    남긴다."""
    from pyspark.sql import functions as F

    n_docs = targets.count()
    stats: list[Stat] = [Stat(DOCUMENTS, domain, n_docs)]

    n_rows = rows.count()
    docs_with = rows.select("doc_key").distinct().count()
    n_selected = rows.where(F.col("selected")).count()
    stats.append(Stat(CANDIDATES, domain, n_rows))
    stats.append(Stat(CANDIDATES_PER_DOC_AVG, domain, (n_rows / n_docs) if n_docs else 0.0))
    stats.append(Stat(SELECTED_PER_DOC_AVG, domain, (n_selected / n_docs) if n_docs else 0.0))
    stats.append(Stat(DOCUMENTS_WITHOUT_CANDIDATES, domain, n_docs - docs_with))

    # 토막 분포 ([04 §2]). **이 둘이 없으면 토막이 실제로 일했는지 알 수 없다** — 증상이
    # "후보가 늘었다" 로만 보이고 그것이 토막 덕인지 다른 변경 탓인지 갈리지 않는다.
    chunked = recognized.where(F.col("row_type") == ROW_DOCUMENT).select("chunks")
    agg = chunked.agg(
        F.avg("chunks").alias("avg"),
        F.sum(F.when(F.col("chunks") >= max_chunks, 1).otherwise(0)).alias("at_limit"),
    ).collect()[0]
    stats.append(Stat(CHUNKS_PER_DOC_AVG, domain, float(agg["avg"] or 0.0)))
    stats.append(Stat(DOCUMENTS_AT_CHUNK_LIMIT, domain, int(agg["at_limit"] or 0)))

    # 버린 것 — 사유별 합. 라벨 게이트(`LABEL`)가 여기 잡히므로 일본어를 켜고 끈 결과가
    # 숫자로 보인다.
    dropped = (
        recognized.where(F.col("row_type") == ROW_DROPPED)
        .groupBy("drop_reason")
        .agg(F.sum("drop_count").alias("n"))
        .collect()
    )
    for row in sorted(dropped, key=lambda r: r["drop_reason"]):
        stats.append(Stat(DROPPED, f"{domain}/{row['drop_reason']}", int(row["n"])))

    # 언어 분포 — 다국어 확장의 모니터링. `unknown` 이 늘면 판별이 새 소스를 못 따라가는 것이다.
    for row in targets.groupBy("lang").agg(F.count(F.lit(1)).alias("n")).collect():
        stats.append(Stat(LANGUAGES, f"{domain}/{row['lang'] or 'null'}", int(row["n"])))

    # 유형 분포 — 라벨마다 몇 개가 살아남았나. 라벨을 바꾼 결과가 여기 보인다.
    for row in (
        rows.select("normalized_key", "kind")
        .distinct()
        .groupBy("kind")
        .agg(F.count(F.lit(1)).alias("n"))
        .collect()
    ):
        stats.append(Stat(ENTITY_TYPES, f"{domain}/{row['kind']}", int(row["n"])))

    # 후보 길이 분포와 신규 유입률.
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
