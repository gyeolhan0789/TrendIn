# 공용 인프라

기본 EC2 `J15A102`에 배치할 공용 서비스의 Docker Compose 설정을 관리한다.
70번의 서비스·네트워크 구조와 71번의 named volume 연결에
73번의 비밀번호 환경변수 및 SSH 터널용 루프백 포트 설정을 추가했고,
175번에서 리프레시 토큰 저장용 Redis 서비스를 같은 규칙으로 추가했다.
실제 EC2 배포와 영속화 검증은 아직 수행하지 않았다.

## 파일 구성

- `compose.yaml`: 공용 Compose 프로젝트, PostgreSQL·Redis 서비스와 각각의 데이터 Volume, 공용 네트워크 정의
- `redis.conf`: Redis의 영속화·메모리 설정. 비밀번호는 이 파일에 두지 않는다.
- `README.md`: 구성 의도, 검증 방법, 후속 이슈의 작업 범위
- `.env.example`: 필요한 비밀번호 환경변수의 빈 템플릿
- 실제 `infra/.env`는 EC2에서만 관리하며 루트 `.gitignore`로 Git 추적에서 제외한다.

## 기본 구성

- 프로젝트 이름: `s15p21a102-infra`
- 서비스 이름: `postgres`, `redis`
- 이미지: 공식 `postgres:17-bookworm`, 공식 `redis:8-bookworm`. 메이저 버전은 각각 17과 8로 고정하며 패치 버전은 태그 갱신에 따라 달라질 수 있다.
- 재시작 정책: 두 서비스 모두 `unless-stopped`. 운영자가 명시적으로 중지한 컨테이너는 중지 상태를 유지한다.
- 공용 네트워크: `s15p21a102-shared` (`bridge`)

공용 네트워크는 이 Compose 프로젝트에서 생성·관리한다.
향후 같은 EC2의 백엔드 Compose는 이 네트워크를 외부 네트워크로 참조하여
서비스 이름 `postgres`, `redis`로 접근할 수 있다. 다른 EC2까지 연결하는 네트워크는 아니다.

DB 포트와 Redis 포트는 호스트의 `127.0.0.1:5432`, `127.0.0.1:6379`에만 연결하고
공인 인터페이스에는 공개하지 않는다.
같은 Docker 네트워크의 컨테이너 사이 통신과 호스트 포트 공개는 별개다.
UFW 변경이나 EC2 배포 작업은 이번 범위에 포함하지 않는다.

### Redis 설정

리프레시 토큰과 세션 상태를 담으므로 재시작 후에도 데이터가 남아야 한다.
설정은 `redis.conf`에 두고 비밀번호만 환경변수로 주입한다.

- 영속화: `appendonly yes`, `appendfsync everysec`. AOF는 Volume의 `/data/appendonlydir`에 기록된다.
- RDB 스냅샷(`save`)도 기본값 수준으로 함께 유지하여 복구 수단을 이중화한다.
- `maxmemory 256mb`, `maxmemory-policy noeviction`.
  토큰은 TTL로 만료되므로 임의 축출(eviction)을 허용하지 않는다.
  대신 상한에 도달하면 쓰기가 실패하고 로그인·토큰 재발급이 막히므로 사용량을 모니터링해야 한다.
- `protected-mode yes`이며 `requirepass`는 `REDIS_PASSWORD`로 주입한다. 비밀번호 없는 접근은 거부된다.
- `bind`는 지정하지 않는다. 컨테이너 네트워크에서 접근해야 하므로 기본값(모든 인터페이스)을 사용하고,
  외부 노출은 루프백 포트 바인딩과 비밀번호로 막는다.

`redis.conf`는 읽기 전용(`:ro`)으로 마운트한다.
`CONFIG SET`으로 런타임 값을 바꿔도 이 파일에는 반영되지 않으므로 영구 변경은 파일을 수정하고 재생성한다.

## 현재 단계의 제한

