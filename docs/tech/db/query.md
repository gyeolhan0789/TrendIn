# DB 쿼리 원문

백엔드가 실제로 DB 에 보내는 SQL 을 정리했다. 파생 질의(메서드 이름으로 만들어지는 것)는 Hibernate 가 생성하는 SQL 로 옮겨 적었고, 별칭은 읽기 쉽게 바꿨다.

페이징은 전부 `limit ? offset ?` 이 붙고, `Page` 반환 타입은 같은 `where` 로 `count(*)` 를 한 번 더 보낸다.

---

## 회원 · 인증

```sql
-- 이메일 중복 확인
select exists (select 1 from members where email = ?);

-- 로그인
select * from members where email = ?;

-- 소셜 로그인 계정으로 회원 찾기 (+ members 조인)
select oauth.*, member.*
from member_oauth_accounts oauth
join members member on member.id = oauth.member_id
where oauth.provider = ? and oauth.provider_user_id = ?;
```

### 리프레시 토큰 — Redis (SQL 아님)

```
SET  refresh:member:{id} {sha256} PX {ttl}     -- 로그인
DEL  refresh:member:{id}                        -- 탈퇴

-- 재발급: 저장된 해시가 일치할 때만 교체 (Lua, 원자적)
if redis.call('GET', KEYS[1]) == ARGV[1] then
    redis.call('SET', KEYS[1], ARGV[2], 'PX', ARGV[3]); return 1
end
return 0

-- 로그아웃: 저장된 해시가 일치할 때만 삭제 (Lua, 원자적)
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
```

---

## 관심 분야

```sql
-- 내 관심 분야 코드 목록
select domain from member_domains where member_id = ?;

-- 새로 고른 분야에 없는 것만 삭제
delete from member_domains
where member_id = ? and domain not in (?, ?, ...);
```

---

## 관심 키워드

```sql
-- 이미 담은 키워드인지
select exists (
    select 1 from member_interest_keywords where member_id = ? and keyword_id = ?
);

-- 내 관심 키워드 전체 (keywords 조인)
select mik.*, keyword.*
from member_interest_keywords mik
join keywords keyword on keyword.id = mik.keyword_id
where mik.member_id = ?
order by mik.id asc;

-- 분야로 좁힌 관심 키워드
select mik.*, keyword.*
from member_interest_keywords mik
join keywords keyword on keyword.id = mik.keyword_id
where mik.member_id = ? and keyword.domain = ?
order by mik.id asc;

-- 소유자 확인과 함께 단건 조회
select * from member_interest_keywords where id = ? and member_id = ?;

-- 관심 분야에서 빠진 분야의 키워드 정리
delete from member_interest_keywords
where member_id = ?
  and keyword_id in (select id from keywords where domain not in (?, ?, ...));

-- 탈퇴 시 전체 삭제
delete from member_interest_keywords where member_id = ?;
```

### 추천 키워드

내 관심 키워드와 **함께 등장하되 아직 담지 않은** 키워드를 연관도순으로.

```sql
select target.id        as keyword_id,
       target.name      as keyword,
       target.domain    as domain,
       max(relation.relation_score) as relation_score
from keyword_relations relation
join keywords target on target.id = relation.target_keyword_id
where exists (
          select 1 from member_interest_keywords mik
          where mik.member_id = ? and mik.keyword_id = relation.source_keyword_id
      )
  and not exists (
          select 1 from member_interest_keywords mik
          where mik.member_id = ? and mik.keyword_id = target.id
      )
group by target.id, target.name, target.domain
order by max(relation.relation_score) desc, target.id asc
limit ?;
```

---

## 저장한 트렌드

```sql
-- 이미 저장했는지
select exists (select 1 from saved_trends where member_id = ? and trend_id = ?);

-- 소유자 확인과 함께 단건 조회
select * from saved_trends where id = ? and member_id = ?;

-- 저장 목록 (trends · keywords 조인, 최신순 페이지)
select saved.*, trend.*, keyword.*
from saved_trends saved
join trends   trend   on trend.id = saved.trend_id
join keywords keyword on keyword.id = trend.keyword_id
where saved.member_id = ?
order by saved.created_at desc, saved.id desc
limit ? offset ?;
```

