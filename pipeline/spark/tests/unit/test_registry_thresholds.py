"""[05] 의 문턱 ([05 §5]). 층 1.

**비어 있으면 Job 이 거부한다.** `extract/thresholds.py` 와 같은 규약이고 이유는 더 강하다 —
승격은 되돌릴 수 없으므로([05 §1]) 근거 없는 문턱으로 서비스 테이블에 행을 넣는 것보다
시작을 거부하는 것이 싸다.
"""

from __future__ import annotations

import pytest
from registry_support import make_registry_thresholds as thresholds

from trendin.spark.common.config import Config, ConfigError
from trendin.spark.registry.thresholds import CONFIGURED, REQUIRED, RegistryThresholds

# `local.yaml`(측정 대상, `REQUIRED`) 과 `base.yaml`(형태, `CONFIGURED`) 이 합쳐진 모습이다.
# 코드에 기본값이 없으므로 둘 중 하나라도 비면 시작하지 않는다.
LOCAL_VALUES = {
    "plural": {"df_dominance": 5},
    "abbreviation": {"min_documents": 3, "transliteration_floor": 0.5},
    "variant": {"min_length": 5, "max_edit_distance": 2, "df_dominance": 10,
                "max_index_size": 20000},
    "alias": {"max_group_size": 10},
    "promote": {
        "min_documents": 5,
        "min_observed_days": 2,
        "min_authors": 3,
        "min_representative_ratio": 0.6,
    },
    "embedding": {"model": None, "dim": 384, "batch_size": 64},
}


def config_of(registry: dict) -> Config:
    return Config({"extract": {"registry": registry}}, profile="test")


def test_채워진_설정은_통과한다():
    result = RegistryThresholds.from_config(config_of(LOCAL_VALUES))

    assert result.promote_min_authors == 3
    assert result.min_sources == 2, "규격이 고정한 값"
    assert not result.layer3_enabled


@pytest.mark.parametrize("missing", (*REQUIRED, *CONFIGURED))
def test_필수_키가_하나라도_비면_거부한다(missing):
    """`REQUIRED`(local.yaml 이 채움) 와 `CONFIGURED`(base.yaml 이 채움) 둘 다 없으면 죽는다.
    **코드가 기본값을 갖지 않는 것이 요점이다** — yaml 과 코드에 같은 숫자가 둘 있으면
    한쪽만 고쳐졌을 때 조용히 갈린다."""
    values = {section: dict(inner) for section, inner in LOCAL_VALUES.items()}
    section, _, key = missing.partition(".")
    values[section].pop(key)

    with pytest.raises(ConfigError, match=missing):
        RegistryThresholds.from_config(config_of(values))


def test_모델이_있는데_유사도_문턱이_없으면_거부한다():
    """문턱이 없으면 모든 쌍이 큐에 올라간다. 그건 큐가 아니라 목록이다."""
    values = {**LOCAL_VALUES, "embedding": {**LOCAL_VALUES["embedding"], "model": "hash"}}

    with pytest.raises(ConfigError, match="similarity_floor"):
        RegistryThresholds.from_config(config_of(values))


def test_비어_있는_설정의_오류_메시지가_어디를_고칠지_말한다():
    with pytest.raises(ConfigError, match=r"local\.yaml"):
        RegistryThresholds.from_config(Config({}, profile="test"))


@pytest.mark.parametrize(
    "override",
    [
        {"plural_df_dominance": 0.5},
        {"variant_df_dominance": 0.9},
        {"promote_min_authors": 0},
        {"promote_min_representative_ratio": 1.5},
        {"variant_max_edit_distance": 0},
        {"review_npmi_ceiling": 2.0},
    ],
)
def test_말이_안_되는_값은_거부한다(override):
    """검사는 `validated()` 가 한다 — 생성자는 시험이 이상한 값을 만들 수 있게 그냥 둔다."""
    with pytest.raises(ConfigError):
        thresholds(**override).validated()
