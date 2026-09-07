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
| `trend_metrics` | aggregate | `(trend_id, period, period_start)` ⚠️ | upsert 또는 범위 삭제 후 삽입 | 재계산 구간 W |
| `keyword_relations` | aggregate | `(source, target)` PK | **source 별 삭제 후 삽입** | 계산한 source 만 |

⚠️ 표시는 **제약이 실제로 존재하는지 확인되지 않은 것**이다. [§5](#5-백엔드에-요청할-것).

### `contents` 와 `keywords` 를 지우지 않는 이유

둘 다 사용자 데이터가 매달려 있다.

- `contents` — `keyword_contents` 가 참조한다. 한 행을 지우면 사용자에게 보이던 관련 콘텐츠 연결이 사라진다.
- `keywords` — `member_interest_keywords`, `trends`, `keyword_contents`, `keyword_relations` 가 참조한다. 자세한 것은 [05 §1](05-keyword-registry-spec.md).

재처리도 이 둘은 upsert 로만 처리한다.

### `trends` 는 갱신만 한다

```sql
INSERT INTO trends (keyword_id, first_detected_at, updated_at)
SELECT keyword_id, :now, :now FROM pl_stage_trends
ON CONFLICT (keyword_id) DO UPDATE SET
  updated_at = EXCLUDED.updated_at;
  -- first_detected_at 은 건드리지 않는다
  -- description · summary · reason 은 건드리지 않는다
```

`first_detected_at` 을 갱신하지 않는 것이 핵심이다 ([07 §4](07-metrics-and-ranking-spec.md)). 갱신하면 오래된 트렌드가 매번 "방금 감지됨"이 된다.

`description`·`summary`·`reason` 을 `DO UPDATE` 에서 빼는 이유는, 나중에 LLM 태스크가 채운 값을 `aggregate` 가 다시 `NULL` 로 덮어쓰지 않게 하기 위해서다. **지금은 채우지 않지만 미래를 막지 않는다.**

### `keyword_relations` 만 삭제 후 삽입인 이유

상위 N 으로 자르기 때문이다. upsert 로는 **이번에 상위 N 에서 밀려난 행을 지울 수 없다.** 자세한 것은 [06 §7](06-related-keyword-spec.md).

### `trend_metrics` 는 이력이다

기간별 최신 1행이 아니라 측정마다 행이 쌓인다 ([07 §2](07-metrics-and-ranking-spec.md)). 그래서 upsert 의 충돌 키가 `trend_id` 가 아니라 `(trend_id, period, period_start)` 다.

**`previous_rank`·`previous_mention_count` 를 직전 행에서 이월하지 않는다.** 직전 구간을 원자료에서 다시 계산한다 ([07 §5](07-metrics-and-ranking-spec.md)). 덕분에 같은 날 몇 번을 재실행해도 결과가 같다 — 이월 구조였다면 재실행이 곧 오염이었다.

## 3. 파이프라인 내부 테이블

| 테이블 | 담는 것 | 쓰는 Job |
| --- | --- | --- |
| `pl_processing_ledger` | `(event_id, job)` 별 상태·건수·시각 | 전부 |
| `pl_processing_error` | DLQ 미러. `error_type`, 원본 이벤트 | ingest |
| `pl_batch_stat` | 배치별 정제 통계 + **일자별 수집 상태** ([02 §4](02-input-contract.md)) | ingest |
| `pl_content_id_map` | `url_hash` → `contents.id` | ingest |
| `pl_keyword_id_map` | `(domain, normalized_key)` → `keywords.id` | extract |
| `pl_candidate` | 후보 마스터. 대표 표기, **최초 관측 시각**, 승격 상태 | extract |
| `pl_document_candidate` | 문서 × 후보 점수 ([04 §7](04-keyword-extraction-spec.md)) | extract |
| `pl_keyword_daily_stat` | **키워드·후보별 일별 원자료** | extract |
| `pl_alias` | 별칭 → 대표. 근거 층, 신뢰도 | extract |
| `pl_merge_log` | 병합 이력 ([05 §8](05-keyword-registry-spec.md)) | extract |
| `pl_review_queue` | 검수 큐 ([05 §7](05-keyword-registry-spec.md)) | extract |
| `pl_embedding_cache` | 표기 → 벡터 ([01 §5](01-architecture.md)) | extract |
| `pl_config_history` | 임계값 변경 이력 ([04 §10](04-keyword-extraction-spec.md)) | 수동 |

### `pl_keyword_daily_stat` 이 이 묶음의 실질적 원본이다

현행 스키마에 키워드별 일별 지표 테이블이 없으므로, **이 내부 테이블이 모든 집계의 원자료**다. `trend_metrics` 는 여기서 파생된 요약이다.

| 컬럼 | 왜 필요한가 |
| --- | --- |
| `(domain, normalized_key)` | **승격 전 후보는 `keyword_id` 가 없다.** 그래서 키가 이것이다 |
| `keyword_id` | 승격 후 채운다. `NULL` 이면 아직 후보 |
| `stat_date` | 발행 기준 날짜 ([07 §3](07-metrics-and-ranking-spec.md)) |
| `doc_count` | 언급량. 서비스로 나가는 유일한 값 |
| `occurrence_count` | 이상 탐지 ([07 §7](07-metrics-and-ranking-spec.md)) |
| `source_count` | 승격·`NEW` 판정 ([05 §5](05-keyword-registry-spec.md), [07 §5](07-metrics-and-ranking-spec.md)) |
| `author_count` | 같음 — **봇 방어의 핵심** |
| `doc_count_with_dup` | 크로스포스트 영향 측정 |

**승격 전 후보의 통계가 여기 있어야만 승격 심사가 성립한다.** 후보는 `keywords` 에 없으므로 서비스 테이블 어디에도 값을 둘 수 없는데, 승격을 판단하려면 누적 통계가 필요하다.

`pl_candidate.최초 관측 시각` 도 같은 이유다. 이 값이 승격 시점에 `keywords.first_seen_at` 으로 옮겨 가고, 그게 `NEW` 판정의 근거가 된다 ([05 §5](05-keyword-registry-spec.md)).

### 보존

| 테이블 | 정리 |
| --- | --- |
| `pl_document_candidate` | 가장 빠르게 자란다. 최근 N일만 유지 |
| `pl_keyword_daily_stat` | **지우지 않는다.** 모든 재계산의 원본이다 |
| `pl_processing_ledger` · `pl_batch_stat` | 오래 남긴다. 작고 운영 조회에 쓴다 |
| `pl_candidate` · `pl_alias` · `pl_merge_log` | 지우지 않는다. 최초 관측 시각이 소실되면 `NEW` 판정이 깨진다 |
| `pl_embedding_cache` | 표기가 사라지면 함께 정리 |

`pl_document_candidate` 를 지우면 [04 §10](04-keyword-extraction-spec.md) 의 "임계값을 낮춰 재평가"가 그 구간에서 불가능해진다. 보존 기간은 재평가하고 싶은 범위와 같게 잡는다.

## 4. 쓰는 방법 — 스테이징 + 서버사이드 MERGE

**Spark JDBC 는 upsert 를 못 한다.** `mode="append"` 는 순수 INSERT 라 충돌하면 배치가 죽는다.

```
1. Spark  →  JDBC append  →  pl_stage_*        (순수 INSERT, 빠름)
2. 서버   →  BEGIN
              INSERT ON CONFLICT / DELETE+INSERT
              TRUNCATE pl_stage_*
             COMMIT
3. 필요하면 매핑 테이블을 JDBC 로 되읽는다
```

### 왜 `foreachPartition` 이 아닌가

| | 스테이징 | foreachPartition |
| --- | --- | --- |
| 원자성 | **한 트랜잭션.** 전부 반영되거나 전부 아님 | 파티션별 커밋. 중간 실패 시 절반만 반영 |
| 커넥션 | 드라이버 1개 | executor 수만큼 동시 접속 |
| 범위 삭제 | 같은 트랜잭션 안에서 가능 | 별도 처리 필요 |
| `RETURNING` 회수 | 매핑 테이블 경유로 자연스럽다 | executor 로 흩어져 모으기 어렵다 |
| 코드 | SQL 이 밖에 나온다 | 파이썬 안에 다 있다 |

**절반만 반영된 상태가 가장 나쁘다.** 재실행하면 이미 들어간 것 위에 또 쓰게 된다.

작은 테이블(`pl_config_history` 등)은 `foreachPartition` 으로 해도 무방하다. 규칙은 "서비스 테이블은 스테이징, 내부 잡다한 것은 자유"다.

### `RETURNING` 회수

`contents.id` 와 `keywords.id` 는 DB 가 발급하므로 Spark 가 미리 모른다 ([03 §8](03-normalization-spec.md), [05 §5](05-keyword-registry-spec.md)).

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

Job 하나가 몇 분 돌 수 있는데, 그동안 트랜잭션을 열어두면 서비스 조회가 락에 걸리고 WAL 이 쌓인다. 단계 사이의 원자성은 [01 §4](01-architecture.md) 의 원장으로 확보한다.

## 5. 백엔드에 요청할 것

Spark 는 DDL 권한이 없으므로 정리해 전달한다. **[§6](#6-스키마를-고쳐나가는-방법) 의 티어 구분에 따라 급한 순이다.**

### 티어 1 — 지금 안 하면 나중에 못 한다

| # | 요청 | 없으면 |
| --- | --- | --- |
| 1 | **`keywords (domain, normalized_name)` UNIQUE** | `ON CONFLICT` 가 동작하지 않는다. **같은 키워드가 매 배치마다 새 행으로 쌓인다.** 며칠이면 복구 불가 ([05 §5](05-keyword-registry-spec.md)) |
| 2 | **`trend_metrics (trend_id, period, period_start)` UNIQUE** | 재실행마다 같은 측정이 중복 삽입된다. 그래프에 같은 날짜가 여러 번 나온다 |

**`normalized_name` 단독 UNIQUE 가 아니라 `domain` 과의 복합이어야 한다.** 단독으로 걸면 개발의 `모델` 과 패션의 `모델` 이 충돌해 한쪽이 들어가지 못한다. 도메인이 다르면 다른 개념이고, 이건 [05 §6](05-keyword-registry-spec.md) 의 동형이의어 분리 근거이기도 하다.

**1번이 압도적으로 급하다.** 나머지는 문제가 생겨도 고칠 수 있지만, 1번은 한 번 어긋나면 어느 행이 진짜인지 판정할 수가 없다 — `keyword_contents` 는 3번 행을, `member_interest_keywords` 는 47번 행을, `trends` 는 88번 행을 가리키고 있는 상태가 되기 때문이다.

### 티어 2 — 지금은 공짜, 나중엔 마이그레이션

| # | 요청 | 왜 지금인가 |
| --- | --- | --- |
| 3 | `trend_metrics` 를 `period_start` 기준 RANGE 파티셔닝 | 테이블이 비어 있을 때는 공짜다. 아래 참조 |
| 4 | `contents.url` 의 varchar 길이 확인, 가능하면 `sha256(url)` 해시 컬럼으로 UNIQUE 이전 | 긴 URL 에서 삽입이 실패해 배치가 죽는다 ([03 §8](03-normalization-spec.md)). 나중에 옮기면 데이터 이관이 따른다 |

`trend_metrics` 는 [07 §2](07-metrics-and-ranking-spec.md) 의 일별 시계열을 담으므로 **가장 빠르게 자란다.** 트렌드 수 × 날짜 수 × 기간 3벌이다. 그리고 매 실행이 최근 W일을 지우고 다시 넣으므로, 파티션이 없으면 대량 DELETE 가 매일 반복되어 테이블이 부풀고 VACUUM 부담이 는다. **성능 최적화가 아니라 매일 반복되는 작업의 형태 문제다.**

### 티어 3 — 언제든 싸다. 구현하면서

| # | 요청 |
| --- | --- |
| 5 | `keyword_relations (source_keyword_id <> target_keyword_id)` CHECK |
| 6 | `trend_metrics (period, period_start)` 인덱스 — 범위 삭제용 ([07 §6](07-metrics-and-ranking-spec.md)) |
| 7 | `trend_metrics (trend_id, period, period_start DESC)` 인덱스 — 시계열 조회 |
| 8 | `keyword_relations (source_keyword_id, relation_score DESC)` 인덱스 |
| 9 | `keyword_contents (keyword_id)` 인덱스 |

6번이 적재 쪽에서 특히 중요하다. `trend_metrics` PK 가 `id` 라 `period_start` 범위 조건이 인덱스를 못 탄다. 다만 3번(파티셔닝)이 들어가면 자동 해소된다.

### 확인만 필요한 것

| # | 질문 | 왜 |
| --- | --- | --- |
| 10 | `domain` 필드에 `@Enumerated(EnumType.STRING)` 이 붙어 있는가 | JPA 기본값이 `ORDINAL` 이다 ([01 §6](01-architecture.md)) |
| 11 | `growth_amount` 가 생성 컬럼인가 | 생성 컬럼이면 INSERT 에서 빼야 한다 |
| 12 | `keywords` 를 참조하는 FK 의 `ON DELETE` 정책 | [05 §1](05-keyword-registry-spec.md) |
| 13 | `relation_score` · `growth_rate` 의 numeric 정밀도 | 반올림 자리를 맞춰야 한다 |
| 14 | `contents.title` 의 varchar 길이 | 초과 시 자를 위치 |
| 15 | `NOT NULL` 인 컬럼 목록 | 다이어그램에 표시가 없다 |

### 미리 요청하지 않는 것

`trend_metrics` 나 `trends` 에 `domain` 을 비정규화하는 것. 지금은 도메인별 목록 조회가 `trend_metrics → trends → keywords` 3단 조인이다 ([07 §5](07-metrics-and-ranking-spec.md)).

[00 §3](00-overview.md) 규모에서 이 조인이 문제될지 알 수 없고, 비정규화는 갱신 일관성 부담을 만든다. **티어 3이므로 백엔드가 느리다고 할 때 넣으면 된다.**

## 6. 스키마를 고쳐나가는 방법

DB 가 초기 버전이라 구현하면서 고칠 수 있다. **그게 옳은 방식이다** — 실제 데이터를 보기 전에 스키마를 확정하는 것은 추측이고, [04](04-keyword-extraction-spec.md)~[07](07-metrics-and-ranking-spec.md) 이 임계값을 숫자로 못박지 않은 것과 같은 이유다.

다만 변경 비용이 균일하지 않다.

| 티어 | 무엇 | 언제 |
| --- | --- | --- |
| **1. 지금 안 하면 나중에 못 한다** | **UNIQUE 제약** | **먼저** |
| 2. 지금은 공짜, 나중엔 마이그레이션 | 파티셔닝, 컬럼 타입 변경, UNIQUE 대상 컬럼 이전 | 가능하면 먼저 |
| 3. 언제든 싸다 | 인덱스, nullable 컬럼 추가, CHECK, 비정규화 | 구현하면서 |

**티어 1 이 유일한 예외인 이유** — 제약은 나쁜 데이터를 *막는* 장치라, 이미 나빠진 데이터에는 소급 적용이 안 된다. 중복이 쌓인 뒤에 UNIQUE 를 붙이려면 먼저 청소해야 하는데, 여러 FK 가 서로 다른 중복 행을 가리키고 있으면 무엇이 진짜인지 판정할 수 없다. 여기서는 "나중에 고치면 된다"가 성립하지 않는다.

### ⚠️ 지금은 점진적 변경이 불가능하다

`backend/backend/src/main/resources/application-dev.yml` 이 이렇다.

```yaml
  jpa:
    hibernate:
      ddl-auto: create
```

`update` 가 아니라 **`create` 다. 백엔드가 기동할 때마다 스키마를 전부 drop 하고 다시 만든다.** 그리고 `build.gradle` 에 Flyway 도 Liquibase 도 없다 — 마이그레이션 도구가 없고 JPA 가 스키마의 유일한 소유자다.

이 상태의 결과:

- **Spark 가 며칠 수집한 데이터가 백엔드 재배포 한 번에 사라진다.** `contents`, `keywords`, `trend_metrics` 전부.
- 재수집으로 복구되지 않는다. `keywords.first_seen_at` 이 리셋되면 [07 §5](07-metrics-and-ranking-spec.md) 의 `NEW` 판정이 통째로 어긋난다. 그건 **시간이 지나야만 다시 쌓이는 값**이다.
- 스키마를 고치는 수단이 `ddl-auto` 뿐인데 그게 곧 전체 초기화라, **점진적 변경이라는 개념 자체가 성립하지 않는다.**

| 시점 | 조치 |
| --- | --- |
| **지금 당장** | `ddl-auto: create` → `update`. 데이터 유실을 먼저 막는다 |
| 중기 | Flyway 도입, `ddl-auto: validate`. 마이그레이션 파일이 스키마의 단일 진실이 되고, [§5](#5-백엔드에-요청할-것) 의 제약도 거기에 얹는다 |

`update` 는 임시방편이다. **UNIQUE 제약을 추가해주지 않고 컬럼 삭제도 하지 않는다.** 그래서 [§5](#5-백엔드에-요청할-것) 티어 1 은 `update` 상태에서도 별도로 DDL 을 쳐야 한다.

### `pl_*` 는 서비스 테이블에 FK 를 걸지 않는다

Hibernate 의 PostgreSQL dialect 는 `drop table ... cascade` 를 쓴다. 내부 테이블이 서비스 테이블에 FK 를 걸어두면 **`ddl-auto` 가 서비스 테이블을 지울 때 그 FK 가 조용히 함께 지워진다.** 남는 것은 끊어진 참조뿐이고, 오류도 나지 않는다.

그래서 `pl_content_id_map.content_id`, `pl_keyword_id_map.keyword_id` 같은 컬럼은 **논리적 참조로만 둔다.** 무결성은 파이프라인이 책임진다.

FK 가 없으므로 **끊어진 참조를 스스로 감지해야 한다.** 각 Job 시작 시 매핑 테이블의 id 가 실제로 서비스 테이블에 있는지 표본 검사하고, 어긋나면 그 구간을 재처리 대상으로 표시한다 ([02 §6](02-input-contract.md) 모드 B). 스키마가 초기화됐는데 파이프라인이 모르고 계속 도는 상황이 가장 나쁘다.
