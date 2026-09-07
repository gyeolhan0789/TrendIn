# ERD 01 — 열거 타입 · 회원 · 인증 · 분류 체계 · 관심사

> 문서 구성
>
> - **01 (이 문서)**: 열거 타입, 회원·인증, 분류 체계(DOMAINS·CATEGORIES), 관심 분야·관심 키워드
> - **02**: 키워드 사전, 분석 기반(ANALYSIS_RUNS·DETECTION_RULES), 트렌드, 연관 관계
> - **03**: 일별·국가별 지표, 콘텐츠, 브리핑, 알림, 남은 미결정 목록

---

## 1. 열거 타입(ENUM)

| 타입 | 값 | 근거 |
| --- | --- | --- |
| `auth_provider` | `LOCAL` (제공자 확정 후 추가) | 01·06 `authProvider` |
| `metric_period` | `24H` / `7D` / `30D` | 15 `period` |
| `trend_type` | `CURRENT` / `NEW` / `RISING` | 15 `type` |
| `run_status` | `RUNNING` / `COMPLETED` / `FAILED` | 분석 배치 상태 |
| `data_coverage` | `COMPLETE` / `PARTIAL` / `NO_DATA` | 17 `evidence.dataCoverage` |
| `ai_status` | `PENDING` / `COMPLETED` / `FAILED` / `NO_DATA` | 17 `aiAnalysis.status`, 19 `summaryStatus` |
| `relation_status` | `NEW` / `RISING` / `STABLE` | 16·20 `relationStatus` |
| `collection_status` | `COMPLETED` / `PARTIAL` / `MISSING` | 18·23 수집 누락 구분 |
| `notification_type` | `NEW_TREND` / `RISING_TREND` | 26 `type` |

- `auth_provider`는 03번에서 제공자가 미확정이므로 `LOCAL`만 정의하고, 확정 시 `ALTER TYPE ... ADD VALUE`로 확장한다.
- `relation_status`의 `STABLE`은 ERD에서 정의한 값이며 API 문서에는 예시로 `NEW`·`RISING`만 등장한다. API 쪽에 값 목록을 명시해야 한다.
- `collection_status`(`COMPLETED`/`PARTIAL`/`MISSING`)와 18·22·23 응답의 `dataStatus`(`AVAILABLE`/`PARTIAL`/`NO_DATA`)는 서로 다른 값 집합이다. 매핑 규칙은 03 문서 §1에서 정의한다.

---

## 2. MEMBERS — 서비스 회원

| 컬럼 | 타입 | 제약 | 설명 |
| --- | --- | --- | --- |
| id | bigint | PK | 응답의 `memberId` |
| email | varchar(254) | NOT NULL | 01에서 최대 254자 |
| password_hash | varchar(255) |  | BCrypt 해시. **OAuth 전용 계정은 NULL** |
| nickname | varchar(30) | NOT NULL | 앞뒤 공백 제거 후 2~30자 |
| auth_provider | auth_provider | NOT NULL, DEFAULT 'LOCAL' | 최초 가입 경로 |
| onboarding_completed | boolean | NOT NULL, DEFAULT false | 관심 분야 최초 등록 시 true |
| password_updated_at | timestamptz |  | 31 비밀번호 변경 시각 |
| created_at | timestamptz | NOT NULL | 가입 시점 |
| updated_at | timestamptz | NOT NULL | 최근 수정 시점 |
| deleted_at | timestamptz |  | 08 탈퇴 처리 시각 |

```sql
UNIQUE INDEX ON members (lower(email)) WHERE deleted_at IS NULL;
CHECK (auth_provider <> 'LOCAL' OR password_hash IS NOT NULL);
```

- 부분 유니크 인덱스는 01 `EMAIL_ALREADY_EXISTS`와 30 `available` 판정의 단일 근거다.
- `CHECK`는 "LOCAL 계정이면 비밀번호가 있다"를 보장할 뿐, 31번의 `409 Conflict`(비밀번호 미설정 계정)를 DB가 걸러주지는 않는다. **409 판정은 애플리케이션의 `password_hash IS NULL` 검사**로 처리한다.
- 07은 `nickname`만 수정한다. 이메일 변경 API는 명세에 없다.
- 01·03 성공 시 `member_notification_settings` 기본 행을 **같은 트랜잭션**에서 생성한다 (28이 항상 값을 반환해야 함).
- `onboarding_completed`는 파생값이 아니라 **저장 컬럼**이다. 11의 "최초 성공 시 true"가 상태 전이이고, 02·03·05 응답이 매번 이 값을 내려주므로 조회 비용을 줄인다.
- **탈퇴는 soft delete(`deleted_at`)인데 하위 테이블은 `ON DELETE CASCADE`다.** 물리 삭제를 하지 않으면 CASCADE가 동작하지 않으므로, 08번이 정리할 테이블과 방식(삭제/비식별)을 애플리케이션 트랜잭션으로 명시해야 한다. 03 문서의 미결정 3번.