- DB 이름은 `forever102`, 사용자는 `ssafy`이며 비밀번호만 `POSTGRES_PASSWORD`로 주입한다.
- Redis는 기본 사용자(`default`)에 `REDIS_PASSWORD`만 설정한다. ACL로 계정을 분리하지 않는다.
- 비밀번호가 없거나 비어 있으면 Compose 명령이 오류로 중단된다. 두 변수 모두 해당한다.
- 비밀번호 하드코딩이나 인증을 우회하는 `trust`·비밀번호 없는 Redis 설정을 사용하지 않는다.
- 데이터 Volume 연결은 구성했지만 실제 기동 및 영속화 검증은 아직 수행하지 않았다.
- EC2의 `infra/.env` 설정과 접근 제어 확인 후 기동한다.
- 이번 작업에서는 `.env` 파일을 생성하거나 실제 비밀번호·키를 저장하지 않는다.
- Redis는 단일 인스턴스다. 복제·Sentinel·Cluster 구성은 포함하지 않는다.
- 백엔드 애플리케이션의 Redis 의존성 추가와 접속 설정은 이번 범위가 아니다.

## EC2에서 준비 및 실행

Docker Engine 및 Compose v2가 설치된 기본 EC2에서 저장소 루트 기준으로 실행한다.
기존 `.env`가 있다면 덮어쓰지 않고 편집한다.

```sh
# 최초 한 번만 실행: 파일이 없을 때 권한을 제한하여 생성
(umask 077; cp -n infra/.env.example infra/.env)
chmod 600 infra/.env
nano infra/.env
```

편집기에서 `POSTGRES_PASSWORD`와 `REDIS_PASSWORD`에 합의한 실제 비밀번호를 입력한다.
이미 `.env`를 사용 중이라면 `REDIS_PASSWORD` 줄만 추가한다.
셸에 같은 이름의 환경변수가 있으면 파일보다 우선하므로, 의도치 않은 값이 설정되어 있지 않은지 확인한다.
실제 비밀번호는 문서·커밋·명령 기록에 남기지 않는다.
`.env`는 암호화 저장소가 아니며 Docker 관리 권한이 있는 사용자는 컨테이너 환경변수를 볼 수 있다.
Redis 비밀번호는 컨테이너 안에서 `redis-server`의 실행 인자로도 보인다.

```sh
docker compose --env-file infra/.env -f infra/compose.yaml config --quiet
docker compose --env-file infra/.env -f infra/compose.yaml up -d postgres redis
docker compose --env-file infra/.env -f infra/compose.yaml ps
```

값을 출력하는 일반 `config`나 `config --environment` 결과는 비밀번호가 포함될 수 있으므로 공유하지 않는다.
DB 이름·사용자·비밀번호는 빈 Volume을 최초 초기화할 때 적용된다.
기존 DB의 비밀번호는 `.env` 수정만으로 변경되지 않으며, 변경이 필요하면 DB 내부에서 별도로 변경해야 한다.
`ssafy`는 공식 이미지가 생성하는 관리자(superuser) 계정이다. 추후 애플리케이션 운영 시에는 최소 권한 계정 분리를 권장한다.

Redis의 `requirepass`는 매 기동 시 인자로 주입하므로 `.env`를 수정하고 재생성하면 즉시 반영된다.
이 점은 최초 초기화 때만 적용되는 PostgreSQL 비밀번호와 다르다.

기동 확인은 아래처럼 컨테이너 안에서 실행한다.
`-a` 옵션에 비밀번호를 직접 적으면 셸 기록에 남으므로 컨테이너의 환경변수를 그대로 사용한다.

```sh
docker compose --env-file infra/.env -f infra/compose.yaml exec redis \
  sh -c 'redis-cli --no-auth-warning -a "$REDIS_PASSWORD" PING'
```

`PONG`이 출력되어야 한다. 비밀번호 없이 실행하면 `NOAUTH` 오류가 나는 것이 정상이다.

## SSH 터널 접속

