"""후보 필터 ([04 §5]). 층 1."""

from __future__ import annotations

import pytest

from trendin.spark.extract import filters
from trendin.spark.extract.filters import CandidateLimits, df_bounds, df_reason, rejection_reason
from trendin.spark.extract.lexicon import Lexicon

LEXICON = Lexicon.of(stopwords=["thing", "이번"], noise=["tmp", "foo", "json"])
LIMITS = CandidateLimits(min_chars=2, max_chars=20)


def reason(key):
    return rejection_reason(key, lexicon=LEXICON, limits=LIMITS)


@pytest.mark.parametrize("key", ["2026", "3.12", "---", "a", "ㄱ", "29,000원", "30%", "$99"])
def test_형태_필터_숫자만_기호만_한_글자_가격(key):
    assert reason(key) == filters.SHAPE


def test_길이_필터():
    assert reason("x" * 21) == filters.LENGTH
    assert reason("x" * 20) is None


def test_불용어():
    assert reason("thing") == filters.STOPWORD
    assert reason("이번") == filters.STOPWORD


def test_노이즈는_모든_토큰이_노이즈일_때만():
    assert reason("tmp") == filters.NOISE
    assert reason("tmp foo") == filters.NOISE
    # 하나만 노이즈인 n-gram 은 살린다 — 문장 속 단어로 쓰인 것까지 지우면 과하다.
    assert reason("tmp directory") is None


def test_순서대로_싼_것부터():
    """형태가 불용어보다 먼저다 — 한 글자 불용어는 SHAPE 다."""
    lexicon = Lexicon.of(stopwords=["a"])
    assert rejection_reason("a", lexicon=lexicon, limits=LIMITS) == filters.SHAPE


def test_통과():
    assert reason("ballet sneakers") is None
    assert reason("python 3.12") is None  # 숫자 꼬리는 형태 필터에 걸리지 않는다


# --- DF 경계 — 비율 ([04 §5] 5·6번) --------------------------------------------


def test_비율이_문서_수로_환산된다():
    bounds = df_bounds(700, min_ratio=0.005, max_ratio=0.3)
    assert (bounds.low, bounds.high) == (4, 210)  # ceil(3.5), floor(210)


def test_하한은_최소_1_이다():
    assert df_bounds(10, min_ratio=0.0, max_ratio=0.5).low == 1


def test_작은_코퍼스에서_상한이_하한_아래로_내려가지_않는다():
    """문서 1건 코퍼스에서 `floor(0.5 × 1) = 0` 이면 전부 "너무 흔하다" 로 사라진다."""
    bounds = df_bounds(1, min_ratio=0.01, max_ratio=0.5)
    assert (bounds.low, bounds.high) == (1, 1)
    assert df_reason(1, bounds) is None


def test_경계_판정():
    bounds = df_bounds(100, min_ratio=0.02, max_ratio=0.5)
    assert df_reason(1, bounds) == filters.DF_LOW
    assert df_reason(2, bounds) is None
    assert df_reason(50, bounds) is None
    assert df_reason(51, bounds) == filters.DF_HIGH


def test_코퍼스가_자라면_같은_비율이_다른_절대값이_된다():
    """절대값으로 걸면 초기에는 전부 통과하고 반년 뒤에는 전부 탈락한다 — 비율인 이유."""
    early = df_bounds(200, min_ratio=0.01, max_ratio=0.3)
    later = df_bounds(20000, min_ratio=0.01, max_ratio=0.3)
    assert early.low == 2 and later.low == 200
