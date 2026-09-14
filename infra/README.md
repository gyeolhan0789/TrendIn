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

## Flyway

마이그레이션 파일은 `backend/src/main/resources/db/migration`에서 관리한다.
신규 PostgreSQL은 `V1__baseline.sql`부터 실행하고, 이후 변경은 기존 파일을 수정하지 않고
`V2__...sql`, `V3__...sql` 순서로 추가한다. 로컬 H2에서는 Flyway를 사용하지 않는다.

기존 EC2 DB에는 V1이 수동 적용되어 있으므로 최초 Flyway 배포 전에 DB를 백업하고 현재 테이블을 확인한다.
첫 배포에서만 `infra/.env`의 값을 다음처럼 변경하면 Flyway가 스키마를 다시 만들지 않고
`flyway_schema_history`에 V1 적용 완료 상태를 기록한다.

```dotenv
DEV_FLYWAY_BASELINE_ON_MIGRATE=true
```

Backend가 정상 기동한 뒤 다음 명령으로 baseline 이력을 확인한다.

```sh
docker compose --env-file infra/.env -f infra/compose.yaml exec postgres \
  psql -U ssafy -d forever102 -c \
  'SELECT installed_rank, version, description, type, success FROM flyway_schema_history ORDER BY installed_rank;'
```

`version=1`, `type=BASELINE`, `success=true`를 확인한 뒤
`DEV_FLYWAY_BASELINE_ON_MIGRATE=false`로 되돌린다. 이후 Backend 시작 시 미적용 migration만 순서대로 실행하고,
Hibernate `ddl-auto: validate`가 최종 Entity 정합성을 확인한다. 기존 V1을 수정하거나 DB·Volume을 삭제하지 않는다.

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