EC2에서 UFW는 반드시 active로 유지한다. 기존 SSH 허용 규칙과 접속을 확인한 후 변경하며,
UFW 및 관리 가능한 보안 그룹에서 공인망의 5432와 6379를 열지 않는다.
Docker 공개 포트는 UFW 규칙을 우회할 수 있어 루프백 바인딩을 유지해야 한다.
Docker 28.0.0 미만에는 동일 L2 네트워크에서 루프백 공개 포트에 접근할 수 있는 주의사항이 있으므로
배포 전에 지원되는 최신 Docker 버전과 기본 bridge/NAT 구성을 확인한다.

팀원 PC에서 실행하고 터널을 사용하는 동안 터미널을 유지한다. PEM 경로는 로컬 경로로 바꾼다.

```sh
ssh -i "J15A102T.pem" -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:15432:127.0.0.1:5432 \
  -L 127.0.0.1:16379:127.0.0.1:6379 \
  ubuntu@j15a102.p.ssafy.io
```

- DB 클라이언트: Host `127.0.0.1`, Port `15432`, Database `forever102`, User `ssafy`
- Redis 클라이언트: Host `127.0.0.1`, Port `16379`, User `default`
- Password: EC2의 `.env`에 설정한 값 (Git·문서로 공유하지 않음)
- 같은 공용 Docker 네트워크의 백엔드: Host `postgres` Port `5432`, Host `redis` Port `6379`

제공받은 관리자 PEM을 팀 전체에 복사하기보다 개인별 승인된 SSH 키·계정을 사용하는 것을 권장한다.
배포 후 외부 PC에서 서버의 5432·6379로 직접 접속은 실패하고 SSH 터널 접속은 성공하는지 확인한다.

## 구성 검증

EC2에서 `infra/.env`를 준비한 후 저장소 루트를 기준으로 실행한다.
아래 명령은 컨테이너를 실행하지 않고 Compose 구성을 검증한다.

```sh
docker compose --env-file infra/.env -f infra/compose.yaml config --quiet
docker compose --env-file infra/.env -f infra/compose.yaml config --services
docker compose --env-file infra/.env -f infra/compose.yaml config --networks
docker compose --env-file infra/.env -f infra/compose.yaml config --volumes
```

서비스 목록에는 `postgres`와 `redis`, 네트워크 목록에는 `shared`,
Volume 목록에는 `postgres_data`와 `redis_data`가 표시되어야 한다.
구성 검증 통과는 기동이나 영속화 검증을 의미하지 않는다.

## 데이터 영속화

Compose의 `postgres_data`는 Docker named volume `s15p21a102-postgres-data`를 사용한다.
이를 PostgreSQL 17 이미지의 기본 데이터 디렉터리 `/var/lib/postgresql/data`에 연결한다.
DB 파일은 컨테이너의 임시 파일시스템이 아니라 Docker 호스트의 Volume에 저장되므로,
컨테이너를 재시작하거나 재생성해도 같은 Volume을 연결하면 기존 데이터를 사용한다.
별도의 `PGDATA` 환경변수는 설정하지 않는다.

`redis_data`는 named volume `s15p21a102-redis-data`를 Redis 이미지의 기본 데이터 디렉터리 `/data`에 연결한다.
`redis.conf`의 `dir /data`가 같은 경로를 가리키므로 AOF와 RDB 파일이 이 Volume에 남는다.
리프레시 토큰이 재시작으로 사라지면 사용자가 로그아웃되므로 이 연결을 해제하지 않는다.

- `docker compose --env-file infra/.env -f infra/compose.yaml restart postgres redis`는 컨테이너를 재시작한다.
- `docker compose --env-file infra/.env -f infra/compose.yaml up -d --force-recreate postgres redis`는 컨테이너를 재생성하되 기존 named volume을 재사용한다.
- 일반 `docker compose down`은 named volume을 삭제하지 않지만, 공용 네트워크와 서비스에 영향을 주므로 운영 중 실행에 주의한다.
- **`docker compose down -v` 또는 `--volumes` 옵션은 DB·Redis Volume과 데이터를 삭제할 수 있으므로 사용하지 않는다.** Volume 직접 삭제 및 Volume을 포함한 prune 명령도 주의한다.
- **Redis의 `FLUSHALL`·`FLUSHDB`는 저장된 모든 세션을 무효화하므로 사용하지 않는다.**
- Volume 이름·마운트 경로를 임의로 변경하지 않는다. 같은 호스트의 다른 인스턴스에 이 Volume을 동시에 연결하지 않는다.
- 기존 익명 Volume의 데이터는 자동으로 이전되지 않는다. 이미 사용 중인 인스턴스가 있다면 백업·이관 후 적용한다.
- 이 구성은 PostgreSQL 17, Redis 8 기준이다. 메이저 버전 업그레이드는 이미지 태그 변경만으로 진행하지 않는다.
- Volume은 백업이 아니다. EC2 디스크 손실·Volume 삭제에 대비한 별도 백업이 필요하다.

