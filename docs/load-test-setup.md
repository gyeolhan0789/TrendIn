# 부하테스트 환경 구축 (Phase 0 · 1)

부하를 걸기 전에 두 가지를 먼저 만들었다. **무엇이 느린지 볼 수 있는 계측**(Phase 0)과,
**운영을 망가뜨리지 않고 부하를 받을 대상**(Phase 1)이다.

```
                     ┌─ backend (운영)      :8080 ─┐
                     │                              ├─ postgres ─┬─ forever102   (운영)
   Prometheus ──긁음─┤                              │            └─ trendin_test (부하테스트)
                     │                              │
                     └─ backend-loadtest   :18080 ─┘
                            └─ redis-loadtest (별도. 운영 Redis 와 섞지 않는다)
                                        │
                                   Grafana "TrendIn 부하테스트"
                                   상단 `대상` 드롭다운으로 둘을 오간다
```

부하 시나리오와 더미 데이터는 다음 단계(Phase 2 이후)이고, 이 문서는 그 밑작업까지만 다룬다.
운영 절차는 [`load-test/README.md`](../load-test/README.md) 에 따로 있다.

## 왜 계측이 먼저인가

부하테스트는 "느리다"까지만 알려준다. 원인을 짚으려면 **힙과 GC**, **HikariCP 의 대기 커넥션**,
**엔드포인트별 응답 분포**를 같이 봐야 한다. 착수 시점의 모니터링은 node_exporter 와 cAdvisor
뿐이어서 컨테이너 CPU·메모리밖에 없었다. 그 상태로 부하를 걸면 숫자는 나오지만 개선으로
이어지지 않는다.

---

## Phase 0 — 계측 붙이기

### 0-1. 코드 변경

| 파일 | 무엇 |
| --- | --- |
| `backend/build.gradle` | `spring-boot-starter-actuator` · `micrometer-registry-prometheus` |
| `backend/src/main/resources/application.yml` | `health,prometheus` 만 노출, `http.server.requests` histogram |
| `backend/.../global/config/SecurityConfig.java` | 위 두 엔드포인트만 `permitAll` |
| `infra/prometheus/prometheus.yml` | `backend:8080` 스크랩 잡 |
| `infra/compose.monitoring.yaml` | remote write receiver, prometheus 를 `shared` 에 연결 |
| `infra/compose.yaml` | postgres 에 `pg_stat_statements` |
| `infra/nginx/trendin.conf` | `/api/actuator` 를 404 로 막음 |

**histogram 을 켜는 것이 핵심이다.** `management.metrics.distribution.percentiles-histogram`
이 없으면 `http.server.requests` 는 count·sum·max 만 남아 **p95·p99 를 계산할 수 없다.**
부하테스트 결과를 백분위로 말하려면 이 설정이 있어야 한다.

**actuator 는 외부에 열면 안 된다.** nginx 가 `/api/` 를 백엔드로 그대로 프록시하므로
`/api/actuator/prometheus` 가 인터넷에 노출된다. JVM 내부 상태와 전체 URI 목록이 함께
드러난다. Prometheus 는 컨테이너 네트워크로 직접 긁으니 nginx 를 거칠 이유가 없어 404 로 막았다.
`^~` 는 `/api/` 보다 먼저 매칭된다.

```nginx
location ^~ /api/actuator {
    return 404;
}
```

### 0-2. 서버 반영

**CD 는 `backend` 서비스만 재생성한다.**

```groovy
docker compose ... up --detach --no-deps --force-recreate backend
```

그래서 postgres · monitoring · nginx 변경은 **자동으로 반영되지 않는다.** 사람이 직접 해야 한다.

순서가 중요하다. **nginx 를 머지보다 먼저** 해야 actuator 가 배포되는 순간의 노출 창이 생기지 않는다.

