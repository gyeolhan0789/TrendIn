# 인프라 구성

TrendIn 서비스는 EC2에서 Nginx와 Docker Compose를 중심으로 운영한다. Nginx가 외부 요청과 Frontend 정적 파일을 처리하고, Backend와 데이터 저장소는 컨테이너로 실행한다. Jenkins는 GitLab 이벤트를 기반으로 Frontend와 Backend의 CI/CD를 수행한다.

## 전체 구성

```text
Client
  └─ Nginx (:80)
      ├─ /, SPA 경로 ──────────> Frontend 정적 파일
      ├─ /api, 기존 API 경로 ──> Backend (:8080)
      │                           ├─ PostgreSQL (:5432)
      │                           └─ Redis (:6379)
      └─ /grafana/ ────────────> Grafana (127.0.0.1:3000)

GitLab ── webhook ──> Jenkins ──> CI / CD

Grafana (:3000) ──> Prometheus (:9090)
                         ├─ node_exporter ──> EC2 시스템 메트릭
                         ├─ cAdvisor ───────> Docker 컨테이너 메트릭
                         └─ Data EC2 StatsD exporter <── Airflow / Spark Task 메트릭
```

| 구성 요소 | 역할 |
| --- | --- |
| Nginx | Frontend 정적 파일 제공, SPA 라우팅, Backend API 리버스 프록시 |
| Backend | Spring Boot API 서버 |
| PostgreSQL | 서비스 데이터와 파이프라인 적재 데이터 저장 |
| Redis | 인증용 리프레시 토큰 저장 |
| Prometheus | 모니터링 대상의 메트릭 수집 및 저장 |
| Grafana | Prometheus 메트릭 조회 및 시각화 기반 제공 |
| node_exporter | EC2의 CPU, 메모리, 디스크, 네트워크 메트릭 제공 |
| cAdvisor | Docker 컨테이너별 CPU, 메모리, 네트워크, 파일시스템 메트릭 제공 |
| StatsD exporter | Airflow DAG/Task 메트릭을 Prometheus 형식으로 변환 |
| Jenkins | GitLab 변경 사항에 대한 Frontend/Backend 빌드와 배포 자동화 |

## Docker Compose

`infra/compose.yaml`은 기존 서비스 세 개를 `s15p21a102-shared` 네트워크로 연결한다. 모니터링은 `infra/compose.monitoring.yaml`의 별도 프로젝트와 `s15p21a102-monitoring` 네트워크에서 실행하므로 기존 서비스의 기동 및 Jenkins 배포에 영향을 주지 않는다.

| 서비스 | 이미지·빌드 | 주요 구성 |
| --- | --- | --- |
| `backend` | `backend/Dockerfile`로 빌드 | PostgreSQL과 Redis 연결, 호스트의 `127.0.0.1:8080`으로 공개 |
| `postgres` | `postgres:17-bookworm` | `forever102` 데이터베이스 사용, named volume에 데이터 저장 |
| `redis` | `redis:8-bookworm` | 비밀번호 인증과 AOF/RDB 영속화, named volume에 데이터 저장 |
| `prometheus` | `prom/prometheus:v3.14.0` | 설정 파일에 정의된 대상의 메트릭 수집, named volume에 시계열 데이터 저장 |
| `grafana` | `grafana/grafana:13.2.1` | provisioning으로 Prometheus Data Source 등록, named volume에 설정 저장 |
| `node_exporter` | `prom/node-exporter:v1.11.1` | 읽기 전용 host root와 host PID를 사용해 EC2 시스템 메트릭 제공 |
| `cadvisor` | `ghcr.io/google/cadvisor:v0.60.5` | Docker와 host 정보를 읽기 전용으로 마운트해 컨테이너 메트릭 제공 |

환경별 비밀번호와 Backend 설정은 Git에 포함되지 않는 `infra/.env`에서 주입하며, 필요한 항목은 `infra/.env.example`에서 확인할 수 있다. PostgreSQL은 데이터 파이프라인 연동 시 지정된 사설 IP로만 공개할 수 있다.

## Jenkins CI/CD

Frontend와 Backend는 CI와 CD Job을 각각 분리해 운영한다. CI는 `dev` 대상 Merge Request에서 실행되고, CD는 `dev` 브랜치 push에서 실행된다. 각 Job은 관련 경로가 변경된 경우에만 빌드 또는 배포를 수행하고 결과를 GitLab Commit Status로 전달한다.

