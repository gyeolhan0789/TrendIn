"""층 3 임베딩 ([05 §4], [01 §5]). 층 1.

**배선 회귀가 목적이다.** 실제 모델은 설정으로 두고 기본이 `null` 이므로
(`conf/base.yaml`), 여기서 지키는 것은 "모델을 붙였을 때 깨지지 않는 형태" 다 —
클로저에 무엇이 들어가는지, 캐시가 적중하는지, 제공자가 프로세스당 하나인지.
"""

from __future__ import annotations

import dataclasses
import pickle

import pytest
from registry_support import make_registry_thresholds as thresholds

from trendin.spark.registry import embedding
from trendin.spark.registry.embedding import EmbeddingSpec, HashProvider

DOMAIN = "fashion"
SPEC = EmbeddingSpec(model=embedding.MODEL_HASH, dim=16, batch_size=4)


def test_설정은_pickle_되고_모델_객체는_클로저에_없다():
    """**배선 회귀** ([01 §5]). `extract/morphology.py` 의 같은 시험과 한 쌍이다 — 모델을
    클로저로 보내면 대개 pickle 이 안 되고, 되더라도 태스크마다 전송된다.

    `provider_for` 를 `mapInPandas` 안에서 부르는 형태로 옮길 때 이 성질이 조건이다
    (`registry/embedding.py` 의 `pandas_udf` 절).
    """
    pickle.loads(pickle.dumps(SPEC))

    assert isinstance(embedding.provider_for(SPEC), HashProvider)
    # spec 이 담는 것은 원시값뿐이다 — 모델 객체가 한 칸이라도 들어가면 위 pickle 이 그것을
    # 함께 실어 보내고, 실제 모델에서는 그 자리에서 `TypeError` 로 죽는다.
    assert all(
        isinstance(getattr(SPEC, field.name), (str, int)) for field in dataclasses.fields(SPEC)
    )
    # 그리고 캐시 키가 되려면 해시 가능해야 한다.
    assert hash(SPEC)


def test_제공자는_spec_당_하나다():
    """모듈 수준 lazy singleton ([01 §5]). 워커 프로세스가 태스크 사이에 살아남으므로
    프로세스당 한 번 만들어진다."""
    assert embedding.provider_for(SPEC) is embedding.provider_for(SPEC)
    assert embedding.provider_for(SPEC) is not embedding.provider_for(
        EmbeddingSpec(model=embedding.MODEL_HASH, dim=8)
    )


def test_캐시에_있는_표기는_다시_계산하지_않는다():
    """**표기가 바뀌지 않으면 다시 계산하지 않는다** ([01 §5])."""
    cached = {"데님": embedding.provider_for(SPEC).encode(["데님"])[0]}

    fresh = embedding.encode_missing(["데님", "코트"], cached=cached, spec=SPEC)

    assert list(fresh) == ["코트"]


def test_같은_표기는_같은_벡터를_받는다():
    """`HashProvider` 는 결정적이다 — 그래서 시험이 재실행마다 같은 결과를 낸다."""
    first = embedding.provider_for(SPEC).encode(["데님"])
    second = embedding.provider_for(SPEC).encode(["데님"])

    assert first == second
    assert len(first[0]) == SPEC.dim


def test_벡터는_JSON_왕복을_견딘다():
    """`pl_embedding_cache` 가 `jsonb` 라 그 경로로 오간다 ([08 §4] 배열·enum 절)."""
    vector = embedding.provider_for(SPEC).encode(["코트"])[0]

    restored = embedding.vector_from_json(embedding.vector_to_json(vector))

    assert restored is not None
    assert len(restored) == SPEC.dim
    assert restored == pytest.approx(vector, abs=1e-6)


def test_형태가_깨진_캐시는_다시_계산한다():
    assert embedding.vector_from_json(None) is None
    assert embedding.vector_from_json("깨진 값") is None
    assert embedding.vector_from_json("[]") is None


def test_유사도가_문턱_이상인_쌍만_큐_후보가_된다():
    vectors = {"a": [1.0, 0.0], "b": [0.99, 0.14], "c": [0.0, 1.0]}
    keys = {"a": "alpha", "b": "beta", "c": "gamma"}

    pairs = embedding.similar_pairs(vectors, domain=DOMAIN, keys_by_surface=keys, floor=0.9)

    assert [(pair.representative, pair.absorbed) for pair in pairs] == [("alpha", "beta")]
    assert pairs[0].layer == embedding.LAYER_EMBEDDING


def test_NPMI_가_상한을_넘으면_연관어로_보고_큐에_올리지_않는다():
    """[05 §4] 의 표 셋째 줄. **지금은 NPMI 가 없어 이 분기가 놀고 있다** — [06] 이 값을
    주면 그때 갈린다."""
    vectors = {"a": [1.0, 0.0], "b": [0.99, 0.14]}
    keys = {"a": "alpha", "b": "beta"}

    pairs = embedding.similar_pairs(
        vectors,
        domain=DOMAIN,
        keys_by_surface=keys,
        floor=0.9,
        npmi={("alpha", "beta"): 0.7},
        npmi_ceiling=0.3,
    )

    assert pairs == ()


def test_모델이_없으면_층_3_이_꺼진다():
    """기본 구성이다 (`conf/base.yaml`). 배선은 있고 계산이 안 돈다."""
    assert not thresholds().layer3_enabled
    assert thresholds(embedding_model="hash", review_similarity_floor=0.9).layer3_enabled
