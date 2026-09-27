# TrendIn 포팅 매뉴얼

| 번호 | 문서 | 내용 |
| --- | --- | --- |
| 1 | [빌드 및 배포](1-build-deploy.md) | 제품·버전, 환경 변수, 실행 절차, 배포 특이사항, 계정·프로퍼티 파일 목록 |
| 2 | [외부 서비스](2-external-services.md) | 가입과 키 발급이 필요한 외부 서비스 |
| 3 | [DB 덤프](db/README.md) | `trendin-dump-20260927.sql` 과 복원 절차 |
| 4 | [시연 시나리오](4-demo-scenario.md) | 화면별·클릭별 시연 순서 |

배포된 서비스: <https://j15a102.p.ssafy.io>

---

## 로컬에서 바로 띄우기

**PostgreSQL 도 DB 덤프도 필요 없습니다.** `local` 프로파일이 인메모리 H2 를 쓰고, 기동하면서 키워드·트렌드·AI 해설·시드 계정을 자동으로 넣습니다.

```sh
# 1. Redis
docker run -d --name trendin-redis -p 6379:6379 redis:8

# 2. 백엔드 (http://localhost:8080)
cd backend && ./gradlew bootRun --args='--spring.profiles.active=local'

# 3. 프론트 (http://localhost:5173) — 새 터미널
cd frontend && cp .env.example .env.local && npm ci && npm run dev
```

로그인은 **`fashion@example.com` / `password123!`** 로 합니다. 다른 시드 계정은 [1번 문서](1-build-deploy.md#시드-계정)에 있습니다.

---

## 시스템 구성

운영은 **EC2 2대**입니다.

| 서버 | 올라가는 것 |
| --- | --- |
| **서비스 EC2** (`j15a102.p.ssafy.io`) | Nginx · Backend · PostgreSQL · Redis · Prometheus · Grafana |
| **데이터 EC2** | MinIO · Airflow · Spark |

데이터 EC2 의 Spark 가 서비스 EC2 의 PostgreSQL 에 직접 적재합니다.

```text
[사용자] ──HTTPS──> Nginx ──┬──> 정적 파일 (React 빌드 산출물)
                            └──> Backend :8080 ──┬──> PostgreSQL :5432 <──┐
                                                 └──> Redis :6379         │
                                                                     JDBC │
[매체 41곳] <──수집── Airflow(데이터 EC2) ──> MinIO ──> Spark ───────────┘
```
