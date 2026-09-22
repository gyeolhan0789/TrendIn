# 다국어 개념 후보 통합 재정렬

미등록 표기의 원문, 언어, LLM 영어 이름과 추정 분류를 받아 정확·정규화·문자·음가·벡터
검색 결과를 개념 번호로 합친다. 구현은 `concept/retrieval.py`, 운영 진입점은
`scripts/concept-judge.py`다.

## 점수와 근거

각 후보는 채널별 원점수, 어느 입력(`original` 또는 `english`)에서 나온 점수인지, 일치한 표현
번호를 보존한다. 채널 임계값을 넘은 점수에 가중치를 곱한 값 중 최댓값을 기본 점수로 삼고,
서로 다른 채널이 같은 개념을 지지하면 합의 보너스를 더한다. 추정 분류와 후보 분류가 다르면
최종 점수에 `category_mismatch_factor`를 곱한다. 따라서 이름이 같은 사람과 브랜드가 함께
검색돼도 분류가 맞는 개념이 먼저 온다.

정책값은 `spark/conf/base.yaml`의 `concept.retrieval`에서 조정한다.

- `top_k`: LLM에 넘길 후보 수
- `thresholds`: 채널별 최소 원점수
- `weights`: 채널별 신뢰 가중치
- `consensus_bonus`: 복수 채널 합의 보너스
- `category_mismatch_factor`: 분류 불일치 감점
- `min_combined_score`: 이보다 최고점이 낮을 때 `DEFER`

## 평가

`scripts/concept-vector-holdout-eval.py`는 알려진 별칭 하나를 숨기고 정답 개념이 Top K 안에
복구되는지 측정한다. 출력에는 각 채널의 `channel_recall_at_k`와 최종
`combined_recall_at_k`가 함께 포함된다. 이 평가는 새 미등록 표현의 정확도를 직접 나타내지는
않으며, 실제 적용 전에는 사람이 라벨링한 표본으로 임계값을 다시 확인해야 한다.

실제 미등록·신규·제외·모호 표현을 함께 재는 골드셋, 최종 LINK 안전성, 비용과 운영 승인 기준은
[개념 연결 품질 평가](concept-quality-evaluation.md)를 따른다.
