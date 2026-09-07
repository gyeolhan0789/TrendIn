# ERD 02 — 키워드 사전 · 분석 기반 · 트렌드 · 연관 관계

# ERD 02 — 키워드 사전 · 분석 기반 · 트렌드 · 연관 관계

> 01 문서(열거 타입·회원·분류 체계)에서 이어진다. 이 문서에서 바뀐 부분은 **§1 `KEYWORDS.category_id`**, **§5 `TRENDS.description`**, **§9 `KEYWORD_RELATIONS`의 `period`** 세 곳이다.
> 

---

## 1. KEYWORDS — 정규 키워드 사전(인정)

| 컬럼 | 타입 | 제약 | 설명 |
| --- | --- | --- | --- |
| id | bigint | PK | 응답의 `keywordId` |
| domain_id | bigint | FK(DOMAINS), NOT NULL | 소속 대분류 |
| name | varchar(100) | NOT NULL | `Ballet Sneakers`, `Kubernetes` |
| normalized_name | varchar(100) | NOT NULL | 매칭·중복 판정용 |
| **description** | **varchar(300)** | **NULL 허용** | **15·16·17 `description`. 카드용 한 줄 설명 [추가]** |
| **description_updated_at** | **timestamptz** |  | **설명 생성·갱신 시각 [추가]** |
| created_at | timestamptz | NOT NULL | 생성 시점 |
| updated_at | timestamptz | NOT NULL | 최근 수정 시점 |

```sql
UNIQUE (domain_id, normalized_name);   -- 분야 내 중복 방지

-- [추가] 중분류의 분야와 키워드의 분야가 어긋나는 것을 DB가 막는다
FOREIGN KEY (category_id, domain_id)
  REFERENCES categories (id, domain_id) ON DELETE SET NULL;

INDEX USING GIN (name gin_trgm_ops);   -- 21 부분 일치 검색
INDEX (category_id) WHERE category_id IS NOT NULL;
```

- 파이프라인의 "LLM 기반 키워드 정제 및 유사 표현 통합" **결과물**이다. 후보 키워드·필터링 중간 산출물은 파이프라인 내부에 둔다.
- 14의 "공유 키워드 사전과 분석 데이터는 삭제하지 않는다" — 관심 키워드 삭제가 이 테이블에 영향을 주지 않는다.
- `category_id`를 NULL 허용으로 둔 이유는 키워드 탐지와 중분류 배정 시점이 다르기 때문이다. 배정 전 키워드도 15·21에 노출되어야 하며, 17 응답의 `category`는 이때 `null`이다.
- `ON DELETE SET NULL`을 쓴 것은 중분류 개편이 키워드를 지워서는 안 되기 때문이다. 다만 `domain_id`는 그대로 남으므로 대분류 계보는 유지된다.

---

## 2. DAILY_COLLECTION_STATUS — 일자별 수집 상태

| 컬럼 | 타입 | 제약 | 설명 |
| --- | --- | --- | --- |
| stat_date | date | PK | 집계 일자 (Asia/Seoul) |
| status | collection_status | NOT NULL | COMPLETED / PARTIAL / MISSING |
| total_collected_content_count | bigint | NOT NULL, DEFAULT 0 | 해당 일자 전체 수집량 |
| created_at | timestamptz | NOT NULL | 생성 시점 |
| updated_at | timestamptz | NOT NULL | 최근 갱신 시점 |

**18의 "0"과 "null"을 구분하기 위한 테이블**이다. 언급량 0인 날에도 행을 만들면 키워드 × 일자만큼 행이 늘어나므로, 수집 상태를 일자 단위로 따로 관리하고 조회 시 조합한다.

| 조건 | 18 응답 |
| --- | --- |
| `status = COMPLETED`이고 `keyword_daily_metrics`에 행 없음 | `mentionCount: 0` |
| `status = MISSING` | `mentionCount: null` |
| 해당 기간에 상태 행이 하나도 없음 | `dataStatus: NO_DATA`, 빈 `history` |

`status = PARTIAL`인 일자의 `mentionCount` 처리 규칙이 정의되지 않았다. 수집이 일부만 된 날은 값을 그대로 내릴지 `null`로 볼지 결정이 필요하다 (§10 미결정 6번).

---

## 3. KEYWORD_DAILY_METRICS — 키워드 일별 언급량

| 컬럼 | 타입 | 제약 | 설명 |
| --- | --- | --- | --- |
| keyword_id | bigint | PK, FK(KEYWORDS) ON DELETE CASCADE | 대상 키워드 |
| stat_date | date | PK | 언급 일자 |
| mention_count | bigint | NOT NULL, CHECK(>0) | 해당 일자 언급량 |
| created_at | timestamptz | NOT NULL | 적재 시점 |