---

## 3. MEMBER_OAUTH_ACCOUNTS — OAuth 연동

| 컬럼 | 타입 | 제약 | 설명 |
| --- | --- | --- | --- |
| id | bigint | PK | 식별자 |
| member_id | bigint | FK(MEMBERS) ON DELETE CASCADE, NOT NULL | 연결 회원 |
| provider | auth_provider | NOT NULL | OAuth 제공자 |
| provider_user_id | varchar(255) | NOT NULL | 제공자 측 사용자 식별자 |
| connected_at | timestamptz | NOT NULL | 연동 시점 |

```sql
UNIQUE (provider, provider_user_id);
UNIQUE (member_id, provider);
```

- `UNIQUE(provider, provider_user_id)`는 03 재로그인 시 기존 회원 식별에 쓴다.
- 03의 `isNewMember`는 이 테이블에 행을 새로 만들었는지로 판정한다.
- `code`·`state`는 일회용 값이므로 저장하지 않는다.
- **현재 `auth_provider`에 값이 `LOCAL` 하나뿐이라 이 테이블이 실질적으로 동작하지 않는다.** 제공자 확정 전까지는 `UNIQUE(member_id, provider)`가 무의미하고 03번 `UNSUPPORTED_PROVIDER`의 판정 근거도 없다. 제공자 목록 확정이 선행 조건이다.
- `UNIQUE(provider, provider_user_id)`에 `deleted_at` 조건이 없어 탈퇴 회원이 같은 소셜 계정으로 재가입할 수 없다. `email` 쪽 부분 인덱스와 대칭을 맞출지 결정이 필요하다.

---

## 4. REFRESH_TOKENS — Refresh Token

| 컬럼 | 타입 | 제약 | 설명 |
| --- | --- | --- | --- |
| id | bigint | PK | 식별자 |
| member_id | bigint | FK(MEMBERS) ON DELETE CASCADE, NOT NULL | 소유 회원 |
| token_hash | varchar(255) | UK, NOT NULL | 토큰 원문이 아닌 해시 |
| expires_at | timestamptz | NOT NULL | 만료 시각 (발급 시 +1,209,600초) |
| revoked_at | timestamptz |  | 폐기 시각 |
| created_at | timestamptz | NOT NULL | 발급 시점 |

```sql
INDEX (member_id) WHERE revoked_at IS NULL;
```

- 04 로그아웃은 요청 본문의 `refreshToken`에 해당하는 **한 행만** 폐기한다 (세션 단위).
- 05 재발급은 기존 행 폐기 + 신규 발급(**rotation**). 응답이 `refreshToken`도 새로 내려주므로 회전이 전제다.
- 08 탈퇴는 해당 회원의 **모든 유효 토큰**을 폐기한다.
- Access Token은 무상태 검증이므로 저장하지 않는다.

---

## 5. MEMBER_NOTIFICATION_SETTINGS — 알림 수신 설정

| 컬럼 | 타입 | 제약 | 설명 |
| --- | --- | --- | --- |
| member_id | bigint | PK, FK(MEMBERS) ON DELETE CASCADE | 대상 회원 (1:1) |
| new_trend_enabled | boolean | NOT NULL, DEFAULT true | 신규 트렌드 알림 |
| rising_trend_enabled | boolean | NOT NULL, DEFAULT true | 급상승 트렌드 알림 |
| created_at | timestamptz | NOT NULL | 생성 시점 |
| updated_at | timestamptz | NOT NULL | 최근 수정 시점 |

