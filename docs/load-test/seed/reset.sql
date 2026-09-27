-- 시드를 지우고 처음부터 다시 부을 수 있게 비운다.
--
-- TRUNCATE 는 되돌릴 수 없다. 이 파일이 운영 데이터베이스에서 실행되면 서비스가
-- 사라진다. 가드를 두 번 건다.

DO $$ BEGIN
    IF current_database() <> 'trendin_test' THEN
        RAISE EXCEPTION
            'TRUNCATE 는 trendin_test 에서만 허용한다. 지금 연결된 곳: %',
            current_database();
    END IF;
END $$;

TRUNCATE TABLE
    notifications,
    notification_settings,
    saved_trends,
    member_interest_keywords,
    member_domains,
    member_oauth_accounts,
    members,
    keyword_country_daily_metrics,
    keyword_metric_history,
    keyword_metrics,
    keyword_relations,
    keyword_contents,
    contents,
    trend_analyses,
    trends,
    keywords
RESTART IDENTITY CASCADE;

-- RESTART IDENTITY 는 identity 컬럼의 시퀀스만 되돌린다. member_domains 가 쓰는
-- 독립 시퀀스는 따로 손대야 한다.
SELECT setval('member_domains_seq', 1, false);

\echo 'reset 완료: 시드 테이블을 비웠다'
