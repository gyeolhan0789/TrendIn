```
contract/    입력 계약 샘플 — 이벤트 5건 + 그 이벤트가 가리키는 객체 (S15P21A102-159)
corpus.json    한국어·혼합 문서 30건 (실제 수집 데이터에서 발췌, 익명화)
snapshots.json 각 문서의 추출 결과
```

## `contract/`

`ingest` 가 Kafka·MinIO 없이 파싱·검증 코드를 테스트하는 근거다. 계약은 [02](../../docs/02-input-contract.md),
생산 측 설명은 [`pipeline/docs/spark-integration.md`](../../../docs/spark-integration.md).

```
contract/
├─ article-event.json         기사 이벤트. object_key 가 있다
├─ run-summary-success.json   실행 요약(성공). object_key 가 null 이고 record_count > 0
├─ run-summary-failed.json    실행 요약(실패). failure_reason 이 있다
├─ collect-run-summary-success.json  collect-run-summary 토픽의 요약(성공). 소비는 S15P21A102-206
├─ collect-run-summary-failed.json   collect-run-summary 토픽의 요약(실패)
└─ objects/<object_key 그대로>/
   ├─ article.json            article-event.json 의 object_key 가 가리키는 실물
   └─ raw.xml                 raw_object_key 가 가리키는 실물
```

`objects/` 아래 경로는 MinIO 의 `object_key` 와 **같은 형태**이다. 그래서 테스트가 버킷 루트만
바꿔 끼우면 실제 s3a 경로와 같은 코드로 읽힌다.

**손으로 고치지 않는다.** `sha256(article.json)` 이 이벤트의 `checksum` 과 같아야 하고, 메시지의
값이 `article.json` 의 값과 같아야 한다. 크롤러 쪽 `pipeline/tests/common/test_contract_fixtures.py`
가 그 둘을 검사하므로, 손으로 고치면 그쪽이 깨진다. 갱신 절차는
[`spark-integration.md`](../../../docs/spark-integration.md) 의 "fixture 갱신" 절이다.

`objects/` 아래 두 파일은 `pipeline/.gitattributes` 가 `-text` 로 묶어 뒀다. `core.autocrlf=true`
인 Windows 작업자가 체크아웃해도 개행이 바뀌지 않는다 — 바뀌면 sha256 이 달라져 fixture 가
거짓말을 하게 된다.

**⚠️ 소비 측 단위 테스트는 아직 이 fixture 를 읽지 않는다.** `spark/tests/unit/test_contract.py`
가 메시지 형태를 손으로 옮겨 뒀다. 둘이 나뉘어져도 지금은 아무도 못 잡으므로, `classify()` 를 여기
3건에 돌리는 테스트를 하나 두는 편이 낫다.

## `corpus.json` · `snapshots.json` · `review/`

회귀 스냅샷과 수동 검수용 고정 데이터 ([09 §4](../../docs/09-dev-and-test.md) · [04 §9](../../docs/04-keyword-extraction-spec.md)).

**2026-09-09 에 채웠다.** 수집 스냅숏(fashion 373건, `spark/trendin-collect-20260909`)에서 30건을
발췌했다 ([10 §5.1](../../docs/10-delivery-plan.md)).

```
corpus.json     article.json 30건 (발췌·익명화). 키가 `{소스}-{article_id}.json`
snapshots.json  각 문서의 정제 + 문서 안 추출 결과. 키가 같다
review/     검수 산출물 — 사람이 매긴다
```

`review/` 에는 **검수 한 번에 파일 하나**를 둔다.

| 파일 | 무엇 |
| --- | --- |
| `morphology-vs-rules-2026-09-09.md` | **형태소 분석기 교체의 전후 비교** ([04 §2](../../docs/04-keyword-extraction-spec.md)). `spark/scripts/evaluate-extract.py` 가 냈고 §5 의 명사 분류만 사람이 채웠다 |

**"전" 실행의 시트를 따로 두지 않는다.** 처음에는 규칙 기반 실행의 top-10 시트를 따로
뒀는데(`precision-at-10-2026-09-09.md`), 전후 비교 문서 §3 이 두 실행을 **한 줄에 나란히**
놓아 같은 내용을 담는다. 파일 둘이면 어느 쪽이 최신인지가 헷갈리고 481줄이 중복된다.

### 왜 문서마다 파일이 아니라 파일 하나인가

처음에는 문서마다 파일을 하나씩 뒀다 (`corpus/fashion-vogue-854781.json` …). 그러면
**픽스처만 60개**가 되어 변경 목록의 절반을 넘고, 정작 읽어야 할 구현·테스트가 묻힌다 —
S4 커밋에서 116개 중 60개가 이것이었다.

키를 이름(`{소스}-{article_id}.json`)으로 정렬해 담으므로 **한 파일 안의 diff 가
지역적이다** — 문서 하나가 바뀌면 그 자리만 바뀐다. `git diff --stat` 이 "30건 중 몇 건"
을 안 알려 주는 것이 유일한 손실이고, 그건 `update-snapshots.py` 가 갱신할 때 이름을
줄줄이 찍어 대신한다.

**두 파일의 키가 같아야 한다.** `test_스냅샷과_코퍼스의_키가_짝이_맞는다` 가 지킨다.

### 갱신하는 법

```sh
pipeline/.venv/bin/python spark/scripts/update-snapshots.py
pytest spark/tests/unit/test_extract_snapshots.py
```

