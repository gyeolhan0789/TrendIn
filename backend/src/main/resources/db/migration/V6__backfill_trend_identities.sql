-- V5 적용 전에 집계됐지만 AI 분석을 받지 못한 키워드에도 상세 진입 ID를 준다.
-- 대표 유형은 우선순위가 높은 기간의 값으로 초기화하며, 기존 trends 행은 건드리지 않는다.
INSERT INTO trends (keyword_id, trend_types, description, updated_at)
SELECT DISTINCT ON (m.keyword_id)
       m.keyword_id, m.trend_types, NULL, now()
  FROM keyword_metrics m
 WHERE m.trend_types && ARRAY['NEW', 'RISING', 'CURRENT']::varchar[]
 ORDER BY m.keyword_id,
          CASE m.period::text WHEN '30D' THEN 0 WHEN '7D' THEN 1 ELSE 2 END
ON CONFLICT (keyword_id) DO NOTHING;
