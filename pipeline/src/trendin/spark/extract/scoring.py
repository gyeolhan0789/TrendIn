"""점수 ([04 §6](../../../../spark/docs/04-keyword-extraction-spec.md)).

**축이 다섯에서 하나로 줄었다** (2026-09-16). 후보의 점수는 이제 실체 인식 모델이 준
확률이고 (`extract/document._score`), 이 파일에는 기록용 BM25 만 남는다.

## 없어진 것

| | 왜 |
| --- | --- |
| C-value | n-gram 조각이 애초에 생기지 않는다. 구간을 모델이 준다 |
| `latin` · `proper` 축 | 고유명사 인식이 모델 안에 있다. `is_proper` 는 라벨에서 온다 |
| 다섯 축 가중합 · 문서 안 정규화 | 점수가 하나라 합칠 것도 척도를 맞출 것도 없다 |

가중합을 없앤 것이 이 교체에서 가장 큰 단순화다. 옛 경로는 빈도(1~50) · C-value · 위치
(0/1)를 문서 안에서 0~1 로 정규화한 뒤 가중치 다섯 개로 합쳤고, 그 가중치가 전부 측정
없이는 정할 수 없는 값이었다.

## BM25 를 남긴 이유

**점수에 넣지 않고 칸에만 적는다.** 옛 경로의 값어치는 상위권이 아니라 꼬리 쪽 재현율에
있었고 (`scratchpad/kwlab/RESULTS.md` §2.1), 나중에 축으로 되살릴지는 실데이터를 보고 정할
일이다. 적어 두지 않으면 그 판단을 하려고 재추출해야 한다.

선별(상위 K · 하한)은 여기 없다. 순수 파이썬 구현을 두었다가 2026-09-17 에 지웠다 —
`extract/batch.py` 가 Spark 창함수로 같은 일을 하고 있어 아무도 부르지 않았고, 둘이
갈려도 테스트가 통과하는 상태였다.

**pyspark 를 import 하지 않는다** ([09 §4] 층 1).
"""

from __future__ import annotations

import math


def bm25_idf(df: int, corpus_size: int) -> float:
    """Robertson 의 IDF. `+1` 안쪽에 있어 df 가 코퍼스의 절반을 넘어도 음수가 되지 않는다."""
    return math.log(1.0 + (corpus_size - df + 0.5) / (df + 0.5))


def bm25(
    tf: int, *, doc_len: int, avg_doc_len: float, idf: float, k1: float = 1.2, b: float = 0.75
) -> float:
    """문서 하나 · 후보 하나의 BM25. 길이 정규화 항이 소스 간 글 길이 차이를 흡수한다.

    `doc_len` 은 글자 수다 (`document.DocumentExtraction.doc_len`). 언어마다 어절 수의
    척도가 달라 토큰 수를 쓰지 않는다.
    """
    if tf <= 0:
        return 0.0
    ratio = (doc_len / avg_doc_len) if avg_doc_len > 0 else 1.0
    norm = k1 * (1.0 - b + b * ratio)
    return idf * (tf * (k1 + 1.0)) / (tf + norm)
