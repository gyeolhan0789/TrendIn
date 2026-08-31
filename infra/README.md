# 공용 인프라

기본 EC2 `J15A102`에 배치할 공용 서비스의 Docker Compose 설정을 관리한다.
현재는 **S15P21A102-70의 서비스·네트워크 골격만 구성한 상태**이며,
실제 DB 기동과 운영은 71번·73번 설정을 완료한 뒤 진행한다.

## 파일 구성

- `compose.yaml`: 공용 Compose 프로젝트, PostgreSQL 서비스, 공용 네트워크 정의
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
- 명시적인 데이터 Volume 연결이 없다. 이미지가 생성하는 익명 Volume을 공용 DB의 영속화 구성으로 취급하지 않는다.
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

## 후속 작업

- **S15P21A102-71**: PostgreSQL named volume, 데이터 영속화, DB 초기화, 재시작·재생성 후 데이터 유지 검증
- **S15P21A102-73**: 환경변수 연결, `.env.example`, Secret 제외 규칙, DB 접속 설정, 루프백 포트 바인딩 및 SSH 터널 접속 가이드

데이터 파이프라인과 추가 EC2 `J15A102A`의 실행 서비스는 이번 구성에 포함하지 않는다.

## 참고

- [PostgreSQL 공식 이미지](https://hub.docker.com/_/postgres)
- [Compose 네트워크](https://docs.docker.com/reference/compose-file/networks/)
- [Compose 서비스](https://docs.docker.com/reference/compose-file/services/)
