-- 기간별 지표 150,000 · 일별 이력 4,500,000
--
-- 이 파일이 제일 오래 걸린다. keyword_metric_history 는 키워드 50,000 × 90일이고
-- 유니크 인덱스가 둘 달려 있다. 몇 분을 예상한다.
--
-- 언급 수를 롱테일로 만든다. 전부 비슷한 값이면 상위 목록 조회가 어느 키워드를
-- 집어도 같은 비용이 되어, 실제로 사람들이 보는 화면과 다른 것을 재게 된다.

DO $$ BEGIN
    IF current_database() <> 'trendin_test' THEN
        RAISE EXCEPTION 'trendin_test 전용이다. 현재: %', current_database();
    END IF;
END $$;

SELECT setseed(0.42);

INSERT INTO keyword_metrics (
    keyword_id, period, period_start, period_end,
    mention_count, previous_mention_count, growth_amount,
    growth_rate, mention_rank, trend_types
)
WITH base AS (
    SELECT k.i AS keyword_id,
           p.period,
           p.span,
           CASE WHEN k.i <= 2000  THEN 500 + (random() * 5000)::bigint
                WHEN k.i <= 10000 THEN  50 + (random() *  500)::bigint
                ELSE                          (random() *   50)::bigint
           END AS mention_count
    FROM generate_series(1, 50000) AS k(i)
    CROSS JOIN (VALUES ('24H', interval '1 day'),
                       ('7D',  interval '7 days'),
                       ('30D', interval '30 days')) AS p(period, span)
),
calc AS (
    SELECT base.*,
           greatest(0, (mention_count * (0.5 + random()))::bigint) AS previous_mention_count
    FROM base
)
SELECT keyword_id,
       period::metric_period,
       now() - span,
       now(),
       mention_count,
       previous_mention_count,
       mention_count - previous_mention_count,
       CASE WHEN previous_mention_count = 0 THEN NULL
            ELSE round(((mention_count - previous_mention_count)::numeric
                        / previous_mention_count) * 100, 2)
       END,
       (row_number() OVER (PARTITION BY period ORDER BY mention_count DESC))::int,
       ARRAY[(ARRAY['CURRENT','RISING','NEW'])[1 + keyword_id % 3]]::varchar[]
FROM calc;

-- 90일치 일별 이력. /trends/{id}/history 가 이 위를 긁는다.
INSERT INTO keyword_metric_history (keyword_id, bucket_start, bucket_end, mention_count)
SELECT k.i,
       d.day,
       d.day + interval '1 day',
       CASE WHEN k.i <= 2000  THEN (10 + random() * 200)::bigint
            WHEN k.i <= 10000 THEN ( 1 + random() *  20)::bigint
            ELSE                   (     random() *   3)::bigint
       END
FROM generate_series(1, 50000) AS k(i)
CROSS JOIN generate_series(
    date_trunc('day', now() - interval '89 days'),
    date_trunc('day', now()),
    interval '1 day'
) AS d(day);

\echo '03 완료: keyword_metrics · keyword_metric_history'
