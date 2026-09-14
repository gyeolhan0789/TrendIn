# 공용 인프라

기본 EC2 `J15A102`에 배치할 공용 서비스의 Docker Compose 설정을 관리한다.
70번의 서비스·네트워크 구조와 71번의 named volume 연결에
73번의 비밀번호 환경변수 및 SSH 터널용 루프백 포트 설정을 추가했고,
175번에서 리프레시 토큰 저장용 Redis 서비스를 같은 규칙으로 추가했다.
실제 EC2 배포와 영속화 검증은 아직 수행하지 않았다.

## 파일 구성

- `compose.yaml`: 공용 Compose 프로젝트, PostgreSQL·Redis 서비스와 각각의 데이터 Volume, 공용 네트워크 정의
- `../backend/Dockerfile`: 빌드된 실행 JAR을 Java 25 런타임 이미지에 포함하는 정의
- `../backend/.dockerignore`: 백엔드 이미지 빌드에 필요하지 않은 로컬 파일 제외
- `redis.conf`: Redis의 영속화·메모리 설정. 비밀번호는 이 파일에 두지 않는다.
- `nginx/trendin.conf`: EC2 호스트 Nginx에서 백엔드로 전달하는 HTTP 리버스 프록시 설정
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
- 백엔드의 기존 Redis 의존성과 프로필별 접속 설정은 유지하고 Compose에서 환경변수만 주입한다.

## 백엔드 컨테이너

백엔드는 Gradle로 먼저 빌드한 `backend/build/libs/app.jar`를 Java 25 런타임 이미지에 포함한다.
`bootJar` 출력 이름은 `app.jar`로 고정하며 plain JAR은 이미지에 포함하지 않는다.
Dockerfile에서는 Gradle을 실행하지 않으므로 로컬·EC2 수동 이미지 빌드 전에도 Gradle 빌드가 필요하다.
컨테이너는 일반 사용자 `spring`으로 실행하고 `dev` 프로필을 사용한다.
`application-dev.yml`의 `ddl-auto`는 `validate`이므로 기동 시 공용 DB를 생성하거나 변경하지 않고,
사전에 적용한 baseline과 Entity가 일치하는지만 검사한다.

Compose의 백엔드 서비스는 공용 네트워크에서 `postgres:5432`, `redis:6379`로 접근한다.
DB·Redis 비밀번호와 JWT Secret은 이미지에 포함하지 않고 EC2의 `infra/.env`에서 주입한다.
Nginx 적용 전까지 애플리케이션 포트도 호스트의 `127.0.0.1`에만 연결한다.

EC2에서 기존 `infra/.env`에 `.env.example`의 Backend 항목을 추가하고 실제 Secret과 허용할
프런트엔드 Origin을 입력한 뒤 저장소 루트에서 실행한다.
`DEV_JWT_SECRET`은 HS256 서명에 사용할 임의의 값으로 설정하며 UTF-8 기준 최소 32바이트여야 한다.

```sh
docker compose --env-file infra/.env -f infra/compose.yaml config --quiet
(cd backend && ./gradlew clean build --no-daemon --console=plain)
docker compose --env-file infra/.env -f infra/compose.yaml build backend
docker compose --env-file infra/.env -f infra/compose.yaml up -d backend
docker compose --env-file infra/.env -f infra/compose.yaml ps
docker compose --env-file infra/.env -f infra/compose.yaml logs --tail=100 backend
```

EC2 내부에서는 `curl http://127.0.0.1:8080`으로 연결을 확인한다. 외부 PC에서 임시로 확인할 때는
5432와 마찬가지로 SSH 터널 `-L 18080:127.0.0.1:8080`을 사용하며 8080을 공인망에 열지 않는다.

## Nginx 리버스 프록시

