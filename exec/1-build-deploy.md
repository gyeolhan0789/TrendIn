# 1. 빌드 및 배포

```sh
git clone https://lab.ssafy.com/s15-bigdata-dist-sub1/S15P21A102.git
cd S15P21A102
```

---

## 1) 사용 제품 종류와 버전

| 구분 | 제품 | 버전 | 설정 위치 |
| --- | --- | --- | --- |
| **IDE (백엔드)** | IntelliJ IDEA | **2026.2.1** | |
| **IDE (프론트·파이프라인)** | Visual Studio Code | **1.138.0** | |
| **JVM** | Eclipse Temurin JDK | **25** | `backend/build.gradle`, `backend/Dockerfile` |
| **빌드 도구** | Gradle Wrapper | **9.7.1** | `backend/gradle/wrapper/gradle-wrapper.properties` |
| **WAS** | Spring Boot 내장 Tomcat | Spring Boot **4.1.1** 번들 | `backend/build.gradle` |
| **웹서버** | Nginx | 1.24 이상 | `infra/nginx/trendin.conf` |
| **DB** | PostgreSQL (pgvector) | **17** / pgvector 0.8.6 | `infra/compose.yaml` |
| **캐시** | Redis | **8** | `infra/compose.yaml` |
| **객체 저장소** | MinIO | latest | `datastore/compose.yaml` |
| **프론트 런타임** | Node.js | **20.19 이상** 또는 **22.12 이상** | Vite 7 요구 사항 |
| **프론트 빌드** | Vite **7.1** · TypeScript **5.9** · React **19.2** | | `frontend/package.json` |
| **파이프라인** | Python **3.12** · Apache Airflow **3.3.1** · PySpark | | `pipeline/pyproject.toml`, `pipeline/Dockerfile` |
| **컨테이너** | Docker Engine + Compose v2 | 24 이상 | |
| **인증서** | Let's Encrypt (certbot) | — | `/etc/letsencrypt/live/j15a102.p.ssafy.io/` |

**WAS 를 따로 설치하지 않습니다.** Spring Boot 내장 Tomcat 을 쓰는 실행 가능 JAR 이고 `java -jar` 로 기동합니다.

**Nginx 는 컨테이너가 아니라 호스트에 설치합니다.** 인증서 갱신과 정적 파일 경로(`/var/www/trendin`)가 호스트 기준입니다.

### 주요 설정 값

| 항목 | 값 |
| --- | --- |
| 백엔드 포트 | `8080` (호스트는 `127.0.0.1` 에만 바인딩) |
| DB 포트 / 이름 | `5432` / `forever102` |
| Redis 포트 | `6379` |
| Spring 프로파일 | 운영 `dev` · 로컬 `local` |
| JPA `ddl-auto` | 운영 `validate` · 로컬 `create-drop` |
| Flyway | 운영에서만 활성 (`V1`~`V12`) |
| JWT 만료 | 액세스 15분 · 리프레시 14일 |
| 알림 배치 | 매일 `00:00` (Asia/Seoul) |
| 집계 배치 | 매일 `00:10` (KST) |

---

## 2) 빌드 시 사용되는 환경 변수

`.env.example` 을 복사해 씁니다. 실제 값이 든 `.env` 는 Git 에 올라가지 않습니다.

**`infra/.env.example` 과 `frontend/.env.example` 은 예시 값이 이미 채워져 있어, 복사만 하면 그대로 뜹니다.**

| 어디까지 띄울 때 | 필요한 파일 |
| --- | --- |
| **로컬 실행** (H2 + Redis) | `frontend/.env.local` **하나뿐** |
| PostgreSQL 로 컨테이너 기동 | 위 + `infra/.env` |
| 수집·분석 파이프라인까지 | 위 + `datastore/.env` · `pipeline/.env` |

```sh
cp frontend/.env.example   frontend/.env.local
cp infra/.env.example      infra/.env          # 전체 스택을 띄울 때만
cp datastore/.env.example  datastore/.env      # 파이프라인을 띄울 때만
cp pipeline/.env.example   pipeline/.env       # 파이프라인을 띄울 때만
```

> ⚠️ 예시 값의 비밀번호와 JWT 키는 **로컬 확인용**입니다. 운영에 올릴 때는 `POSTGRES_PASSWORD` · `REDIS_PASSWORD` · `DEV_JWT_SECRET` · `GRAFANA_ADMIN_PASSWORD` 넷을 반드시 새로 만듭니다.

### `infra/.env` — 백엔드·DB·모니터링

