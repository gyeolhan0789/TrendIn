층 3 — compose 를 띄우고 실제 경로를 한 번 훑는 테스트 (09 §4).

시나리오 목록은 [09 §4](../../docs/09-dev-and-test.md) 에 있다. 아직 비어 있다 —
`ingest` 가 실제로 무언가 하기 전에는 확인할 것이 없다.

## 서비스 스키마는 백엔드의 것을 그대로 쓴다

로컬에서 `contents` · `keywords` 같은 서비스 테이블이 필요하면 백엔드의 Flyway 마이그레이션을
적용한다.

```sh
docker exec -i <postgres> psql -U trendin -d <db> -v ON_ERROR_STOP=1 \
  < backend/src/main/resources/db/migration/V1__baseline.sql
```

**사본을 따로 두지 않는다.** 예전에는 엔티티를 보고 옮겨 적은 `service-schema-local.sql` 을
여기에 두었는데, 그 사본이 정본과 갈린 줄 모르는 채로 로컬 검증이 통과했다 — 2026-09-15 에
`trends.trend_types` 가 사본에서는 `trend_type[]`, baseline 에서는 `varchar(255)[]` 라
`aggregate` 가 서버에서만 죽는 상태였다. 정본이 저장소 안에 있는 지금은 사본을 유지할 이유가
없다.

운영 스키마와 맞는지 보려면 검증용 DB 를 따로 만들어 거기에 적용한다. 옛 로컬 DB 는 제약을
손으로 더해 둔 상태라 실제보다 관대하다.
