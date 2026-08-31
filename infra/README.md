# 공용 인프라

기본 EC2 `J15A102`에 배치할 공용 서비스의 Docker Compose 설정을 관리한다.
70번의 서비스·네트워크 구조에 **71번의 PostgreSQL named volume 연결을 추가한 상태**다.
실제 DB 기동과 영속화 검증은 73번의 인증 설정을 완료한 뒤 진행한다.

## 파일 구성

- `compose.yaml`: 공용 Compose 프로젝트, PostgreSQL 서비스·데이터 Volume, 공용 네트워크 정의
- `README.md`: 구성 의도, 검증 방법, 후속 이슈의 작업 범위

## 기본 구성

- 프로젝트 이름: `s15p21a102-infra`
- 서비스 이름: `postgres`
- 이미지: 공식 `postgres:17-bookworm`. 메이저 버전은 17로 고정하며 패치 버전은 태그 갱신에 따라 달라질 수 있다.
- 재시작 정책: `unless-stopped`. 운영자가 명시적으로 중지한 컨테이너는 중지 상태를 유지한다.
- 공용 네트워크: `s15p21a102-shared` (`bridge`)

공용 네트워크는 이 Compose 프로젝트에서 생성·관리한다.
향후 같은 EC2의 백엔드 Compose는 이 네트워크를 외부 네트워크로 참조하여
서비스 이름 `postgres`로 접근할 수 있다. 다른 EC2까지 연결하는 네트워크는 아니다.

현재 `ports`를 선언하지 않아 DB 포트를 호스트에 공개하지 않는다.
같은 Docker 네트워크의 컨테이너 사이 통신과 호스트 포트 공개는 별개다.
UFW 변경이나 EC2 배포 작업은 이번 범위에 포함하지 않는다.

## 현재 단계의 제한

- DB 인증 환경변수가 없으므로 이 파일만으로 최초 PostgreSQL 초기화를 완료할 수 없다.
- 비밀번호 하드코딩이나 인증을 우회하는 `trust` 설정을 사용하지 않는다.
- 데이터 Volume 연결은 구성했지만 실제 DB 기동 및 영속화 검증은 아직 수행하지 않았다.
- 후속 설정 전에는 `docker compose up`으로 공용 DB를 배포하거나 실제 데이터를 저장하지 않는다.
- 이번 작업에서는 `.env` 파일을 생성하거나 실제 비밀번호·키를 저장하지 않는다.

## 구성 검증

Docker Compose v2가 설치된 환경에서 저장소 루트를 기준으로 실행한다.
아래 명령은 컨테이너를 실행하지 않고 Compose 구성을 검증한다.

```sh
docker compose -f infra/compose.yaml config --quiet
docker compose -f infra/compose.yaml config --services
docker compose -f infra/compose.yaml config --networks
```

서비스 목록에는 `postgres`, 네트워크 목록에는 `shared`가 표시되어야 한다.
구성 검증 통과는 DB 기동이나 영속화 검증을 의미하지 않는다.

## 데이터 영속화

Compose의 `postgres_data`는 Docker named volume `s15p21a102-postgres-data`를 사용한다.
이를 PostgreSQL 17 이미지의 기본 데이터 디렉터리 `/var/lib/postgresql/data`에 연결한다.
DB 파일은 컨테이너의 임시 파일시스템이 아니라 Docker 호스트의 Volume에 저장되므로,
컨테이너를 재시작하거나 재생성해도 같은 Volume을 연결하면 기존 데이터를 사용한다.
별도의 `PGDATA` 환경변수는 설정하지 않는다.

- `docker compose -f infra/compose.yaml restart postgres`는 컨테이너를 재시작한다.
- `docker compose -f infra/compose.yaml up -d --force-recreate postgres`는 컨테이너를 재생성하되 기존 named volume을 재사용한다.
- 일반 `docker compose down`은 named volume을 삭제하지 않지만, 공용 네트워크와 서비스에 영향을 주므로 운영 중 실행에 주의한다.
- **`docker compose down -v` 또는 `--volumes` 옵션은 DB Volume과 데이터를 삭제할 수 있으므로 사용하지 않는다.** Volume 직접 삭제 및 Volume을 포함한 prune 명령도 주의한다.
- Volume 이름·마운트 경로를 임의로 변경하지 않는다. 같은 호스트의 다른 DB 인스턴스에 이 Volume을 동시에 연결하지 않는다.
- 기존 익명 Volume의 데이터는 자동으로 이전되지 않는다. 이미 사용 중인 DB가 있다면 백업·이관 후 적용한다.
- 이 구성은 PostgreSQL 17 기준이다. 메이저 버전 업그레이드는 이미지 태그 변경만으로 진행하지 않는다.
- Volume은 백업이 아니다. EC2 디스크 손실·Volume 삭제에 대비한 별도 백업이 필요하다.

### 추후 EC2 검증 순서

73번 인증 설정을 완료한 뒤, 테스트 DB와 확정된 DB 계정으로 검증한다.
아래 과정은 이번 작업에서 실행하지 않았으며, 모든 Compose 명령은 저장소 루트 기준이다.

1. `docker compose -f infra/compose.yaml up -d postgres`로 기동하고 DB가 쿼리를 받을 준비가 되었는지 확인한다.
2. `docker volume inspect s15p21a102-postgres-data`로 Volume을 확인한다. `docker compose -f infra/compose.yaml ps -q postgres`로 얻은 컨테이너 ID를 `docker inspect <컨테이너-ID>`에 넣어 `Mounts`의 이름과 대상 경로가 위 설정과 일치하는지 확인한다.
3. DB에서 `SHOW data_directory;` 결과가 `/var/lib/postgresql/data`인지 확인한다. 테스트용 일반 테이블(임시 테이블 아님)에 식별 가능한 행을 INSERT하고 COMMIT한 뒤 조회 결과를 기록한다.
4. 위 `restart postgres` 명령 실행 후 DB 준비를 기다리고, 같은 테이블의 행이 그대로 조회되는지 확인한다.
5. 위 `up -d --force-recreate postgres` 명령 실행 후 DB 준비를 기다린다. 컨테이너 ID가 변경되었고, 같은 Volume이 연결되어 있으며, 기존 행이 그대로 조회되는지 확인한다.

검증 중 재시작·재생성 사이에 테스트 행을 다시 생성하거나 INSERT하지 않는다.

## 후속 작업

- **영속화 실행 검증**: 73번 인증 설정 완료 후 위 절차로 재시작·재생성 시 데이터 유지를 확인
- **S15P21A102-73**: 환경변수 연결, `.env.example`, Secret 제외 규칙, DB 접속 설정, 루프백 포트 바인딩 및 SSH 터널 접속 가이드

데이터 파이프라인과 추가 EC2 `J15A102A`의 실행 서비스는 이번 구성에 포함하지 않는다.

## 참고

- [PostgreSQL 공식 이미지](https://hub.docker.com/_/postgres)
- [Compose 네트워크](https://docs.docker.com/reference/compose-file/networks/)
- [Compose 서비스](https://docs.docker.com/reference/compose-file/services/)
- [Compose Volume](https://docs.docker.com/reference/compose-file/volumes/)
- [Compose down과 Volume 삭제 옵션](https://docs.docker.com/reference/cli/docker/compose/down/)
