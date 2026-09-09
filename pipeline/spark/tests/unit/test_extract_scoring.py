"""스코어링과 선별 ([04 §6·§7]). 층 1."""

from __future__ import annotations

import math

import pytest

from trendin.spark.extract.scoring import (
    ScoreWeights,
    bm25,
    bm25_idf,
    c_value,
    combine,
    minmax,
    select,
    title_axis,
)

# --- C-value ---------------------------------------------------------------------


def test_늘_긴_후보_안에서만_나오는_짧은_후보는_0():
    """`agentic workflow` 200회, `workflow` 200회가 전부 그 안 — `workflow` 는 독립 키워드가
    아니다."""
    assert c_value(1, 200, [200]) == 0.0


def test_독립적으로도_나오면_살아남는다():
    """[04 §6] 의 예시 — `workflow` 가 500회 나오면 둘 다 살아남는다."""
    assert c_value(1, 500, [200]) > 0
    assert c_value(2, 200, []) > 0


def test_단일_토큰도_빈도에_비례한다():
    """`log2(|a|)` 였다면 여기서 늘 0 이라 위 예시가 성립하지 않는다 (`scoring.c_value` 의 근거)."""
    assert c_value(1, 10) == pytest.approx(math.log2(2) * 10)


def test_긴_후보에_가산점():
    assert c_value(3, 10) > c_value(2, 10) > c_value(1, 10)


def test_음수는_0_에서_자른다():
    assert c_value(1, 5, [10]) == 0.0


# --- BM25 -----------------------------------------------------------------------


def test_idf_는_흔할수록_낮고_음수가_되지_않는다():
    assert bm25_idf(1, 100) > bm25_idf(50, 100) > bm25_idf(99, 100) > 0


def test_tf_에_따라_오르되_포화한다():
    idf = bm25_idf(5, 100)
    one = bm25(1, doc_len=100, avg_doc_len=100, idf=idf)
    two = bm25(2, doc_len=100, avg_doc_len=100, idf=idf)
    ten = bm25(10, doc_len=100, avg_doc_len=100, idf=idf)
    assert one < two < ten
    assert (ten - two) < 8 * (two - one)  # 포화


def test_긴_문서의_같은_tf_는_덜_중요하다():
    """TF-IDF 와 갈리는 지점 — 문서 길이 정규화 ([04 §6])."""
    idf = bm25_idf(5, 100)
    short = bm25(3, doc_len=50, avg_doc_len=100, idf=idf)
    long = bm25(3, doc_len=400, avg_doc_len=100, idf=idf)
    assert short > long


def test_tf_0_과_분모_0():
    assert bm25(0, doc_len=10, avg_doc_len=10, idf=1.0) == 0.0
    # 평균 길이 0 (빈 코퍼스) 이어도 죽지 않는다.
    assert bm25(1, doc_len=10, avg_doc_len=0, idf=1.0) > 0


# --- 정규화 · 결합 ------------------------------------------------------------------


def test_minmax():
    assert minmax(5, 0, 10) == 0.5
    assert minmax(0, 0, 10) == 0.0 and minmax(10, 0, 10) == 1.0


def test_축의_값이_전부_같으면_값_유무로_정한다():
    """후보 하나짜리 문서에서 제목에 없고 C-value 0 인 후보가 1 점을 받으면 안 된다."""
    assert minmax(0, 0, 0) == 0.0
    assert minmax(3, 3, 3) == 1.0


def test_가중합은_0_1_척도다():
    weights = ScoreWeights(c_value=0.3, bm25=0.4, title=0.3)
    assert combine(1, 1, 1, weights) == pytest.approx(1.0)
    assert combine(0, 0, 0, weights) == 0.0
    assert combine(0, 0, 1, weights) == pytest.approx(0.3)


def test_가중치가_전부_0_이면_0():
    assert combine(1, 1, 1, ScoreWeights(0, 0, 0)) == 0.0


def test_위치_축은_있고_없고다():
    assert title_axis(0) == 0.0 and title_axis(1) == 1.0 and title_axis(5) == 1.0


# --- 선별 ([04 §7]) -----------------------------------------------------------------


def test_상위_K_이고_하한_이상():
    scored = [("a", 0.9), ("b", 0.5), ("c", 0.1), ("d", 0.7)]
    assert select(scored, top_k=3, floor=0.4) == ["a", "d", "b"]
    assert select(scored, top_k=2, floor=0.4) == ["a", "d"]
    # 키워드가 적은 문서에서 억지로 K 를 채우지 않는다.
    assert select(scored, top_k=10, floor=0.6) == ["a", "d"]


def test_동점은_사전순_결정적():
    assert select([("z", 0.5), ("a", 0.5), ("m", 0.5)], top_k=2, floor=0) == ["a", "m"]


def test_후보_하나_와_빈_목록():
    assert select([("only", 0.3)], top_k=5, floor=0.2) == ["only"]
    assert select([], top_k=5, floor=0.2) == []