호스트 Nginx가 `j15a102.p.ssafy.io`의 80 포트 요청을 받고, 루프백에만 공개된 백엔드
`127.0.0.1:8080`으로 전달한다. 클라이언트의 Host, IP, 전달 경로의 프로토콜은 표준 proxy header로
백엔드에 전달한다. HTTPS와 인증서 설정은 이번 구성에 포함하지 않는다.

EC2에서 백엔드가 정상 실행 중인지 먼저 확인한 뒤 저장소 루트에서 다음 명령을 실행한다.

```sh
curl --silent --show-error --output /dev/null --write-out 'HTTP %{http_code}\n' http://127.0.0.1:8080/

sudo apt-get update
sudo apt-get install -y nginx
sudo install -o root -g root -m 644 infra/nginx/trendin.conf /etc/nginx/sites-available/trendin
sudo ln -sfn /etc/nginx/sites-available/trendin /etc/nginx/sites-enabled/trendin
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx
```

UFW는 비활성화하지 않는다. SSH 허용 규칙과 현재 접속을 먼저 확인하고 HTTP만 추가한다.
AWS 보안 그룹도 외부 HTTP 접속이 필요하면 TCP 80만 허용하며, 8080은 열지 않는다.

```sh
sudo ufw status verbose
sudo ufw allow 'Nginx HTTP'
sudo ufw status verbose
```

EC2에서는 Host 헤더를 포함해 프록시 응답을 확인하고, 외부에서는 공인 도메인으로 확인한다.
애플리케이션에 `/` 엔드포인트가 없어 404가 반환되더라도 Nginx 응답과 백엔드 로그를 함께 확인한다.

```sh
curl -i -H 'Host: j15a102.p.ssafy.io' http://127.0.0.1/
curl -i http://j15a102.p.ssafy.io/
sudo journalctl -u nginx --since '10 minutes ago' --no-pager
docker compose --env-file infra/.env -f infra/compose.yaml logs --tail=100 backend
```

설정 변경 시에는 항상 `sudo nginx -t`를 먼저 통과시킨 뒤 reload한다. 기존 Nginx 설정이나 다른
가상 호스트가 있다면 `sites-enabled`의 80 포트 및 같은 `server_name` 충돌 여부를 먼저 확인한다.

## Jenkins CI/CD

Jenkins는 역할별 Pipeline Job과 Jenkinsfile을 사용한다.

- `trendin-backend-ci`: `infra/jenkins/Jenkinsfile.ci`에서 MR 소스 SHA를 checkout하고 Gradle만 실행한다.
- `trendin-backend-cd`: `infra/jenkins/Jenkinsfile.cd`에서 dev SHA를 checkout하고 기존 배포·롤백을 실행한다.

MR 상태는 해당 소스 SHA의 `jenkins/backend-ci`, dev 배포 상태는 `jenkins/backend-cd` 이름으로 GitLab에
전달한다. Checkout 완료 직후 `running`, 최종 결과에 따라 `success`, `failed`, `canceled`를 전송한다.

1. 소스 체크아웃 및 배포 브랜치·도구·환경 파일 검증
2. Gradle `clean build`를 통한 테스트와 백엔드 빌드
3. `<commit SHA>-<Jenkins build number>` 태그로 `backend` 이미지 빌드
4. 현재 실행 중인 이미지 참조를 보존한 뒤 `--no-deps --force-recreate backend`로 백엔드만 재생성
5. `127.0.0.1:8080`의 비 5xx HTTP 응답 확인 및 JUnit 결과 게시
6. 배포 또는 HTTP 검증 실패 시 보존한 이미지로 backend 자동 롤백

배포와 롤백 단계는 PostgreSQL과 Redis를 시작하거나 재생성하지 않는다. 실패한 새 backend의 최근 로그와
롤백 결과를 Jenkins 콘솔에 출력한다. backend 교체 중 짧은 중단은 발생할 수 있으며 무중단 배포는 이번
범위에 포함하지 않는다.
Jenkins는 Compose 실행 시에만 `BACKEND_IMAGE`를 배포별 태그로 덮어쓰며 `infra/.env`의
`BACKEND_IMAGE=s15p21a102/backend:dev` 값은 수동 배포용으로 유지한다.

