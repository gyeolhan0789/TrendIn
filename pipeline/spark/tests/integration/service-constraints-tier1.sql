-- [08 §5] 티어 1 요청 세 개를 **로컬에만** 적용한다. 운영에서는 datastore·백엔드가 친다.
--
-- 이 파일이 있는 이유는 요청의 효과를 말이 아니라 실행으로 보이기 위해서다. 이걸 돌린
-- DB 에서는 `extract` 의 승격이 열리고 `aggregate` 가 세 표를 채운다 — 돌리지 않은 DB 에서
-- 무슨 일이 일어나는지도 함께 확인할 수 있다 (승격이 건너뛰어지고 지표 대상이 0 이 된다).
--
--   docker exec -i <postgres> psql -U trendin -d trendin < service-constraints-tier1.sql

-- 1. **압도적으로 급하다.** 없으면 `ON CONFLICT` 가 동작하지 않아 같은 키워드가 매 배치마다
--    새 행으로 쌓이고, 며칠이면 어느 행이 진짜인지 판별할 수 없다 ([05 §5]).
--    `normalized_name` 단독이 아니라 `domain` 과의 복합이어야 한다 — 단독으로 걸면 개발의
--    `모델` 과 패션의 `모델` 이 충돌해 한쪽이 들어가지 못한다.
CREATE UNIQUE INDEX IF NOT EXISTS uk_keywords_domain_normalized_name
    ON keywords (domain, normalized_name);

-- 2. 기간별 1행. 백엔드 엔티티의 UNIQUE 는 `period_start`·`period_end` 까지 포함한 4열이라
--    **D 가 하루 넘어가면 같은 키워드·같은 기간의 행이 하나 더 생긴다.** 우리 적재는
--    "옛 구간 행 지우기" 로 그걸 막지만(`io/metrics.metrics_merge_sql`), 제약이 막아 주는
--    편이 낫다 — 다른 경로로 들어온 행까지 덮는다.
CREATE UNIQUE INDEX IF NOT EXISTS uk_keyword_metrics_keyword_period
    ON keyword_metrics (keyword_id, period);

-- 3. 버킷별 1행. 없으면 재계산할 때마다 같은 날짜가 그래프에 여러 번 나온다 —
--    **화면에 바로 보이는 종류의 오류다.**
CREATE UNIQUE INDEX IF NOT EXISTS uk_keyword_metric_history_keyword_bucket
    ON keyword_metric_history (keyword_id, bucket_start);
