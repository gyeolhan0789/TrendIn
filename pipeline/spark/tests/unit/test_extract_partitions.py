"""추론 파티션 수 (`extract/batch.py` 의 `_partition_count`). 층 1.

세션도 프레임도 흉내로 충분하다 — 이 함수가 읽는 것은 코어 수와 문서 수 둘뿐이고, 그래서
Spark 없이 시험할 수 있다 ([09 §4] 층 1).

**여기서 지키려는 것은 GPU 의 안전장치다.** 모델은 executor 파이썬 프로세스마다 적재되므로
(`entities.recognizer_for`) 코어가 여럿이면 같은 가중치가 VRAM 에 여러 벌 올라간다. 터지는
자리가 `_predict_chunk` 의 `except` 안이라 **Job 은 후보 0건으로 정상 종료하고**, 로그를 안
보면 성공으로 오인한다.
"""

from __future__ import annotations

import pytest

from trendin.spark.common.config import ConfigError
from trendin.spark.extract.batch import MAX_DOCS_PER_PARTITION, _partition_count
from trendin.spark.extract.entities import RecognizerSpec


class FakeFrame:
    def __init__(self, documents: int) -> None:
        self._documents = documents

    def count(self) -> int:
        return self._documents


class FakeSession:
    def __init__(self, cores: int) -> None:
        self.sparkContext = type("Context", (), {"defaultParallelism": cores})()


def partitions(*, cores: int, documents: int, device: str = "cpu") -> int:
    return _partition_count(
        FakeSession(cores), FakeFrame(documents), recognizer=RecognizerSpec(device=device)
    )


# --- CPU — 종전 그대로 --------------------------------------------------------------


def test_코어_수에_맞춘다():
    """모델이 코어마다 적재되므로 코어를 놀리지 않는다."""
    assert partitions(cores=4, documents=100) == 4


def test_문서가_많으면_상한이_파티션을_늘린다():
    """파티션을 통째로 메모리에 올리므로(`_recognize`) 무한정 키우지 않는다."""
    documents = MAX_DOCS_PER_PARTITION * 3
    assert partitions(cores=2, documents=documents) == 3


def test_문서보다_많은_파티션을_만들지_않는다():
    assert partitions(cores=8, documents=3) == 3


def test_문서가_없어도_최소_하나다():
    assert partitions(cores=4, documents=0) == 1


# --- GPU — 워커가 하나여야 한다 -----------------------------------------------------


def test_GPU_에_코어가_여럿이면_시작_전에_거부한다():
    with pytest.raises(ConfigError, match="local\\[1\\]"):
        partitions(cores=4, documents=100, device="cuda")


def test_GPU_에_코어가_하나면_돈다():
    assert partitions(cores=1, documents=100, device="cuda") == 1


def test_GPU_라도_문서가_많으면_파티션은_나뉜다():
    """파티션이 나뉘어도 코어가 하나라 순차로 돌아 모델은 한 벌만 올라간다."""
    documents = MAX_DOCS_PER_PARTITION * 2
    assert partitions(cores=1, documents=documents, device="cuda") == 2


def test_장치_번호를_붙여도_막는다():
    with pytest.raises(ConfigError):
        partitions(cores=2, documents=100, device="cuda:1")
