# 08 — 저장 스키마

무엇을 어디에 쓰는지, 그리고 두 번 써도 결과가 같게 만드는 방법.

## 1. 두 층

**서비스 테이블은 백엔드가 소유하고, Spark 는 값만 넣는다.** 중간 산출물은 파이프라인이 소유한다.

| | 서비스 계약 층 | 파이프라인 내부 층 |
| --- | --- | --- |
| 소유 | 백엔드 | Spark |
| DDL 권한 | **없음.** 변경은 백엔드에 요청 ([§5](#5-백엔드에-요청할-것)) | 있음 |
| 읽는 쪽 | Spring Boot | Spark 만 |
| 이름 | [`erd/erd-00-current.md`](erd/erd-00-current.md) 그대로 | `pl_` 접두 |

`pl_` 접두를 붙이는 이유는 psql 에서 `\dt` 를 쳤을 때 소유가 눈에 보이게 하기 위해서다. 백엔드 개발자가 내부 테이블을 서비스 테이블로 착각하고 조회하는 일을 막는다.

**같은 데이터베이스에 둔다.** 별도 DB 로 나누면 `RETURNING` 으로 받은 `id` 를 매핑 테이블에 넣는 것이 크로스 DB 작업이 되고, 트랜잭션으로 묶을 수 없다.

## 2. 서비스 테이블 적재

| 테이블 | Job | 충돌 키 | 전략 | 삭제 |
| --- | --- | --- | --- | --- |
| `contents` | ingest | `url` (UK) | `ON CONFLICT DO UPDATE` | **절대 안 함** |
| `keywords` | extract | `(domain, normalized_name)` ⚠️ | `ON CONFLICT DO UPDATE` | **절대 안 함** |
| `keyword_contents` | extract | `(keyword_id, content_id)` PK | `ON CONFLICT DO NOTHING` | 재추출 시 해당 문서분만 |
| `trends` | aggregate | `keyword_id` (UK) | `ON CONFLICT DO UPDATE` | 안 함 |
| `keyword_metrics` | aggregate | `(keyword_id, period)` ⚠️ | `ON CONFLICT DO UPDATE` | 같은 `period` 의 옛 구간 행 |
| `keyword_metric_history` | aggregate | `(keyword_id, bucket_start)` ⚠️ | upsert 또는 범위 삭제 후 삽입 | 재계산 구간 W |
| `keyword_relations` | aggregate | `(source, target)` PK | **source 별 삭제 후 삽입** | 계산한 source 만 |

⚠️ 표시는 **제약이 실제로 존재하는지 확인되지 않은 것**이다. [§5](#5-백엔드에-요청할-것).

**`aggregate` 의 네 테이블은 같은 회차에 쓴다.** 상세 화면 하나가 `keyword_metrics`(숫자)와 `keyword_metric_history`(그래프)를 함께 읽으므로, 한쪽만 갱신된 상태로 남으면 화면의 숫자와 그래프가 어긋난다.

### `contents` 와 `keywords` 를 지우지 않는 이유

둘 다 사용자 데이터가 딸려 있다.

- `contents` — `keyword_contents` 가 참조한다. 한 행을 지우면 사용자에게 보이던 관련 콘텐츠 연결이 사라진다.
- `keywords` — `member_interest_keywords`, `trends`, `keyword_contents`, `keyword_relations`, `keyword_metrics`, `keyword_metric_history` 가 참조한다. 자세한 것은 [05 §1](05-keyword-registry-spec.md).

재처리도 이 둘은 upsert 로만 처리한다.

### `trends` 는 갱신만 한다

```sql
INSERT INTO trends (keyword_id, trend_types, updated_at)
SELECT keyword_id, trend_types::trend_type[], :now FROM pl_stage_trends
ON CONFLICT (keyword_id) DO UPDATE SET
  trend_types = EXCLUDED.trend_types,
  updated_at  = EXCLUDED.updated_at;
  -- description · summary · reason 은 건드리지 않는다
```

`description`·`summary`·`reason` 을 `DO UPDATE` 에서 빼는 이유는, 나중에 LLM 태스크가 채운 값을 `aggregate` 가 다시 `NULL` 로 덮어쓰지 않게 하기 위해서다. **지금은 채우지 않지만 미래를 막지 않는다.**

`trend_types` 는 매 회차 덮어쓴다. 이번에 아무 유형도 못 받은 트렌드는 **빈 배열**로 갱신되어 목록에서 사라진다 ([07 §6](07-metrics-and-ranking-spec.md)). 행은 지우지 않는다 — `briefing_trends`·`notifications` 가 참조하고, 채워진 설명 텍스트도 함께 사라진다.

**`::trend_type[]` 캐스트가 붙는 이유** — 다이어그램의 타입이 `trend_type_array` 다. 네이티브 enum 배열이면 Spark 가 보낸 문자열 배열이 캐스트 없이 들어가지 않는다 ([§4](#4-쓰는-방법--스테이징--서버사이드-merge), [01 §6](01-architecture.md)). 스테이징 컬럼을 `text[]` 로 두고 MERGE 에서 캐스트하는 것이 **어느 쪽이든 동작하는 형태**다.

### `keyword_relations` 만 삭제 후 삽입인 이유

상위 N 으로 자르기 때문이다. upsert 로는 **이번에 상위 N 에서 밀려난 행을 지울 수 없다.** 자세한 것은 [06 §7](06-related-keyword-spec.md).

### 지표는 두 테이블로 갈렸다

| 테이블 | 행의 단위 | 충돌 키 |
| --- | --- | --- |
| `keyword_metrics` | 키워드 × 기간에 **1행** | `(keyword_id, period)` |
| `keyword_metric_history` | 키워드 × 버킷(1일)에 1행 | `(keyword_id, bucket_start)` |

**둘 다 이력 테이블이 아니라 자연 키가 있는 테이블이다.** v1 의 `trend_metrics` 는 측정이 쌓이는 구조라 그냥 INSERT 하면 재실행마다 중복이 생겼는데, 지금은 upsert 가 자연스럽다. SQL 은 [07 §7](07-metrics-and-ranking-spec.md).

**⚠️ `keyword_metrics` 는 유령 행이 남을 수 있다.** 이번 회차에 언급이 0 으로 떨어진 키워드는 스테이징에 없어 갱신되지 않고, 옛 구간을 가리키는 행이 그대로 남는다. 같은 `period` 에서 `period_start` 가 이번 구간이 아닌 행을 지워야 한다 ([07 §7](07-metrics-and-ranking-spec.md)).

**`previous_mention_count` 를 지난 실행의 행에서 이월하지 않는다.** 직전 구간을 원자료에서 다시 계산한다 ([07 §5](07-metrics-and-ranking-spec.md)). 덕분에 같은 날 몇 번을 재실행해도 결과가 같다 — 이월 구조였다면 재실행이 곧 오염이었다.

`keyword_metrics` 가 `trends` 를 거치지 않으므로 **트렌드가 아닌 키워드도 적재 대상이다.** 관심 키워드로 등록만 한 키워드의 지표가 여기서 나온다.

## 3. 파이프라인 내부 테이블

| 테이블 | 담는 것 | 쓰는 Job |
| --- | --- | --- |
| `pl_processing_ledger` | `(event_id, job)` 별 상태·건수·시각 | 전부 |
| `pl_processing_error` | DLQ 미러. `error_type`, 원본 이벤트 | ingest |
| `pl_batch_stat` | 실행별 정제 통계. **`(일자, 소스)` 별 수집 상태**는 여기 얹을 예정이고 아직 없다 — 지금은 `pl_processing_ledger` 의 요약 이벤트 행이 원자료다 ([02 §4](02-input-contract.md)) | ingest |
| `pl_content_id_map` | `url_hash` → `contents.id` | ingest |
| `pl_keyword_id_map` | `(domain, normalized_key)` → `keywords.id` | extract |
| `pl_candidate` | 후보 마스터. 대표 표기, **최초·최근 관측일**(`first_seen_date` · `last_seen_date`, 발행일 기준), 승격 상태, `keyword_id` | extract |
| `pl_document_candidate` | 문서 × 후보 점수 ([04 §7](04-keyword-extraction-spec.md)). `tf` · `df` · `c_value` · `bm25` · `score` · `rank` · **`selected`**(상위 K) · `stat_date` · `is_dup` | extract |
| `pl_keyword_daily_stat` | **키워드·후보별 일별 원자료** | extract |
| `pl_abbreviation_observation` | `전개형 (약어)` 관측 — 문서 × 쌍. [05 §3](05-keyword-registry-spec.md) 통합의 결정적 증거. `initials_match` 가 첫 글자 대응 여부 | extract |
| `pl_alias` | 별칭 → 대표. 근거 층, 신뢰도 | extract |
| `pl_merge_log` | 병합 이력 ([05 §8](05-keyword-registry-spec.md)) | extract |
| `pl_trend_type_log` | **회차별 유형 판별 이력.** `(keyword_id, period, 회차)` → 유형 ([07 §6](07-metrics-and-ranking-spec.md)) | aggregate |
| `pl_review_queue` | 검수 큐 ([05 §7](05-keyword-registry-spec.md)) | extract |
| `pl_embedding_cache` | 표기 → 벡터 ([01 §5](01-architecture.md)) | extract |
| `pl_config_history` | 임계값 변경 이력 ([04 §10](04-keyword-extraction-spec.md)) | 수동 |

### `pl_processing_ledger` 의 키가 두 종류를 담는다

`event_id` 하나로 두 형태의 이벤트를 함께 받는다 ([02 §2](02-input-contract.md)).

| `event_id` 꼴 | 무엇 | 처리 이력 상태 |
| --- | --- | --- |
| `{source}-{article_id}` | 기사 이벤트 | `COMPLETED` / `FAILED` |
| `{source}-{run_id}` | 실행 요약 이벤트 | `COMPLETED` / `SOURCE_FAILED` |

**형식만으로는 구분되지 않는다.** `run_id` 는 `yyyyMMddTHHmmss` 이고 `article_id` 는 소스마다 다른 숫자 문자열인데(두산 계열은 `?p=854414` 의 숫자, `hn` 은 `objectID`), 우연히 겹치지 않는다는 보장이 계약에 없다. 그래서 **처리 이력에 이벤트 종류를 담는 컬럼을 둔다.** 없으면 `pl_batch_stat` 집계가 기사 행을 요약 행으로 세거나 그 반대를 한다.

`SOURCE_FAILED` 는 기사 이벤트에 나올 수 없다 — 기사 이벤트의 `status` 는 늘 `success` 다(불변식 5). 나오면 [02 §2](02-input-contract.md) 의 계약 위반 분기가 먼저 DLQ 로 보낸다.

### DDL 은 각 `io/*.py` 가 들고 있다

`pl_*` 는 파이프라인 내부 테이블이라 우리가 만든다. 서비스 테이블은 백엔드 소유고 Spark 에 DDL 권한이 없다([§1](#1-두-층)) — 그 경계를 넘지 않는다. Job 이 시작할 때 `ensure_schema()` 로 멱등하게 적용한다.

| 모듈 | 테이블 |
| --- | --- |
| `io/ledger.py` | `pl_processing_ledger` |
| `io/dlq.py` | `pl_processing_error` |
| `io/stats.py` | `pl_batch_stat` |
| `io/contents.py` | `pl_content_id_map` · `pl_stage_contents` |
| `io/candidates.py` | `pl_document_candidate` · `pl_candidate` · `pl_keyword_daily_stat` · `pl_abbreviation_observation` (+ 스테이징 셋) |

### `extract` 의 네 표는 한 트랜잭션으로 쓴다

`io/candidates.CandidateSink.write` 가 스테이징 셋을 같은 연결에서 채우고 MERGE 까지 간다 ([§4](#4-쓰는-방법--스테이징--서버사이드-merge)). 순서가 중요하다.

1. 영향받는 `(domain, stat_date)` 를 **지우기 전에** 모은다 — 처리한 문서의 옛 행이 가리키던 날짜 ∪ 새 행의 날짜.
2. 처리한 문서(`pl_stage_extracted_document`, 후보가 0 개인 문서 포함)의 옛 `pl_document_candidate` 행을 지우고 새 행을 넣는다.
3. `pl_candidate` upsert. `first_seen_date` 는 `LEAST` 로 지킨다 — 재실행이 앞당기지도 늦추지도 않는다.
4. 영향받은 날짜의 `pl_keyword_daily_stat` 을 **저장된 `pl_document_candidate` 전체에서 다시 센다.** 한 `stat_date` 의 문서가 여러 `ingest_run_id` 에 흩어져 오므로([07 §2](07-metrics-and-ranking-spec.md)) 이번 배치의 행만으로는 그 날의 값을 알 수 없다. `keyword_id` 는 [05] 가 채우는 칸이라 건드리지 않고, 그 날짜에서 사라진 후보의 행은 지운다.
5. `pl_abbreviation_observation` upsert.

**⚠️ 2번의 결과 — `pl_document_candidate` 에는 실행 하나만 남는다.** 같은 문서를 두 번 처리하면 먼저 실행의 행이 지워지므로 `extract_run_id` 로 두 실행이 공존하지 않는다. **의도한 설계다** — 재실행이 행을 쌓으면 DF 가 두 배가 되고 `pl_keyword_daily_stat` 재집계(4번)가 같은 문서를 여러 번 센다. 대가는 전후 비교를 이 표로 할 수 없는 것이고, 그래서 `spark/scripts/evaluate-extract.py` 가 실행 직후에 행을 파일로 뜬다 ([09 §4](09-dev-and-test.md) 검수 절). `extract_run_id` 컬럼은 "이 행을 누가 썼나" 를 말하는 것이고 "실행별 이력" 이 아니다.

**`doc_count` 는 필터를 통과한 후보 전부를 센다** — 상위 K 만이 아니다 ([04 §7](04-keyword-extraction-spec.md) "내부 후보 통계에 남길 것 = 필터를 통과한 전부"). 승격 심사([05 §5](05-keyword-registry-spec.md))가 그 누적 관측을 보고, `keyword_contents` 와 동시출현([06](06-related-keyword-spec.md))은 `selected` 로 좁힌다. `is_dup` 문서는 `doc_count` · `source_count` · `author_count` 에서 빼고 `doc_count_with_dup` 에만 들어간다.

컬럼 중 이름만으로 안 읽히는 둘:

| 컬럼 | 무엇 |
| --- | --- |
| `event_shape` | `ARTICLE` \| `SUMMARY`. 위 표대로 `event_id` 형식만으로는 안 나뉜다 |
| `stage` | **이 Job 이 이벤트를 어디까지 끌고 갔는지.** `contract`(메시지 판별) · `object`(객체 조회·검증) · `normalize`(정제·적재, 171) |

`Ledger.filter_new()` 는 `event_id` 만이 아니라 **`(event_id, stage)`** 로 대조한다. 판별이 도달할 단계를 미리 정해 주므로(`ingest/routing.decide`) 대조 시점에 그 값이 이미 있다.

| 이벤트 | 도달 단계 |
| --- | --- |
| 메시지에서 거절 | `contract` — 객체까지 가지 않는다 |
| 요약 이벤트 | `contract` — 조회할 객체가 없다 |
| 메시지를 통과한 기사 | `normalize` — 객체 검증에서 걸려도, 정제에서 필터로 버려져도 거기서 끝난다 (`ingest/routing.decide`). 170 까지는 `object` 였다 |

**단계를 더할 때 손으로 옮길 것이 없다.** 객체 검증이 붙기 전에 `contract` 까지만 적힌 기사 이벤트는 이제 `object` 를 목표로 오므로 대조에 걸리지 않고, 다시 처리되어 같은 행이 `object` 로 갱신된다(PK 가 `(event_id, job)` 이라 행은 늘지 않는다). 2026-09-08 에 실제로 확인했다. **`event_id` 만 봤다면 그 행들이 새 단계를 통째로 건너뛰었고, 아무 증상도 없었다.**

**⚠️ 승격은 그 이벤트가 다시 흐를 때만 일어난다.** Kafka 는 checkpoint 가 이미 지난 오프셋을 다시 주지 않으므로, **단계가 늘기 전에 소비를 마친 이벤트는 저절로 올라가지 않는다.** 그 구간까지 올리려면 [02 §6](02-input-contract.md) 의 `--source objects` 로 다시 흘리거나 checkpoint 를 그 절차대로 되돌려야 한다.

**동시에 두 개가 돌면 안 된다.** 처리 이력과 DLQ 가 스테이징 테이블을 공유하므로([§4](#4-쓰는-방법--스테이징--서버사이드-merge)) `ingest` DAG 은 `max_active_runs=1` 이어야 한다. 겹치면 한쪽의 행이 다른 쪽 트랜잭션에 딸려 들어간다.

### `pl_keyword_daily_stat` 이 이 묶음의 실질적 원본이다

서비스 스키마에 키워드별 **일별** 지표 테이블이 없으므로(`keyword_metric_history` 는 정규 키워드의 언급량만 담는다), **이 내부 테이블이 모든 집계의 원자료**다. 두 서비스 지표 테이블은 여기서 파생된 요약이다.

| 컬럼 | 왜 필요한가 |
| --- | --- |
| `(domain, normalized_key)` | **승격 전 후보는 `keyword_id` 가 없다.** 그래서 키가 이것이다 |
| `keyword_id` | 승격 후 채운다. `NULL` 이면 아직 후보 |
| `stat_date` | 발행 기준 날짜 ([07 §2](07-metrics-and-ranking-spec.md)) |
| `doc_count` | 언급량. 서비스로 나가는 유일한 값 |
| `occurrence_count` | 이상 탐지 ([07 §8](07-metrics-and-ranking-spec.md)) |
| `source_count` | 승격·`NEW` 판별 ([05 §5](05-keyword-registry-spec.md), [07 §6](07-metrics-and-ranking-spec.md)) |
| `author_count` | 같음 — **봇 방어의 핵심** |
| `doc_count_with_dup` | 크로스포스트 영향 측정 |

**승격 전 후보의 통계가 여기 있어야만 승격 심사가 성립한다.** 후보는 `keywords` 에 없으므로 서비스 테이블 어디에도 값을 둘 수 없는데, 승격을 판단하려면 누적 통계가 필요하다.

### ⚠️ `keywords.first_seen_at` 이 없어진 뒤 이 테이블의 무게가 늘었다

v2 스키마에는 `first_seen_at` 이 없다. `NEW` 판별이 **언급량 이력으로만** 이뤄지고, 그 이력은 여기밖에 없다 ([07 §6](07-metrics-and-ranking-spec.md)).

| 필요한 것 | 왜 |
| --- | --- |
| `30D`·`NEW` 를 위해 **120일** 보존 | 최근 30일 + 그 이전 90일이 조용했는지 봐야 한다 |
| **후보 시절 행까지 보존** | 3주간 후보로 관측되다 승격된 키워드를 `NEW` 로 오인하지 않는 근거가 이것이다 |
| `pl_candidate` 의 최초 관측 시각 | 승격 심사와 운영 조회에 쓴다. 서비스로 옮겨 가는 자리는 이제 없다 |

**이건 좋은 방향의 변화다.** 근거가 서비스 테이블의 한 컬럼이 아니라 파이프라인이 소유한 원자료가 됐으므로, 백엔드가 스키마를 다시 만들어도([§6](#6-스키마를-고쳐나가는-방법)) `NEW` 판별 근거는 살아남는다.

### 보존

| 테이블 | 정리 |
| --- | --- |
| `pl_document_candidate` | 가장 빠르게 자란다. 최근 N일만 유지 |
| `pl_keyword_daily_stat` | **지우지 않는다.** 모든 재계산의 원본이고 `NEW` 판별의 유일한 근거다 |
| `pl_processing_ledger` · `pl_batch_stat` | 오래 남긴다. 작고 운영 조회에 쓴다 |
| `pl_candidate` · `pl_alias` · `pl_merge_log` | 지우지 않는다. 승격 심사가 누적 관측에 의존한다 |
| `pl_trend_type_log` | 오래 남긴다. 작고, 임계값 변경 전후 비교에 쓴다 |
| `pl_embedding_cache` | 표기가 사라지면 함께 정리 |

`pl_document_candidate` 를 지우면 [04 §10](04-keyword-extraction-spec.md) 의 "임계값을 낮춰 재평가"가 그 구간에서 불가능해진다. 보존 기간은 재평가하고 싶은 범위와 같게 잡는다.

## 4. 쓰는 방법 — 스테이징 + 서버사이드 MERGE

**Spark JDBC 는 upsert 를 못 한다.** `mode="append"` 는 순수 INSERT 라 충돌하면 배치가 죽는다.

```
1. 드라이버  →  행을 collect() 해 psycopg2 로  BEGIN
                                              TRUNCATE pl_stage_*
                                              INSERT pl_stage_*            (execute_values)
                                              INSERT ON CONFLICT / DELETE+INSERT
                                              TRUNCATE pl_stage_*
                                             COMMIT
2. 필요하면 매핑 테이블을 Spark JDBC 로 되읽는다
```

**스테이징 INSERT 도 드라이버가 같은 연결에서 한다** (`io/jdbc.stage_and_merge`). 처음 설계는 1 을
Spark JDBC `append` 로 두었는데, 그러면 그 INSERT 가 **자기 연결에서 파티션마다 커밋**하는 별개
트랜잭션이라 MERGE 가 죽었을 때 스테이징 행이 남아 다음 실행의 MERGE 에 섞였다 (2026-09-09 리뷰).
[00 §3](00-overview.md) 규모(배치당 수백 행)에서는 드라이버로 모으는 것이 맞고, 행이 수만 단위가
되면 Spark JDBC 로 돌아가되 실행별 토큰으로 스테이징을 격리한다. timestamp 는 오프셋 붙은
문자열로 내려 세션 시간대에 의존하지 않는다.

### 왜 `foreachPartition` 이 아닌가

| | 스테이징 | foreachPartition |
| --- | --- | --- |
| 원자성 | **한 트랜잭션.** 스테이징 INSERT 부터 MERGE 까지 같은 연결. 전부 반영되거나 전부 아님 | 파티션별 커밋. 중간 실패 시 절반만 반영 |
| 커넥션 | 드라이버 1개 | executor 수만큼 동시 접속 |
| 범위 삭제 | 같은 트랜잭션 안에서 가능 | 별도 처리 필요 |
| `RETURNING` 회수 | 매핑 테이블 경유로 자연스럽다 | executor 로 흩어져 모으기 어렵다 |
| 코드 | SQL 이 밖에 나온다 | 파이썬 안에 다 있다 |

**절반만 반영된 상태가 가장 나쁘다.** 재실행하면 이미 들어간 것 위에 또 쓰게 된다.

작은 테이블(`pl_config_history` 등)은 `foreachPartition` 으로 해도 무방하다. 규칙은 "서비스 테이블은 스테이징, 내부 잡다한 것은 자유"다.

### 배열·enum 컬럼은 스테이징에서 타입을 맞춘다

`trends.trend_types` 가 다이어그램상 `trend_type_array` 다. **Spark JDBC 는 이 타입에 직접 쓸 수 없다고 보고 짠다.**

| 스테이징 컬럼 | MERGE 에서 |
| --- | --- |
| `pl_stage_trends.trend_types text[]` | `trend_types::trend_type[]` 로 캐스트 |

이렇게 두면 실제 타입이 무엇으로 확정되든(`varchar[]`·네이티브 enum 배열·`text[]`) 캐스트 한 줄만 고치면 된다. 반대로 Spark 가 최종 타입에 직접 쓰게 짜두면, 타입이 바뀔 때 적재 코드를 고쳐야 한다.

**⚠️ `@ElementCollection` 이면 배열 컬럼이 아니다.** JPA 로 enum 컬렉션을 매핑할 때 `@ElementCollection` 을 쓰면 Hibernate 는 배열 컬럼이 아니라 **별도 조인 테이블**(`trends_trend_types` 같은 이름)을 만든다. 그러면 적재 대상이 테이블 하나 더가 되고, 유형을 바꿀 때 그 테이블의 행을 지우고 다시 넣어야 한다. 실제 DDL 을 보고 확인해야 한다 ([§5](#5-백엔드에-요청할-것)).

### `RETURNING` 회수

`contents.id` 와 `keywords.id` 는 DB 가 발행하므로 Spark 가 미리 모른다 ([03 §8](03-normalization-spec.md), [05 §5](05-keyword-registry-spec.md)).

```sql
BEGIN;
WITH upserted AS (
  INSERT INTO contents (title, source, url, body_object_key, published_at, collected_at)
  SELECT title, source, url, body_object_key, published_at, collected_at
    FROM pl_stage_contents
  ON CONFLICT (url) DO UPDATE SET
    title = EXCLUDED.title,
    body_object_key = EXCLUDED.body_object_key
  RETURNING id, url
)
INSERT INTO pl_content_id_map (url_hash, content_id)
SELECT sha256(u.url::bytea), u.id
  FROM upserted u
ON CONFLICT (url_hash) DO UPDATE SET content_id = EXCLUDED.content_id;
COMMIT;
```

**`DO NOTHING` 이 아니라 `DO UPDATE` 인 것이 핵심이다.** `DO NOTHING` 은 충돌한 행에 대해 `RETURNING` 을 내주지 않는다. 이미 존재하는 문서의 `id` 를 못 받으면 재처리 때 `keyword_contents` 를 만들 수 없다.

매핑 테이블을 거치는 이유는 결과가 드라이버 메모리를 거치지 않게 하기 위해서다. Spark 는 `pl_content_id_map` 을 평범한 JDBC 소스로 읽어 조인한다. 키를 `url_hash` 로 두는 이유는 긴 URL 문자열을 조인 키로 쓰지 않기 위해서다.

### 트랜잭션 경계

**Job 전체를 한 트랜잭션으로 묶지 않는다.** 테이블 단위(또는 논리 단계 단위)로 커밋한다.

Job 하나가 몇 분 돌 수 있는데, 그동안 트랜잭션을 열어두면 서비스 조회가 락에 걸리고 WAL 이 쌓인다. 단계 사이의 원자성은 [01 §4](01-architecture.md) 의 처리 이력으로 확보한다.

## 5. 백엔드에 요청할 것

Spark 는 DDL 권한이 없으므로 정리해 전달한다. **[§6](#6-스키마를-고쳐나가는-방법) 의 티어 구분에 따라 급한 순이다.**

### 티어 1 — 지금 안 하면 나중에 못 한다

| # | 요청 | 없으면 |
| --- | --- | --- |
| 1 | **`keywords (domain, normalized_name)` UNIQUE** | `ON CONFLICT` 가 동작하지 않는다. **같은 키워드가 매 배치마다 새 행으로 쌓인다.** 며칠이면 복구 불가 ([05 §5](05-keyword-registry-spec.md)) |
| 2 | **`keyword_metrics (keyword_id, period)` UNIQUE** | "기간별 1행" 이 보장되지 않는다. 재실행마다 같은 기간이 중복 삽입되고 목록에 같은 키워드가 여러 번 나온다 |
| 3 | **`keyword_metric_history (keyword_id, bucket_start)` UNIQUE** | 재계산할 때마다 같은 날짜가 그래프에 여러 번 나온다. **화면에 바로 보이는 종류의 오류다** |

**`normalized_name` 단독 UNIQUE 가 아니라 `domain` 과의 복합이어야 한다.** 단독으로 걸면 개발의 `모델` 과 패션의 `모델` 이 충돌해 한쪽이 들어가지 못한다. 도메인이 다르면 다른 개념이고, 이건 [05 §6](05-keyword-registry-spec.md) 의 동형이의어 분리 근거이기도 하다.

**1번이 압도적으로 급하다.** 2·3 은 중복이 쌓여도 청소할 수 있다 — 아무 FK 도 그 두 테이블을 참조하지 않으므로 지우고 다시 계산하면 된다. 1번은 한 번 어긋나면 어느 행이 진짜인지 판별할 수가 없다 — `keyword_contents` 는 3번 행을, `member_interest_keywords` 는 47번 행을, `trends` 는 88번 행을 가리키고 있는 상태가 되기 때문이다.

### 티어 2 — 지금은 공짜, 나중엔 마이그레이션

| # | 요청 | 왜 지금인가 |
| --- | --- | --- |
| 4 | `keyword_metric_history` 를 `bucket_start` 기준 RANGE 파티셔닝 | 테이블이 비어 있을 때는 공짜다. 아래 참조 |
| 5 | `contents.url` 의 varchar 길이 확인, 가능하면 `sha256(url)` 해시 컬럼으로 UNIQUE 이전 | 긴 URL 에서 삽입이 실패해 배치가 죽는다 ([03 §8](03-normalization-spec.md)). 나중에 옮기면 데이터 이관이 따른다 |

`keyword_metric_history` 가 **가장 빠르게 자라는 테이블이다.** 활성 키워드 × 날짜이고, 매 실행이 최근 W일 버킷을 다시 쓴다. 파티션이 없으면 그 갱신·삭제가 테이블 전체를 상대로 반복되어 부풀고 VACUUM 부담이 는다. **성능 최적화가 아니라 매일 반복되는 작업의 형태 문제다.**

`keyword_metrics` 는 파티셔닝이 필요 없다. 활성 키워드 × 3 으로 크기가 고정된다 — 이력이 아니라 스냅샷이기 때문이다.

### 티어 3 — 언제든 싸다. 구현하면서

| # | 요청 |
| --- | --- |
| 6 | **`keyword_metrics` 에 `trend_types` 추가** — 기간별 유형을 담을 자리 ([07 §6](07-metrics-and-ranking-spec.md)) |
| 7 | `keyword_metrics (period, mention_rank)` 인덱스 — 목록 조회 |
| 8 | `keyword_metric_history (bucket_start)` 인덱스 — 범위 삭제·재계산용 |
| 9 | `keyword_relations (source_keyword_id <> target_keyword_id)` CHECK |
| 10 | `keyword_relations (source_keyword_id, relation_score DESC)` 인덱스 |
| 11 | `keyword_contents (keyword_id)` 인덱스 |
| 12 | `keyword_metrics` 에 `previous_rank` 추가 — 순위 변동을 보여주기로 하면 |

**6번이 티어 3 중 유일하게 화면을 바꾼다.** 지금 `trend_types` 는 `trends` 에 있어 기간 구분이 없다. `24H` 에서만 `RISING` 인 키워드가 `30D` 목록에서도 `RISING` 배지를 단다. 컬럼 하나가 그걸 정확하게 만든다. 8번은 4번(파티셔닝)이 들어가면 자동 해소된다.

### 확인만 필요한 것

| # | 질문 | 왜 |
| --- | --- | --- |
| 13 | **`trend_type_array` 가 실제로 무엇인가** | 네이티브 enum 배열이면 캐스트가 필요하고, `@ElementCollection` 이면 별도 조인 테이블이라 적재 대상이 달라진다 ([§4](#4-쓰는-방법--스테이징--서버사이드-merge)) |
| 14 | `trend_types` 의 "유형 없음" 을 빈 배열로 둘 것인가 | 빈 배열과 `NULL` 이 섞이면 조회 조건이 두 가지가 된다 ([07 §6](07-metrics-and-ranking-spec.md)) |
| 15 | `domain` 필드에 `@Enumerated(EnumType.STRING)` 이 붙어 있는가 | JPA 기본값이 `ORDINAL` 이다 ([01 §6](01-architecture.md)) |
| 16 | `growth_amount` 가 생성 컬럼인가 | 생성 컬럼이면 INSERT 에서 빼야 한다 |
| 17 | `mention_rank` 가 `NOT NULL` 인가 | 언급량 0 인 기간에 넣을 순위가 없다 ([07 §5](07-metrics-and-ranking-spec.md)) |
| 18 | `keywords` 를 참조하는 FK 의 `ON DELETE` 정책 | [05 §1](05-keyword-registry-spec.md) |
| 19 | `relation_score` · `growth_rate` 의 numeric 정밀도 | 반올림 자리를 맞춰야 한다 |
| 20 | `contents.title` 의 varchar 길이 | 초과 시 자를 위치 |
| 21 | `period` 의 허용 값 | varchar 라 코드가 정하는 대로 굳는다. `24H`/`7D`/`30D` 를 제안 |
| 22 | `NOT NULL` 인 컬럼 목록 | 다이어그램에 표시가 없다 |

### 미리 요청하지 않는 것

**`keyword_metrics`·`keyword_metric_history` 에 `domain` 을 비정규화하는 것.** v1 에서는 도메인별 목록 조회가 `trend_metrics → trends → keywords` 3단 조인이라 이 논의가 있었다. 지표의 키가 키워드로 바뀌면서 `keyword_metrics → keywords` 2단이 됐으므로 **논의 자체가 필요 없어졌다.**

**`keyword_metric_history` 의 시간 버킷.** 버킷 폭은 두 시각의 차로 담기므로 스키마 변경 없이 나중에 섞을 수 있다 ([07 §3](07-metrics-and-ranking-spec.md)). 필요한 것은 컬럼이 아니라 원자료를 시간 단위로 세우는 일이다.

**`keyword_metrics.measured_at`.** 그 행이 언제 계산됐는지는 운영 정보라 내부 `pl_batch_stat` 으로 충분하다. 서비스 화면이 요구하면 그때 티어 3 으로 넣는다.

## 6. 스키마를 고쳐나가는 방법

DB 가 초기 버전이라 구현하면서 고칠 수 있다. **그게 옳은 방식이다** — 실제 데이터를 보기 전에 스키마를 확정하는 것은 추측이고, [04](04-keyword-extraction-spec.md)~[07](07-metrics-and-ranking-spec.md) 이 임계값을 숫자로 명시하지 않은 것과 같은 이유다.

다만 변경 비용이 균일하지 않다.

| 티어 | 무엇 | 언제 |
| --- | --- | --- |
| **1. 지금 안 하면 나중에 못 한다** | **UNIQUE 제약** | **먼저** |
| 2. 지금은 공짜, 나중엔 마이그레이션 | 파티셔닝, 컬럼 타입 변경, UNIQUE 대상 컬럼 이전 | 가능하면 먼저 |
| 3. 언제든 싸다 | 인덱스, nullable 컬럼 추가, CHECK, 비정규화 | 구현하면서 |

**티어 1 이 유일한 예외인 이유** — 제약은 나쁜 데이터를 *막는* 장치라, 이미 나빠진 데이터에는 소급 적용이 안 된다. 중복이 쌓인 뒤에 UNIQUE 를 붙이려면 먼저 청소해야 하는데, 여러 FK 가 서로 다른 중복 행을 가리키고 있으면 무엇이 진짜인지 판별할 수 없다. 여기서는 "나중에 고치면 된다"가 성립하지 않는다.

### ⚠️ 지금은 점진적 변경이 불가능하다

`backend/backend/src/main/resources/application-dev.yml` 이 이렇다.

```yaml
  jpa:
    hibernate:
      ddl-auto: create
```

`update` 가 아니라 **`create` 다. 백엔드가 기동할 때마다 스키마를 전부 drop 하고 다시 만든다.** 그리고 `build.gradle` 에 Flyway 도 Liquibase 도 없다 — 마이그레이션 도구가 없고 JPA 가 스키마의 유일한 소유자다.

이 상태의 결과:

- **Spark 가 며칠 수집한 데이터가 백엔드 재배포 한 번에 사라진다.** `contents`, `keywords`, `keyword_metrics`, `keyword_metric_history`, `trends` 전부. 사용자의 `member_interest_keywords` 도 같이 간다.
- **`pl_*` 는 살아남는다.** JPA 가 매핑하지 않는 테이블이라 `ddl-auto` 가 손대지 않는다. 그래서 지표와 시계열은 원자료에서 다시 계산할 수 있다 — **v2 에서 `keywords.first_seen_at` 이 없어진 덕에 "시간이 지나야만 다시 쌓이는 값" 이 서비스 테이블에서 사라졌다.** `NEW` 판별 근거가 파이프라인 소유 원자료로 내려왔다 ([§3](#3-파이프라인-내부-테이블)).
- **그래도 자동 복구는 안 된다.** `contents`·`keywords` 의 `id` 가 새로 발행되므로 `pl_content_id_map`·`pl_keyword_id_map` 이 전부 끊어진 참조가 된다. `contents` 를 다시 채우려면 Kafka checkpoint 가 이미 지나 있어 [02 §6](02-input-contract.md) 모드 B(MinIO 프리픽스 스캔)로 재처리해야 한다.
- 스키마를 고치는 수단이 `ddl-auto` 뿐인데 그게 곧 전체 초기화라, **점진적 변경이라는 개념 자체가 성립하지 않는다.**

| 시점 | 조치 |
| --- | --- |
| **지금 당장** | `ddl-auto: create` → `update`. 데이터 유실을 먼저 막는다 |
| 중기 | Flyway 도입, `ddl-auto: validate`. 마이그레이션 파일이 스키마의 단일 진실이 되고, [§5](#5-백엔드에-요청할-것) 의 제약도 거기에 덧붙인다 |

`update` 는 임시방편이다. **UNIQUE 제약을 추가해주지 않고 컬럼 삭제도 하지 않는다.** 그래서 [§5](#5-백엔드에-요청할-것) 티어 1 은 `update` 상태에서도 별도로 DDL 을 쳐야 한다.

### `pl_*` 는 서비스 테이블에 FK 를 걸지 않는다

Hibernate 의 PostgreSQL dialect 는 `drop table ... cascade` 를 쓴다. 내부 테이블이 서비스 테이블에 FK 를 걸어두면 **`ddl-auto` 가 서비스 테이블을 지울 때 그 FK 가 조용히 함께 지워진다.** 남는 것은 끊어진 참조뿐이고, 오류도 나지 않는다.

그래서 `pl_content_id_map.content_id`, `pl_keyword_id_map.keyword_id` 같은 컬럼은 **논리적 참조로만 둔다.** 무결성은 파이프라인이 책임진다.

FK 가 없으므로 **끊어진 참조를 스스로 감지해야 한다.** 각 Job 시작 시 매핑 테이블의 id 가 실제로 서비스 테이블에 있는지 표본 검사하고, 어긋나면 그 구간을 재처리 대상으로 표시한다 ([02 §6](02-input-contract.md) 모드 B). 스키마가 초기화됐는데 파이프라인이 모르고 계속 도는 상황이 가장 나쁘다.
