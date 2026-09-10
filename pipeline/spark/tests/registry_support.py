"""[05] 시험이 함께 쓰는 문턱 생성자.

`conftest.py` 에 두고 `from conftest import ...` 로 가져오면 층 2 의
`tests/spark/conftest.py` 와 이름이 충돌한다 — 전체 수집에서 어느 쪽이 잡히는지가
디렉터리 순서에 달린다. 그래서 고유한 이름의 모듈로 둔다 (`tests/conftest.py` 가 이
디렉터리를 sys.path 에 넣는다).
"""

from __future__ import annotations

from trendin.spark.registry.thresholds import RegistryThresholds

# `spark/conf/local.yaml` 의 잠정값과 같은 숫자다. 시험이 설정 파일을 읽지 않는 이유는 그
# 값이 S6 에서 바뀔 예정이고, 바뀔 때 판정 시험이 함께 빨개지면 무엇이 깨진 것인지 알 수
# 없기 때문이다 — **판정과 설정을 따로 지킨다.**
DEFAULTS = dict(
    plural_df_dominance=5.0,
    abbreviation_min_documents=3,
    variant_min_length=5,
    variant_max_edit_distance=2,
    variant_df_dominance=10.0,
    variant_max_index_size=20000,
    promote_min_documents=5,
    promote_min_observed_days=2,
    promote_min_authors=3,
    promote_min_representative_ratio=0.6,
    embedding_model=None,
    embedding_dim=8,
    embedding_batch_size=4,
    review_similarity_floor=None,
    review_npmi_ceiling=None,
)


def make_registry_thresholds(**overrides) -> RegistryThresholds:
    """문턱 하나만 바꿔 그 조건이 걸리는지 보는 시험용 생성자.

    **`validated()` 를 부르지 않는다** — 말이 안 되는 값을 만들어 검사가 잡는지 보는
    시험이 있어서다 (`test_registry_thresholds.py`).
    """
    return RegistryThresholds(**{**DEFAULTS, **overrides})
