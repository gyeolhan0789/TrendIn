"""중복 제거 3단계 ([03 §6](../../../../spark/docs/03-normalization-spec.md)).

| 단계 | 판별 | 처리 |
| --- | --- | --- |
| 1. 동일 문서 | 같은 `(source_id, source_document_id)` | 나중 것을 버린다 |
| 2. 같은 URL | 같은 `url_hash` | 대표 하나만 남긴다 |
| 3. 근사 중복 | 본문 SimHash 해밍 거리 ≤ 임계값 | `dup_of` 에 대표를 기록하고 **집계에서 제외** |

**지우지 않고 표시한다.** 1·2 단계는 `filter_reason` 을, 3 단계는 `dup_of` 를 채운다.
그래야 [03 §7] 이 "단계별 제외 건수" 를 한 번의 집계로 셀 수 있다 — 단계마다 행을 떨어뜨리면
건수를 세려고 배치를 세 번 더 훑어야 하고, 그렇게 나온 세 숫자가 같은 스냅샷에서 나왔다는
보장이 없어진다.

**3 단계를 지우지 않는 것은 규격의 결정이다.** 근사 중복 판별은 임계값에 민감해서 틀릴 수
있고, 지워버리면 임계값을 조정했을 때 되살릴 방법이 객체 재처리뿐이다. `dup_of` 로
표시해두면 집계 쿼리의 조건만 바꿔 다시 실험할 수 있다.

**1 단계가 왜 필요한가** — 생산자 쪽에서 거의 다 걸러져 온다(불변식 7·12). 그래도 두는
이유는 at-least-once 다. 같은 이벤트가 두 번 오면 `event_id` 처리 이력이 먼저 막지만
([01 §4] 중복 차단 2), 처리 이력을 우회하는 `--force` 재처리에서는 이 단계가 마지막
방어선이다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from trendin.spark.common.logging import get_logger

if TYPE_CHECKING:
    from pyspark.sql import Column, DataFrame

log = get_logger(__name__)

# 제외 사유. `normalize/filters.py` 의 품질 사유와 같은 칸(`filter_reason`)에 들어가고,
# [03 §7] 이 그 칸으로 단계별 건수를 센다.
DUP_SAME_DOCUMENT = "DUP_SAME_DOCUMENT"
DUP_SAME_URL = "DUP_SAME_URL"

# 3 단계는 행을 버리지 않으므로 사유가 없다. 대신 `dup_of IS NOT NULL` 로 센다.


@dataclass(frozen=True, slots=True)
class DedupThresholds:
    """근사 중복 문턱. `conf/*.yaml` 의 `ingest.normalize.dedup` 에서 온다.

    **기본값은 잠정이되 근거가 있다.** 2026-09-08 에 합성 한국어 기사로 문서 길이를 바꿔
    가며 쌍 거리를 재 봤다 (6~58 토큰, 64비트 지문):

    | 쌍 | 해밍 거리 |
    | --- | --- |
    | 본문이 완전히 같음 | **0** |
    | 머리말만 붙음 | 2~9 |
    | 머리말 + 한 단어 교체 | **8~13** (짧은 문서에서는 19~25) |
    | 서로 다른 주제의 글 | **31~40** |

    두 군집이 13 과 31 사이에서 갈린다. **12 는 그 사이에 있다** — 가벼운 편집 쌍을 잡고,
    무관한 글과는 2.5배 이상 떨어져 있다.

    **통상 쓰이는 3 을 그대로 두면 3단계가 사실상 놀고 있다.** 표적이 8~13 인데 3 은 "머리말만
    다른" 일부만 잡는다. 두산 계열이 같은 보도자료를 각각 올릴 때 제목·머리말·맺음말이
    조금씩 다르므로, 그 일부만 잡는 것은 이 단계를 두는 값을 거의 없앤다.

    **높게 잡는 위험은 그 간격만큼 남아 있다** — 서로 다른 기사를 같은 것으로 묶으면 언급량이
    실제보다 줄고 그게 잘못된 하락 판별이 된다 ([07 §5]). 그래서 군집 사이의 아래쪽에 붙였다.

    **짧은 문서에서 지문이 불안정하다** (6~14 토큰에서 편집 쌍이 19~25). 그쪽은 이 문턱으로
    잡히지 않는데, 본문 길이 하한 필터가 그 문서들을 먼저 걸러내므로 실제로는 거의 오지 않는다.

    **합성 문서의 측정이다.** [S6] 이 실데이터의 쌍 거리 분포를 보고 확정하며, 그때
    `pl_config_history` 에 근거와 함께 기록된다 ([09 §7] 항목 5).
    """

    max_distance: int = 12

    @classmethod
    def from_section(cls, section: dict) -> "DedupThresholds":
        # `slots=True` 에서 `cls.max_distance` 는 슬롯 서술자다 (`lang.py` 의 같은 함수).
        return cls(max_distance=int(section.get("max_distance", cls().max_distance)))


def _order_key() -> "Column":
    """중복 사이에서 누가 대표인지 정하는 순서.

    `collected_at` 을 앞에 두는 이유는 규격이 "나중 것을 버린다" 이기 때문이다. `url_hash`
    를 뒤에 두는 이유는 **재현성**이다 — 같은 시각에 수집된 두 문서 사이에서 누가 남았는지
    설명할 수 있어야 한다. `dropDuplicates` 를 쓰지 않는 것도 같은 이유다
    (`ingest/batch.deduplicate` 와 같은 판단).
    """
    from pyspark.sql import functions as F

    # 시각이 없는 문서를 맨 뒤로 보낸다. 앞에 오면 시각을 아는 문서가 시각 모르는 문서에
    # 밀려 버려진다.
    return F.struct(
        F.col("collected_at").isNull().alias("_undated"),
        F.col("collected_at"),
        F.hex(F.col("url_hash")).alias("_hash"),
    )


def _rank_within(*keys: str) -> "Column":
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    return F.row_number().over(
        Window.partitionBy(*[F.col(key) for key in keys]).orderBy(_order_key())
    )


def mark_exact_duplicates(documents: "DataFrame") -> "DataFrame":
    """1·2 단계. `dup_reason` 칸을 붙인다. 대표는 `null` 이다.

    **`url_hash` 가 없는 행은 건드리지 않는다.** 정체성이 없는 문서끼리 묶으면 `null` 키
    하나에 전부 모여 하나만 남고 나머지가 `DUP_SAME_URL` 로 센다. 그건 중복이 아니라 URL 이
    없는 것이고, 품질 필터의 `NO_URL` 이 이미 그 사유를 들고 있다 — 사유가 두 곳에서
    갈리면 [03 §7] 집계가 어느 쪽도 맞지 않는다.
    """
    from pyspark.sql import functions as F

    identified = F.col("url_hash").isNotNull()
    # 1 단계 — 같은 `(source_id, source_document_id)`. 생산자 불변식 7 이 거의 다 막지만
    # `--force` 재처리에는 이것뿐이다.
    same_document = identified & F.col("source_document_id").isNotNull()

    ranked = documents.withColumn(
        "_doc_rank",
        F.when(same_document, _rank_within("source_id", "source_document_id")).otherwise(F.lit(1)),
    ).withColumn(
        "_url_rank",
        F.when(identified, _rank_within("url_hash")).otherwise(F.lit(1)),
    )

    return ranked.withColumn(
        "dup_reason",
        F.when(F.col("_doc_rank") > 1, F.lit(DUP_SAME_DOCUMENT))
        # 1 단계를 먼저 보는 이유는 규격의 단계 순서이고, 같은 문서가 같은 URL 이기도 할 때
        # 더 구체적인 사유를 남기는 편이 진단에 쓸모 있기 때문이다.
        .when(F.col("_url_rank") > 1, F.lit(DUP_SAME_URL))
        .otherwise(F.lit(None).cast("string")),
    ).drop("_doc_rank", "_url_rank")


def mark_near_duplicates(
    documents: "DataFrame", thresholds: DedupThresholds | None = None
) -> "DataFrame":
    """3 단계. 근사 중복이면 `dup_of` 에 대표의 `url_hash` 를 넣는다.

    **비교 범위를 `(domain, published_date)` 로 자른다.** 밴딩 없이 전량 비교하는 것이
    [00 §3] 규모에서는 감당되지만([03 §6]), 그건 *하루치* 이야기다. 6주치를 한 번에 흘리는
    과거분 백필(`web-collect.md` #9)에서는 배치가 수만 건이 되고 제곱이 듣는다. 날짜로 자르면
    같은 보도자료를 **다른 날** 실은 쌍을 놓치는데, 두산 계열의 보도자료 동시 게재라는 실제
    표적은 같은 날 올라오므로 그 손실을 받는다. 범위를 넓히고 싶으면 이 블로킹 키가 손잡이다.

    **본문 없는 문서는 지문이 `null` 이라 조인에 걸리지 않는다** ([03 §6]) — 제목만으로
    SimHash 를 계산하면 해밍 거리가 우연히 가까워져 dev 도메인 전량이 서로 중복으로 판별될
    수 있다. `simhash.simhash()` 가 그 자리에서 `None` 을 내므로 여기서 따로 막지 않는다.

    **1·2 단계에서 이미 버린 행은 대표가 될 수 없다.** 안 그러면 버려질 행이 살아남을 행의
    대표가 되어, 집계에서 둘 다 빠진다.
    """
    from pyspark.sql import functions as F

    limits = thresholds or DedupThresholds()

    candidates = documents.where(F.col("simhash").isNotNull() & F.col("dup_reason").isNull())
    left = candidates.select(
        F.col("url_hash").alias("_l_hash"),
        F.col("domain").alias("_l_domain"),
        F.col("published_date").alias("_l_date"),
        F.col("simhash").alias("_l_simhash"),
        _order_key().alias("_l_order"),
    )
    right = candidates.select(
        F.col("url_hash").alias("_r_hash"),
        F.col("domain").alias("_r_domain"),
        F.col("published_date").alias("_r_date"),
        F.col("simhash").alias("_r_simhash"),
        _order_key().alias("_r_order"),
    )

    same_block = (F.col("_l_domain").eqNullSafe(F.col("_r_domain"))) & (
        F.col("_l_date").eqNullSafe(F.col("_r_date"))
    )
    # `bit_count(xor)` 이 해밍 거리다. 부호 있는 값이어도 비트 패턴이 같으므로 맞다
    # (`simhash.to_signed64`).
    near = F.bit_count(F.col("_l_simhash").bitwiseXOR(F.col("_r_simhash"))) <= limits.max_distance
    # 자기보다 앞선 것만 대표 후보로 본다. 이 조건이 자기 자신과의 조인도 함께 막는다.
    earlier = F.col("_r_order") < F.col("_l_order")

    representatives = (
        left.join(right, same_block & near & earlier, "inner")
        # 가장 앞선 것 하나. `min(struct)` 은 사전식으로 비교하므로 순서 정의가 그대로 듣는다.
        .groupBy("_l_hash")
        .agg(F.min(F.struct(F.col("_r_order"), F.col("_r_hash"))).alias("_rep"))
        .select(
            F.col("_l_hash").alias("url_hash"),
            F.col("_rep._r_hash").alias("_dup_of"),
        )
    )

    return (
        documents.join(representatives, on="url_hash", how="left")
        .withColumn("dup_of", F.col("_dup_of"))
        .drop("_dup_of")
    )


def apply_dedup(
    documents: "DataFrame", thresholds: DedupThresholds | None = None
) -> "DataFrame":
    """3 단계를 순서대로. `dup_reason` 과 `dup_of` 가 채워진 프레임을 준다.

    **순서를 바꿀 수 없다.** 3 단계가 `dup_reason` 을 읽어 "이미 버려질 행" 을 대표에서
    빼기 때문이다.
    """
    return mark_near_duplicates(mark_exact_duplicates(documents), thresholds)