```sql
PRIMARY KEY (keyword_id, stat_date);
```

- **언급이 있는 날만 적재**한다. 0인 날은 행을 만들지 않고 `daily_collection_status`와의 조합으로 해석한다. `CHECK(>0)`이 이 규칙을 강제한다.
- 18의 `period`(7d/30d/90d)는 별도 컬럼 없이 `stat_date` 범위 조건으로 처리한다.
- 15의 `mention_count`도 이 테이블의 구간 합계와 일치해야 한다. 불일치 시 `trend_period_metrics`가 우선한다 (분석 시점 고정값).
- 데이터 증가 시 `stat_date` 기준 RANGE 파티셔닝을 고려한다.

---

## 8. CONTENTS — 수집 콘텐츠 메타데이터

| 컬럼 | 타입 | 제약 | 설명 |
| --- | --- | --- | --- |
| id | bigint | PK | 응답의 `contentId` |
| title | varchar(300) | NOT NULL | 콘텐츠 제목 |
| source | varchar(100) |  | 출처 매체 |
| url | varchar(1000) | NOT NULL | 원문 URL |
| url_hash | bytea | UK, NOT NULL | **중복 판정용 해시 [변경]** |
| country_code | char(2) | FK(COUNTRIES) | 출처 국가. 미상이면 NULL |
| published_at | timestamptz |  | 발행 시각. **NULL 가능** |
| created_at | timestamptz | NOT NULL | 수집 시점 |

```sql
UNIQUE (url_hash);   -- sha256(url). 수집 중복 제거의 최종 방어선
CHECK (summary_status = 'COMPLETED' OR summary IS NULL);
```

- **`url`에 직접 UNIQUE를 걸지 않는다.** varchar(1000)에 멀티바이트 URL이 들어오면 B-tree 인덱스 항목 상한(약 2704바이트)을 넘겨 삽입이 실패할 수 있다. 해시 컬럼에 유니크를 걸고 `url`은 표시·이동용으로만 쓴다.
- **본문은 저장하지 않는다.** 19가 "수집 본문 전체를 공개하지 않는다"고 명시하며, 원문은 `url`로만 제공한다.
- 22의 "수집 콘텐츠의 출처 국가 기준"이므로 `country_code`는 이용자 거주 국가가 아니다.

---

## 9. KEYWORD_CONTENTS — 키워드-콘텐츠 등장 관계

| 컬럼 | 타입 | 제약 | 설명 |
| --- | --- | --- | --- |
| keyword_id | bigint | PK, FK(KEYWORDS) ON DELETE CASCADE | 등장 키워드 |
| content_id | bigint | PK, FK(CONTENTS) ON DELETE CASCADE | 콘텐츠 |
| published_at | timestamptz |  | **비정규화**. 정렬·구간 필터용 |
| created_at | timestamptz | NOT NULL | 연결 시점 |

```sql
INDEX (keyword_id, published_at DESC NULLS LAST, content_id);   -- 19 정렬과 정확히 일치
```

- 19가 "**정규 키워드**가 등장한 콘텐츠"를 기준으로 하므로 트렌드가 아닌 **키워드**에 연결한다. 트렌드는 `trends.keyword_id`를 거쳐 접근한다.
- 19의 "현재 트렌드 분석의 최근 기간"은 `analysis_runs.recent_start / recent_end`를 `published_at`에 적용해 필터한다. 다만 **어느 `period`의 run인지 정해지지 않았다** (§10 미결정 3번).
- `published_at`을 비정규화한 이유는 정렬 키가 `contents` 쪽에 있으면 매 조회마다 조인 후 정렬이 필요하기 때문이다.

---

## 6. TREND_PERIOD_METRICS — 기간별 지표·순위·유형

