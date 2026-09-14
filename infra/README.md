# 인프라 운영 가이드

EC2 `J15A102`에서 Docker Compose로 PostgreSQL, Redis, Backend를 운영한다.
Nginx는 Backend 리버스 프록시, Jenkins는 CI/CD를 담당한다.

## 구조

```text
infra/
├── compose.yaml
├── .env.example
├── jenkins/
│   ├── Jenkinsfile.ci
│   └── Jenkinsfile.cd
├── nginx/
│   └── trendin.conf
└── redis/
    └── redis.conf
```

Backend Docker 이미지는 `backend/Dockerfile`을 사용한다.

## 환경변수

```sh
cp infra/.env.example infra/.env
```

실제 Secret은 `infra/.env`에서 관리하며 Git에 커밋하지 않는다.

## Docker Compose

저장소 루트에서 실행한다.

```sh
docker compose --env-file infra/.env -f infra/compose.yaml up -d
docker compose --env-file infra/.env -f infra/compose.yaml ps
docker compose --env-file infra/.env -f infra/compose.yaml logs --tail=100
```

PostgreSQL과 Redis는 named volume을 사용하므로 데이터 삭제 방지를 위해 `docker compose down -v`를 사용하지 않는다.

## Jenkins CI/CD

| Job | 실행 조건 | 역할 |
| --- | --- | --- |
| `trendin-backend-ci` | dev 대상 MR | Gradle 테스트 및 빌드 |
| `trendin-backend-cd` | dev push | Docker 빌드 및 Backend 배포 |

- CI: `infra/jenkins/Jenkinsfile.ci`
- CD: `infra/jenkins/Jenkinsfile.cd`
- CD는 Backend만 재배포하며 PostgreSQL과 Redis는 유지한다.
- 빌드 결과는 GitLab에 `jenkins/backend-ci`, `jenkins/backend-cd` 상태로 전달한다.

## Nginx

설정 파일: `infra/nginx/trendin.conf`

```text
80 → 127.0.0.1:8080 → Backend
```

설정 변경 후 검증하고 reload한다.

```sh
sudo nginx -t
sudo systemctl reload nginx
```

## Redis

설정 파일: `infra/redis/redis.conf`

Redis 비밀번호 등 Secret은 설정 파일에 직접 저장하지 않고 `infra/.env`에서 관리한다.