| 변수 | 필수 | 설명 |
| --- | :---: | --- |
| `POSTGRES_PASSWORD` | ✅ | PostgreSQL 계정 비밀번호 |
| `REDIS_PASSWORD` | ✅ | Redis 인증 비밀번호 |
| `POSTGRES_BIND_IP` | | 비우면 루프백만. 데이터 EC2 가 붙어야 하면 **이 EC2 의 사설 IP** |
| `BACKEND_IMAGE` | ✅ | 예: `s15p21a102/backend:dev` |
| `BACKEND_PORT` | ✅ | 호스트 공개 포트 |
| `DEV_POSTGRES_URL` | ✅ | `jdbc:postgresql://postgres:5432/forever102` |
| `DEV_POSTGRES_USER_NAME` | ✅ | DB 계정명 (예: `ssafy`) |
| `DEV_FLYWAY_BASELINE_ON_MIGRATE` | | 기본 `false`. Flyway 이력 없는 기존 스키마에 처음 배포할 때만 `true` |
| `DEV_REDIS_HOST` / `DEV_REDIS_PORT` | ✅ | `redis` / `6379` |
| `DEV_JWT_SECRET` | ✅ | HS256 서명 키. 32바이트 이상 난수 (`openssl rand -hex 32`) |
| `DEV_CORS_ALLOWED_ORIGINS` | ✅ | `https://j15a102.p.ssafy.io` |
| `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD` | ✅ | Grafana 초기 관리자 |
| `PROMETHEUS_PORT` / `GRAFANA_PORT` | | 기본 `9090` / `3000` |
| `PIPELINE_METRICS_HOST` | | 데이터 EC2 사설 IP |
| `GITLAB_OAUTH_CLIENT_ID` / `_SECRET` / `_REDIRECT_URI` | | 소셜 로그인. 비어도 서버는 뜨고 그 기능만 실패 |

> `✅` 변수가 비어 있으면 컴포즈가 `Set ... in infra/.env` 메시지와 함께 기동을 거부합니다.

### `frontend/.env.local` — 프론트 빌드 시점 주입

| 변수 | 필수 | 설명 |
| --- | :---: | --- |
| `VITE_API_BASE_URL` | ✅ | 운영 `https://j15a102.p.ssafy.io/api` · 로컬 `http://localhost:8080` |
| `VITE_GITLAB_OAUTH_BASE_URL` | | 기본 `https://lab.ssafy.com` |
| `VITE_GITLAB_OAUTH_CLIENT_ID` | | 백엔드와 같은 애플리케이션의 ID |
| `VITE_GITLAB_OAUTH_REDIRECT_URI` | | 비우면 현재 주소로 `/oauth/gitlab/callback` |

### `datastore/.env` — MinIO (데이터 EC2)

| 변수 | 필수 | 설명 |
| --- | :---: | --- |
| `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` | ✅ | 관리자 계정 |
| `MINIO_CRAWLER_ACCESS_KEY` / `_SECRET_KEY` | ✅ | 크롤러용 (쓰기 전용) |
| `MINIO_SPARK_ACCESS_KEY` / `_SECRET_KEY` | ✅ | Spark 용 |
| `MINIO_BIND` / `MINIO_API_PORT` / `MINIO_CONSOLE_PORT` | | 기본 `127.0.0.1` / `9000` / `9001` |
| `MINIO_BUCKET` / `MINIO_CURATED_BUCKET` | | 기본 `raw-data` / `curated` |
| `MINIO_RAW_EXPIRE_DAYS` | | 원문 보관 기간. 기본 `90` |

### `pipeline/.env` — Airflow (데이터 EC2)

| 변수 | 필수 | 설명 |
| --- | :---: | --- |
| `AIRFLOW_UID` | ✅ | `id -u` 값 |
| `AIRFLOW_DB_PASSWORD` / `APP_DB_PASSWORD` | ✅ | 메타 DB · 앱 DB 비밀번호 |
| `AIRFLOW_JWT_SECRET` | ✅ | `openssl rand -hex 32` |
| `GMS_KEY` | ✅ | **LLM 게이트웨이 키.** 없으면 AI 해설이 생성되지 않습니다 |
| `AIRFLOW_CONN_APP_DB` | ✅ | 앱 DB URI. 운영은 **서비스 EC2 의 DB** |
| `TRENDIN_MINIO_ACCESS_KEY` / `_SECRET_KEY` | ✅ | `datastore/.env` 의 `MINIO_CRAWLER_*` 와 같은 값 |
| `TRENDIN_MINIO_SPARK_ACCESS_KEY` / `_SECRET_KEY` | ✅ | `datastore/.env` 의 `MINIO_SPARK_*` 와 같은 값 |
| `SPARK_APP_DB_URL` / `_USER` / `_PASSWORD` | ✅ | `jdbc:postgresql://<서비스 EC2 사설 IP>:5432/forever102` |
| `AIRFLOW_UI_PORT` / `AIRFLOW_METRICS_BIND_IP` | | UI 포트 · StatsD 바인딩 |