---

## 알림

```sql
-- 알림 목록 (trends 조인, 최신순 페이지)
select notification.*, trend.*
from notifications notification
join trends trend on trend.id = notification.trend_id
where notification.member_id = ?
order by notification.created_at desc, notification.id desc
limit ? offset ?;

-- 위 질의의 count
select count(*) from notifications where member_id = ?;

-- 안 읽은 개수
select count(*) from notifications where member_id = ? and is_read = false;

-- 소유자 확인과 함께 단건 조회
select * from notifications where id = ? and member_id = ?;

-- 모두 읽음 처리
update notifications set is_read = true
where member_id = ? and is_read = false;

-- 탈퇴 시 전체 삭제
delete from notifications where member_id = ?;
```

> 위 네 질의가 `V12` 인덱스 두 개의 대상이다. 인덱스 전에는 p95 가 900ms 였다 — [알림 인덱스](../summary/01-notification-index.md)
>
> ```sql
> CREATE INDEX idx_notifications_member_created
>     ON notifications (member_id, created_at DESC, id DESC);
> CREATE INDEX idx_notifications_member_unread
>     ON notifications (member_id) WHERE is_read = false;
> ```

### 알림 배치

```sql
-- 알림 대상: 관심 키워드 ⋈ 트렌드 (전 회원)
select mik.*, member.*, trend.*, keyword.name
from member_interest_keywords mik
join members  member on member.id  = mik.member_id
join trends   trend  on trend.keyword_id = mik.keyword_id
join keywords keyword on keyword.id = mik.keyword_id;

-- 이미 보낸 알림 걸러내기
select dedup_key from notifications where dedup_key in (?, ?, ...);

-- 회원들의 알림 설정 한 번에
select * from notification_settings where member_id in (?, ?, ...);

-- 알림 설정 단건 (members 조인)
select setting.*, member.*
from notification_settings setting
join members member on member.id = setting.member_id
where setting.member_id = ?;
```

---

## 트렌드 조회

```sql
-- 트렌드 단건 (keywords 조인)
select trend.*, keyword.*
from trends trend
join keywords keyword on keyword.id = trend.keyword_id
where trend.id = ?;

-- 키워드 여러 개의 트렌드 한 번에
select trend.*, keyword.*
from trends trend
join keywords keyword on keyword.id = trend.keyword_id
where trend.keyword_id in (?, ?, ...);

-- AI 해설 단건
select * from trend_analyses where trend_id = ? and period = ?;

-- 목록 화면용 해설 일괄 조회
select * from trend_analyses where trend_id in (?, ?, ...) and period = ?;

-- 언급량 추이 차트
select * from keyword_metric_history
where keyword_id = ? and bucket_start >= ? and bucket_start < ?
order by bucket_start asc;

-- 특정 구간의 지표 단건
select * from keyword_metrics
where keyword_id = ? and period = ? and period_start = ? and period_end = ?
order by id desc limit 1;

-- 여러 키워드의 같은 구간 지표
select * from keyword_metrics
where keyword_id in (?, ?, ...) and period = ? and period_start = ? and period_end = ?;

-- 원본 기사 목록 (발행일 최신순)
select content.*
from contents content
join keyword_contents kc on kc.content_id = content.id
where kc.keyword_id = ?
order by content.published_at desc, content.id desc
limit ? offset ?;

-- 연관 키워드 (연관도순)
select relation.*, target.*
from keyword_relations relation
join keywords target on target.id = relation.target_keyword_id
where relation.source_keyword_id = ? and target.id <> ?
order by relation.relation_score desc, target.id asc;
```

### 키워드 검색

정확히 일치하는 것을 맨 앞으로 올린다.

