# TrendIn API 설계서

| | |
| --- | --- |
| 엔드포인트 | 36개 (컨트롤러 6개) |
| 외부 주소 | `https://<host>/api` |
| 인증 | Bearer JWT |
| 스키마 | [ERD](../erd/erd.md) |

⚠️ **경로 앞의 `/api` 는 nginx 가 떼고 넘긴다** ([trendin.conf:60](../../infra/nginx/trendin.conf#L60) 의
`proxy_pass http://127.0.0.1:8080/`). 그래서 컨트롤러의 `@RequestMapping` 에는 `/api` 가 없고,
이 문서의 경로도 그 기준이다. 프론트에서는 앞에 `/api` 를 붙인다.

---

## 공통 규약

### 응답 봉투

성공·실패 모두 같은 모양이다 ([`BaseResponse`](../../backend/src/main/java/com/forever102/global/response/BaseResponse.java)).

```jsonc
// 성공
{ "success": true,  "data": { /* 엔드포인트마다 다름 */ }, "message": null }

// 실패
{ "success": false, "data": null, "message": "존재하지 않는 트렌드입니다." }
```

**실패 응답에 오류 코드 이름은 실리지 않는다.** 내려가는 것은 HTTP 상태와 사람이 읽는
`message` 뿐이므로, 클라이언트가 분기해야 하면 상태 코드로 가른다.

`data` 가 없는 성공(삭제·읽음 처리 등)은 `data: null` 이다.

📌 **아래 모든 Response 예시는 `data` 안쪽만 보여 준다.** 실제로는 위 봉투에 한 번 더 싸여
내려간다. 값은 모양을 보이기 위한 것이라 실제 데이터와 다르다.

### 인증

로그인으로 받은 액세스 토큰을 헤더에 싣는다.

```
Authorization: Bearer <accessToken>
```

**아래 경로만 인증 없이 열려 있다** ([`SecurityConfig`](../../backend/src/main/java/com/forever102/global/config/SecurityConfig.java#L31)).
나머지는 전부 인증이 필요하다.

| 메서드 | 경로 |
| --- | --- |
| `GET` | `/domains` · `/trends` · `/trends/*/contents` |
| `POST` | `/auth/signup` · `/auth/login` · `/auth/reissue` · `/auth/email-check` · `/auth/oauth/*/login` |
| `OPTIONS` | 전부 (CORS 사전 요청) |

랜딩이 로그인 전에 보여 주는 것만 열었다. **키워드 검색과 트렌드 상세는 인증을 유지한다.**

### 페이지네이션

목록은 같은 모양을 쓴다.

```jsonc
{ "content": [ ... ], "page": 0, "size": 20, "hasNext": true }
```

`page` 는 0부터, `size` 는 1 이상이어야 한다(`@Min(0)` · `@Positive`). **전체 개수는 주지
않는다** — `hasNext` 로만 다음 쪽 유무를 알린다. 예외가 하나 있다:
`GET /trends/{trendId}/contents` 만 `totalElements` 를 함께 준다.

### 기간과 시간대

`period` 는 `24H` · `7D` · `30D` 셋 중 하나다. 그 밖의 값은 `400`.

구간은 **KST 자정으로 끊은 반열린 구간** `[start, end)` 이고, 응답의 `timezone` 필드가 기준
시간대를 함께 알려 준다. 시각은 `OffsetDateTime`(오프셋 포함), 날짜는 `LocalDate` 다.

---

## 1. 인증 `/auth`

### `POST /auth/signup` → `201`

| 필드 | 규칙 |
| --- | --- |
| `email` | 필수, 이메일 형식. **소문자로 정규화되고 앞뒤 공백이 잘린다** |
| `password` | 필수, 8~128자, **영문·숫자·특수문자 각각 1자 이상** |
| `nickname` | 필수, 2~30자, 앞뒤 공백이 잘린다 |

**Request**

```json
{
  "email": "trendin@example.com",
  "password": "Trendin1234!",
  "nickname": "트렌드러버"
}
```

**Response** `201`

```json
{
  "memberId": 1,
  "email": "trendin@example.com",
  "nickname": "트렌드러버",
  "onboardingCompleted": false
}
```

`409 EMAIL_ALREADY_EXISTS` 가 중복 가입을 막는다.

### `POST /auth/email-check` → `200`

**Request**

```json
{ "email": "trendin@example.com" }
```

**Response**

```json
{ "available": true }
```

### `POST /auth/login` → `200`

**Request**

```json
{
  "email": "trendin@example.com",
  "password": "Trendin1234!"
}
```

**Response**

```json
{
  "accessToken": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.kQ3...",
  "refreshToken": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIiwi...",
  "tokenType": "Bearer",
  "accessTokenExpiresIn": 1800,
  "refreshTokenExpiresIn": 1209600,
  "onboardingCompleted": false
}
```

`onboardingCompleted` 가 `false` 면 온보딩으로 보낸다.
실패는 `401 INVALID_CREDENTIALS` 하나로 묶인다 — 이메일이 없는 것과 비밀번호가 틀린 것을
가르지 않는다.

### `POST /auth/oauth/{provider}/login` → `200`

**Request** — `POST /auth/oauth/gitlab/login`

```json
{ "code": "a1b2c3d4e5f6..." }
```

**Response** — 로그인과 같고 **`isNewMember` 가 하나 더 붙는다.**

```json
{
  "accessToken": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiI5In0.Lm8...",
  "refreshToken": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiI5Iiwi...",
  "tokenType": "Bearer",
  "accessTokenExpiresIn": 1800,
  "refreshTokenExpiresIn": 1209600,
  "isNewMember": true,
  "onboardingCompleted": false
}
```

제공자는 경로 변수라 패턴으로 열려 있고, **지원하지 않는 이름은 서비스가
`400 UNSUPPORTED_PROVIDER` 로 거른다.** 제공자와 통신 자체가 실패하면 `502 OAUTH_PROVIDER_ERROR`.

### `POST /auth/reissue` → `200`

**Request**

```json
{ "refreshToken": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIiwi..." }
```

**Response** — 로그인과 같은 모양(`isNewMember` 없음). 실패는 `401 INVALID_REFRESH_TOKEN`.

```json
{
  "accessToken": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.9Fa...",
  "refreshToken": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIiwi...",
  "tokenType": "Bearer",
  "accessTokenExpiresIn": 1800,
  "refreshTokenExpiresIn": 1209600,
  "onboardingCompleted": true
}
```

### `POST /auth/logout` → `200` 🔒

**Request**

```json
{ "refreshToken": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIiwi..." }
```

**Response** — `data: null`. 인증이 필요한 유일한 `/auth` 엔드포인트다.

---

## 2. 분야 `/domains`

### `GET /domains` → `200` 🔓

**Response**

```json
[
  { "domain": "DEVELOP", "name": "개발" },
  { "domain": "FASHION", "name": "패션" }
]
```

코드와 표시 이름의 대응표다. 관심 키워드 응답 등이 코드만 주므로 이름은 여기서 찾아 붙인다.

---

## 3. 내 정보 `/members/me` 🔒

이 절의 모든 엔드포인트는 인증이 필요하고, 회원은 **토큰에서 온다** — 경로에 회원 id 가 없다.

### `GET /members/me` → `200`

**Response**

```json
{
  "memberId": 1,
  "email": "trendin@example.com",
  "nickname": "트렌드러버",
  "onboardingCompleted": true
}
```

### `PATCH /members/me` → `200`

**지금 고칠 수 있는 것은 닉네임뿐이다**(2~30자). 응답은 고쳐진 프로필 전체다.

**Request**

```json
{ "nickname": "트렌드마스터" }
```

**Response**

```json
{
  "memberId": 1,
  "email": "trendin@example.com",
  "nickname": "트렌드마스터",
  "onboardingCompleted": true
}
```

### `DELETE /members/me` → `204`

본인 계정을 탈퇴 처리하고 모든 기기의 세션을 끊는다 (`AUTH-006`).

**Request** — 본문 없음

**Response** — **`204 No Content`.** 본문이 없다.

⚠️ **이 엔드포인트만 공통 응답 봉투를 쓰지 않는다.** 204는 본문을 실을 수 없는 상태 코드라
`success`/`data`/`message` 가 내려가지 않는다. 클라이언트는 상태 코드만 본다.

함께 사라지는 것 — 관심 분야 · 관심 키워드 · 저장한 트렌드 · 알림 설정 · 개인 알림 ·
외부 로그인 연결. **남는 것** — 트렌드 · 콘텐츠 · 키워드처럼 여럿이 함께 보는 자료.

⚠️ **액세스 토큰은 즉시 폐기되지 않는다.** 서명과 만료만 보는 JWT라 이미 발급된 것은 남은
유효 기간(최대 30분) 동안 필터를 통과한다. 그 요청은 회원을 찾지 못해
`404 MEMBER_NOT_FOUND` 로 끝난다. 클라이언트는 탈퇴 응답을 받으면 토큰을 직접 버린다.

### `GET /members/me/domains` → `200`

**Response**

```json
[
  { "domain": "DEVELOP", "name": "개발" }
]
```

### `PUT /members/me/domains` → `200`

전체 교체다. **최소 1개**여야 하고, 비우면 `400 INTEREST_COUNT_INVALID`.

**Request**

```json
{ "domains": ["DEVELOP", "FASHION"] }
```

**Response**

```json
[
  { "domain": "DEVELOP", "name": "개발" },
  { "domain": "FASHION", "name": "패션" }
]
```

---

## 4. 관심 키워드 🔒

### `POST /members/me/interest-keywords` → `201`

**이름이 아니라 키워드 id 로 등록한다.** 서버가 모르는 말은 담을 수 없다. 중복은
`409 INTEREST_KEYWORD_ALREADY_EXISTS`.

**Request**

```json
{ "keywordId": 81 }
```

**Response** `201`

```json
{
  "interestKeywordId": 12,
  "keywordId": 81,
  "keyword": "리액트"
}
```

### `GET /members/me/interest-keywords` → `200`

`?domain=DEVELOP` (선택) — 주면 그 분야만, 없으면 전부 **등록한 순서(id 오름차순)** 로.

**Response** — `domain` 은 **코드만** 온다. 표시 이름은 `GET /domains` 에서 찾아 붙인다.

```json
[
  { "interestKeywordId": 12, "keywordId": 81, "keyword": "리액트", "domain": "DEVELOP" },
  { "interestKeywordId": 13, "keywordId": 94, "keyword": "발레코어", "domain": "FASHION" }
]
```

**페이지네이션이 없다.** 전부 내려주므로 화면에서 나눈다.

### `DELETE /members/me/interest-keywords/{interestKeywordId}` → `200`

⚠️ **키가 `keywordId` 가 아니라 `interestKeywordId`(등록 기록 id)다.** 없으면
`404 INTEREST_KEYWORD_NOT_FOUND`.

**Request** — `DELETE /members/me/interest-keywords/12` (본문 없음)

**Response** — `data: null`

### `GET /members/me/recommended-keywords` → `200`

내 관심 키워드와 함께 언급되는 말을 **연관도 높은 순으로 최대 40개** 준다. 개수는 서버가
정하며 파라미터로 바꿀 수 없다. 이미 담은 키워드는 빠진다. 관심 키워드가 하나도 없으면
기댈 곳이 없어 **빈 배열**이 온다.

**Response**

```json
[
  {
    "keywordId": 203,
    "keyword": "넥스트js",
    "domain": { "code": "DEVELOP", "name": "개발" },
    "relationScore": 91.50
  },
  {
    "keywordId": 118,
    "keyword": "타입스크립트",
    "domain": { "code": "DEVELOP", "name": "개발" },
    "relationScore": 87.25
  }
]
```

---

## 5. 저장한 트렌드 🔒

### `GET /members/me/saved-trends` → `200`

`?period=24H&page=0&size=20` (기본 `24H` · `0` · `20`)

**Response**

```json
{
  "content": [
    {
      "savedTrendId": 7,
      "trendId": 42,
      "keywordId": 81,
      "keyword": "리액트",
      "domain": { "code": "DEVELOP", "name": "개발" },
      "trendTypes": ["RISING"],
      "description": "리액트는 컴포넌트 기반 UI 라이브러리로 최근 서버 컴포넌트 도입이 논의된다.",
      "mentionCount": 120,
      "growthRate": 200.00,
      "savedAt": "2026-09-20T14:12:03+09:00"
    }
  ],
  "page": 0,
  "size": 20,
  "hasNext": false
}
```

### `POST /members/me/saved-trends` → `201`

중복은 `409 SAVED_TREND_ALREADY_EXISTS`.

**Request**

```json
{ "trendId": 42 }
```

**Response** `201`

```json
{
  "savedTrendId": 7,
  "trendId": 42,
  "savedAt": "2026-09-20T14:12:03+09:00"
}
```

### `DELETE /members/me/saved-trends/{savedTrendId}` → `200`

키가 `trendId` 가 아니라 **`savedTrendId`** 다. 없으면 `404 SAVED_TREND_NOT_FOUND`.

**Request** — `DELETE /members/me/saved-trends/7` (본문 없음)

**Response** — `data: null`

---

## 6. 알림 🔒

### `GET /members/me/notifications` → `200`

`?page=0&size=20`

**Response**

```json
{
  "content": [
    {
      "notificationId": 1,
      "trendId": 42,
      "notificationType": "KEYWORD_SURGE",
      "message": "관심 키워드 '리액트'의 언급량이 크게 늘었습니다.",
      "isRead": false,
      "createdAt": "2026-09-22T10:00:00+09:00"
    }
  ],
  "page": 0,
  "size": 20,
  "hasNext": true
}
```

유형은 다섯 가지 — `TREND_CHANGE` · `KEYWORD_SURGE` · `KEYWORD_DROP` · `NEW_TREND` ·
`TREND_TURNING_POINT`.

⚠️ **필드 이름이 `isRead` 다.** Jackson 기본 규칙대로면 `read` 로 나갔을 것을
`@JsonProperty("isRead")` 로 고정했다. 프론트는 `isRead` 를 읽는다.

### `GET /members/me/notifications/unread-count` → `200`

**헤더에 늘 붙어 모든 화면에서 호출된다.**

**Response**

```json
{ "unreadCount": 3 }
```

### `PATCH /members/me/notifications/{notificationId}` → `200`

한 건을 읽음으로. 없으면 `404 NOTIFICATION_NOT_FOUND`.

**Request** — `PATCH /members/me/notifications/1` (본문 없음)

**Response** — `data: null`

### `PATCH /members/me/notifications/read-all` → `200`

안 읽은 것을 전부 읽음으로.

**Request** — 본문 없음

**Response** — `data: null`

### `GET /members/me/notification-settings` → `200`

**Response**

```json
{
  "keywordSurgeEnabled": true,
  "keywordDropEnabled": true,
  "newTrendEnabled": true,
  "trendTurningPointEnabled": true
}
```

### `PUT /members/me/notification-settings` → `200`

**네 값을 모두 보내야 한다**(각 `@NotNull`). 일부만 바꾸는 경로는 없다.

**Request**

```json
{
  "keywordSurgeEnabled": true,
  "keywordDropEnabled": false,
  "newTrendEnabled": true,
  "trendTurningPointEnabled": false
}
```

**Response** — 고쳐진 설정 전체. Request 와 같은 모양이다.

```json
{
  "keywordSurgeEnabled": true,
  "keywordDropEnabled": false,
  "newTrendEnabled": true,
  "trendTurningPointEnabled": false
}
```

---

## 7. 트렌드 `/trends`

### `GET /trends` → `200` 🔓

`?domain=DEVELOP&type=RISING&period=7D&page=0&size=20`
`domain` · `type` · `period` 는 **필수**, 나머지는 기본값이 있다.
`type` 은 `CURRENT` · `NEW` · `RISING`.

**Response**

```json
{
  "content": [
    {
      "trendId": 42,
      "keywordId": 81,
      "keyword": "리액트",
      "description": "리액트는 컴포넌트 기반 UI 라이브러리로 최근 서버 컴포넌트 도입이 논의된다.",
      "domain": { "code": "DEVELOP", "name": "개발" },
      "trendTypes": ["RISING"],
      "rank": 3,
      "mentionCount": 120,
      "previousMentionCount": 40,
      "growthAmount": 80,
      "growthRate": 200.00
    }
  ],
  "page": 0,
  "size": 20,
  "hasNext": true,
  "analysisWindow": {
    "recentStart": "2026-09-16T00:00:00+09:00",
    "recentEnd": "2026-09-23T00:00:00+09:00",
    "previousStart": "2026-09-09T00:00:00+09:00",
    "previousEnd": "2026-09-16T00:00:00+09:00"
  }
}
```

**줄 세우는 기준이 갈래마다 다르다.**

| `type` | 정렬 |
| --- | --- |
| `CURRENT` · `NEW` | `mention_count` 내림차순 |
| `RISING` | `growth_rate` 내림차순 (NULL 은 뒤) |

⚠️ **`rank` 를 화면의 순위로 쓰면 안 된다.** 이 값은 `keyword_metrics.mention_rank`, 즉
**분야 전체의 언급량 순위**다. 급상승 목록은 증가율로 줄을 세우므로 `rank` 는 251·35·52
처럼 뒤섞여 온다. 판에 보이는 번호는 **받은 차례**를 쓴다.

### `GET /trends/{trendId}` → `200` 🔒

`?period=7D` 필수.

**Response**

```json
{
  "trendId": 42,
  "keywordId": 81,
  "keyword": "리액트",
  "description": "리액트는 컴포넌트 기반 UI 라이브러리로 최근 서버 컴포넌트 도입이 논의된다.",
  "domain": { "code": "DEVELOP", "name": "개발" },
  "trendTypes": ["RISING"],
  "mentionCount": 120,
  "previousMentionCount": 40,
  "growthAmount": 80,
  "growthRate": 200.00,
  "analysisWindow": {
    "recentStart": "2026-09-16T00:00:00+09:00",
    "recentEnd": "2026-09-23T00:00:00+09:00",
    "previousStart": "2026-09-09T00:00:00+09:00",
    "previousEnd": "2026-09-16T00:00:00+09:00"
  },
  "summary": "서버 컴포넌트와 관련한 논의가 여러 매체에 공통으로 나타난다.",
  "reason": "새 릴리스 발표 직후 관련 글이 몰렸고, 컨퍼런스 발표가 겹치며 관심이 올랐다."
}
```

⚠️ `description`(한 줄 요약) · `summary` · `reason`(뜨는 이유)은 **AI 분석 결과**이고, 분석이
아직 없으면 셋 다 `null` 이다. 지표만 있고 분석이 없는 상태가 정상이다.

```json
{
  "trendId": 55,
  "keywordId": 90,
  "keyword": "바이브코딩",
  "description": null,
  "domain": { "code": "DEVELOP", "name": "개발" },
  "trendTypes": ["NEW"],
  "mentionCount": 18,
  "previousMentionCount": 0,
  "growthAmount": 18,
  "growthRate": null,
  "analysisWindow": { "...": "위와 같음" },
  "summary": null,
  "reason": null
}
```

### `GET /trends/{trendId}/history` → `200` 🔒

`?period=7D` 필수. 그래프의 재료다.

**Response**

```json
{
  "trendId": 42,
  "period": "7D",
  "timezone": "Asia/Seoul",
  "startAt": "2026-09-16T00:00:00+09:00",
  "endAt": "2026-09-23T00:00:00+09:00",
  "history": [
    {
      "bucketStart": "2026-09-16T00:00:00+09:00",
      "bucketEnd": "2026-09-17T00:00:00+09:00",
      "mentionCount": 12
    },
    {
      "bucketStart": "2026-09-17T00:00:00+09:00",
      "bucketEnd": "2026-09-18T00:00:00+09:00",
      "mentionCount": 21
    }
  ]
}
```

### `GET /trends/{trendId}/contents` → `200` 🔓

`?page=0&size=10` (기본 `0` · `10`). **기간을 타지 않는다.**

**Response** — `totalElements` 가 있는 유일한 목록이다.

```json
{
  "content": [
    {
      "contentId": 9001,
      "title": "리액트 서버 컴포넌트, 무엇이 달라지나",
      "source": "요즘IT",
      "url": "https://yozm.wishket.com/magazine/detail/9001/",
      "publishedAt": "2026-09-22T09:30:00+09:00"
    }
  ],
  "page": 0,
  "size": 10,
  "hasNext": true,
  "totalElements": 134
}
```

### `GET /trends/{trendId}/related-keywords` → `200` 🔒

연관도(0~100) 내림차순. **기간을 타지 않고 페이지네이션도 없다.**

**Response**

```json
{
  "trendId": 42,
  "relatedKeywords": [
    { "keywordId": 203, "keyword": "넥스트js", "relationScore": 91.50 },
    { "keywordId": 118, "keyword": "타입스크립트", "relationScore": 87.25 }
  ]
}
```

---

## 8. 트렌드의 지역 `/trends/{trendId}/regions`

### `GET /trends/{trendId}/regions` → `200` 🔒

`?period=7D` 필수.

**Response**

```json
{
  "trendId": 42,
  "period": "7D",
  "timezone": "Asia/Seoul",
  "startDate": "2026-09-16",
  "endDate": "2026-09-23",
  "regions": [
    { "rank": 1, "countryCode": "KR", "countryName": "대한민국", "mentionCount": 82 },
    { "rank": 2, "countryCode": "US", "countryName": "미국", "mentionCount": 26 }
  ]
}
```

### `GET /trends/{trendId}/regions/{countryCode}/history` → `200` 🔒

`?period=7D` 필수. `countryCode` 는 ISO 3166-1 alpha-2(대문자 2자).

**Response**

```json
{
  "trendId": 42,
  "countryCode": "KR",
  "countryName": "대한민국",
  "period": "7D",
  "timezone": "Asia/Seoul",
  "startAt": "2026-09-16T00:00:00+09:00",
  "endAt": "2026-09-23T00:00:00+09:00",
  "history": [
    {
      "bucketStart": "2026-09-16T00:00:00+09:00",
      "bucketEnd": "2026-09-17T00:00:00+09:00",
      "mentionCount": 9
    }
  ]
}
```

### `GET /trends/{trendId}/regions/journey` → `200` 🔒

**`period` 를 받지 않는다.** 나라별 첫 등장 순서를 준다.

**Response**

```json
{
  "trendId": 42,
  "period": "30D",
  "timezone": "Asia/Seoul",
  "startDate": "2026-08-24",
  "endDate": "2026-09-23",
  "regions": [
    { "countryCode": "US", "countryName": "미국", "firstDetectedDate": "2026-08-27", "order": 1 },
    { "countryCode": "KR", "countryName": "대한민국", "firstDetectedDate": "2026-09-02", "order": 2 }
  ]
}
```

---

## 9. 나라 축 `/regions` 🔒

7·8절이 **트렌드 하나를 나라로 쪼갠다면**, 이쪽은 **나라를 먼저 고르고 그 안의 트렌드를 본다.**

### `GET /regions` → `200`

`?domain=DEVELOP&period=7D` (둘 다 필수)

`totalMentionCount` 는 **잘라 내기 전 전체 언급량**이다. 목록을 상위 N개로 잘라도 나라별
몫(%)을 제대로 낼 수 있게 분모를 따로 준다.

**Response**

```json
{
  "domain": "DEVELOP",
  "period": "7D",
  "timezone": "Asia/Seoul",
  "startDate": "2026-09-16",
  "endDate": "2026-09-23",
  "totalMentionCount": 5820,
  "countries": [
    { "rank": 1, "countryCode": "KR", "countryName": "대한민국", "mentionCount": 2410 },
    { "rank": 2, "countryCode": "US", "countryName": "미국", "mentionCount": 1180 }
  ]
}
```

### `GET /regions/{countryCode}/trends` → `200`

`?domain=DEVELOP&period=7D&size=5` (`size` 기본 5)

**Response**

```json
{
  "domain": "DEVELOP",
  "countryCode": "KR",
  "countryName": "대한민국",
  "period": "7D",
  "timezone": "Asia/Seoul",
  "startDate": "2026-09-16",
  "endDate": "2026-09-23",
  "totalMentionCount": 2410,
  "trends": [
    { "rank": 1, "trendId": 42, "keywordId": 81, "keyword": "리액트", "mentionCount": 120 },
    { "rank": 2, "trendId": 51, "keywordId": 118, "keyword": "타입스크립트", "mentionCount": 96 }
  ]
}
```

---

## 10. 키워드 검색 `/keywords`

### `GET /keywords/search` → `200` 🔒

`?query=리액트&domain=DEVELOP&page=0&size=20`
`query` 는 **필수이고 공백만으로는 안 된다**(`@NotBlank`). `domain` 은 선택.

**Response**

```json
{
  "content": [
    {
      "keywordId": 81,
      "keyword": "리액트",
      "domain": { "code": "DEVELOP", "name": "개발" },
      "trendId": 42,
      "trendTypes": ["RISING"],
      "growthRate": 200.00
    },
    {
      "keywordId": 305,
      "keyword": "리액트 네이티브",
      "domain": { "code": "DEVELOP", "name": "개발" },
      "trendId": null,
      "trendTypes": [],
      "growthRate": null
    }
  ],
  "page": 0,
  "size": 20,
  "hasNext": false
}
```

⚠️ **`trendId` 가 `null` 일 수 있다.** 상세 진입 키는 `trends` 행이 있어야 하는데, 판정을
받은 적 없는 키워드에는 그 행이 없다. 반면 `trendTypes` 와 `growthRate` 는 지표 행에서 오므로
값이 실릴 수 있다. **`trendId` 가 null 이면 상세로 보내지 않는다.**

---

## 오류

| 상태 | 코드 | 메시지 |
| --- | --- | --- |
| `400` | `VALIDATION_ERROR` | 입력값이 올바르지 않습니다. |
| `400` | `INTEREST_COUNT_INVALID` | 관심 분야는 최소 1개 이상 선택해야 합니다. |
| `400` | `UNSUPPORTED_PROVIDER` | 지원하지 않는 OAuth 제공자입니다. |
| `401` | `INVALID_CREDENTIALS` | 이메일 또는 비밀번호가 일치하지 않습니다. |
| `401` | `UNAUTHORIZED` | 인증이 필요합니다. |
| `401` | `INVALID_TOKEN` | 유효하지 않은 토큰입니다. |
| `401` | `EXPIRED_TOKEN` | 만료된 토큰입니다. |
| `401` | `INVALID_REFRESH_TOKEN` | 유효하지 않거나 만료된 리프레시 토큰입니다. |
| `401` | `OAUTH_AUTHENTICATION_FAILED` | OAuth 인증에 실패했습니다. |
| `403` | `ACCESS_DENIED` | 접근 권한이 없습니다. |
| `404` | `TREND_NOT_FOUND` | 존재하지 않는 트렌드입니다. |
| `404` | `MEMBER_NOT_FOUND` | 존재하지 않는 회원입니다. |
| `404` | `DOMAIN_NOT_FOUND` | 존재하지 않는 분야입니다. |
| `404` | `KEYWORD_NOT_FOUND` | 존재하지 않는 키워드입니다. |
| `404` | `INTEREST_KEYWORD_NOT_FOUND` | 존재하지 않는 관심 키워드입니다. |
| `404` | `SAVED_TREND_NOT_FOUND` | 존재하지 않는 저장 트렌드입니다. |
| `404` | `NOTIFICATION_NOT_FOUND` | 존재하지 않는 알림입니다. |
| `409` | `EMAIL_ALREADY_EXISTS` | 이미 가입된 이메일입니다. |
| `409` | `INTEREST_KEYWORD_ALREADY_EXISTS` | 이미 등록된 관심 키워드입니다. |
| `409` | `SAVED_TREND_ALREADY_EXISTS` | 이미 저장한 트렌드입니다. |
| `500` | `INTERNAL_SERVER_ERROR` | 서버에 오류가 발생했습니다. |
| `502` | `OAUTH_PROVIDER_ERROR` | OAuth 제공자와 통신하지 못했습니다. |

정본은 [`ErrorCode`](../../backend/src/main/java/com/forever102/global/exception/ErrorCode.java).
**코드 이름은 응답에 실리지 않는다** — 위 표는 어떤 상황에 어떤 상태가 오는지 읽기 위한 것이다.