```bash
# 1) nginx — 머지 전에
#    실제 파일은 nginx -T | grep "configuration file" 로 찾는다.
#    이 서버에서는 /etc/nginx/sites-enabled/trendin 이었다.
sudo nginx -t && sudo systemctl reload nginx

# 2) 머지 → CD 가 백엔드 재배포

# 3) 서버에서 pull
cd ~/S15P21A102 && git pull origin dev

# 4) postgres 재생성 — DB 가 10~30초 끊긴다
cd infra
docker compose --env-file .env -f compose.yaml up -d --no-deps --force-recreate postgres
docker compose --env-file .env -f compose.yaml exec postgres \
  psql -U ssafy -d forever102 -c 'CREATE EXTENSION IF NOT EXISTS pg_stat_statements;'

# 5) 모니터링 재생성
docker compose --env-file .env -f compose.monitoring.yaml up -d
```

`shared_preload_libraries` 는 **기동 시점에만** 읽히므로 4번은 재시작 말고는 방법이 없다.
발표·데모·QA 가 없는 시간대에 한다. 2번 배포로 어차피 한 번 끊기므로 같이 몰아서 하면
중단이 한 번으로 끝난다.

### 0-3. Prometheus 가 백엔드에 닿게 하기

Prometheus 는 `s15p21a102-monitoring` 에만 있었고 백엔드는 `s15p21a102-shared` 에 있어
이름으로 부를 수 없었다. 백엔드 포트는 호스트 루프백에만 공개되므로 host-gateway 로도
우회할 수 없다. **prometheus 를 `shared` 에 함께 붙였다.**

```yaml
networks:
  monitoring:
    name: s15p21a102-monitoring
    driver: bridge
  shared:
    name: s15p21a102-shared
    external: true
```

그 대가로 의존성이 생겼다. **서버를 재부팅하면 `compose.yaml` 을 `compose.monitoring.yaml`
보다 먼저 띄워야 한다.** 네트워크가 없으면 모니터링 스택이 기동에 실패한다.

### 0-4. Grafana 대시보드

커뮤니티 대시보드 **4701(JVM Micrometer)** 을 import 했더니 패널이 전부 No Data 였다.
Micrometer 가 Prometheus Java client 1.x 로 넘어오기 전 기준이라 지표 이름이 어긋난다.

그래서 필요한 패널만 직접 만들어 `infra/grafana/provisioning/dashboards/` 에 두었다.
`provisioning` 디렉터리는 compose 가 이미 마운트하고 있어 **compose 변경 없이** 읽힌다.
손으로 import 한 것은 그 서버의 Grafana 볼륨에만 남아, 컨테이너를 다시 만들거나 팀원이
각자 띄우면 사라진다.

| 패널 | 무엇을 보나 |
| --- | --- |
| 응답시간 p50/p95/p99 | p99 가 벌어지면 꼬리 지연 |
| **엔드포인트별 p95** | 느린 API 를 고른다. 병목 분석의 출발점 |
| 처리량 (RPS) | 더 안 오르면 포화점 |
| 에러율 | 튀는 지점이 한계 |
| **HikariCP 커넥션 풀** | 대기(pending) 가 0 을 넘으면 풀이 말랐다 |
| 커넥션 획득 대기시간 | 위와 같이 오른다 |
| JVM 힙 · GC · CPU | 원인 구분 |

`job` 을 변수로 두어 운영과 부하테스트 대상을 한 화면에서 오간다.

G1 GC 는 Eden·Survivor 의 `jvm_memory_max_bytes` 를 `-1` 로 보고한다. 그대로 합치면 힙
최대치가 어긋나므로 양수만 더한다.

### 0-5. 확인

```bash
# 내부는 열리고
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/actuator/prometheus   # 200
# 외부는 막혔는지
curl -s -o /dev/null -w '%{http_code}\n' https://j15a102.p.ssafy.io/api/actuator/prometheus  # 404

# Prometheus 가 긁고 있나
curl -s 'localhost:9090/api/v1/label/job/values'

# pg_stat_statements 가 사나
docker compose --env-file .env -f compose.yaml exec postgres \
  psql -U ssafy -d forever102 -c 'SELECT count(*) FROM pg_stat_statements;'
```