```sql
select *
from keywords
where position(? in normalized_name) > 0
  and (? is null or domain = ?)
order by case when normalized_name = ? then 0 else 1 end, id asc
limit ? offset ?;
```

---

## 트렌드 순위 — 인기 · 신규 · 급상승

**유일하게 네이티브로 쓴 세 질의다.** `trend_types` 가 **배열 컬럼**이라 `= any(...)` 가 필요하고, `period` 와 `trend_type` 이 **PostgreSQL DOMAIN 타입**이라 명시적 `cast` 가 필요하다. JPQL 로는 표현되지 않는다.

```sql
-- 인기 (CURRENT) — 언급량순
select metric.*
from keyword_metrics metric
join keywords keyword on keyword.id = metric.keyword_id
where keyword.domain = :domain
  and cast('CURRENT' as trend_type) = any(metric.trend_types)
  and metric.period = cast(:period as metric_period)
  and metric.period_start = :startAt
  and metric.period_end   = :endAt
order by metric.mention_count desc, metric.id asc
limit ? offset ?;
```

`NEW` · `RISING` 은 같은 모양에서 **상수와 정렬 기준만** 다르다.

| 유형 | 조건 | 정렬 |
| --- | --- | --- |
| 인기 | `cast('CURRENT' as trend_type) = any(...)` | `mention_count desc` |
| 신규 | `cast('NEW' as trend_type) = any(...)` | `mention_count desc` |
| 급상승 | `cast('RISING' as trend_type) = any(...)` | `growth_rate desc` |

---

## 국가별 트렌드

```sql
-- 나라별 최초 등장일 — 확산 경로의 순서
select country_code, min(metric_date) as first_detected_date
from keyword_country_daily_metrics
where keyword_id = ?
group by country_code
order by min(metric_date), country_code;

-- 나라별 언급량 합계 (지도 색칠용)
select country_code, sum(mention_count) as mention_count
from keyword_country_daily_metrics metric
join keywords keyword on keyword.id = metric.keyword_id
where keyword.domain = ? and metric.metric_date between ? and ?
group by country_code
order by sum(mention_count) desc, country_code;

-- 한 나라의 키워드별 언급량 합계
select metric.keyword_id, sum(metric.mention_count) as mention_count
from keyword_country_daily_metrics metric
join keywords keyword on keyword.id = metric.keyword_id
where keyword.domain = ? and metric.country_code = ? and metric.metric_date between ? and ?
group by metric.keyword_id
order by sum(metric.mention_count) desc, metric.keyword_id
limit ?;

-- 분야 전체 언급량 (비중 계산의 분모)
select coalesce(sum(metric.mention_count), 0)
from keyword_country_daily_metrics metric
join keywords keyword on keyword.id = metric.keyword_id
where keyword.domain = ? and metric.metric_date between ? and ?;

-- 나라별 일별 지표
select * from keyword_country_daily_metrics
where keyword_id = ? and metric_date between ? and ?;
```

---

## 개념 이름 (파이프라인 표 조회)

파이프라인이 만든 `pl_*` 표를 읽는 유일한 질의다. **모호하지 않은 것만** 가져오려고 `having` 으로 거른다 — 개념이 하나로 좁혀지고(`count(distinct) = 1`) 영어 표현이 아닌 경우만.

```sql
select keyword.id, min(concept.canonical_name)
from keywords keyword
join pl_concept_expression concept_expression
  on concept_expression.normalized = keyword.normalized_name
 and concept_expression.status = 'ACTIVE'
join pl_concept concept
  on concept.id = concept_expression.concept_id
 and concept.status = 'ACTIVE'
where keyword.id in (:keywordIds)
group by keyword.id
having count(distinct concept.id) = 1
   and sum(case when concept_expression.lang = 'en' then 1 else 0 end) = 0;
```

---

## 참고

- 표 구조와 관계: [ERD](../../erd/erd.md)
- 인덱스 정의: `backend/src/main/resources/db/migration/`
- 원본 코드: `backend/src/main/java/com/forever102/*/repository/`