### 추후 EC2 검증 순서

EC2의 `.env` 설정을 완료한 뒤, 테스트용 데이터로 검증한다.
아래 과정은 이번 작업에서 실행하지 않았으며, 모든 Compose 명령은 저장소 루트 기준이다.

1. `docker compose --env-file infra/.env -f infra/compose.yaml up -d postgres redis`로 기동하고 각 서비스가 요청을 받을 준비가 되었는지 확인한다.
2. `docker volume inspect s15p21a102-postgres-data s15p21a102-redis-data`로 Volume을 확인한다. `docker compose --env-file infra/.env -f infra/compose.yaml ps -q postgres`로 얻은 컨테이너 ID를 `docker inspect --format '{{json .Mounts}}' <컨테이너-ID>`에 넣어 이름과 대상 경로가 위 설정과 일치하는지 확인한다. `redis`도 같은 방법으로 확인한다.
3. DB에서 `SHOW data_directory;` 결과가 `/var/lib/postgresql/data`인지 확인한다. 테스트용 일반 테이블(임시 테이블 아님)에 식별 가능한 행을 INSERT하고 COMMIT한 뒤 조회 결과를 기록한다.
4. Redis에서 `CONFIG GET dir` 결과가 `/data`, `CONFIG GET appendonly` 결과가 `yes`인지 확인한다. 식별 가능한 키를 `SET`한 뒤 `appendfsync everysec` 주기로 기록되도록 몇 초 기다린다.
5. 위 `restart` 명령 실행 후 준비를 기다리고, 같은 테이블의 행과 같은 Redis 키가 그대로 조회되는지 확인한다.
6. 위 `up -d --force-recreate` 명령 실행 후 준비를 기다린다. 컨테이너 ID가 변경되었고, 같은 Volume이 연결되어 있으며, 기존 행과 키가 그대로 조회되는지 확인한다.

검증 중 재시작·재생성 사이에 테스트 데이터를 다시 생성하거나 INSERT하지 않는다.

## 후속 작업

- **EC2 적용 및 검증**: `.env` 준비, UFW·Docker 설정 확인, PostgreSQL·Redis 기동, 터널 접속 및 데이터 유지 검증
- **백엔드 연동**: `spring-boot-starter-data-redis` 의존성 추가와 프로필별 접속 설정, 리프레시 토큰 저장 로직

데이터 파이프라인과 추가 EC2 `J15A102A`의 실행 서비스는 이번 구성에 포함하지 않는다.

## 참고

- [PostgreSQL 공식 이미지](https://hub.docker.com/_/postgres)
- [Redis 공식 이미지](https://hub.docker.com/_/redis)
- [Redis 영속화(AOF·RDB)](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/)
- [Redis 보안과 requirepass](https://redis.io/docs/latest/operate/oss_and_stack/management/security/)
- [Compose 네트워크](https://docs.docker.com/reference/compose-file/networks/)
- [Compose 서비스](https://docs.docker.com/reference/compose-file/services/)
- [Compose Volume](https://docs.docker.com/reference/compose-file/volumes/)
- [Compose down과 Volume 삭제 옵션](https://docs.docker.com/reference/cli/docker/compose/down/)
- [Compose 환경변수](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/)
- [Docker 포트 공개](https://docs.docker.com/engine/network/port-publishing/)
