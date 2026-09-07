# ERD 00 — 현행 정본 (이미지 전사)

**이 문서가 정본이다.** 같은 디렉터리의 `erd-01-*`, `erd-02-*` 는 별도로 진행된 개정 제안이며 현재 채택되지 않았다 ([`README.md`](README.md) 참조).

원본은 다이어그램 이미지다. 이 파일은 Spark 쪽에서 참조하기 위한 **전사본**이며, 원본 다이어그램이 바뀌면 여기도 갱신해야 한다. 타입·제약은 이미지에 표시된 것만 옮겼고, 이미지에 없는 것(ON DELETE 정책, 인덱스, CHECK, NOT NULL 여부)은 **미표기**다.

## 테이블 12개

### members

| 타입 | 컬럼 | 키 |
| --- | --- | --- |
| bigint | id | PK |
| varchar | email | UK |
| varchar | password_hash | |
| varchar | nickname | |
| boolean | onboarding_completed | |
| timestamptz | created_at | |

### member_domains

| 타입 | 컬럼 | 키 |
| --- | --- | --- |
| bigint | id | PK |
| bigint | member_id | FK → members |
| varchar | domain | |

### member_interest_keywords

| 타입 | 컬럼 | 키 |
| --- | --- | --- |
| bigint | id | PK |
| bigint | member_id | FK → members |
| bigint | keyword_id | FK → keywords |
| timestamptz | created_at | |

### keywords

| 타입 | 컬럼 | 키 |
| --- | --- | --- |
| bigint | id | PK |
| varchar | domain | |
| varchar | name | |
| varchar | normalized_name | |
| timestamptz | first_seen_at | |

### contents

| 타입 | 컬럼 | 키 |
| --- | --- | --- |
| bigint | id | PK |
| varchar | title | |
| varchar | source | |
| varchar | url | UK |
| text | body_object_key | |
| timestamptz | published_at | |
| timestamptz | collected_at | |
| text | summary | |

### keyword_contents

| 타입 | 컬럼 | 키 |
| --- | --- | --- |
| bigint | keyword_id | PK, FK → keywords |
| bigint | content_id | PK, FK → contents |

### keyword_relations

| 타입 | 컬럼 | 키 |
| --- | --- | --- |
| bigint | source_keyword_id | PK, FK → keywords |
| bigint | target_keyword_id | PK, FK → keywords |
| numeric | relation_score | |
| bigint | co_occurrence_count | |
| timestamptz | updated_at | |

### trends

| 타입 | 컬럼 | 키 |
| --- | --- | --- |
| bigint | id | PK |
| bigint | keyword_id | FK → keywords, **UK** |
| timestamptz | first_detected_at | |
| varchar | description | |
| text | summary | |
| text | reason | |
| timestamptz | updated_at | |

`keyword_id` 에 UK 가 있으므로 키워드 하나당 트렌드는 최대 하나다. 모든 키워드가 트렌드가 되는 것은 아니다.

### trend_metrics

| 타입 | 컬럼 | 키 |
| --- | --- | --- |
| bigint | id | PK |
| bigint | trend_id | FK → trends |
| varchar | period | |
| date | period_start | |
| date | period_end | |
| varchar | trend_type | |
| int | rank | |
| int | previous_rank | |
| bigint | mention_count | |
| bigint | previous_mention_count | |
| bigint | growth_amount | |
| numeric | growth_rate | |
| timestamptz | measured_at | |

PK 가 `id` 이고 `trend_id` 는 단순 FK 이므로 **한 트렌드에 여러 지표 행이 쌓인다.** 기간별 최신 1행이 아니라 이력 구조다.

### briefings · briefing_trends · notifications

Spark 범위 밖 (차후 확장). 컬럼은 원본 다이어그램 참조.

## 관계

| 관계명 | 연결 |
| --- | --- |
| 관심 분야 | members → member_domains |
| 관심 키워드 | members → member_interest_keywords, keywords → member_interest_keywords |
| 브리핑 | members → briefings |
| 트렌드 | keywords → trends |
| source / target | keywords → keyword_relations (양방향) |
| 관련 콘텐츠 | keywords → keyword_contents |
| 콘텐츠 | contents → keyword_contents |
| 알림 | members → notifications |
| 알림 대상 | trends → notifications |
| 기간별 지표 | trends → trend_metrics |
| 구성 | trends → briefing_trends |
| 브리핑 포함 | briefings → briefing_trends |

## Spark 가 쓰는 테이블

| 테이블 | Job |
| --- | --- |
| `contents` | ingest |
| `keywords` | extract |
| `keyword_contents` | extract |
| `keyword_relations` | aggregate |
| `trends` | aggregate |
| `trend_metrics` | aggregate |

나머지 여섯(`members`, `member_domains`, `member_interest_keywords`, `briefings`, `briefing_trends`, `notifications`)은 건드리지 않는다.

## 이미지에 없어서 확인이 필요한 것

다이어그램은 제약을 다 담지 못한다. 아래는 적재 코드가 성립하려면 반드시 정해져야 하는 것들이다. 자세한 근거는 [`../08-storage-schema.md` §5](../08-storage-schema.md).

| # | 항목 | 없으면 |
| --- | --- | --- |
| 1 | `keywords` 의 `(domain, normalized_name)` UNIQUE | **upsert 충돌 키가 없어 같은 키워드가 계속 새 행으로 쌓인다** |
| 2 | `trend_metrics` 의 `(trend_id, period, period_start)` UNIQUE | 재실행할 때마다 같은 측정이 중복 삽입된다 |
| 3 | `contents.url` 의 길이와 인덱스 | varchar UK 라 긴 URL 에서 삽입 실패 위험 |
| 4 | `growth_amount` 가 생성 컬럼인지 | 생성 컬럼이면 INSERT 에서 빼야 한다 |
| 5 | `period` · `trend_type` 의 허용 값 | varchar 라 값 규약이 코드 밖에 없다 |
| 6 | `keywords.domain` · `member_domains.domain` 의 허용 값 | 수집 이벤트는 `dev` 를 주는데 백엔드 enum 은 `DEVELOP`, 표시명은 `개발` 이다. 세 표기가 다르므로 `ingest` 가 매핑한다 ([`../01-architecture.md` §6](../01-architecture.md)) |
| 7 | `keywords` 삭제 시 FK 동작 | 트렌드·관심사·연관이 매달려 있다 |
