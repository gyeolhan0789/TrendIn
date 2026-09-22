# 개념 연결 품질 평가

S15P21A102-362의 평가 계약이다. 후보 검색과 최종 LLM 판정을 같은 골드셋으로 재되,
비용이 드는 실행 결과는 JSONL로 저장하고 평가는 외부 호출 없이 반복한다.

## 골드셋

버전 1은 `spark/tests/fixtures/concept/quality-gold-v1.jsonl`이다. 운영 점검에서 발견한 표현과
저장소 기사·사전 표본 32개를 한국어 8개, 영어·일본어·프랑스어·이탈리아어 각 6개로 묶었다.
정답은 다음 넷 중 하나다.

| 정답 | 뜻 |
| --- | --- |
| `LINK` | 같은 대상·같은 범위의 기존 개념이 있다. `expected_concept`가 필수다 |
| `NEW` | 패션 트렌드로 셀 대상이지만 기존 개념이 없다 |
| `EXCLUDE` | 매체·플랫폼·장소처럼 세지 않을 표현이다 |
| `DEFER` | 문맥만으로 브랜드/사람, 넓은 말/좁은 말을 안전하게 고를 수 없다 |

각 행은 언어·분류·문맥·난이도·출처를 보존한다. `LINK` 외 정답에 기존 개념을 적거나 모르는
분류를 쓰면 평가 명령이 실패한다. 골드셋 자체는 다음처럼 검사한다.

```sh
cd pipeline
.venv/bin/python scripts/concept-quality-eval.py --validate-only
```

Windows에서는 `.venv/Scripts/python`을 쓴다.

이 32개는 평가 배선과 회귀를 확인하는 **작은 기준셋**이다. 영어 제안명 일부가 저장소 사전에서
온 표본이므로 이 결과만으로 자동 연결을 승인하지 않는다. 운영 승인용 표본은 최근 미등록 표현을
언어·분류별 층화 추출하고 두 사람이 독립 판정한 뒤 불일치를 합의해 200개 이상 별도 버전으로
고정한다. 같은 표본으로 임계값을 고르고 승인 수치를 보고하지 않는다.

## 재현 명령

저장소 사전만 사용하는 비교는 DB와 LLM이 필요 없다. 표본 표기와 같은 표현 행은 사전에서
숨겨 자기 자신을 찾는 누설을 막는다.

```sh
.venv/bin/python scripts/concept-quality-retrieval.py \
  --output artifacts/concept-quality-predictions.jsonl
.venv/bin/python scripts/concept-quality-eval.py \
  --predictions artifacts/concept-quality-predictions.jsonl \
  --output artifacts/concept-quality-report.json
```

운영 DB 사전과 pgvector를 읽는 실험은 다음과 같다. 트랜잭션을 쓰거나 LLM을 호출하지 않는다.

```sh
.venv/bin/python scripts/concept-quality-retrieval.py \
  --profile dev --vectors --top-k 10 \
  --output artifacts/concept-quality-live.jsonl
```

`--vectors`는 원표기·영어 제안명 각각을 검색하고, 숨긴 표현 ID를 pgvector SQL에서도 제외한다.
출력 실험명으로 원표기만/영어명 추가와 문자·음가/통합 검색을 비교할 수 있다. `@1/3/5/10`은
한 번 저장한 상위 10개를 잘라 계산하므로 Top K마다 모델을 다시 부르지 않는다.

운영과 같은 2단계 판정은 다음으로 돌린다. `--dry-run`은 LLM을 부르지 않고 배선만 확인한다.

```sh
.venv/bin/python scripts/concept-quality-judge.py   --model gpt-4o-mini --output artifacts/judge.jsonl
.venv/bin/python scripts/concept-quality-eval.py   --predictions artifacts/judge.jsonl --output artifacts/judge-report.json
```

한 번 부르고 두 실험을 적는다. `llm-judge-raw`는 모델 판단 그대로이고 `llm-judge-gated`는 자동
반영 관문을 통과한 것만 LINK로 적는다. 관문이 실제로 무엇을 막는지 추가 비용 없이 같이 잰다.
각 행에는 판정한 영어 이름과 분류, 어느 경로를 탔는지(`exact`/`verify`/`none`), 막혔다면 어느
관문인지, 표현당 토큰이 함께 남는다. 이것이 없으면 실행을 다시 부르지 않고는 따져 볼 수 없다.