---

## 3) 빌드 및 실행

### 로컬 실행

**PostgreSQL 도 DB 덤프도 필요 없습니다.** `local` 프로파일이 인메모리 H2 를 쓰고, 기동하면서
키워드·트렌드·AI 해설·시드 계정을 **자동으로 넣습니다**. 필요한 외부 요소는 Redis 하나입니다.

```sh
# 1. Redis (리프레시 토큰 저장용)
docker run -d --name trendin-redis -p 6379:6379 redis:8

# 2. 백엔드 — H2 + 데모 데이터 자동 생성
cd backend
./gradlew bootRun --args='--spring.profiles.active=local'
#    http://localhost:8080
#    H2 콘솔: http://localhost:8080/h2-console  (JDBC URL: jdbc:h2:mem:trendin / 사용자 sa)
```

> ⚠️ **`bootRun` 은 끝나지 않습니다.** 서버를 포그라운드로 계속 돌리는 명령이라
> 진행률이 `85% EXECUTING` 에서 멈춘 것처럼 보이는 것이 정상입니다. 로그에
> **`Started BackendApplication`** 이 지나갔으면 이미 떠 있는 것이고, 끄려면 `Ctrl+C` 입니다.
>
> **첫 실행은 5~15분 걸립니다** — Gradle 9.7.1 배포판과 의존성을 처음 내려받기 때문입니다.
> 두 번째부터는 10초대입니다. 진행 상황을 줄 단위로 보려면 `--console=plain` 을 붙입니다.

```sh
# 3. 프론트 (새 터미널)
cd frontend
cp .env.example .env.local     # 값이 이미 로컬 기준으로 채워져 있습니다
npm ci
npm run dev
#    http://localhost:5173
```

#### 시드 계정

기동하면서 만들어지는 계정입니다. **비밀번호는 모두 `password123!`** 입니다.

| 이메일 | 닉네임 | 상태 |
| --- | --- | --- |
| `fashion@example.com` | 스타일리스트 | 패션 분야, 관심 키워드 있음 — **시연에 쓰기 좋습니다** |
| `heavy@example.com` | 관심많은사람 | 관심 키워드가 많음 |
| `both@example.com` | 두분야모두 | 두 분야 모두 선택 |
| `dev@example.com` | 백엔드개발자 | 개발 분야 |
| `newbie@example.com` | 신규가입자 | **온보딩 미완료** — 온보딩 화면 확인용 |
| `nokeyword@example.com` | 키워드없음 | 관심 키워드 없음 |
| `quiet@example.com` | 조용한사용자 | 활동 적음 |

> H2 는 인메모리라 **백엔드를 끄면 데이터가 사라집니다.** 다시 켜면 같은 데이터가 새로 만들어집니다.

#### 로컬에서 안 되는 것

| 기능 | 이유 |
| --- | --- |
| GitLab 소셜 로그인 | OAuth 자격증명이 비어 있음. **이메일 로그인은 그대로 됩니다** |
| 실시간 수집·집계 | 파이프라인(Airflow·Spark·MinIO)을 띄우지 않음. 데이터는 시드로 대체됩니다 |

---

### 확인

```sh
curl -fsS http://localhost:8080/actuator/health
# {"status":"UP"} 이면 정상입니다
```

> PostgreSQL 로 운영과 같은 구성을 띄우고 실제 자료를 넣으려면 [3번 문서](db/README.md)를 보세요.

---

## 4) 배포 시 특이사항

### ⚠️ Redis 가 없으면 로그인이 실패합니다

애플리케이션은 Redis 없이도 **기동은 됩니다.** 화면도 뜨고 트렌드 목록도 보입니다. 다만 로그인이
리프레시 토큰을 Redis 에 저장하므로, 그 단계에서 오류가 납니다. 증상이 "서버가 안 떴다" 가 아니라
"로그인만 안 된다" 로 보이니 헷갈리기 쉽습니다.

```sh
docker run -d --name trendin-redis -p 6379:6379 redis:8
```

### ⚠️ H2 는 인메모리라 껐다 켜면 초기화됩니다

로컬 프로파일의 데이터는 기동할 때마다 새로 만들어집니다. 회원가입을 하거나 키워드를 담아 둬도
백엔드를 재시작하면 사라지고, 시드 계정과 데모 데이터만 다시 생깁니다. **자료를 남겨 두려면**
PostgreSQL 로 띄우고 DB 덤프를 복원합니다 — [3번 문서](db/README.md).

