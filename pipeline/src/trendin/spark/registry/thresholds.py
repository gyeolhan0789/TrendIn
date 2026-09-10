"""[05] 의 임계값 — `conf/*.yaml` 의 `extract.registry` 구역.

`extract/thresholds.py` 와 같은 규약이다. **비어 있으면 Job 이 거부한다** — 승격은
되돌릴 수 없으므로([05 §1]) 근거 없는 문턱으로 서비스 테이블에 행을 넣는 것보다 시작을
거부하는 것이 싸다. `base.yaml` 이 측정이 필요한 값을 `null` 로 두고 `local.yaml` 이
S6 측정을 돌릴 잠정값을 채운다.

**규격이 숫자를 준 값은 여기서 고정한다.** [05 §3] 의 "서로 다른 소스 2곳 이상" 과
[05 §5] 의 "서로 다른 소스 ≥ 2" 가 그것이다 — 측정으로 정할 값이 아니라 규격의 일부라
`conf` 에서 낮출 수 있게 두지 않는다.

**pyspark 를 import 하지 않는다** ([09 §4] 층 1).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from trendin.spark.common.config import Config, ConfigError

SECTION = "extract.registry"

# 측정 없이 정할 수 없어 `base.yaml` 이 `null` 로 두는 키. 전부 있어야 시작한다.
#
# `review.similarity_floor` 는 여기 없다 — 임베딩 모델이 설정되지 않으면 층 3 이 아예
# 돌지 않으므로([05 §4], `registry/embedding.py`) 그때 값을 요구하면 쓰지도 않는 숫자를
# 채우게 만든다. 모델이 설정된 경우에만 `validated()` 가 요구한다.
REQUIRED = (
    "abbreviation.min_documents",
    "variant.min_length",
    "variant.max_edit_distance",
    "variant.df_dominance",
    "plural.df_dominance",
    "promote.min_documents",
    "promote.min_observed_days",
    "promote.min_authors",
    "promote.min_representative_ratio",
)

# `base.yaml` 이 값을 채워 두는 키. **측정 대상이 아니다** — 여기 있는 이유는 코드가
# 기본값을 갖지 않게 하려는 것이다 ([09 §3] "임계값을 코드에 두지 않는다"). 코드와 yaml 에
# 같은 숫자가 둘 있으면 한쪽만 고쳐졌을 때 조용히 갈리고, 갈린 쪽이 이기는지는 호출 경로에
# 달린다. 위 `REQUIRED` 와 나눈 것은 고치는 곳이 달라서다 — 저쪽은 `local.yaml`, 이쪽은
# `base.yaml` 이다.
CONFIGURED = (
    "variant.max_index_size",
    "embedding.dim",
    "embedding.batch_size",
)

# [05 §3]·[05 §5] 가 못 박은 값. 설정으로 낮추지 않는다. **이건 코드에 둔다** — 측정으로
# 정할 값이 아니라 규격의 일부라 `conf` 에서 낮출 수 있게 두지 않는다 (모듈 docstring).
MIN_SOURCES = 2


@dataclass(frozen=True, slots=True)
class RegistryThresholds:
    """[05] 의 숫자 전부. S6 의 재확정이 파일 하나를 고치는 일이어야 해서 한 곳에 모은다."""

    # --- 층 1 — 조건부 복수형 ([05 §2]) ---------------------------------
    # 한쪽 DF 가 다른 쪽의 이 배수를 넘어야 접는다. 양쪽이 다 흔하면 접지 않는다.
    plural_df_dominance: float

    # --- 층 2 — 약어 ↔ 전개형 ([05 §3]) ---------------------------------
    # 괄호 패턴이 관측된 **서로 다른 문서** 수 하한. 한 사람의 오기를 막는다.
    abbreviation_min_documents: int

    # --- 층 2 — 표기 변형(오타) ([05 §3]) -------------------------------
    # 이보다 짧은 표기에는 적용하지 않는다. 4자 이하에서 편집 거리 1은 딴 낱말이 흔하다.
    variant_min_length: int
    variant_max_edit_distance: int
    variant_df_dominance: float
    # 색인 쪽(대표 후보) 크기 상한. 넘으면 층 2 변형을 건너뛰고 크게 남긴다 — 조용히
    # 몇 분을 태우는 것보다 낫다. 근거는 `registry/merge.py` 의 비용 주석.
    variant_max_index_size: int

    # --- 층 5 — 승격 ([05 §5]) ------------------------------------------
    promote_min_documents: int
    promote_min_observed_days: int
    promote_min_authors: int
    promote_min_representative_ratio: float

    # --- 층 3 — 임베딩 ([05 §4], [01 §5]) -------------------------------
    # `null` 이면 층 3 을 돌리지 않는다. 그때 검수 큐에는 층 2 신호가 있는데 자동 병합
    # 조건을 못 채운 쌍만 올라간다.
    embedding_model: str | None
    embedding_dim: int
    embedding_batch_size: int
    review_similarity_floor: float | None
    # NPMI 상한 — 이 값을 넘으면 연관어로 보고 큐에 올리지 않는다 ([05 §3] 의 표).
    # **NPMI 는 [06] 이 계산하고 그건 다음 에픽이다.** 그래서 지금은 값이 있어도 읽을
    # 원자료가 없고, 없는 채로 두면 연관어 쌍까지 큐에 올라간다 — 자동 병합은 안 되니
    # 안전하지만 검수자가 지친다. 그 상태를 [10] 후속 표에 올려 뒀다.
    review_npmi_ceiling: float | None

    # 규격이 고정한 값. 필드로 두는 이유는 판정 함수가 설정을 하나만 받게 하려는 것이다.
    min_sources: int = MIN_SOURCES

    @classmethod
    def from_config(cls, config: Config) -> "RegistryThresholds":
        section = config.section(SECTION)
        missing = [key for key in REQUIRED if _lookup(section, key) is None]
        if missing:
            raise ConfigError(
                "extract.registry 임계값이 비어 있다 — 후보 분포를 재기 전이면 local.yaml 의 "
                "잠정값으로 돌린다 ([10 §4] S6): "
                f"{', '.join(f'{SECTION}.{key}' for key in missing)}"
            )
        absent = [key for key in CONFIGURED if _lookup(section, key) is None]
        if absent:
            raise ConfigError(
                "extract.registry 설정이 비어 있다 — base.yaml 이 채우는 값이라 코드가 "
                "기본값을 갖지 않는다 ([09 §3]): "
                f"{', '.join(f'{SECTION}.{key}' for key in absent)}"
            )
        plural = section.get("plural") or {}
        abbreviation = section.get("abbreviation") or {}
        variant = section.get("variant") or {}
        promote = section.get("promote") or {}
        embedding = section.get("embedding") or {}
        review = section.get("review") or {}
        model = embedding.get("model") or None
        return cls(
            plural_df_dominance=float(plural["df_dominance"]),
            abbreviation_min_documents=int(abbreviation["min_documents"]),
            variant_min_length=int(variant["min_length"]),
            variant_max_edit_distance=int(variant["max_edit_distance"]),
            variant_df_dominance=float(variant["df_dominance"]),
            variant_max_index_size=int(variant["max_index_size"]),
            promote_min_documents=int(promote["min_documents"]),
            promote_min_observed_days=int(promote["min_observed_days"]),
            promote_min_authors=int(promote["min_authors"]),
            promote_min_representative_ratio=float(promote["min_representative_ratio"]),
            embedding_model=None if model is None else str(model),
            embedding_dim=int(embedding["dim"]),
            embedding_batch_size=int(embedding["batch_size"]),
            review_similarity_floor=_optional_float(review.get("similarity_floor")),
            review_npmi_ceiling=_optional_float(review.get("npmi_ceiling")),
        ).validated()

    @property
    def layer3_enabled(self) -> bool:
        """층 3 을 돌릴지. 모델이 없으면 임베딩 계산도 검수 큐 적재도 하지 않는다."""
        return self.embedding_model is not None

    def validated(self) -> "RegistryThresholds":
        if self.plural_df_dominance < 1:
            raise ConfigError(f"{SECTION}.plural.df_dominance 는 1 이상이어야 한다")
        if self.abbreviation_min_documents < 1:
            raise ConfigError(f"{SECTION}.abbreviation.min_documents 는 1 이상이어야 한다")
        if self.variant_min_length < 1:
            raise ConfigError(f"{SECTION}.variant.min_length 는 1 이상이어야 한다")
        if self.variant_max_edit_distance < 1:
            raise ConfigError(f"{SECTION}.variant.max_edit_distance 는 1 이상이어야 한다")
        if self.variant_df_dominance < 1:
            raise ConfigError(f"{SECTION}.variant.df_dominance 는 1 이상이어야 한다")
        if self.variant_max_index_size < 1:
            raise ConfigError(f"{SECTION}.variant.max_index_size 는 1 이상이어야 한다")
        if self.promote_min_documents < 1:
            raise ConfigError(f"{SECTION}.promote.min_documents 는 1 이상이어야 한다")
        if self.promote_min_observed_days < 1:
            raise ConfigError(f"{SECTION}.promote.min_observed_days 는 1 이상이어야 한다")
        if self.promote_min_authors < 1:
            raise ConfigError(f"{SECTION}.promote.min_authors 는 1 이상이어야 한다")
        if not 0 <= self.promote_min_representative_ratio <= 1:
            raise ConfigError(f"{SECTION}.promote.min_representative_ratio 는 0~1 이어야 한다")
        if self.embedding_dim < 1:
            raise ConfigError(f"{SECTION}.embedding.dim 은 1 이상이어야 한다")
        if self.embedding_batch_size < 1:
            raise ConfigError(f"{SECTION}.embedding.batch_size 는 1 이상이어야 한다")
        if self.layer3_enabled and self.review_similarity_floor is None:
            # 모델이 있는데 문턱이 없으면 모든 쌍이 큐에 올라간다. 그건 큐가 아니라 목록이다.
            raise ConfigError(
                f"{SECTION}.embedding.model 이 설정됐으면 "
                f"{SECTION}.review.similarity_floor 도 있어야 한다"
            )
        if self.review_similarity_floor is not None and not 0 <= self.review_similarity_floor <= 1:
            raise ConfigError(f"{SECTION}.review.similarity_floor 는 0~1 이어야 한다")
        if self.review_npmi_ceiling is not None and not -1 <= self.review_npmi_ceiling <= 1:
            raise ConfigError(f"{SECTION}.review.npmi_ceiling 은 -1~1 이어야 한다")
        return self


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _lookup(section: dict[str, Any], dotted: str) -> Any:
    node: Any = section
    for part in dotted.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node
