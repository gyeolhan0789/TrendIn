-- 관심 키워드 · 저장한 트렌드 · 알림. 회원마다 양이 크게 다르다.
--
-- 여기가 이 시드에서 가장 중요한 파일이다. 모든 회원에게 같은 양을 주면
-- PostgreSQL 의 통계가 "회원 하나당 N 행"으로 잡히고, 플래너는 늘 같은 계획을
-- 고른다. 실제 서비스는 그렇지 않다. 절반은 아무것도 저장하지 않고, 소수가
-- 수천 건을 쌓는다. 그 소수를 조회할 때 무엇이 무너지는지가 부하테스트에서
-- 알고 싶은 것이다.
--
-- 이 분포가 없으면 측정은 돌아가지만 조용히 틀린 값을 준다. 에러가 나지 않아
-- 알아채기 어렵다.

DO $$ BEGIN
    IF current_database() <> 'trendin_test' THEN
        RAISE EXCEPTION 'trendin_test 전용이다. 현재: %', current_database();
    END IF;
END $$;

SELECT setseed(0.42);

-- 회원을 네 무리로 나눈다. 비율은 실제 서비스의 흔한 모양을 따랐다.
--   0 (50%) 가입만 함        1 (30%) 가볍게 씀
--   2 (15%) 꾸준히 씀        3  (5%) 헤비 — 최악의 경우를 만든다
CREATE TEMP TABLE member_activity AS
SELECT g.i AS member_id,
       t.tier,
       CASE t.tier WHEN 0 THEN 0
                   WHEN 1 THEN   1 + (random() *   4)::int
                   WHEN 2 THEN   6 + (random() *  24)::int
                   ELSE        100 + (random() * 400)::int
       END AS saved_count,
       CASE t.tier WHEN 0 THEN       (random() *   1)::int
                   WHEN 1 THEN   2 + (random() *   3)::int
                   WHEN 2 THEN   5 + (random() *  10)::int
                   ELSE         20 + (random() *  30)::int
       END AS interest_count,
       CASE t.tier WHEN 0 THEN       (random() *   2)::int
                   WHEN 1 THEN   5 + (random() *  15)::int
                   WHEN 2 THEN  50 + (random() * 150)::int
                   ELSE        300 + (random() * 1200)::int
       END AS notification_count
FROM generate_series(1, 10000) AS g(i)
CROSS JOIN LATERAL (
    SELECT CASE WHEN g.i % 100 < 50 THEN 0
                WHEN g.i % 100 < 80 THEN 1
                WHEN g.i % 100 < 95 THEN 2
                ELSE 3
           END AS tier
) AS t;

-- generate_series(1, 0) 은 한 행도 내지 않는다. tier 0 이 자연히 비워진다.
-- 곱수를 서로 다르게 둬서 한 회원 안에서 같은 대상이 두 번 뽑히지 않게 한다.

INSERT INTO member_interest_keywords (member_id, keyword_id, created_at, was_trending)
SELECT a.member_id,
       1 + ((a.member_id * 11 + n.k * 41) % 50000),
       now() - (random() * interval '180 days'),
       (random() < 0.3)
FROM member_activity a
CROSS JOIN LATERAL generate_series(1, a.interest_count) AS n(k)
ON CONFLICT DO NOTHING;

INSERT INTO saved_trends (member_id, trend_id, created_at)
SELECT a.member_id,
       1 + ((a.member_id * 13 + n.k * 37) % 50000),
       now() - (random() * interval '180 days')
FROM member_activity a
CROSS JOIN LATERAL generate_series(1, a.saved_count) AS n(k)
ON CONFLICT DO NOTHING;

-- 30% 는 읽지 않은 채로 둔다. 헤더의 안 읽은 개수 조회가 셀 것이 있어야 한다.
-- notifications 에는 member_id 인덱스가 없다. 이 테이블이 커질수록 그 조회가
-- 전체를 훑는다 — Phase 4 에서 확인할 첫 번째 대상이다.
INSERT INTO notifications (
    member_id, trend_id, notification_type, message, is_read, created_at, dedup_key
)
SELECT a.member_id,
       1 + ((a.member_id * 17 + n.k) % 50000),
       (ARRAY['KEYWORD_SURGE','KEYWORD_DROP','NEW_TREND',
              'TREND_TURNING_POINT','TREND_CHANGE'])[1 + n.k % 5],
       '관심 키워드에 변화가 있다 (' || n.k || ')',
       (random() < 0.7),
       now() - (random() * interval '90 days'),
       'loadtest:' || a.member_id || ':' || n.k
FROM member_activity a
CROSS JOIN LATERAL generate_series(1, a.notification_count) AS n(k);

\echo '07 완료: member_interest_keywords · saved_trends · notifications'