| 컬럼 | 타입 | 제약 | 설명 |
| --- | --- | --- | --- |
| trend_id | bigint | PK, FK(TRENDS) ON DELETE CASCADE | 대상 트렌드 |
| period | metric_period | PK | 24H / 7D / 30D |
| domain_id | bigint | NOT NULL | **비정규화**. 15 필터용 |
| trend_type | trend_type | NOT NULL | 해당 기간의 판정 유형 |
| rank | int | NOT NULL, CHECK(≥1) | 분야·유형·기간 내 언급량 순위 |
| previous_rank | int | CHECK(≥1) | 직전 동일 기간 순위. 없으면 NULL |
| mention_count | bigint | NOT NULL, CHECK(≥0) | 현재 기간 언급량 |
| previous_mention_count | bigint | NOT NULL, CHECK(≥0) | 직전 동일 기간 언급량 |
| growth_amount | bigint | GENERATED ALWAYS AS (mention_count - previous_mention_count) STORED | 증가량 |
| growth_rate | numeric(10,1) |  | 증가율 %. **이전 언급량 0이면 NULL** |
| data_coverage | data_coverage | NOT NULL, DEFAULT 'COMPLETE' | 17 `evidence.dataCoverage` |
| created_at | timestamptz | NOT NULL | 생성 시점 |
| updated_at | timestamptz | NOT NULL | 최근 갱신 시점 |

```sql
PRIMARY KEY (trend_id, period);   -- 기간별 1행, 분석 배치가 upsert
CHECK (previous_mention_count > 0 OR growth_rate IS NULL);

INDEX (domain_id, period, trend_type, rank);   -- 15 목록 조회 및 페이징
INDEX (trend_id);                              -- 17 상세 조회
```

- **`trend_type`과 지표가 기간에 종속된다.** 같은 키워드가 `7D`에서는 `RISING`, `30D`에서는 `CURRENT`일 수 있으므로 `trends`에 둘 수 없다.
- `rank`를 **저장**하는 이유: 15가 "페이지와 무관한 전체 결과 기준 순위"를 요구하고, `previous_rank`는 직전 분석 결과가 있어야 산출된다. 조회 시 계산하면 매 요청마다 두 기간의 전체 집합을 정렬해야 한다.
- `growth_amount`는 생성 컬럼(PostgreSQL 12+)이라 애플리케이션이 계산·저장할 필요가 없다.
- `growth_rate`는 소수 첫째 자리 반올림이 명세된 값이라 `numeric(10,1)`로 고정한다.
- `previous_rank = NULL`은 "이전 순위 없음"이며 **`trend_type = NEW`를 의미하지 않는다**. 15가 명시적으로 구분한다.
- **동점 처리 규칙이 미정이다.** 15번 원문이 "공동 순위 여부와 동점 정렬 기준은 확정하지 않았다"고 적었다. `rank`가 저장 컬럼이므로 배치가 값을 넣기 전에 규칙이 필요하다.
- 21번 검색이 `growthRate`를 반환하는데 `period` 파라미터가 없어 어느 행을 읽을지 정해지지 않았다. 03 문서 미결정 2번.

---

6-1. 집계 테이블 필요

---

## 7. TREND_AI_ANALYSES — AI 요약·상승 배경

| 컬럼 | 타입 | 제약 | 설명 |
| --- | --- | --- | --- |
| trend_id | bigint | PK, FK(TRENDS) ON DELETE CASCADE | 대상 트렌드 (1:1) |
| status | ai_status | NOT NULL, DEFAULT 'PENDING' | PENDING / COMPLETED / FAILED / NO_DATA |
| summary | text |  | 콘텐츠 기반 요약 |
| reason | text |  | 상승 배경 |
| generated_at | timestamptz |  | 생성 시각 |
| created_at | timestamptz | NOT NULL | 생성 시점 |
| updated_at | timestamptz | NOT NULL | 최근 갱신 시점 |

```sql
CHECK (status = 'COMPLETED'
    OR (summary IS NULL AND reason IS NULL AND generated_at IS NULL));
```

- 별도 테이블로 분리한 이유는 **상태를 표현해야 하기 때문**이다. `trends`의 컬럼으로 두면 "분석 전"과 "분석 실패"를 구분할 수 없다.
- 17은 분석 미완료를 오류로 취급하지 않으므로, 행이 없어도 `PENDING`으로 응답할 수 있도록 트렌드 생성 시 기본 행을 함께 만든다.
- **17번 개정본은 `aiAnalysis`도 "선택한 period 기준"이라고 적었으나 이 테이블은 트렌드당 1행이다.** AI 요약이 실제로 기간과 무관하다면 API 문장을 고치고, 기간별로 달라져야 한다면 `TREND_PERIOD_METRICS`처럼 PK에 `period`를 추가해야 한다. 03 문서 미결정 4번.

---

## 8. TREND_AI_SOURCE_CONTENTS — AI 분석 근거 콘텐츠

