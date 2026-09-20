-- 처리 이력의 run_id 를 옛 행에 채운다 (S15P21A102-341). **한 번만, 배포 직후에** 돌린다.
--
-- 2026-09-20 이전의 ingest 는 처리 이력의 run_id 를 비워 두었다 (Kafka 시절 생산자 실행 번호
-- 자리였고 장부 뷰에는 그 값이 없다). 이제 extract 는 "ingest 이력에 run_id 로 기록된 실행" 만
-- curated 에서 집으므로, 이 칸이 비어 있으면 어떤 실행도 대상이 되지 않는다 (jobs/extract.py
-- 의 _ingested_run_ids 가 오류 로그를 남긴다).
--
-- 값의 출처는 contents.body_object_key 다 — 그 기사가 마지막으로 정제된 실행의 파티션 경로를
-- 들고 있다. 장부 뷰(collected_article_event)가 event_id 와 url 을 같이 내므로 그것으로 잇는다.
-- 정제 필터에 걸려 contents 에 없는 기사는 NULL 로 남는다. 실행 하나에 행이 하나만 있어도
-- extract 는 그 실행을 알므로 충분하다.
--
-- 실행 (서비스 EC2 의 postgres 컨테이너, 소유자 계정):
--   docker exec -i s15p21a102-infra-postgres-1 psql -U ssafy -d forever102 < backfill-ledger-run-id.sql
-- 로컬은 trendin DB 에 같은 파일을 돌린다. 멱등하다 — run_id 가 이미 있는 행은 건드리지 않는다.

BEGIN;

UPDATE pl_processing_ledger AS l
   SET run_id = substring(c.body_object_key FROM 'ingest_run_id=([^/]+)')
  FROM collected_article_event AS e
  JOIN contents AS c ON c.url = e.url
 WHERE l.job = 'ingest'
   AND l.run_id IS NULL
   AND l.event_id = e.event_id
   AND c.body_object_key IS NOT NULL;

-- 확인: 실행별 행 수. 값이 curated 의 파티션 목록과 맞는지 눈으로 본다.
SELECT run_id, count(*) AS rows_
  FROM pl_processing_ledger
 WHERE job = 'ingest'
 GROUP BY run_id
 ORDER BY run_id NULLS FIRST;

COMMIT;