### EC2 준비

Jenkins는 [공식 Debian/Ubuntu 설치 안내](https://www.jenkins.io/doc/book/installing/linux/)의 LTS 저장소를
따라 설치한다. 현재 백엔드가 호스트의 `127.0.0.1:8080`을 사용하므로 Jenkins 기본 8080 포트와 충돌한다.
Jenkins를 시작하기 전에 systemd override의 `JENKINS_PORT`를 8081 등 사용하지 않는 포트로 변경한다.
설치 시 자동 시작에 실패했다면 포트 변경 후 다시 시작한다.

```sh
sudo systemctl edit jenkins
```

열린 편집기에 다음 override를 저장한 뒤 Jenkins를 시작한다.

```ini
[Service]
Environment="JENKINS_PORT=8081"
```

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now jenkins
sudo systemctl status jenkins --no-pager
```

`infra/.env`는 `ubuntu`와 `jenkins`가 함께 읽을 수 있도록 `deploy` 그룹으로 관리한다. `ubuntu`만
수정할 수 있고 Jenkins는 읽기만 가능하게 하며, 그룹 구성 후 기존 로그인 세션은 다시 접속한다.

```sh
sudo groupadd --force deploy
sudo usermod -aG deploy ubuntu
sudo usermod -aG deploy jenkins
sudo chown ubuntu:deploy /absolute/path/to/infra/.env
sudo chmod 640 /absolute/path/to/infra/.env
sudo -u jenkins test -r /absolute/path/to/infra/.env
```

Jenkins 작업을 실행하는 `jenkins` 사용자는 Docker CLI와 Compose v2를 실행할 수 있어야 한다.
호스트 Docker를 사용하는 경우 Docker 그룹 권한은 사실상 호스트 관리자 권한이므로 Jenkins 관리자와
Job 수정 권한을 최소화한 뒤 적용한다.

```sh
sudo usermod -aG docker jenkins
sudo systemctl restart jenkins
sudo -u jenkins docker version
sudo -u jenkins docker compose version
```

실제 Secret이 든 `infra/.env`는 Git 저장소와 Jenkinsfile에 넣지 않는다. Jenkins 작업공간 정리에도
영향받지 않는 EC2 경로에 보관하고, 해당 파일은 소유자와 `deploy` 그룹만 읽을 수 있게 권한을 제한한다.
기존 `infra/.env`를 그대로 사용한다면 파일을 이동하거나 복사하지 말고 그 절대 경로를 사용한다.

Jenkins의 Job 또는 노드 환경변수 `DEPLOY_ENV_FILE`에는 위 파일의 절대 경로만 설정한다. 이 변수는
Secret 값이 아니라 경로이며, 비밀번호와 JWT Secret은 파일 내부에만 유지한다. Jenkins가 실행되는
EC2에서 `curl`과 Java 21 이상도 사용할 수 있어야 한다. Gradle은 프로젝트 설정에 따라 빌드용 Java 25
툴체인을 내려받으므로 최초 빌드 시 외부 저장소 접근과 추가 시간이 필요하다.

### Jenkins Job과 GitLab 설정

- Jenkins에 Pipeline, Git, JUnit, GitLab 연동 플러그인을 설치한다.
- 두 Pipeline Job의 SCM 저장소와 Credential은 같게 설정하고 Branch Specifier는 모두 `*/dev`로 둔다.
- `trendin-backend-ci` Script Path: `infra/jenkins/Jenkinsfile.ci`
- `trendin-backend-cd` Script Path: `infra/jenkins/Jenkinsfile.cd`
- Job에서 GitLab Connection은 Jenkinsfile에 지정된 `ssafy-gitlab`을 사용한다. 이 Connection의 API Token이
  해당 프로젝트 commit status를 갱신할 권한을 가지고 있는지 확인한다.
- 비공개 저장소 접근용 GitLab Credential은 Jenkins Credentials에서 관리하고 Job의 SCM에 연결한다.
- CI Job은 GitLab Trigger의 Merge Request Events를 활성화하고 Push Events와 Pipeline Events는 끈다.
  MR 생성·업데이트를 활성화하고 `Rebuild open Merge Requests`를 source branch push 시 재빌드하는 값으로
  설정해 MR 소스 변경마다 다시 실행되게 한다.
- CD Job은 Push Events만 활성화하고 Name-based filter의 include branch를 `dev`로 설정한다.
- Job의 Pipeline script는 SCM의 `dev` 브랜치에서 읽도록 유지한다. Pipeline이 Webhook의 검증된
  소스 브랜치와 commit SHA를 별도로 checkout하므로 MR 코드가 배포 설정 자체를 변경하지 못한다.
- GitLab에서 `jenkins/backend-ci` 상태가 MR의 최신 commit SHA에 연결되어 MR Pipelines 탭에 표시되는지,
  `jenkins/backend-cd` 상태가 dev commit에 표시되는지 첫 실행에서 확인한다.
- Webhook이 Jenkins에 도달할 수 있는 네트워크 경로를 마련하되 Jenkins 관리 화면을 공인망 전체에
  노출하지 않는다. 관리 화면 접근은 SSH 터널 또는 허용된 관리 IP로 제한한다.
- 현재 Nginx는 모든 80 포트 요청을 백엔드로 전달하므로 Jenkins Webhook을 프록시하지 않는다. 8081을
  직접 사용한다면 UFW와 AWS 보안 그룹에서 팀이 확인한 GitLab Webhook 송신 대역과 관리 IP만 허용하고,
  `0.0.0.0/0`으로 공개하지 않는다.
- Jenkins 기본 포트 변경만으로 Nginx가 Jenkins를 프록시하지는 않는다. 별도 공개 경로가 필요하면
  인증·접근 제어를 포함한 Nginx/보안 그룹 정책을 먼저 정한 뒤 구성한다.

첫 자동 배포 전 Jenkins 사용자로 아래 명령을 실행해 실제 환경 파일과 Compose 구성을 확인한다.
일반 `docker compose config` 출력에는 Secret이 포함될 수 있으므로 `--quiet`를 유지한다.

```sh
sudo -u jenkins docker compose \
  --env-file /absolute/path/to/infra/.env \
  -f /absolute/path/to/repository/infra/compose.yaml config --quiet
```

배포 후 `docker compose ps backend`, Jenkins 단계별 콘솔 로그, `http://127.0.0.1:8080` 응답과
Nginx를 통한 80 포트 응답을 확인한다. PostgreSQL과 Redis 컨테이너 ID가 배포 전후 동일한지도 확인한다.

## EC2에서 준비 및 실행

Docker Engine 및 Compose v2가 설치된 기본 EC2에서 저장소 루트 기준으로 실행한다.
기존 `.env`가 있다면 덮어쓰지 않고 편집한다.

```sh
# 최초 한 번만 실행: 파일이 없을 때 생성
(umask 077; cp -n infra/.env.example infra/.env)
sudo chown ubuntu:deploy infra/.env
sudo chmod 640 infra/.env
nano infra/.env
```

편집기에서 `POSTGRES_PASSWORD`와 `REDIS_PASSWORD`에 합의한 실제 비밀번호를 입력한다.
이미 `.env`를 사용 중이라면 기존 값을 유지하면서 `.env.example`의 `BACKEND_*`, `DEV_*` 항목을
모두 추가하고 환경에 맞게 설정한다. 빈 필수 변수가 하나라도 있으면 Compose 설정 해석이 중단된다.
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