LLM 또는 다른 프롬프트 실험도 아래 모양으로 한 행씩 저장하면 같은 평가기를 쓴다. `experiment`에
프롬프트 버전, 문맥 길이, 분류 필터, 임계값을 구분해 적는다.

```json
{"case_id":"ko-001","experiment":"candidate-v1-context500-k5-s055","decision":"LINK","concept":"vest","category":"apparel","candidates":[{"name":"vest","category":"apparel"}],"elapsed_ms":842.1,"llm_calls":2,"input_tokens":731,"output_tokens":41}
```

가격은 GMS 정책값이므로 코드에 고정하지 않는다. 실제 단가를 넘기면 입력·출력 토큰으로 예상
비용과 표현당 비용을 함께 계산한다.

```sh
.venv/bin/python scripts/concept-quality-eval.py \
  --predictions artifacts/concept-quality-workflow.jsonl \
  --input-usd-per-million INPUT_RATE \
  --output-usd-per-million OUTPUT_RATE
```

## 지표 정의

- 후보 Recall@K의 분모는 정답이 `LINK`인 모든 예다. 후보가 하나도 없는 경우도 실패에 포함한다.
- LINK precision은 올바른 개념을 고른 LINK / 전체 LINK다. 잘못된 개념 LINK도 거짓 양성이며,
  정답 링크를 놓쳤으므로 동시에 거짓 음성이다.
- 오연결률은 잘못된 LINK / 전체 LINK다. 작은 표본의 0건을 0%로 과신하지 않도록 precision의
  Wilson 95% 하한과 오연결률의 Wilson 95% 상한도 출력한다.
- DEFER 비율은 명시적 유보, 사람 검토량은 LINK하지 않은 `DEFER+NEW+EXCLUDE` 전부다.
- 시간은 표현별 `elapsed_ms`의 평균·p50·p95·최댓값, 비용은 호출 수·입출력 토큰·주입한 단가로
  계산한다.
- 모든 지표는 전체와 언어별·분류별로 똑같이 출력한다. `candidate_miss`, `wrong_link`,
  `category_mismatch`, `unresolved_link` 사례는 별도 목록으로 남는다.

## 현재 측정과 결정

2026-09-21 저장소 사전 16,000여 표현을 로컬에서 읽어 32개 기준셋을 실행했다. 후보 정답 17개에
대한 결과다. 로컬 시간은 Python 문자·음가 색인 조회만 포함하며 운영 DB 지연은 아니다.

| 실험 | Recall@1 | Recall@3/5/10 | 평균 | p95 |
| --- | ---: | ---: | ---: | ---: |
| 원표기 문자·음가 | 47.1% (8/17) | 47.1% | 14.0ms | 32.6ms |
| 원표기 + 정답 영어 제안명 | 100% (17/17) | 100% | 27.0ms | 60.4ms |

원표기만 쓸 때 언어별 Recall@5는 한국어 0/2, 영어 1/3, 일본어 4/4, 프랑스어 1/4,
이탈리아어 2/4였다. 영어 제안명은 강한 보완 신호지만 이 표본의 영어 이름이 사람이 확정한
정답이라 LLM 영어명 정확도까지 뜻하지 않는다.

2026-09-20 운영 holdout 120개의 참고치는 문자·음가 80/120(66.7%), 벡터 98/120(81.7%),
둘 중 하나가 정답을 찾은 비율 104/120(86.7%)였다. 정확 pgvector 검색 p95는 국가별
68.2~86.5ms였다. 이는 360 통합 점수와 최종 LLM을 같은 골드셋으로 평가한 승인 수치가 아니므로
새 평가 파일에서 다시 재야 한다.

2026-09-22 같은 기준셋에 운영과 같은 2단계 판정을 gpt-4o-mini 로 돌렸다. 이름을 먼저 묻고 그
이름으로 사전을 조회하고, 정확 일치가 없을 때만 후보를 보여 주며 같은 대상인지 되묻는 순서다.
한 번 부르고 모델 판단 그대로와 자동 반영 관문을 통과한 것만 두 벌로 적었다.

| 실험 | Recall@5 | LINK precision | 오연결 | 사람 검토 |
| --- | ---: | ---: | ---: | ---: |
| 모델 판단 그대로 | 82.4% | 73.7% (14/19) | 5건 | 40.6% |
| 자동 반영 관문 통과 | 82.4% | 87.5% (14/16) | 2건 | 50.0% |

