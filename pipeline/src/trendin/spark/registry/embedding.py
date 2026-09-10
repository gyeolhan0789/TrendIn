"""층 3 — 임베딩은 후보만 만든다 ([05 §4], [01 §5]).

**자동 병합하지 않는다.** 임베딩은 "관련 있음" 과 "같음" 을 구분하지 못한다 — `React` 와
`Vue` 는 유사도가 매우 높지만 합치면 서비스가 망가진다. [05 §1] 때문에 잘못 병합하면
되돌리기가 거의 불가능하고, 자동화의 이득보다 사고 비용이 훨씬 크다.

| 상황 | 처리 |
| --- | --- |
| 유사도 높음 + 층 2 증거 있음 | 층 2 규칙대로 자동 병합. 임베딩은 확인 역할 |
| 유사도 높음 + NPMI 낮음 | **검수 큐**로. 동의어 후보 |
| 유사도 높음 + NPMI 높음 | 병합하지 않는다. 연관어다 → [06] |
| 유사도 낮음 | 무관 |

## ⚠️ NPMI 가 아직 없다

[05 §3] 이 "NPMI 계산은 [06] 이 하고 05 는 그 값을 읽어 판별에 쓴다" 로 정했고, [06] 은
[10 §1] 이 **다음 에픽**으로 뺐다. 그래서 위 표의 둘째·셋째 줄이 지금 갈리지 않는다 —
연관어 쌍까지 검수 큐에 올라온다. **자동 병합은 안 되니 위험하지 않고 검수자가 지친다.**
`review.npmi_ceiling` 자리를 비워 둔 채로 두고, 값이 생기면 판별이 그때 갈린다.

## 모델은 설정이고, 배선은 코드다

`extract.registry.embedding.model` 이 `null` 이면 이 층이 아예 돌지 않는다. 기본이 그렇다 —
실제 모델(`sentence-transformers`)은 torch 를 끌고 와 이미지가 1 GB 이상 커지고, NPMI 가
없는 동안은 판별이 반쪽이라 지금 붙일 이유가 없다 ([10] 후속 표).

**배선·캐시·테스트는 진짜다.** 아래 네 가지가 [01 §5] 가 요구한 형태 그대로다.

| [01 §5] 의 요구 | 여기서 |
| --- | --- |
| 모델 객체를 클로저로 보내지 않는다 | 클로저에 담는 것은 `EmbeddingSpec` 뿐 —
  **작고 해시 가능해야** 캐시 키가 된다 |
| 모듈 수준 lazy singleton | `_CACHE: dict[EmbeddingSpec, Provider]` — spec 별로 하나 |
| 이미지에 포함, 런타임에 받지 않는다 | 모델을 설정으로 두고, 켜는 쪽이 이미지에 넣는다 |
| 계산된 벡터를 내부 테이블에 캐시 | `pl_embedding_cache` (`io/keywords.py`) |

## ⚠️ `pandas_udf` 가 아니라 드라이버에서 배치로 돈다

[01 §5] 는 배치 추론을 `mapInPandas`·`pandas_udf` 로 하라고 적었는데 여기서는 드라이버에서
한 번에 인코딩한다. 근거는 규모다 — 대상이 문서가 아니라 **사용자에게 보이게 될 표기**라
수백~수천이고([01 §5] "고유 키워드 수천 개는 몇 초다"), executor 로 흩으면 워커마다 모델을
한 번씩(110 MB~수백 MB) 올리는 비용이 계산보다 크다. `pandas`·`pyarrow` 를 이미지에 넣지
않아도 되는 것이 부수 효과다 (지금 둘 다 없다).

**옮겨야 할 때 바뀌는 것은 부르는 자리 하나다.** `provider_for(spec)` 를 `mapInPandas` 안에서
부르면 그대로 executor 당 1회 로드가 된다 — spec 이 picklable 이고 provider 가 아닌 것을
층 1 테스트가 지킨다 (`test_registry_embedding.py`, `extract/morphology.py` 와 같은 방식).

**pyspark 를 import 하지 않는다** ([09 §4] 층 1).
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from trendin.spark.common.logging import get_logger
from trendin.spark.registry.merge import MergePair, signal_of
from trendin.spark.registry.review import LAYER_EMBEDDING

log = get_logger(__name__)

# 의존성 없이 도는 결정적 제공자. 층 1·2 테스트와, 모델을 붙이기 전에 배선을 돌려 보는 데
# 쓴다. **실제 의미를 담지 않는다** — 같은 표기가 같은 벡터를 받을 뿐이라 유사도가 무의미하다.
MODEL_HASH = "hash"

RULE_EMBEDDING = "embedding"


@dataclass(frozen=True, slots=True)
class EmbeddingSpec:
    """executor 로 건너갈 수 있는 것 전부. **작고 해시 가능해야** 캐시 키가 된다.

    모델 객체가 여기 없는 것이 요점이다 ([01 §5]) — 대개 pickle 이 안 되고, 되더라도
    태스크마다 전송된다. `extract/morphology.AnalyzerSpec` 와 같은 형태다.
    """

    model: str
    dim: int = 384
    batch_size: int = 64


class Provider(Protocol):
    """표기 여럿 → 단위 벡터 여럿. 순서를 지킨다."""

    dim: int

    def encode(self, surfaces: Sequence[str]) -> list[list[float]]: ...


# 모듈 수준 lazy singleton. 워커 프로세스가 태스크 사이에 살아남으므로
# (`spark.python.worker.reuse` 기본 참) 프로세스당 한 번 만들어진다 — 드라이버에서 부르면
# 드라이버에 하나다.
_CACHE: dict[EmbeddingSpec, Provider] = {}


def provider_for(spec: EmbeddingSpec) -> Provider:
    """spec 하나에 제공자 하나. 두 번째 호출부터 이미 만들어진 것을 준다."""
    provider = _CACHE.get(spec)
    if provider is None:
        provider = _build(spec)
        _CACHE[spec] = provider
        log.info("임베딩 제공자 준비: model=%s dim=%d", spec.model, provider.dim)
    return provider


def _build(spec: EmbeddingSpec) -> Provider:
    if spec.model == MODEL_HASH:
        return HashProvider(dim=spec.dim)
    return SentenceTransformerProvider(spec)


class HashProvider:
    """표기의 해시를 벡터로 펼친다. 결정적이고 의존성이 없다.

    유사도에 의미가 없으므로 **이것으로 검수 큐를 채우면 잡음만 쌓인다.** 배선이 도는지를
    보는 용도이고, 그래서 층 2 테스트도 이 제공자로 "쌍이 큐에 들어가는 경로" 만 검증한다.
    """

    def __init__(self, *, dim: int) -> None:
        self.dim = dim

    def encode(self, surfaces: Sequence[str]) -> list[list[float]]:
        return [self._one(surface) for surface in surfaces]

    def _one(self, surface: str) -> list[float]:
        raw = b""
        # 필요한 길이만큼 해시를 이어 붙인다. 같은 입력에 같은 출력이면 충분하다.
        while len(raw) < self.dim * 2:
            raw = hashlib.sha256(raw + surface.encode("utf-8")).digest() + raw
        values = [
            int.from_bytes(raw[index * 2 : index * 2 + 2], "big") / 65535.0 - 0.5
            for index in range(self.dim)
        ]
        return _unit(values)


class SentenceTransformerProvider:
    """`sentence-transformers` 모델. **런타임에 인터넷에서 받지 않는다** ([01 §5]).

    import 를 생성 시점까지 늦춘다 — 모듈을 import 하는 것만으로 torch 가 올라오면
    임계값 검사나 층 1 테스트처럼 임베딩과 무관한 경로가 함께 느려진다.
    """

    def __init__(self, spec: EmbeddingSpec) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as error:  # pragma: no cover — 의존성이 없는 것이 기본이다
            raise RuntimeError(
                "extract.registry.embedding.model 이 설정됐는데 sentence-transformers 가 "
                f"없다 (model={spec.model}). 이미지에 넣거나 model 을 null 로 두어 층 3 을 "
                f"끈다 — 또는 {MODEL_HASH} 로 배선만 돌린다 ([05 §4])"
            ) from error
        self._model = SentenceTransformer(spec.model)
        self._batch_size = spec.batch_size
        self.dim = int(self._model.get_sentence_embedding_dimension() or spec.dim)

    def encode(self, surfaces: Sequence[str]) -> list[list[float]]:
        vectors = self._model.encode(
            list(surfaces),
            batch_size=self._batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return [[float(value) for value in row] for row in vectors]


def encode_missing(
    surfaces: Iterable[str], *, cached: Mapping[str, Sequence[float]], spec: EmbeddingSpec
) -> dict[str, list[float]]:
    """캐시에 없는 표기만 인코딩한다. **표기가 바뀌지 않으면 다시 계산하지 않는다** ([01 §5]).

    돌려주는 것은 **이번에 새로 계산한 것만**이다. 부른 쪽이 그것만 `pl_embedding_cache`
    에 넣으면 되고, 유사도 계산에는 캐시와 합쳐서 쓴다.
    """
    pending = sorted({surface for surface in surfaces if surface and surface not in cached})
    if not pending:
        return {}
    vectors = provider_for(spec).encode(pending)
    return dict(zip(pending, vectors))


def similar_pairs(
    vectors: Mapping[str, Sequence[float]],
    *,
    domain: str,
    keys_by_surface: Mapping[str, str],
    floor: float,
    npmi: Mapping[tuple[str, str], float] | None = None,
    npmi_ceiling: float | None = None,
) -> tuple[MergePair, ...]:
    """유사도가 문턱 이상인 쌍. **병합이 아니라 검수 큐 후보다** ([05 §4]).

    `keys_by_surface` 로 표기를 비교키로 되돌린다 — 임베딩은 표기에 걸고 병합은 비교키
    단위이기 때문이다. 대표·흡수 방향은 사전순으로 고정한다. 어느 쪽이 대표인지는 사람이
    정하므로 여기서 추측하지 않고, 다만 같은 쌍이 두 행이 되지 않게 순서만 정규화한다.

    `npmi` 가 주어지면 상한을 넘는 쌍(=연관어)을 뺀다. **지금은 주어지지 않는다** — 위
    docstring 의 경고.
    """
    surfaces = sorted(surface for surface in vectors if surface in keys_by_surface)
    if len(surfaces) < 2:
        return ()
    matrix = [_unit(list(vectors[surface])) for surface in surfaces]
    pairs: list[MergePair] = []
    for left_index, right_index, similarity in _above(matrix, floor):
        left_key = keys_by_surface[surfaces[left_index]]
        right_key = keys_by_surface[surfaces[right_index]]
        if left_key == right_key:
            continue
        representative, absorbed = sorted((left_key, right_key))
        value = None if npmi is None else npmi.get((representative, absorbed))
        if npmi_ceiling is not None and value is not None and value > npmi_ceiling:
            continue
        pairs.append(
            MergePair(
                domain=domain,
                representative=representative,
                absorbed=absorbed,
                layer=LAYER_EMBEDDING,
                rule=RULE_EMBEDDING,
                confidence=round(similarity, 4),
                signal=signal_of(
                    similarity=round(similarity, 4),
                    npmi=value,
                    surfaces=[surfaces[left_index], surfaces[right_index]],
                ),
            )
        )
    return tuple(pairs)


def _above(matrix: list[list[float]], floor: float) -> list[tuple[int, int, float]]:
    """단위 벡터 목록에서 코사인 유사도가 `floor` 이상인 (i, j, 값). i < j.

    numpy 가 있으면 행렬곱 한 번이다. 없으면 파이썬으로 돈다 — 층 3 이 꺼진 기본
    구성에서는 numpy 를 요구하지 않아야 해서 두 경로를 둔다.
    """
    try:
        import numpy as np
    except ImportError:  # pragma: no cover — numpy 는 보통 있다
        return _above_python(matrix, floor)
    array = np.asarray(matrix, dtype=np.float32)
    scores = array @ array.T
    rows, columns = np.triu_indices(len(matrix), k=1)
    mask = scores[rows, columns] >= floor
    return [
        (int(row), int(column), float(scores[row, column]))
        for row, column in zip(rows[mask], columns[mask])
    ]


def _above_python(matrix: list[list[float]], floor: float) -> list[tuple[int, int, float]]:
    found: list[tuple[int, int, float]] = []
    for left in range(len(matrix)):
        for right in range(left + 1, len(matrix)):
            score = sum(a * b for a, b in zip(matrix[left], matrix[right]))
            if score >= floor:
                found.append((left, right, score))
    return found


def vector_from_json(text: str | None) -> list[float] | None:
    """`pl_embedding_cache` 가 준 문자열 → 벡터. 형태가 깨졌으면 `None` — 다시 계산한다."""
    if not text:
        return None
    try:
        values = json.loads(text)
    except ValueError:
        return None
    if not isinstance(values, list) or not values:
        return None
    return [float(value) for value in values]


def vector_to_json(vector: Sequence[float]) -> str:
    """벡터 → `pl_embedding_cache` 에 넣을 문자열.

    `double precision[]` 컬럼이 아니라 `jsonb` 인 이유는 Spark JDBC 로 배열 컬럼에 직접
    쓸 수 없다고 보고 짜기 때문이다 ([08 §4] 배열·enum 절). 이 표는 드라이버가 쓰지만
    나중에 executor 로 옮겨도 형태를 안 바꾸게 둔다.
    """
    return json.dumps([round(float(value), 6) for value in vector])


def _unit(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in values))
    if norm == 0:
        return values
    return [value / norm for value in values]