| 컬럼 | 타입 | 제약 | 설명 |
| --- | --- | --- | --- |
| trend_id | bigint | PK, FK(TREND_AI_ANALYSES) ON DELETE CASCADE | 대상 분석 |
| content_id | bigint | PK, FK(CONTENTS) ON DELETE CASCADE | 근거 콘텐츠 |
| sort_order | int | NOT NULL, DEFAULT 0 | 17 `sourceContentIds` 순서 |
- 17의 `sourceContentIds`다. 19에서 실제 조회 가능한 **살아있는 콘텐츠**를 참조하므로 배열이 아닌 테이블로 두고 FK 무결성을 건다.

---

## 9. KEYWORD_RELATIONS — 키워드 연관 관계 **[개정]**

| 컬럼 | 타입 | 제약 | 설명 |
| --- | --- | --- | --- |
| source_keyword_id | bigint | PK, FK(KEYWORDS) ON DELETE CASCADE | 기준 키워드 |
| target_keyword_id | bigint | PK, FK(KEYWORDS) ON DELETE CASCADE | 연관 키워드 |
| **period** | **metric_period** | **PK** | **24H / 7D / 30D [추가]** |
| analysis_run_id | bigint | FK(ANALYSIS_RUNS), NOT NULL | 집계 구간 |
| co_occurrence_count | bigint | NOT NULL, CHECK(≥0) | 동시 등장 콘텐츠 수 |
| relation_score | numeric(5,4) | NOT NULL, CHECK(0~1) | 연관 정도 |
| previous_relation_score | numeric(5,4) | CHECK(0~1) | 직전 동일 기간 연관 정도 |
| change_rate | numeric(10,1) |  | 변화율 %. **이전 점수 0이면 NULL** |
| relation_status | relation_status | NOT NULL | NEW / RISING / STABLE |
| computed_at | timestamptz | NOT NULL | 산출 시점 |

```sql
PRIMARY KEY (source_keyword_id, target_keyword_id, period);   -- [변경]

CHECK (source_keyword_id <> target_keyword_id);
CHECK (previous_relation_score > 0 OR change_rate IS NULL);   -- [추가] 20 changeRate 규칙

-- 20 정렬(점수 내림차순, keywordId 오름차순)
INDEX (source_keyword_id, period, relation_score DESC, target_keyword_id);   -- [변경]
-- 16의 신규·상승 우선 정렬
INDEX (source_keyword_id, period, relation_status);                          -- [변경]
```

### 개정 근거

16번 개정본이 `period`를 **필수**로 받고 "연관도와 연관도 변화는 선택한 `period`와 직전 동일 기간을 기준으로 계산한다"고 명시한다. 기존 PK `(source, target)`으로는 기간당 한 벌만 저장할 수 있어 24H·7D·30D 요청을 구분할 수 없었다.

`TREND_PERIOD_METRICS`가 `(trend_id, period)`를 PK로 두고 기간별 upsert하는 것과 동일한 패턴을 적용했다. 지표 테이블 전반에서 "기간 종속 데이터는 PK에 `period`를 포함한다"는 규칙이 일관되게 유지된다.

`analysis_run_id`는 그대로 두되, `analysis_runs.period`와 이 행의 `period`가 반드시 일치해야 한다. DB로 강제하려면 `analysis_runs`에 `UNIQUE(id, period)`를 만들고 복합 FK를 걸 수 있다. 배치가 단일 진입점이므로 애플리케이션 검증으로 갈지는 선택 사항이다.

### 유지되는 설계

- **양방향 2행으로 저장**한다. 20은 트렌드 → 연관 키워드 방향, 16은 관심 키워드 → 연관 트렌드 방향이라 한쪽만 저장하면 16에서 UNION이 필요해진다. `period` 추가로 행 수는 기간 수만큼 늘어난다(기존 대비 3배).
- 20의 `trendId`는 `target_keyword_id → trends` 조인 결과이며, 트렌드 미탐지 키워드는 `LEFT JOIN` 결과 NULL이다.
- `previous_relation_score`를 행 안에 두므로 이력 테이블 없이 기간별 최신 1행만 upsert한다.

### 행 수 관리

기간 3벌 × 양방향 2행이므로 키워드 쌍 하나가 최대 6행이 된다. 상위 N개만 저장하도록 배치에서 잘라내는 정책이 필요하다. 20·16이 페이징을 지원하므로 실제 노출량 기준으로 상한을 잡는다.

### 함께 필요한 API 수정

20번 연관 키워드 조회에 `period` 파라미터가 없다. 응답에는 `analysisWindow`가 있으므로 이미 기간 개념이 전제되어 있고, 스키마가 기간별로 나뉜 이상 20번도 `period`를 받아야 한다. 03 문서 미결정 1번.