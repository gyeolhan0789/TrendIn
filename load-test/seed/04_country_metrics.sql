-- 국가별 일별 지표 약 2,400,000
--
-- /trends/{id}/regions, /regions/{code}/history, /regions/journey 세 엔드포인트가
-- 전부 이 테이블을 읽는다. 비워 두면 셋 다 빈 결과를 즉시 돌려주므로 측정이 되지 않는다.
--
-- 키워드 전부에 주지는 않는다. 50,000 × 20개국 × 90일이면 9천만 행이라 감당이 안 되고,
-- 실제로도 모든 키워드에 국가 정보가 붙지는 않는다. 상위 2,000 개에만 준다.
--
-- 나라마다 등장 시점을 어긋나게 한다. 전부 같은 날 시작하면 journey 의
-- min(metric_date) 집계가 모든 국가에 같은 값을 돌려주어 화면이 무의미해진다.

DO $$ BEGIN
    IF current_database() <> 'trendin_test' THEN
        RAISE EXCEPTION 'trendin_test 전용이다. 현재: %', current_database();
    END IF;
END $$;

SELECT setseed(0.42);

INSERT INTO keyword_country_daily_metrics (keyword_id, country_code, metric_date, mention_count)
SELECT k.i,
       c.code,
       d.day::date,
       (random() * 50)::bigint
FROM generate_series(1, 2000) AS k(i)
CROSS JOIN unnest(ARRAY[
    'KR','US','JP','CN','GB','FR','DE','IT','ES','IN',
    'BR','CA','AU','SG','TW','VN','TH','ID','MX','NL'
]) WITH ORDINALITY AS c(code, ord)
CROSS JOIN generate_series(
    (now() - interval '89 days')::date,
    now()::date,
    interval '1 day'
) AS d(day)
-- 키워드마다 나라별로 0~59일 늦게 등장한다.
WHERE d.day::date >= (now()::date - 89 + (((k.i * 7 + c.ord * 11) % 60))::int);

\echo '04 완료: keyword_country_daily_metrics'
