-- 안전장치. 나머지 파일 맨 앞에도 같은 검사를 둔다.
--
-- trendin_test 는 운영 forever102 와 같은 PostgreSQL 인스턴스에 있다. psql 의 -d 를
-- 한 글자 잘못 치면 운영 데이터베이스에 수백만 행이 들어가고 되돌릴 수 없다.
-- 사람의 주의력에 기대지 않고 데이터베이스가 직접 거절하게 한다.

DO $$
BEGIN
    IF current_database() <> 'trendin_test' THEN
        RAISE EXCEPTION
            '부하테스트 시드는 trendin_test 전용이다. 지금 연결된 곳: %',
            current_database();
    END IF;
END $$;

-- 이미 채워진 데이터베이스에 또 부으면 유니크 제약에 걸려 중간에 죽는다.
-- 그 상태는 절반만 들어간 데이터라 측정에 쓸 수 없다. 시작 전에 막는다.
DO $$
DECLARE
    existing bigint;
BEGIN
    SELECT count(*) INTO existing FROM members;
    IF existing > 0 THEN
        RAISE EXCEPTION
            'members 에 이미 % 행이 있다. 다시 부으려면 먼저 비운다: load-test/seed/reset.sql',
            existing;
    END IF;
END $$;

\echo '가드 통과: trendin_test, 비어 있음'
