-- 서비스 테이블의 **로컬 미러** — 백엔드 엔티티를 그대로 옮긴 것이다.
--
-- 이 파일은 `backend/` 를 고치지 않고 적재를 검증하려고 둔다 ([10 §5] 담당 경계). 운영
-- 스키마의 소유자는 여전히 백엔드의 JPA 이고, 여기 있는 것은 **그 시점의 사본**이다.
--
-- 출처: `backend/src/main/java/com/forever102/trend/domain/` 의
--   Keyword · KeywordMetric · KeywordMetricHistory · Trend · AnalysisPeriod · TrendType
--   (2026-09-10 확인)
--
-- ⚠️ **일부러 제약을 빼 두었다.** 백엔드 엔티티에 없는 것은 여기에도 없다 —
--    * `keywords (domain, normalized_name)` UNIQUE 없음 ([08 §5] 티어 1 의 1번)
--    * `keyword_metrics` 의 UNIQUE 는 **4열**이다 (우리가 요청한 2열이 아니다)
--    * `keyword_metric_history` 의 UNIQUE 는 **3열**이다
--    * `trends.keyword_id` 에 UNIQUE 없음 (ERD 는 UK 라고 적었지만 엔티티에는 없다)
--    * `trends.description` 이 `NOT NULL` 이다 — AI 설명이 범위 밖인데도 값이 필요하다
--
-- 요청분을 적용한 상태를 보려면 `service-constraints-tier1.sql` 을 이어서 돌린다.
--
--   docker exec -i <postgres> psql -U trendin -d trendin < service-schema-local.sql

-- 네이티브 enum 둘. `@JdbcTypeCode(SqlTypes.NAMED_ENUM)` 과 `SqlTypes.ARRAY` + `@Enumerated`
-- 가 만드는 형태이고, 백엔드 조회가 `cast('CURRENT' as trend_type)` 로 쓰는 것이 그 증거다.
-- `metric_period` 의 값이 enum 이름(`HOURS_24`)이 아니라 `@EnumeratedValue` 가 붙은
-- `value` 필드(`24H`)인 것이 요점이다 — 이것이 [09 §7] 항목 3(기간 값 규약)의 답이다.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'metric_period') THEN
        CREATE TYPE metric_period AS ENUM ('24H', '7D', '30D');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'trend_type') THEN
        CREATE TYPE trend_type AS ENUM ('CURRENT', 'RISING', 'NEW');
    END IF;
END $$;

-- `domain` 은 `@Enumerated(EnumType.STRING)` 이라 varchar 이고 값은 `DEVELOP`/`FASHION` 이다
-- ([01 §6], `io/contract.DOMAIN_VALUES`).
CREATE TABLE IF NOT EXISTS keywords (
    id              bigserial PRIMARY KEY,
    name            varchar(255) NOT NULL,
    normalized_name varchar(255) NOT NULL,
    domain          varchar(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS keyword_metrics (
    id                     bigserial PRIMARY KEY,
    keyword_id             bigint        NOT NULL REFERENCES keywords (id),
    period                 metric_period NOT NULL,
    period_start           timestamptz   NOT NULL,
    period_end             timestamptz   NOT NULL,
    mention_count          bigint        NOT NULL,
    previous_mention_count bigint        NOT NULL,
    -- 생성 컬럼이 아니다 ([08 §5] 확인 16번). 평범한 `@Column` 이라 INSERT 에 값을 넣는다.
    growth_amount          bigint        NOT NULL,
    growth_rate            numeric(38, 2),
    -- `Integer` 라 nullable 이다 ([08 §5] 확인 17번). 언급량 0 인 기간에 `NULL` 을 넣을 수 있다.
    mention_rank           integer,
    CONSTRAINT uk_keyword_metrics_period
        UNIQUE (keyword_id, period, period_start, period_end)
);

CREATE TABLE IF NOT EXISTS keyword_metric_history (
    id            bigserial PRIMARY KEY,
    keyword_id    bigint      NOT NULL REFERENCES keywords (id),
    bucket_start  timestamptz NOT NULL,
    bucket_end    timestamptz NOT NULL,
    mention_count bigint      NOT NULL,
    CONSTRAINT uk_keyword_metric_history_bucket
        UNIQUE (keyword_id, bucket_start, bucket_end)
);

CREATE TABLE IF NOT EXISTS trends (
    id          bigserial PRIMARY KEY,
    keyword_id  bigint       NOT NULL REFERENCES keywords (id),
    trend_types trend_type[] NOT NULL,
    -- ⚠️ `nullable = false` 다. AI 설명은 이 에픽의 범위 밖이라([00 §4]) 새 행에 빈 문자열을
    -- 넣는다 (`io/metrics.EMPTY_DESCRIPTION`). 갱신에서는 건드리지 않는다.
    description varchar(255) NOT NULL,
    summary     text,
    reason      text,
    updated_at  timestamptz  NOT NULL
);

-- `keyword_contents` 는 [05] 가 쓴다. 여기서는 승격 경로를 돌리려고 함께 만든다.
-- `url` 의 UNIQUE 는 엔티티에 있다 (`@Column(nullable = false, unique = true)`). 없으면
-- `io/contents.py` 의 `ON CONFLICT (url)` 이 "no unique or exclusion constraint" 로 죽는다.
--
-- ⚠️ 길이가 varchar(255) 다 ([08 §5] 요청 5번) — 긴 URL 에서 삽입이 실패한다. 미러는 실제
-- 스키마를 흉내 내는 것이 목적이라 여기서도 255 로 둔다. 그래야 그 결함이 로컬에서 드러난다.
CREATE TABLE IF NOT EXISTS contents (
    id              bigserial PRIMARY KEY,
    title           varchar(255) NOT NULL,
    source          varchar(255) NOT NULL,
    url             varchar(255) NOT NULL UNIQUE,
    body_object_key text,
    published_at    timestamptz  NOT NULL,
    collected_at    timestamptz  NOT NULL
);
CREATE TABLE IF NOT EXISTS keyword_contents (
    keyword_id bigint NOT NULL REFERENCES keywords (id),
    content_id bigint NOT NULL REFERENCES contents (id),
    PRIMARY KEY (keyword_id, content_id)
);
