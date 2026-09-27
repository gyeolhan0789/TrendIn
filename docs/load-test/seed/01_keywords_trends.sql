-- 키워드 50,000 · 트렌드 50,000 · 트렌드 분석 150,000
--
-- trends 는 keyword 와 1:1 이다(uk_trends_keyword). 설명·요약·근거는 V7 에서
-- trends 를 떠나 trend_analyses 로 갔으므로, 상세 API 가 읽을 것은 그쪽이다.

DO $$ BEGIN
    IF current_database() <> 'trendin_test' THEN
        RAISE EXCEPTION 'trendin_test 전용이다. 현재: %', current_database();
    END IF;
END $$;

-- 같은 데이터를 다시 만들 수 있어야 측정을 비교할 수 있다.
SELECT setseed(0.42);

-- 이름을 전부 같은 접두사로 만들면 키워드 검색이 항상 전체를 맞힌다. 실제 검색의
-- 선택도를 흉내내려면 어휘가 갈라져 있어야 한다. 분야별로 10개씩 돌려 쓴다.
INSERT INTO keywords (id, name, normalized_name, domain)
SELECT g.i,
       v.word || '-' || g.i,
       lower(v.word || '-' || g.i),
       v.domain
FROM generate_series(1, 50000) AS g(i)
CROSS JOIN LATERAL (
    SELECT CASE WHEN g.i % 2 = 0 THEN 'DEVELOP' ELSE 'FASHION' END AS domain,
           CASE WHEN g.i % 2 = 0
                THEN (ARRAY['react','spring','kotlin','python','docker',
                            'kubernetes','graphql','rust','llm','observability'])[1 + (g.i / 2) % 10]
                ELSE (ARRAY['denim','linen','loafer','trench','knit',
                            'sneaker','tailoring','archive','minimal','layering'])[1 + (g.i / 2) % 10]
           END AS word
) AS v;

INSERT INTO trends (id, keyword_id, updated_at)
SELECT g.i, g.i, now() - (random() * interval '30 days')
FROM generate_series(1, 50000) AS g(i);

-- 기간마다 한 벌씩. 상세 화면이 period 를 받아 이 중 하나를 고른다.
INSERT INTO trend_analyses (
    trend_id, period, trend_types, description, summary, reason,
    input_fingerprint, analyzed_at
)
SELECT t.i,
       p.period::metric_period,
       ARRAY[(ARRAY['CURRENT','RISING','NEW'])[1 + (t.i + p.ord) % 3]]::varchar[],
       '키워드 ' || t.i || ' 의 ' || p.period || ' 분석',
       repeat('이 키워드는 최근 언급이 늘고 있다. ', 12),
       repeat('연관 콘텐츠의 증가가 근거다. ', 10),
       md5(t.i::text || p.period),
       now() - (random() * interval '7 days')
FROM generate_series(1, 50000) AS t(i)
CROSS JOIN (VALUES ('24H', 1), ('7D', 2), ('30D', 3)) AS p(period, ord);

\echo '01 완료: keywords · trends · trend_analyses'
