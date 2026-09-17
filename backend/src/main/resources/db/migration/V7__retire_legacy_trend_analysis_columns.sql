-- V5에서 기존 분석은 7D로 이관했다. 기간별 저장으로 생성된 최신 분석은 덮어쓰지 않는다.
-- V5 이후 구 버전 writer가 추가한 행도 누락 없이 보존한다.
INSERT INTO trend_analyses (
    trend_id, period, trend_types, description, summary, reason, analyzed_at
)
SELECT id, '7D'::metric_period, trend_types, description, summary, reason, updated_at
  FROM trends
 WHERE description IS NOT NULL
ON CONFLICT (trend_id, period) DO NOTHING;

ALTER TABLE trends
    DROP COLUMN description,
    DROP COLUMN summary,
    DROP COLUMN reason,
    DROP COLUMN trend_types;
