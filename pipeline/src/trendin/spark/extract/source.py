"""`curated` 읽기와 대상 문서 선정 ([01 §3](../../../../spark/docs/01-architecture.md)).

`extract` 의 입력은 `ingest` 가 쓴 Parquet 이다. **대상 문서 한 묶음만 읽는다.**

| 묶음 | 무엇 | 왜 |
| --- | --- | --- |
| **대상** | 새 `ingest_run_id` 파티션(평시) 또는 지정 발행일 구간(재추출) | 점수가 적재된다 |

⚠️ **코퍼스 묶음이 2026-09-16 에 없어졌다.** 옛 경로는 DF·BM25 를 재려고 같은 도메인의 최근
N 일 문서를 함께 읽어 매번 다시 토큰화했다. 점수를 실체 인식 모델이 주게 되면서 코퍼스
통계가 선별에 관여하지 않고, 추론은 문서당 약 1초라 그 배선을 두면 하루치 처리가 코퍼스
크기에 비례한다 (`extract/batch.py` 의 주석). 누적 관측이 필요한 [05] 승격 심사는
`pl_candidate` · `pl_keyword_daily_stat` 의 누적을 본다.

**"이번에 새로 쓰인 파티션" 을 `extract` 자신의 처리 이력으로 안다.** [01 §3] 은 `ingest` 가
쓴 파티션 목록을 처리 이력에 남기기로 했지만 아직 없다 — 대신 `extract` 가 처리한
`ingest_run_id` 를 자기 `job` 으로 처리 이력에 적고(`jobs/extract.py`), `curated` 의 파티션
목록에서 그걸 뺀 것이 새 파티션이다. 파티션 컬럼만 읽는 조회라 데이터는 올라오지 않는다.

**같은 문서가 여러 파티션에 있을 수 있다.** `--force` 재처리가 새 `ingest_run_id` 로 다시
쓰고, 옛 파티션은 남는다 ([01 §3] 의 한계). 그래서 `url_hash` 마다 **가장 최근 실행분 하나**만
쓴다 — 둘 다 세면 DF 가 두 배가 된다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from trendin.spark.common.config import Config
from trendin.spark.common.logging import get_logger
from trendin.spark.normalize.curated import curated_root
from trendin.spark.normalize.schema import DOCUMENT_SCHEMA

if TYPE_CHECKING:
    from pyspark.sql import DataFrame
    from pyspark.sql.types import StructType

log = get_logger(__name__)

# `extract` 가 `curated` 에서 읽는 칸. 나머지는 Parquet 이라 디스크에서 올라오지 않는다.
#
# **`source_country` 가 국가 축의 유일한 상류다.** 수집 봉투에서 `curated` 스물세 칸까지는
# 값이 이미 실려 있었는데 이 목록에 없어서 추출 뒤로 흐르지 못했고, 그래서
# `keyword_country_daily_metrics` 가 전 키워드를 한 나라로 채우고 있었다. 국가는 기사가
# 아니라 **소스**의 속성이므로 문서마다 값이 하나이고, 이 칸을 그대로 내려보내면 된다.
COLUMNS = (
    "url_hash",
    "source_id",
    "domain",
    "title",
    "body",
    "lang",
    "author",
    "source_country",
    "published_at",
    "published_date",
    "dup_of",
    "ingest_run_id",
)


@dataclass(frozen=True, slots=True)
class Selection:
    """대상 문서를 고르는 조건. 둘 중 하나다 — 실행 목록(평시) 또는 발행일 구간(재추출)."""

    domain: str
    ingest_run_ids: tuple[str, ...] | None = None
    date_from: date | None = None
    date_to: date | None = None

    @property
    def by_dates(self) -> bool:
        return self.date_from is not None or self.date_to is not None


def curated_schema() -> "StructType":
    """읽을 칸의 스키마. `normalize/schema.DOCUMENT_SCHEMA` 에서 `COLUMNS` 만 뽑는다.

    두 정의가 한 쌍이므로 타입을 여기서 다시 적지 않는다 — 적으면 한쪽만 고쳐졌을 때
    파케이가 조용히 다른 타입으로 읽힌다.
    """
    from pyspark.sql.types import StructType

    fields = {field.name: field for field in DOCUMENT_SCHEMA.fields}
    return StructType([fields[name] for name in COLUMNS])


def read_curated(spark, config: Config, *, root: str | None = None) -> "DataFrame":
    """버킷 루트에서 통째로. 파티션 프루닝은 뒤의 `where` 가 한다.

    **스키마를 명시해 읽는다.** 추론에 맡기면 `mergeSchema` 가 꺼져 있는 기본 설정에서
    Spark 가 **파일 하나의 풋터로** 전체 스키마를 정하고, 어느 파일이 뽑히는지는 리스팅
    순서에 달렸다. `curated` 에는 칸이 다른 세대가 섞여 있다 — `source_country` 는
    2026-09-17 에 들어왔고 그전 파티션에는 없다. 추론에 맡기면 같은 버킷을 읽는 실행이
    어떤 날은 그 칸을 찾지 못해 죽고 어떤 날은 도는, 재현되지 않는 실패가 된다.

    명시하면 없는 칸이 `null` 로 채워지고, 국가는 뒤에서 `XX` 로 접힌다
    (`extract/batch.py`). 옛 파티션의 기사는 실제로 나라를 모르므로 그 값이 맞다.

    `mergeSchema` 를 켜지 않는 이유는 모든 파일의 풋터를 열기 때문이다. 스키마는 계약이라
    파일에 물어볼 값이 아니다.

    `root` 는 층 2 테스트가 임시 디렉터리를 넣는 자리다 ([09 §4]).
    """
    return (
        spark.read.schema(curated_schema())
        .parquet(root or curated_root(config))
        .select(*COLUMNS)
    )


def ingest_run_ids(curated: "DataFrame", *, domain: str) -> list[str]:
    """그 도메인에 있는 `ingest_run_id` 전부. 파티션 컬럼 둘만 읽는다."""
    from pyspark.sql import functions as F

    rows = curated.where(F.col("domain") == domain).select("ingest_run_id").distinct().collect()
    return sorted(row[0] for row in rows if row[0] is not None)


def latest_per_document(documents: "DataFrame") -> "DataFrame":
    """`url_hash` 마다 가장 최근 `ingest_run_id` 의 행 하나. 재처리로 겹친 파티션을 접는다."""
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    order = Window.partitionBy("url_hash").orderBy(F.col("ingest_run_id").desc_nulls_last())
    return (
        documents.withColumn("_rank", F.row_number().over(order))
        .where(F.col("_rank") == 1)
        .drop("_rank")
    )


def target_documents(curated: "DataFrame", selection: Selection) -> "DataFrame":
    """대상 문서. 실행 목록이면 그 파티션들, 발행일 구간이면 그 날짜들(구간 안 모든 실행)."""
    from pyspark.sql import functions as F

    frame = curated.where(F.col("domain") == selection.domain)
    if selection.by_dates:
        if selection.date_from is not None:
            frame = frame.where(F.col("published_date") >= F.lit(selection.date_from))
        if selection.date_to is not None:
            frame = frame.where(F.col("published_date") <= F.lit(selection.date_to))
    else:
        run_ids = list(selection.ingest_run_ids or ())
        if not run_ids:
            return frame.where(F.lit(False))
        frame = frame.where(F.col("ingest_run_id").isin(run_ids))
    return latest_per_document(frame)
