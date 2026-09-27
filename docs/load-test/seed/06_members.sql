-- 회원 10,000 · 관심 분야 15,000 · 알림 설정 10,000
--
-- 비밀번호는 모두 같고, 해시는 미리 한 번만 만들어 재사용한다. 애플리케이션으로
-- 1만 명을 가입시키면 bcrypt(strength 10) 해싱에만 수 분이 든다. 이 값은
-- PasswordEncoderFactories.createDelegatingPasswordEncoder() 로 만들고
-- matches() 로 확인했다.
--
--   로그인 계정: load1@test.com ~ load10000@test.com
--   비밀번호:    Loadtest1234!
--
-- k6 시나리오도 이 계정을 쓴다. 바꾸면 양쪽을 같이 고쳐야 한다.

DO $$ BEGIN
    IF current_database() <> 'trendin_test' THEN
        RAISE EXCEPTION 'trendin_test 전용이다. 현재: %', current_database();
    END IF;
END $$;

SELECT setseed(0.42);

INSERT INTO members (id, email, password, nickname, onboarding_completed, created_at, updated_at)
SELECT g.i,
       'load' || g.i || '@test.com',
       '{bcrypt}$2a$10$HDO9MQswk6iZxoixDLbKPuupswq6.ryMueudfZpNVm50zDg25N65y',
       'user' || g.i,
       true,
       now() - (random() * interval '365 days'),
       now()
FROM generate_series(1, 10000) AS g(i);

-- member_domains 는 identity 가 아니라 INCREMENT BY 50 시퀀스를 쓴다(Hibernate pooled).
-- nextval 로 받아 두면 시퀀스가 알아서 앞서가므로 나중에 setval 로 손볼 일이 없다.
INSERT INTO member_domains (id, member_id, domain, created_at, updated_at)
SELECT nextval('member_domains_seq'), g.i, 'DEVELOP', now(), now()
FROM generate_series(1, 10000) AS g(i);

INSERT INTO member_domains (id, member_id, domain, created_at, updated_at)
SELECT nextval('member_domains_seq'), g.i, 'FASHION', now(), now()
FROM generate_series(1, 10000) AS g(i)
WHERE g.i % 2 = 0;

INSERT INTO notification_settings (
    member_id, keyword_surge_enabled, keyword_drop_enabled,
    new_trend_enabled, trend_turning_point_enabled
)
SELECT g.i, true, true, true, true
FROM generate_series(1, 10000) AS g(i);

\echo '06 완료: members · member_domains · notification_settings'