### ⚠️ 스키마는 Flyway 가 소유합니다

PostgreSQL 로 띄울 때는 `ddl-auto: validate` 라 엔티티가 스키마를 만들지 않습니다. 변경은
`backend/src/main/resources/db/migration/` 에 `V{n}__{설명}.sql` 을 더하는 것으로만 합니다.

`validate` 는 **컬럼 길이를 비교하지 않습니다.** 길이를 바꾸는 변경은 마이그레이션과 엔티티를
손으로 맞춰야 하고, 어긋나면 기동은 성공한 뒤 저장 시점에 터집니다.

`DEV_FLYWAY_BASELINE_ON_MIGRATE` 는 Flyway 이력이 없는 기존 스키마에 처음 붙일 때만 `true` 로
두고, 한 번 지나면 `false` 로 되돌립니다.

### ⚠️ 프론트 환경 변수는 빌드 시점에 굳습니다

`VITE_*` 는 번들에 구워집니다. `npm run build` 로 만든 산출물을 배포한 뒤 `.env.local` 만
고쳐도 반영되지 않으니 **다시 빌드해야** 합니다. (`npm run dev` 는 저장하면 바로 반영됩니다.)

### ⚠️ OAuth Redirect URI 는 세 곳이 글자까지 같아야 합니다

GitLab 등록값 · `infra/.env` · `frontend/.env.local`. 하나라도 다르면 토큰 교환이 거절됩니다.

콜백 경로는 **프런트 라우트여야** 합니다 — Nginx 를 앞에 둘 경우 `/auth` · `/domains` ·
`/keywords` · `/members` · `/trends` 로 시작하는 요청이 백엔드로 넘어가므로, 그 접두어를 피해
`/oauth/...` 를 씁니다.

### ⚠️ Nginx 의 `/trends` 는 화면과 API 를 겸합니다

Nginx 를 앞에 두고 배포할 때만 해당합니다. `/trends/:id` 는 SPA 라우트이면서 API 경로라,
`Accept` 에 `text/html` 이 없으면 백엔드로, 있으면 `index.html` 로 보냅니다.
이 분기를 지우면 **트렌드 상세를 주소로 직접 열 때 JSON 이 보입니다.**

---

## 5) 주요 계정 및 프로퍼티 정의 파일 목록

### 비밀값이 드는 파일 (Git 미포함)

| 파일 | 담는 것 |
| --- | --- |
| `infra/.env` | PostgreSQL·Redis 비밀번호, JWT 서명 키, Grafana 관리자, GitLab OAuth 자격증명 |
| `frontend/.env.local` | 백엔드 주소, GitLab OAuth Client ID |
| `datastore/.env` | MinIO 관리자·크롤러·Spark 키 |
| `pipeline/.env` | Airflow 메타 DB·JWT 비밀, GMS LLM 키, 앱 DB 접속 URI, MinIO 키 |
| `pipeline/spark/.env` | Spark Job 로컬 실행용 접속 정보 |

각 파일의 `.env.example` 이 같은 디렉터리에 있습니다.

### 프로퍼티가 정의된 파일 (Git 포함)

| 파일 | 담는 것 |
| --- | --- |
| `backend/src/main/resources/application.yml` | Redis, JWT 만료, CORS, 알림 배치 크론, OAuth 엔드포인트, actuator |
| `backend/src/main/resources/application-dev.yml` | 운영 — PostgreSQL DataSource, Flyway, `ddl-auto: validate` |
| `backend/src/main/resources/application-local.yml` | 로컬 — H2 인메모리, `ddl-auto: create-drop` |
| `infra/compose.yaml` · `infra/compose.monitoring.yaml` | 컨테이너 정의와 환경 변수 매핑 |
| `infra/nginx/trendin.conf` | HTTPS, SPA 라우팅, API 리버스 프록시 |
| `datastore/compose.yaml` | MinIO 와 버킷·정책 초기화 |
| `pipeline/compose.yaml` | Airflow 서비스 |

### DB 접속 정보

| 항목 | 값·위치 |
| --- | --- |
| **데이터베이스명** | `forever102` |
| **계정** | `infra/.env` 의 `DEV_POSTGRES_USER_NAME` (예: `ssafy`) |
| **비밀번호** | `infra/.env` 의 `POSTGRES_PASSWORD` |
| **접속 URL** | `infra/.env` 의 `DEV_POSTGRES_URL` |
| **스키마 정의** | `backend/src/main/resources/db/migration/V1`~`V12` (Flyway) |
| **ERD** | [`docs/erd/erd.md`](../docs/erd/erd.md) |
| **Airflow 메타 DB** | `pipeline/compose.yaml` 내장, 계정 `airflow` |
