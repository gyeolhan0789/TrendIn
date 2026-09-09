"""키워드 추출 — `extract` Job 의 전반부.

규격은 [04](../../../../spark/docs/04-keyword-extraction-spec.md).

정제 문서(`curated`)에서 후보를 **넓게** 뽑고 점수를 매긴다. 승격 판단은 하지 않는다 —
그건 [05] · `registry/` 의 일이다. 이 패키지는 재현율을, `registry/` 가 정밀도를 담당한다.

```
morphology   한국어 형태소 분석기 — 선정 근거 · 품사표 · 사용자 사전    [04 §2]
tokenize     언어별 토큰화 (ko 형태소 분석 · en 규칙)                [04 §2]
candidates   명사 연속 → n-gram · 약어 · 해시태그 · 약어-전개형 쌍      [04 §3]
keys         비교키                                             [04 §4]
filters      형태 · 길이 · 불용어 · 노이즈 · DF 비율                [04 §5]
scoring      C-value · BM25 · 위치 가중 · 결합 · 선별               [04 §6~7]
document     문서 하나 → 후보 묶음. UDF 의 본체, Spark 없음
batch        Spark 배선. 코퍼스 통계와 문서 간 정규화만 여기서
source       curated 읽기와 대상 파티션 선정
thresholds   conf/*.yaml → 데이터클래스. 비어 있으면 Job 이 거부한다
```

**`document` 까지는 pyspark 를 import 하지 않는다** ([09 §4] 층 1). 코퍼스 전체를 봐야 하는
것(DF · 대표 표기 · C-value 의 빈도 · 문서 내 정규화)만 `batch` 가 Spark 로 한다.
"""