호출 10회에 입력 4,421 · 출력 467 토큰이 들었고 표현당 LLM 호출은 1.25회다. 영어 이름 정확도는
26/32, 분류 정확도는 27/32 였다.

관문은 `Dior`, `Calvin Klein`, `maille` 세 건을 `COMPETING_REFERENT` 로 막았다. 사전이 같은
이름을 브랜드와 사람 양쪽에 갖고 있거나, 분류 추측 때문에 감점되기 전 증거가 더 센 후보가 함께
올라온 경우다. 특히 `maille` 은 정답인 `knitwear` 가 증거 1.0 을 갖고도 `material` 이라는 분류
추측에 눌려 0.25 로 떨어지고 `fabric` 이 이겼다. 분류는 제안이지 정답이 아니므로 그 이유만으로
후보를 묻지 않는다.

남은 오연결 `rose→pink` 와 `Coach` 는 영어 이름 정확 일치로 붙어 관문을 지나지 않는다. 사전에
갈릴 근거가 없으므로 이름 판정 단계가 다의어를 스스로 유보해야 한다.

표본 32개의 precision 은 승인 수치가 아니다. Wilson 95% 하한이 64.0%, 오연결률 상한이 36.0%
라서 이 표본으로는 자동 연결을 승인할 수 없다.

운영 기준은 다음으로 고정한다.

1. 후보는 우선 Top 5를 유지한다. 승인셋에서 전체 Recall@5 90% 이상, 표본 20개 이상인 각
   언어·분류에서 80% 이상이어야 한다. Top 10이 5보다 3%p 이상 높을 때만 비용 증가를 재검토한다.
2. `min_combined_score=0.55`는 후보 유보용 잠정값이다. 자동 연결 임계값으로 승인하지 않는다.
   점수별 precision-recall 표에서 아래 안전 기준을 만족하는 가장 높은 recall 지점을 고른다.
3. 자동 LINK는 독립 승인셋 200개 이상, 점 precision 99% 이상, 오연결 0건, 오연결률 Wilson
   95% 상한 2% 이하를 모두 만족해야 한다. 언어·분류 슬라이스에서 오연결이 한 건이라도 나오면
   그 슬라이스는 유보한다.
4. 안전 기준을 만족하기 전에는 DEFER와 사람 검토량에 상한을 두지 않는다. 만족한 뒤 검토율
   60% 이하를 최적화 목표로 삼는다. 비용 목표는 표현당 LLM 2회 이하이며 실제 GMS 단가로
   다시 계산한다.
5. 문맥 없는 표기, 브랜드↔창업자, 일반 품목↔특정 제품, 일반어↔패션 용어는 점수와 무관하게
   DEFER한다. `concept.automation.enabled`는 계속 `false`로 두고, 승인 전에는
   `--apply-verified`를 사용하지 않는다.

## 관측된 오류 유형과 후속 작업

| 유형 | 사례 | 후속 작업 |
| --- | --- | --- |
| 번역 관계를 문자·음가가 놓침 | `조끼→vest`, `cuir→leather`, `pochette→clutch` | 영어 제안명·벡터 통합 Recall을 승인셋에서 재측정 |
| 벡터 의미 오류 | `실버→silk`, `조끼→flip-flops`, `uncinetto→Uniqlo` | 벡터 단독 연결 금지, 분류 일치와 LLM 검증 유지 |
| 대상 유형 충돌 | `Dior`, `Calvin Klein` | 관문이 막는다 (`COMPETING_REFERENT`) |
| 사전에 갈릴 근거가 없는 다의어 | `rose`, `Coach` | 이름 판정이 스스로 유보하도록 프롬프트를 고친다 |
| 매체·플랫폼 오분류 | `Vogue`, `Elle`, `Instagram` | 이름 판정의 generic 정확도와 EXCLUDE recall 별도 보고 |
| 신규 인물·브랜드 | `제니`, `장원영`, `Brady` | 기존 후보를 억지로 고르지 않는 non-link 안전성 측정 |
| 범위 불일치 | `브이넥`과 `v-neck knit` | 같은 대상뿐 아니라 같은 granularity를 검증하는 프롬프트 유지 |

