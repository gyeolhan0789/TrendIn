# 인프라 운영 가이드

기본 EC2 `J15A102`에서 PostgreSQL, Redis, Backend를 Docker Compose로 운영하고,
호스트 Nginx와 Jenkins로 프록시 및 CI/CD를 관리한다.

## 디렉터리 구조

```text
infra/
├── compose.yaml                # PostgreSQL, Redis, Backend 서비스·네트워크·Volume
├── .env.example                # 운영 환경변수 템플릿
├── jenkins/
│   ├── Jenkinsfile.ci          # Merge Request 테스트·빌드
│   └── Jenkinsfile.cd          # dev 빌드·배포·검증·롤백
├── nginx/
│   └── trendin.conf            # 80 → 127.0.0.1:8080 리버스 프록시
└── redis/
    └── redis.conf              # Redis 영속화·메모리 설정
```

백엔드 이미지 정의는 `backend/Dockerfile`에 있다.

## 환경변수

EC2에서 템플릿을 복사한 뒤 실제 값을 입력한다.

```sh
cp infra/.env.example infra/.env
```

필요한 변수는 다음과 같다.

- `POSTGRES_PASSWORD`, `REDIS_PASSWORD`
- `BACKEND_IMAGE`, `BACKEND_PORT`
- `DEV_POSTGRES_URL`, `DEV_POSTGRES_USER_NAME`
- `DEV_REDIS_HOST`, `DEV_REDIS_PORT`
- `DEV_JWT_SECRET`: UTF-8 기준 최소 32바이트
- `DEV_CORS_ALLOWED_ORIGINS`

`infra/.env`에는 실제 Secret을 저장하고 Git에 커밋하지 않는다.
Compose 내부에서 Backend는 `postgres:5432`, `redis:6379`로 접속한다.

## Docker Compose 실행

모든 명령은 저장소 루트에서 실행한다.

```sh
docker compose --env-file infra/.env -f infra/compose.yaml config --quiet
docker compose --env-file infra/.env -f infra/compose.yaml up -d
docker compose --env-file infra/.env -f infra/compose.yaml ps
docker compose --env-file infra/.env -f infra/compose.yaml logs --tail=100
```

백엔드 이미지를 EC2에서 직접 빌드할 때는 실행 JAR을 먼저 생성한다.

```sh
(cd backend && ./gradlew clean build --no-daemon --console=plain)
docker compose --env-file infra/.env -f infra/compose.yaml build backend
docker compose --env-file infra/.env -f infra/compose.yaml up -d backend
```

PostgreSQL과 Redis 데이터는 각각 named volume
`s15p21a102-postgres-data`, `s15p21a102-redis-data`에 저장된다.
데이터가 삭제될 수 있으므로 `docker compose down -v`와 Volume 삭제 명령은 사용하지 않는다.

## Jenkins CI/CD

| Job | 역할 | Script Path |
| --- | --- | --- |
| `trendin-backend-ci` | MR 소스 코드 Gradle 테스트·빌드 및 `jenkins/backend-ci` 상태 전달 | `infra/jenkins/Jenkinsfile.ci` |
| `trendin-backend-cd` | dev Gradle 빌드, Docker 이미지 생성, Backend-only 배포, HTTP 검증·롤백 및 `jenkins/backend-cd` 상태 전달 | `infra/jenkins/Jenkinsfile.cd` |

- CI Job은 dev 대상 Merge Request 생성·변경 이벤트로 실행한다.
- CD Job은 dev push 이벤트로만 실행한다.
- 두 Job은 GitLab Connection `ssafy-gitlab`을 사용한다.
- CD Job의 `DEPLOY_ENV_FILE`에는 Jenkins가 읽을 수 있는 EC2 `infra/.env`의 절대 경로를 설정한다.
- CD 배포는 Backend만 재생성하며 PostgreSQL과 Redis는 재생성하지 않는다.

## Nginx와 Redis

- Nginx 설정: `infra/nginx/trendin.conf`
  - EC2 호스트의 80 포트 요청을 Backend `127.0.0.1:8080`으로 전달한다.
  - 적용 전 `sudo nginx -t`를 실행하고 성공한 경우에만 Nginx를 reload한다.
- Redis 설정: `infra/redis/redis.conf`
  - Compose에서 `/etc/redis/redis.conf`에 읽기 전용으로 마운트한다.
  - 비밀번호는 설정 파일이 아니라 `infra/.env`의 `REDIS_PASSWORD`로 주입한다.
