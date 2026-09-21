# 부하테스트

운영 컨테이너를 건드리지 않고, 운영과 **같은 이미지**를 **다른 데이터베이스**로 띄워 측정한다.

```text
                     ┌─ backend (운영)      :8080 ─┐
                     │                              ├─ postgres ─┬─ forever102   (운영)
   Prometheus ──긁음─┤                              │            └─ trendin_test (부하테스트)
                     │                              │
                     └─ backend-loadtest   :18080 ─┘
                            └─ redis-loadtest (별도. 운영 Redis 와 섞지 않는다)
```

측정 대상은 `backend-loadtest` 하나다. 운영 `backend` 는 비교용으로 같은 화면에 남겨 둔다.
Grafana 대시보드 **TrendIn 부하테스트** 상단의 `대상` 드롭다운으로 둘을 오간다.

## 왜 이렇게 나눴나

**데이터베이스를 나눈 이유.** 더미 데이터를 수백만 행 붓는다. 운영 스키마에 부으면
되돌릴 수 없다.

**인스턴스는 나누지 못했다.** EC2 가 한 대뿐이라 `trendin_test` 는 운영과 같은
PostgreSQL 안에 있다. 버퍼 풀·WAL·디스크는 여전히 공유하므로, **더미 데이터를 붓는
동안과 부하를 거는 동안 운영 응답이 느려질 수 있다.** 발표·데모·팀원 QA 가 없는
시간대에 돌린다.

**Redis 를 나눈 이유.** 운영 Redis 를 같이 쓰면 리프레시 토큰이 한 공간에 섞인다.
부하테스트가 만든 수천 개의 토큰이 운영 사용자의 것을 밀어내면 실제 사용자가
로그아웃된다.

**알림 배치를 껐다.** 측정 중 스케줄러가 깨어나 커넥션과 CPU 를 먹으면 수치가 흔들린다.
`TREND_NOTIFICATION_CRON: "-"` 로 끈다.

## 전제

`infra/compose.yaml` 이 떠 있어야 한다. `postgres` 와 `s15p21a102-shared` 네트워크를
빌려 쓴다.

## 띄우기

### 1. 테스트 데이터베이스 만들기 (최초 1회)

```bash
cd ~/S15P21A102/infra
docker compose --env-file .env -f compose.yaml exec postgres \
  psql -U ssafy -d postgres -c 'CREATE DATABASE trendin_test OWNER ssafy;'
```

이름은 소문자다. PostgreSQL 은 큰따옴표 없는 식별자를 소문자로 접으므로
`TrendIn_test` 로 만들면 이후 모든 명령에서 따옴표를 쳐야 한다.

### 2. 스키마 옮기기 (최초 1회)

운영 스키마를 그대로 복사한다. Flyway 로 새로 만들지 않는다. 이 애플리케이션에서
Flyway 가 실제로 돌지 않고 있고(아래 "알려진 문제"), 부하테스트는 **운영이 실제로
쓰는 스키마**를 재야 의미가 있기 때문이다.

```bash
cd ~/S15P21A102/infra
docker compose --env-file .env -f compose.yaml exec -T postgres sh -c \
  'PGPASSWORD=$POSTGRES_PASSWORD pg_dump -U ssafy --schema-only --no-owner --no-privileges forever102 \
   | PGPASSWORD=$POSTGRES_PASSWORD psql -U ssafy -d trendin_test'
```

`pl_concept_embedding` 관련 에러는 무시해도 된다. pgvector 확장을 쓰는 파이프라인
테이블이고 백엔드 엔티티에 없다. 빠진 것이 그 하나뿐인지만 확인한다 — 차이가 1 이어야 한다.

```bash
for db in forever102 trendin_test; do
  printf "%-14s " "$db"
  docker compose --env-file .env -f compose.yaml exec -T postgres \
    psql -U ssafy -d $db -tAc \
    "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';"
done
```

### 3. 스택 올리기

```bash
cd ~/S15P21A102/load-test
./up.sh
```

**`docker compose` 를 직접 부르지 않는다.** `up.sh` 는 운영 컨테이너에서 지금 돌고
있는 이미지를 읽어 넘긴다. `infra/.env` 의 `BACKEND_IMAGE` 는 CD 가 갱신하지 않아
최초 설정에 멈춰 있고, 그 옛 이미지로 띄우면 위에서 복사한 운영 스키마와 어긋나
기동에 실패한다.

운영을 새로 배포한 뒤 다시 잴 때는 `./up.sh --recreate` 로 올린다.

### 4. 확인

```bash
# 떴나 — 200 이어야 한다
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:18080/actuator/health

# 운영 DB 를 잘못 보고 있지 않나 — 반드시 0 이어야 한다
cd ../infra && docker compose --env-file .env -f compose.yaml exec postgres \
  psql -U ssafy -d trendin_test -c 'SELECT count(*) FROM members;'
```

마지막 쿼리가 **0 이 아니면 운영 데이터베이스를 보고 있는 것**이다. 즉시 멈추고
`DEV_POSTGRES_URL` 을 확인한다.

### 5. Prometheus 확인

`infra/prometheus/prometheus.yml` 에 `backend-loadtest` job 이 있다. 스택을 올린 뒤
타깃이 `up` 으로 바뀌는지 본다.

```bash
curl -s 'localhost:9090/api/v1/label/job/values'
```

## 내리기

```bash
cd ~/S15P21A102/load-test
docker compose -p s15p21a102-loadtest down
```

`redis-loadtest` 는 볼륨이 없어 함께 사라진다. 데이터베이스는 남는다.

## 완전히 지우기 (Phase 6)

```bash
docker compose -p s15p21a102-loadtest down
cd ../infra && docker compose --env-file .env -f compose.yaml exec postgres \
  psql -U ssafy -d postgres -c 'DROP DATABASE trendin_test;'
df -h   # 디스크가 실제로 회수됐는지 확인한다
```

## 주의


**18080 포트가 비어 있어야 한다.** 쓰고 있으면 `LOADTEST_BACKEND_PORT` 로 바꾼다.
8081 은 이 서버에서 Jenkins 가 쓰고 있어 피했다.

**운영을 새로 배포했으면 이 컨테이너도 다시 만든다.** 이미 떠 있는 컨테이너는 옛
이미지를 계속 쓴다. `./up.sh --recreate` 로 올린다.

## 알려진 문제 — Flyway 가 돌지 않는다

`trendin_test` 를 빈 데이터베이스로 두고 백엔드를 띄웠을 때, Flyway 가 마이그레이션을
하나도 적용하지 않았다. 기동 로그에 Flyway 줄이 한 줄도 찍히지 않는다.
`application-dev.yml` 에 `flyway.enabled: true` 가 있고 같은 파일의
`${DEV_POSTGRES_URL}` 은 정상적으로 풀리므로, 프로필이 안 읽힌 것은 아니다.

운영은 스키마가 이미 있어 아무도 눈치채지 못했을 뿐, 같은 이미지이므로 운영에서도
돌지 않고 있을 가능성이 높다. **그렇다면 앞으로 마이그레이션을 추가해도 배포로는
반영되지 않는다.** 부하테스트에서 찾은 인덱스를 마이그레이션으로 넣을 계획이라면
그 전에 확인해야 한다.

```bash
cd ~/S15P21A102/infra
docker compose --env-file .env -f compose.yaml logs backend | grep -i flyway | head
docker compose --env-file .env -f compose.yaml exec postgres \
  psql -U ssafy -d forever102 -c \
  'SELECT version, description, installed_on, success FROM flyway_schema_history ORDER BY installed_rank DESC LIMIT 5;'
```
