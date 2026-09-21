-- 연관 키워드 약 500,000
--
-- /trends/{id}/related-keywords 가 source_keyword_id 로 찾는다. 기본키가
-- (source, target) 이라 이 조회는 인덱스를 탄다. 비교군으로 둔다.

DO $$ BEGIN
    IF current_database() <> 'trendin_test' THEN
        RAISE EXCEPTION 'trendin_test 전용이다. 현재: %', current_database();
    END IF;
END $$;

SELECT setseed(0.42);

INSERT INTO keyword_relations (
    source_keyword_id, target_keyword_id, relation_score, co_occurrence_count, updated_at
)
SELECT s.i,
       t.target,
       -- ck_keyword_relations_score 가 0~100 을 요구한다.
       round((random() * 100)::numeric, 2),
       (random() * 1000)::bigint,
       now() - (random() * interval '10 days')
FROM generate_series(1, 50000) AS s(i)
CROSS JOIN LATERAL (
    SELECT 1 + ((s.i * 31 + n.k * 7919) % 50000) AS target
    FROM generate_series(1, 10) AS n(k)
) AS t
WHERE t.target <> s.i
ON CONFLICT DO NOTHING;

\echo '05 완료: keyword_relations'