- 29가 `PUT`이고 두 필드 모두 필수이므로 항상 함께 덮어쓴다.
- 29의 "과거 이벤트를 소급 발송하지 않는다"는 알림 생성 배치가 이 값을 **생성 시점에** 읽는다는 뜻이다. 설정 변경 이력은 보관하지 않는다.
- 28번 API가 "응답의 true/false는 기본값을 뜻하지 않는다"고 적었는데 여기서는 `DEFAULT true`로 확정했다. **기본값 정책을 팀에서 확정한 뒤 양쪽 문서를 맞춰야 한다.**

---

## 6. DOMAINS — 서비스 분야 (대분류) ~~→ enum?(유정균)~~

| 컬럼 | 타입 | 제약 | 설명 |
| --- | --- | --- | --- |
| id | bigint | PK | 응답의 `domainId` |
| name | varchar(30) | UK, NOT NULL | 개발, 패션, 게임 |
| sort_order | int | NOT NULL, DEFAULT 0 | 09 노출 순서 |
| is_active | boolean | NOT NULL, DEFAULT true | 09는 **활성 분야만** 반환 |
| created_at | timestamptz | NOT NULL | 생성 시점 |
| updated_at | timestamptz | NOT NULL | 최근 수정 시점 |

- 11의 `DOMAIN_NOT_FOUND`는 "존재하지 않거나 **비활성**"이므로 `is_active`가 필수다.
- 21 검색은 `domainId` 필터에 활성 여부를 적용하지 않는다 (전체 서비스 분야 대상).

---

## 7. CATEGORIES — 중분류 **[신설]**

| 컬럼 | 타입 | 제약 | 설명 |
| --- | --- | --- | --- |
| id | bigint | PK | 17 `category.categoryId` |
| domain_id | bigint | FK(DOMAINS), NOT NULL | 상위 대분류 |
| name | varchar(50) | NOT NULL | 17 `category.name` — 신발, 아우터 |
| sort_order | int | NOT NULL, DEFAULT 0 | 노출 순서 |
| is_active | boolean | NOT NULL, DEFAULT true | 노출 대상 여부 |
| created_at | timestamptz | NOT NULL | 생성 시점 |
| updated_at | timestamptz | NOT NULL | 최근 수정 시점 |

```sql
UNIQUE (domain_id, name);   -- 분야 내 중분류명 중복 방지
UNIQUE (id, domain_id);     -- KEYWORDS의 복합 FK 타깃
INDEX (domain_id, sort_order);
```

### 설계 근거

17번이 대분류·중분류·소분류 3단을 명시하므로 `DOMAINS`와 `KEYWORDS` 사이에 계층이 하나 더 필요하다. `KEYWORDS.category_id`만 두고 분야를 중분류에서 유도하는 방법도 있으나, 15·21이 `domainId`로 직접 필터하고 `TREND_PERIOD_METRICS`가 `domain_id`를 비정규화해 인덱스를 타므로 **`KEYWORDS`는 `domain_id`와 `category_id`를 모두 보유**한다.

이때 "키워드의 분야"와 "키워드가 속한 중분류의 분야"가 어긋날 수 있으므로, `UNIQUE(id, domain_id)`를 FK 타깃으로 삼아 복합 FK로 막는다. `MEMBER_INTEREST_KEYWORDS`가 `member_domains`를 복합 FK로 참조하는 것과 같은 방식이다.

```sql
-- KEYWORDS 측 (02 문서)
FOREIGN KEY (category_id, domain_id)
  REFERENCES categories (id, domain_id) ON DELETE SET NULL;
```

### 남은 결정

- **중분류 조회 API가 없다.** 9번은 대분류만 반환하고 중분류 목록 API는 정의되지 않았다. 17번 응답에서만 등장하므로, 필터 용도로 쓸 계획이면 `GET /domains/{domainId}/categories` 추가가 필요하다.
- 관심사 등록(11·12)은 대분류·키워드 단위라 중분류가 개입하지 않는다. 현재 범위에서 중분류는 **표시 전용**이다.
- 중분류 미분류 키워드를 허용하므로 `KEYWORDS.category_id`는 NULL 가능이고, 17 응답의 `category`도 `null`일 수 있다. API 문서에 이 케이스를 명시해야 한다.

---

## 8. MEMBER_DOMAINS — 사용자 관심 분야

| 컬럼 | 타입 | 제약 | 설명 |
| --- | --- | --- | --- |
| member_id | bigint | PK, FK(MEMBERS) ON DELETE CASCADE | 회원 |
| domain_id | bigint | PK, FK(DOMAINS) | 관심 분야 |
| created_at | timestamptz | NOT NULL | 등록 시점 |

