"""점수 (`extract/scoring.py`). 층 1 ([09 §4]).

**축이 다섯에서 하나로 줄었다** (2026-09-16). 후보의 점수는 모델이 주고
(`extract/document._score`), 여기 남은 것은 기록용 BM25 뿐이다.

선별(상위 K · 하한)은 `extract/batch.py` 가 Spark 창함수로 하고, 그쪽 규칙은 층 2 의
`test_순위와_선별` 이 지킨다.
"""

from __future__ import annotations

from trendin.spark.extract.scoring import bm25, bm25_idf

# --- BM25 — 점수에 들어가지 않고 칸에만 적힌다 --------------------------------------


def test_idf_는_흔할수록_낮고_음수가_되지_않는다():
    assert bm25_idf(1, 1000) > bm25_idf(500, 1000) > 0
    assert bm25_idf(1000, 1000) > 0


def test_tf_에_따라_오르되_포화한다():
    idf = bm25_idf(10, 1000)
    at = lambda tf: bm25(tf, doc_len=1000, avg_doc_len=1000, idf=idf)  # noqa: E731

    assert at(1) < at(2) < at(10)
    # 한 번 더 나올 때의 증가분이 점점 작아진다 — 그것이 `k1` 이 하는 일이다.
    assert (at(10) - at(9)) < (at(2) - at(1))


def test_긴_문서의_같은_tf_는_덜_중요하다():
    idf = bm25_idf(10, 1000)
    short = bm25(3, doc_len=500, avg_doc_len=1000, idf=idf)
    long = bm25(3, doc_len=2000, avg_doc_len=1000, idf=idf)
    assert short > long


def test_tf_0_과_분모_0():
    idf = bm25_idf(10, 1000)
    assert bm25(0, doc_len=1000, avg_doc_len=1000, idf=idf) == 0.0
    # 코퍼스가 비어 평균 길이가 0 이어도 죽지 않는다 — 첫 실행에서 실제로 일어난다.
    assert bm25(1, doc_len=100, avg_doc_len=0.0, idf=idf) > 0
