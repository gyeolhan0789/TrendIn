-- notifications 를 member_id 로 찾는 조회에 인덱스를 준다.
--
-- V1 이 만든 인덱스는 PK(id) 와 dedup_key 유니크 둘뿐이다. PostgreSQL 은 외래키에
-- 인덱스를 만들어 주지 않으므로 fk_notifications_member 는 조회에 쓰이지 않는다.
-- 그런데 NotificationRepository 의 조회는 전부 member_id 로 시작한다.
--
-- 부하테스트 실측 (2026-09-21, 회원 1만 · 알림 68만 행, 10 RPS 고정):
--
--   GET /members/me/notifications               p95  900.5ms
--   GET /members/me/notifications/unread-count  p95  608.1ms
--   GET /members/me/saved-trends                p95   12.5ms   ← 인덱스가 있는 비교군
--
-- 같은 헤비 회원의 같은 개인화 조회인데 72배다. 큐 대기가 없는 도착률에서 잰 값이라
-- 저 900ms 는 전부 서버가 실제로 일한 시간이다.

-- 목록 조회. 필터와 정렬을 한 인덱스로 받는다.
--
--   where member_id = ? order by created_at desc, id desc limit 20
--
-- **정렬 순서까지 맞추는 것이 핵심이다.** (member_id) 단독 인덱스로도 풀스캔은
-- 면하지만, 그 회원의 행을 전부 꺼내 정렬한 뒤 20개만 남기게 된다. 헤비 회원은
-- 알림이 최대 1,500건이다. 순서가 맞으면 플래너가 인덱스를 20행만 걷고 멈춘다
-- (Sort 노드가 사라진다).
--
-- id 를 뒤에 둔 이유는 created_at 이 같은 행의 순서를 고정하기 위해서다. 없으면
-- 같은 시각의 알림이 페이지를 넘길 때마다 순서가 달라져 행이 중복·누락된다.
--
-- 이 인덱스가 페이지네이션의 count(*) 도 같이 받는다. Page 반환 타입이
-- `select count(*) ... where member_id = ?` 를 한 번 더 쏘는데, 선두 컬럼만 쓰므로
-- 인덱스만 읽고 끝난다.
CREATE INDEX idx_notifications_member_created
    ON notifications (member_id, created_at DESC, id DESC);

-- 안 읽은 개수. 헤더에 늘 붙어 있어 화면마다 호출된다.
--
--   where member_id = ? and is_read = false
--
-- **부분 인덱스로 둔다.** 알림의 70% 는 읽은 상태이므로 (member_id, is_read) 보다
-- 3배 작고, 엔트리가 전부 "안 읽음" 이라 count 가 인덱스만 읽고 끝난다. 읽음 처리로
-- is_read 가 true 가 되면 그 엔트리는 인덱스에서 빠져 표가 더 줄어든다.
--
-- ⚠️ **부분 인덱스는 조건이 SQL 에 리터럴로 박혀야 쓰인다.** 플래너가 질의의 조건이
-- 인덱스의 조건을 함의함을 계획 시점에 증명해야 하므로, Hibernate 가 `is_read = ?` 로
-- 바인드 파라미터를 내보내면 이 인덱스를 못 쓴다. Spring Data 의 `...ReadFalse` 파생
-- 질의는 JPQL 에 불리언 리터럴을 넣으므로 `is_read = false` 로 나올 것이 기대되지만,
-- **EXPLAIN 으로 확인해야 한다** (아래).
--
-- 못 쓰더라도 성능이 되돌아가지는 않는다. 위의 idx_notifications_member_created 가
-- `member_id = ?` 를 받고 is_read 를 필터로 처리하므로, 68만 행 풀스캔이 그 회원의
-- 1,500행 인덱스 스캔으로 줄어든다. 파라미터로 나오는 것이 확인되면 이 인덱스를
-- (member_id, is_read) 로 바꾼다.
--
--   EXPLAIN (ANALYZE, BUFFERS)
--   SELECT count(*) FROM notifications WHERE member_id = <헤비회원> AND is_read = false;
--
--   → "Index Only Scan using idx_notifications_member_unread" 가 보이면 의도대로다.
CREATE INDEX idx_notifications_member_unread
    ON notifications (member_id) WHERE is_read = false;