코드를 고쳐 결과가 바뀌면 `test_extract_snapshots.py` 가 먼저 빨개진다. **의도한 변경이면
스크립트로 갱신하고 diff 를 커밋에 남긴다** — 목적은 변경을 막는 것이 아니라 의도하지 않은
변경을 드러내는 것이다.

### 무엇을 고정하나

**문서 하나 안에서 결정되는 것까지다** — 정제(단계 1~8) · 토큰화 · 구간 · n-gram · 비교키 ·
문서 안 필터. DF · 대표 표기 · C-value · BM25 · 점수 · 순위는 **넣지 않았다.** 코퍼스 전체를
봐야 나오는 값이고 S6 가 임계값을 확정하면 바뀌므로, 고정하면 임계값을 만질 때마다 30건이
통째로 흔들려 스냅샷이 경보가 아니라 잡음이 된다.

후보 목록은 상위 15개만 적고 **꼬리의 변화는 `keys_digest`(전체 비교키의 sha256 앞 16자)가
잡는다.** 전부 적으면 문서당 200줄이 되어 눈으로 diff 를 볼 수 없다.

### 축 커버리지

| 축 | 표본 |
| --- | --- |
| `route` | `rss` 16건 · `listing` 14건 |
| 본문 유무 | 있음 24건 · 없음 6건 (회원 전용 3 · 피드 본문 빈 것 3) |
| 소스 | 7 매체 전부 (cosmopolitan 6 · harpersbazaar 6 · vogue 4 · wkorea 4 · gqkorea 4 · marieclaire 3 · allure 3) |
| 결함 회귀 | `관련기사` 위젯 5 · 쇼핑 앵커 3 · 번역 고지 1 · 사진 크레딧 2 · `올가을` 5 · 조사 붙은 불용어 9 · 약어 쌍 1 |

**⚠️ 뒤의 두 회귀는 성격이 바뀌었다** (2026-09-09 형태소 분석기 교체). `올가을` 은 규칙표가 `올가` 로 자르던 것을 보호어로 막는 회귀였는데, 이제 분석기가 `올`(MM) + `가을`(NNG) 로 갈라 **후보가 `가을` 이 된다.** `조사 붙은 불용어`(`컬러의`)도 어간 대조 규칙의 회귀였는데, 이제 비교키가 `컬러` 라 한 번에 걸린다. 표본은 그대로 두는 것이 맞다 — **되돌아가면 빨개지는 자리**다.

**⚠️ `api` · `dev` · `en` 축은 비어 있다.** `hn` 어댑터가 `S15P21A102-165` 대기 중이라 dev
도메인 수집분이 0건이다. `test_extract_snapshots.py::test_축을_덮는다` 가 그 어댑터가 붙는
순간 빨개지도록 조건을 적어 뒀다.

### 본문을 자른 이유

[09 §4](../../docs/09-dev-and-test.md) 가 *"일반 기사 본문은 발췌 길이를 짧게 자르고 출처(URL·매체·발행일)를 함께 둔다"* 고
정했다 (저작권법 제37조, 불변식 3). 그대로 했다 — **앞 1000자 + 꼬리의 상투 요소 줄**이다.
꼬리를 함께 남기는 이유는 [03 §4](../../docs/03-normalization-spec.md) 단계 8 이 노리는 줄(`관련기사` · `구매하러 가기` · 번역 고지)이
본문 **끝**에 있어서, 앞부분만 자르면 그 회귀를 못 잡기 때문이다.

`author` 는 익명화했고(`기자NN`), `raw_key` · `content_sha256` 은 뺐다 — 발췌본이라 원본
객체를 가리키는 값이 거짓이 된다. 코퍼스는 객체를 조회하지 않으므로 필요도 없다.
`_excerpt: true` 가 이 파일들이 발췌본이라는 표시다.

### `review/`

[04 §9](../../docs/04-keyword-extraction-spec.md) 의 수동 검수(precision@K)다. 스냅샷과 성격이 다르다 — **스냅샷은 재현성을,
검수는 품질을 본다.** 각 문서의 선별된 상위 10 후보에 사람이 `O`/`X` 를 적고, 임계값이나
토큰화를 바꾼 뒤 같은 30건에 다시 매겨 전후를 비교한다. 절대 수치는 CI 에 넣지 않는다.

시트의 점수·순위는 **373건 코퍼스에서 나온 값**이다. 30건만으로 다시 돌리면 DF 가 달라져
순위가 바뀐다 — 그 표는 특정 실행의 사진이고, 파일 이름의 날짜가 그것을 말한다.

**전후 비교는 `spark/scripts/evaluate-extract.py` 가 낸다.** 사람이 O/X 를 다 매기기 전에도
조사 잔재 · 서술어 활용형 · 숫자·가격 · 토큰화 오류는 **기계가 같은 잣대로** 셀 수 있고,
그 잣대가 양쪽에 같이 걸리는 것이 비교의 전제다. 사람 눈이 필요한 것(패션 신호 / 스타일
수식어 / 무정보어)만 표로 내어 채운다. `morphology-vs-rules-2026-09-09.md` 가 그 산출물이다.

**⚠️ 그 스크립트로 전후를 재려면 실행 직후에 `--dump` 로 떠 둬야 한다.**
`pl_document_candidate` 는 처리한 문서의 옛 행을 지우고 넣으므로 (`io/candidates.py`)
같은 코퍼스를 두 번 돌리면 **먼저 실행이 없어진다.** `extract_run_id` 로 두 실행이 공존하지
않는다.