| 대상 | CI | CD |
| --- | --- | --- |
| Backend | Gradle 테스트 및 빌드 | Docker 이미지 빌드 후 Backend 컨테이너 교체, 실패 시 이전 이미지로 복구 |
| Frontend | 의존성 설치 및 production build 검증 | production build 결과를 `/var/www/trendin`에 배포하고 Nginx를 통해 제공 |

Jenkins 파이프라인 파일은 다음과 같다.

- Backend CI: `infra/jenkins/Jenkinsfile.ci`
- Backend CD: `infra/jenkins/Jenkinsfile.cd`
- Frontend CI: `infra/jenkins/Jenkinsfile.frontend-ci`
- Frontend CD: `infra/jenkins/Jenkinsfile.frontend-cd`

## 주요 서비스 설정

### Nginx

Nginx는 호스트의 80 포트에서 Frontend 정적 파일을 제공한다. `/api/` 요청은 접두사를 제거해 Backend로 전달하며, 기존 API 경로도 호환성을 위해 프록시한다. `/trends`는 요청의 `Accept` 헤더에 따라 SPA 화면과 기존 API를 구분한다. `/grafana/`는 loopback의 Grafana로 프록시한다.

### PostgreSQL

PostgreSQL 17을 사용하며 데이터는 `s15p21a102-postgres-data` volume에 보관한다. Backend 스키마는 `backend/src/main/resources/db/migration`의 Flyway migration으로 관리한다.

### Redis

Redis 8을 사용하며 Backend 인증용 리프레시 토큰을 저장한다. 비밀번호는 환경변수로 주입하고, AOF와 RDB를 활성화해 데이터를 `s15p21a102-redis-data` volume에 보관한다.

### Prometheus와 Grafana

Prometheus는 자체 상태와 함께 `node_exporter:9100`, `cadvisor:8080`, 데이터 EC2의 StatsD exporter를 15초마다 수집한다. Airflow는 DAG/Task 성공·실패와 실행 시간을 StatsD로 전송하며, Airflow Task로 실행되는 `spark_ingest`, `spark_extract`, `spark_aggregate`도 같은 지표에서 확인한다. Spark는 단기 `local[*]` 작업이므로 동적 Spark UI를 직접 수집하지 않는다. StatsD exporter의 HTTP 포트는 데이터 EC2 사설 IP에만 바인딩하고, 보안 그룹에서 서비스 EC2의 접근만 허용한다. Grafana는 기존 Prometheus Data Source를 그대로 사용한다.

데이터 EC2의 `pipeline/.env`에는 `AIRFLOW_METRICS_BIND_IP`, 서비스 EC2의 `infra/.env`에는 같은 주소를 `PIPELINE_METRICS_HOST`로 설정한다.

`infra/.env`에 Grafana 관리자 비밀번호를 설정한 뒤 저장소 루트에서 다음과 같이 실행한다.

```sh
docker compose --env-file infra/.env -f infra/compose.monitoring.yaml up -d
```

두 포트는 호스트의 loopback에만 바인딩된다. 팀원은 `http://j15a102.p.ssafy.io/grafana/`에서 Grafana에 접속한다. Prometheus는 기존처럼 외부에 공개하지 않는다.

기동 후 `docker compose --env-file infra/.env -f infra/compose.monitoring.yaml ps`로 상태를 확인한다. Prometheus의 **Status > Targets**에는 `prometheus`, `node_exporter`, `cadvisor`, `airflow`가 표시되며, Grafana Explore에서 관련 메트릭을 조회할 수 있다.

## 주요 설정 파일

```text
infra/
├── compose.yaml                         # Backend, PostgreSQL, Redis 구성
├── compose.monitoring.yaml              # Prometheus, Grafana 구성
├── .env.example                         # 인프라 환경변수 예시
├── jenkins/
│   ├── Jenkinsfile.ci                   # Backend CI
│   ├── Jenkinsfile.cd                   # Backend CD
│   ├── Jenkinsfile.frontend-ci          # Frontend CI
│   └── Jenkinsfile.frontend-cd          # Frontend CD
├── nginx/
│   └── trendin.conf                     # 정적 파일 및 API 라우팅
├── prometheus/
│   └── prometheus.yml                   # 수집 주기 및 대상
├── grafana/
│   └── provisioning/datasources/
│       └── prometheus.yml               # Prometheus Data Source
└── redis/
    └── redis.conf                       # Redis 영속화 및 메모리 정책
```

- Backend 이미지: `backend/Dockerfile`
- Backend DB migration: `backend/src/main/resources/db/migration/`
- Frontend 빌드 설정: `frontend/package.json`, `frontend/vite.config.ts`