```sql
PRIMARY KEY (member_id, domain_id);
INDEX (member_id);
```

- PK가 11의 `domainIds` 중복을 막고, 동시에 `member_interest_keywords`의 **복합 FK 타깃**이 된다.
- 11은 **전체 교체**다. 기존 행 삭제 후 재삽입을 한 트랜잭션으로 처리하며, 최초 성공 시 `members.onboarding_completed = true`로 전이한다.
- "최소 1개 유지"(`INTEREST_COUNT_INVALID`)는 행 개수 제약이라 DB로 표현할 수 없으므로 애플리케이션에서 검증한다.
- 제거된 분야의 관심 키워드 연쇄 삭제는 §9의 복합 FK로 **DB가 보장**한다.

---

## 9. MEMBER_INTEREST_KEYWORDS — 사용자 관심 키워드

| 컬럼 | 타입 | 제약 | 설명 |
| --- | --- | --- | --- |
| id | bigint | PK | 응답의 `interestKeywordId` |
| member_id | bigint | NOT NULL | 회원 |
| domain_id | bigint | NOT NULL | 소속 분야 |
| keyword_id | bigint | FK(KEYWORDS) ON DELETE SET NULL | 정규 키워드. 미매칭이면 NULL |
| raw_keyword | varchar(100) | NOT NULL | 사용자 입력 원문 (공백 제거 후 1~100자) |
| normalized_keyword | varchar(100) | NOT NULL | 중복 판정용 정규화 문자열 |
| created_at | timestamptz | NOT NULL | 등록 시점 |
| updated_at | timestamptz | NOT NULL | 키워드 통합 반영 시점 |

```sql
FOREIGN KEY (member_id, domain_id)
  REFERENCES member_domains (member_id, domain_id) ON DELETE CASCADE;

UNIQUE INDEX ON (member_id, domain_id, keyword_id)          WHERE keyword_id IS NOT NULL;
UNIQUE INDEX ON (member_id, domain_id, normalized_keyword)  WHERE keyword_id IS NULL;

INDEX (member_id, domain_id);   -- 13 domainId 필터
```

- 복합 FK 하나로 **두 가지를 동시에 보장**한다. 11의 "제거한 분야의 관심 키워드도 같은 트랜잭션에서 삭제"가 `ON DELETE CASCADE`로 처리되고, 12의 `DOMAIN_NOT_SELECTED`가 FK 위반으로 걸린다.
- 12는 `keyword` 또는 `keywordId` 중 **정확히 하나**를 받는다. `keywordId`로 들어오면 `keywords.name`을, 문자열로 들어오면 정규화 결과를 `keyword_id`에 매칭 시도한다.
- 중복 판정이 이원화되므로 **부분 유니크 인덱스 2개**가 필요하다. 하나로 합치면 `keyword_id`가 NULL인 행끼리 중복이 걸리지 않는다.
- 응답의 `keyword`는 `keyword_id`가 있으면 정규 키워드명, 없으면 `raw_keyword`다. `keywordId`는 미매칭 시 `null`로 내려간다 — **13번 API 문서에 이 null 케이스가 빠져 있어 보완이 필요하다.**
- "이후 키워드 통합 시 중복 관심사를 합친다"는 배치가 `keyword_id`를 채우고, 같은 `(member_id, domain_id, keyword_id)`가 생기면 오래된 행 하나만 남기는 작업이다.

### 구현 시 주의 두 가지

1. **12번의 404와 409를 DB 예외로 구분할 수 없다.** `KEYWORD_OR_DOMAIN_NOT_FOUND`(404, 존재하지 않는 분야)와 `DOMAIN_NOT_SELECTED`(409, 내 관심 분야가 아님) 모두 같은 복합 FK 위반으로 나타난다. 분야 존재 여부를 애플리케이션에서 먼저 조회해 404를 판정하고, FK 위반은 409로 매핑한다.
2. **`keyword_id ON DELETE SET NULL`이 유니크 충돌을 일으킬 수 있다.** SET NULL이 발동한 행은 `WHERE keyword_id IS NULL` 인덱스의 대상이 되는데, 같은 사용자·분야에 동일한 `normalized_keyword` 행이 이미 있으면 키워드 삭제 트랜잭션 자체가 실패한다. 키워드 삭제 배치가 관심 키워드 중복을 먼저 정리하도록 순서를 잡는다.
