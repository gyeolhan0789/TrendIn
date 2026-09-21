-- 콘텐츠 200,000 · 키워드-콘텐츠 연결 약 600,000
--
-- 연결을 고르게 뿌리면 어느 키워드를 눌러도 콘텐츠가 세 개뿐이라 /trends/{id}/contents
-- 가 언제나 빠르다. 실제로는 소수의 키워드에 콘텐츠가 몰린다. 그 쏠린 키워드가
-- 최악의 경우이고, keyword_contents 의 기본키가 (content_id, keyword_id) 라
-- keyword_id 단독 조회가 인덱스를 못 타는 것도 거기서 드러난다.

DO $$ BEGIN
    IF current_database() <> 'trendin_test' THEN
        RAISE EXCEPTION 'trendin_test 전용이다. 현재: %', current_database();
    END IF;
END $$;

SELECT setseed(0.42);

INSERT INTO contents (id, title, source, url, body_object_key, published_at, collected_at)
SELECT g.i,
       '콘텐츠 ' || g.i || ' — ' || md5(g.i::text),
       (ARRAY['hackernews','reddit','medium','techcrunch','vogue','wwd'])[1 + g.i % 6],
       'https://example.test/article/' || g.i,
       'curated/2026/' || lpad((1 + g.i % 12)::text, 2, '0') || '/' || g.i || '.txt',
       now() - (random() * interval '90 days'),
       now() - (random() * interval '90 days')
FROM generate_series(1, 200000) AS g(i);

-- 콘텐츠 하나에 키워드 셋. 70% 는 상위 2,000 개 키워드로 몰아준다.
-- 충돌하면 건너뛴다. 같은 콘텐츠에 같은 키워드가 두 번 뽑힐 수 있다.
INSERT INTO keyword_contents (content_id, keyword_id)
SELECT c.i,
       CASE WHEN random() < 0.7
            THEN 1 + ((c.i * 7 + k.n * 13) % 2000)
            ELSE 1 + ((c.i * 7 + k.n * 13) % 50000)
       END
FROM generate_series(1, 200000) AS c(i)
CROSS JOIN generate_series(0, 2) AS k(n)
ON CONFLICT DO NOTHING;

\echo '02 완료: contents · keyword_contents'