Grafana 의 **TrendIn** 폴더에서 힙과 DB 커넥션 그래프가 보이면 Phase 0 이 끝난 것이다.

---

## Phase 1 — 격리 환경

운영 컨테이너를 건드리지 않고, 운영과 **같은 이미지**를 **다른 데이터베이스**로 띄운다.

### 왜 이렇게 나눴나

**데이터베이스를 나눈다.** 더미 데이터를 수백만 행 붓는다. 운영 스키마에 부으면 되돌릴 수 없다.

**인스턴스는 나누지 못했다.** EC2 가 한 대라 `trendin_test` 는 운영과 같은 PostgreSQL 안에
있다. 버퍼 풀·WAL·디스크는 여전히 공유하므로 **더미 적재와 부하 인가 중 운영이 느려질 수 있다.**

**Redis 는 나눈다.** 같이 쓰면 부하테스트가 만든 수천 개의 리프레시 토큰이 운영 사용자의 것과
한 공간에 섞여, 실제 사용자가 로그아웃된다.

**알림 배치는 끈다.** 측정 중 스케줄러가 커넥션과 CPU 를 먹으면 수치가 흔들린다.
`TREND_NOTIFICATION_CRON: "-"` 이 Spring 이 스케줄을 끄는 값이다.

**포트는 루프백에만 연다.** nginx 를 거치지 않으므로 대상이 외부로 새지 않는다.

### 1-1. 실행 절차

```bash
# 데이터베이스 (최초 1회) — 이름은 소문자로
cd ~/S15P21A102/infra
docker compose --env-file .env -f compose.yaml exec postgres \
  psql -U ssafy -d postgres -c 'CREATE DATABASE trendin_test OWNER ssafy;'

# 스키마 + 마이그레이션 이력
docker compose --env-file .env -f compose.yaml exec -T postgres sh -c \
  'PGPASSWORD=$POSTGRES_PASSWORD pg_dump -U ssafy --schema-only --no-owner --no-privileges forever102 \
   | PGPASSWORD=$POSTGRES_PASSWORD psql -U ssafy -d trendin_test'
docker compose --env-file .env -f compose.yaml exec -T postgres sh -c \
  'PGPASSWORD=$POSTGRES_PASSWORD pg_dump -U ssafy --data-only --table=flyway_schema_history forever102 \
   | PGPASSWORD=$POSTGRES_PASSWORD psql -U ssafy -d trendin_test'

# 스택
cd ../load-test && ./up.sh
```

**빈 DB 에 Flyway 로 만들지 않고 운영에서 떠 왔다.** 마이그레이션에 없는 파이프라인 테이블이
빠지면 운영과 다른 모습이 되고, 부하테스트는 운영이 실제로 쓰는 스키마를 재야 의미가 있다.

**이력 행을 함께 옮기는 것이 중요하다.** `--schema-only` 는 `flyway_schema_history` 를 빈
테이블로 만든다. 이력이 없으면 Flyway 가 아무것도 적용되지 않은 것으로 보고 V1 부터 다시
돌리다 `type "metric_period" already exists` 로 죽는다.

**`docker compose` 를 직접 부르지 않는다.** 아래 "이미지" 항목을 본다.

### 1-2. 확인

```bash
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:18080/actuator/health   # 200

# 운영 DB 를 잘못 보고 있지 않은지 — 반드시 0
docker compose --env-file .env -f compose.yaml exec postgres \
  psql -U ssafy -d trendin_test -c 'SELECT count(*) FROM members;'
```

마지막이 0 이 아니면 운영 데이터베이스를 보고 있는 것이다. 즉시 멈추고 `DEV_POSTGRES_URL` 을 본다.

