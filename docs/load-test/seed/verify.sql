-- 시드가 제대로 들어갔는지 본다. 행 수만 보지 않고 분포와 통계까지 확인한다.
-- 행 수가 맞아도 분포가 고르거나 ANALYZE 가 빠지면 측정이 무의미해지기 때문이다.

\echo ''
\echo '=== 행 수 ==='
SELECT 'keywords'                      AS table_name, count(*) FROM keywords
UNION ALL SELECT 'trends',                     count(*) FROM trends
UNION ALL SELECT 'trend_analyses',             count(*) FROM trend_analyses
UNION ALL SELECT 'contents',                   count(*) FROM contents
UNION ALL SELECT 'keyword_contents',           count(*) FROM keyword_contents
UNION ALL SELECT 'keyword_metrics',            count(*) FROM keyword_metrics
UNION ALL SELECT 'keyword_metric_history',     count(*) FROM keyword_metric_history
UNION ALL SELECT 'keyword_country_daily',      count(*) FROM keyword_country_daily_metrics
UNION ALL SELECT 'keyword_relations',          count(*) FROM keyword_relations
UNION ALL SELECT 'members',                    count(*) FROM members
UNION ALL SELECT 'member_domains',             count(*) FROM member_domains
UNION ALL SELECT 'member_interest_keywords',   count(*) FROM member_interest_keywords
UNION ALL SELECT 'saved_trends',               count(*) FROM saved_trends
UNION ALL SELECT 'notifications',              count(*) FROM notifications
ORDER BY 2 DESC;

\echo ''
\echo '=== 테이블 크기 (인덱스 포함) ==='
SELECT relname AS table_name,
       pg_size_pretty(pg_total_relation_size(c.oid)) AS total
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'r'
ORDER BY pg_total_relation_size(c.oid) DESC
LIMIT 10;

\echo ''
\echo '=== 저장한 트렌드 분포 — 한 쪽으로 쏠려 있어야 정상 ==='
SELECT CASE WHEN cnt = 0 THEN '0개'
            WHEN cnt <= 5 THEN '1-5개'
            WHEN cnt <= 30 THEN '6-30개'
            ELSE '31개 이상' END AS bucket,
       count(*) AS members,
       round(100.0 * count(*) / 10000, 1) AS pct
FROM (
    SELECT m.id, count(s.id) AS cnt
    FROM members m
    LEFT JOIN saved_trends s ON s.member_id = m.id
    GROUP BY m.id
) t
GROUP BY 1
ORDER BY min(cnt);

\echo ''
\echo '=== 알림이 가장 많은 회원 다섯 — Phase 3 의 최악 케이스 ==='
SELECT member_id,
       count(*) AS notifications,
       count(*) FILTER (WHERE NOT is_read) AS unread
FROM notifications
GROUP BY member_id
ORDER BY count(*) DESC
LIMIT 5;

\echo ''
\echo '=== 통계 수집 여부 — last_analyze 가 비어 있으면 ANALYZE 를 다시 돌린다 ==='
SELECT relname AS table_name,
       n_live_tup,
       coalesce(last_analyze, last_autoanalyze) AS analyzed_at
FROM pg_stat_user_tables
WHERE relname IN ('notifications', 'keyword_metric_history',
                  'keyword_country_daily_metrics', 'saved_trends', 'keyword_contents')
ORDER BY relname;
