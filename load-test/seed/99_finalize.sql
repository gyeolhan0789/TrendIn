-- 시퀀스 보정과 통계 수집. 둘 다 빠뜨리면 조용히 망가진다.

DO $$ BEGIN
    IF current_database() <> 'trendin_test' THEN
        RAISE EXCEPTION 'trendin_test 전용이다. 현재: %', current_database();
    END IF;
END $$;

-- id 를 직접 지정해 넣은 테이블은 identity 시퀀스가 1 에 멈춰 있다. 그대로 두면
-- 부하테스트가 회원을 가입시킬 때 1 번부터 발급하려다 기본키 충돌로 실패한다.
-- 측정이 아니라 에러율을 재게 된다.
--
-- setval 은 strict 라서 시퀀스를 찾지 못하면 NULL 을 받아 아무 일 없이 끝난다.
-- 조용히 넘어가면 부하를 걸 때까지 모르므로, 찾지 못하면 여기서 멈춘다.
DO $$
DECLARE
    target text;
    seq    text;
    top_id bigint;
BEGIN
    FOREACH target IN ARRAY ARRAY['members', 'keywords', 'trends', 'contents'] LOOP
        seq := pg_get_serial_sequence(target, 'id');
        IF seq IS NULL THEN
            RAISE EXCEPTION '% 의 id 시퀀스를 찾지 못했다', target;
        END IF;
        EXECUTE format('SELECT max(id) FROM %I', target) INTO top_id;
        IF top_id IS NULL THEN
            RAISE EXCEPTION '% 가 비어 있다. 앞 단계가 실패했다', target;
        END IF;
        PERFORM setval(seq, top_id);
        RAISE NOTICE '% 시퀀스를 % 로 맞췄다', target, top_id;
    END LOOP;
END $$;

-- 나머지 테이블은 id 를 기본값으로 받았으므로 시퀀스가 이미 따라와 있다.
-- member_domains 는 nextval 로 받아 써서 역시 손댈 것이 없다.

-- 통계가 없으면 플래너가 행 수를 짐작으로 잡는다. 인덱스를 탈 자리에서 전체를
-- 훑거나 그 반대가 되어, 측정값이 운영과 다른 경로를 잰 것이 된다. 에러가 나지
-- 않으므로 빠뜨려도 알 수 없다. 시드의 마지막은 반드시 여기다.
ANALYZE;

\echo '99 완료: 시퀀스 보정 · ANALYZE'