---

## 겪은 문제와 원인

같은 곳에서 또 막히지 않도록 남긴다.

| 증상 | 원인 | 대응 |
| --- | --- | --- |
| nginx 설정 파일이 없다 | 경로는 `conf.d/` 가 아니라 `sites-enabled/trendin` 이었다 | `nginx -T \| grep "configuration file"` 로 찾는다 |
| postgres·monitoring 변경이 배포돼도 반영 안 됨 | CD 가 `--no-deps ... backend` 로 백엔드만 재생성한다 | 서버에서 직접 재생성 |
| Grafana 대시보드가 전부 No Data | 4701 이 구 Micrometer 기준 | 지표 이름을 실측 대조해 직접 제작, provisioning 으로 심음 |
| 포트 바인드 실패 (`8081 in use`) | Jenkins 가 8081 을 쓰고 있다 | 기본값을 18080 으로 |
| `missing column [description] in table [trends]` | `infra/.env` 의 `BACKEND_IMAGE` 가 몇 주 전 태그. V7 이 그 컬럼을 지우기 전 이미지였다 | 아래 "이미지" |
| `type "metric_period" already exists` | `--schema-only` 가 Flyway 이력 행을 옮기지 않았다 | `--data-only --table=flyway_schema_history` 추가 |
| `relation "public.pl_concept_embedding" does not exist` | pgvector 를 쓰는 파이프라인 테이블. 확장이 새 DB 에 없다 | 무시해도 된다. 백엔드 엔티티에 없다 |

### 이미지 — 가장 오래 걸린 문제

CD 는 이미지 태그를 **셸 환경변수로만** 넘기고 `infra/.env` 에 써넣지 않는다.

```groovy
BACKEND_IMAGE="$RELEASE_IMAGE" docker compose ... up --detach ... backend
```

그래서 `.env` 의 `BACKEND_IMAGE` 는 최초 설정에서 멈춰 있다. 그 값을 읽어 띄우면 몇 주 전
코드를 재게 된다. **"운영과 같은 이미지를 잰다"는 전제가 조용히 깨진다.** 스키마는 운영에서
떠오는데 코드만 과거라 기동에 실패해서야 드러났다.

[`load-test/up.sh`](../load-test/up.sh) 가 운영 컨테이너를 `docker inspect` 해서 실제
이미지를 읽어 넘긴다. 변수 이름도 `LOADTEST_BACKEND_IMAGE` 로 갈랐다. `BACKEND_IMAGE` 는
`.env` 가 항상 값을 주므로 `:?` 가드가 걸리지 않아, 직접 `docker compose` 를 부르면 낡은
이미지로 **조용히** 뜬다. 이름을 나누면 그 호출이 에러로 멈춘다.

같은 이유로 `down` 과 `logs` 는 `-p s15p21a102-loadtest` 로 프로젝트만 지목한다. `-f` 로
부르면 compose 파일을 파싱하다 같은 가드에 걸린다.

**운영을 새로 배포하면 `./up.sh --recreate` 로 다시 만든다.** 이미 떠 있는 컨테이너는 옛
이미지를 계속 쓴다.

---

## 다음

| Phase | 무엇 |
| --- | --- |
| 2 | 더미 데이터. 분포를 비균등하게, 넣고 나서 `ANALYZE` |
| 3 | 엔드포인트별 베이스라인. VU 마다 로그인하지 말고 토큰을 미리 발급 |
| 4 | `pg_stat_statements` 로 병목을 짚고 인덱스를 마이그레이션으로 추가 |
| 5 | 사용자 여정 시나리오 |
| 6 | `DROP DATABASE trendin_test`, 디스크 회수 확인 |

Phase 2 전에 **`df -h`** 로 여유를 본다. 인덱스까지 3~5GB 를 쓰고, 운영 DB 와 같은 볼륨이라
꽉 차면 운영이 멈춘다.
