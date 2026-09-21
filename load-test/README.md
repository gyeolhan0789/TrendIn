# 부하테스트

운영 컨테이너를 건드리지 않고, 운영과 **같은 이미지**를 **다른 데이터베이스**로 띄워 측정한다.

```text
                     ┌─ backend (운영)      :8080 ─┐
                     │                              ├─ postgres ─┬─ forever102   (운영)
   Prometheus ──긁음─┤                              │            └─ trendin_test (부하테스트)
                     │                              │
                     └─ backend-loadtest    :8081 ─┘
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

### 2. 스택 올리기

```bash
cd ~/S15P21A102/load-test
docker compose --env-file ../infra/.env -f compose.loadtest.yaml up -d
```

빈 데이터베이스이므로 Flyway 가 기동하면서 `V1` 부터 전부 적용한다. 첫 기동은
스키마를 만드느라 조금 오래 걸린다.

### 3. 확인

```bash
# 떴나
curl -s http://127.0.0.1:8081/actuator/health

# 스키마가 다 들어갔나 (마이그레이션 수만큼 나와야 한다)
cd ../infra && docker compose --env-file .env -f compose.yaml exec postgres \
  psql -U ssafy -d trendin_test -c 'SELECT count(*) FROM flyway_schema_history;'

# 운영 DB 를 잘못 보고 있지 않나 — 반드시 0 이어야 한다
docker compose --env-file .env -f compose.yaml exec postgres \
  psql -U ssafy -d trendin_test -c 'SELECT count(*) FROM members;'
```

마지막 쿼리가 **0 이 아니면 운영 데이터베이스를 보고 있는 것**이다. 즉시 멈추고
`DEV_POSTGRES_URL` 을 확인한다.

### 4. Prometheus 확인

`infra/prometheus/prometheus.yml` 에 `backend-loadtest` job 이 있다. 스택을 올린 뒤
타깃이 `up` 으로 바뀌는지 본다.

```bash
curl -s 'localhost:9090/api/v1/label/job/values'
```

## 내리기

```bash
cd ~/S15P21A102/load-test
docker compose --env-file ../infra/.env -f compose.loadtest.yaml down
```

`redis-loadtest` 는 볼륨이 없어 함께 사라진다. 데이터베이스는 남는다.

## 완전히 지우기 (Phase 6)

```bash
docker compose --env-file ../infra/.env -f compose.loadtest.yaml down
cd ../infra && docker compose --env-file .env -f compose.yaml exec postgres \
  psql -U ssafy -d postgres -c 'DROP DATABASE trendin_test;'
df -h   # 디스크가 실제로 회수됐는지 확인한다
```

## 주의

**운영 이미지가 바뀌면 이 컨테이너도 다시 만들어야 한다.** `BACKEND_IMAGE` 는 배포
때마다 갱신되는데, 이미 떠 있는 컨테이너는 옛 이미지를 계속 쓴다. 코드를 고치고
재측정할 때는 `up -d --force-recreate backend-loadtest` 로 올린다.

**8081 포트가 비어 있어야 한다.** 쓰고 있으면 `LOADTEST_BACKEND_PORT` 로 바꾼다.
