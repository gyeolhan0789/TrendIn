"""후보 필터 (`extract/filters.py`). 층 1 ([09 §4]).

**필터가 넷에서 둘로 줄었다** (2026-09-16) — 불용어와 노이즈 사전이 없어졌다. 형태와 길이만
남았고, 라벨 제한은 `extract/adapters.py` 가 한다.
"""

from __future__ import annotations

import pytest

from trendin.spark.extract.filters import CandidateLimits, rejection_reason

LIMITS = CandidateLimits(min_chars=2, max_chars=40)


def reason(key: str) -> str | None:
    return rejection_reason(key, limits=LIMITS)


@pytest.mark.parametrize(
    "key",
    [
        "2026",  # 숫자만
        "---",  # 기호만
        "a",  # 한 글자
        "29,000원",  # 가격
        "55,000円",  # 일본어 가격 — 소스가 늘면서 필요해졌다
        "2026年",  # 연도
        "30%",
    ],
)
def test_형태_필터(key):
    assert reason(key) == "SHAPE"


def test_길이_필터():
    assert reason("x" * 41) == "LENGTH"
    assert reason("x" * 40) is None


@pytest.mark.parametrize("key", ["chanel", "데님 팬츠", "ケンゾー", "wide-leg trousers", "c++"])
def test_통과(key):
    assert reason(key) is None


def test_형태를_길이보다_먼저_본다():
    """한 글자는 길이 하한에도 걸리지만 형태가 더 싼 판정이다."""
    assert reason("7") == "SHAPE"
