# 데이터 EC2 배포 (J15A102A)

MinIO · Airflow · Spark 를 데이터 EC2 한 대에 올린다. 서비스 DB `forever102` 와 Redis 는
기본 EC2 `J15A102` 의 `infra/` 가 맡는다 ([infra/README.md](../infra/README.md)).

```
데이터 EC2 ── Docker 엔진 1개
├─ [datastore]  minio                                             상시 1 + 초기화 1
└─ [pipeline]   postgres · apiserver · scheduler · dag-processor  상시 4
                  ↳ 태스크가 뜰 때 이 안에서 spark-submit 이 돌고 끝난다
```

Spark 는 상시 서비스가 아니라 Airflow 컨테이너 안에서 깨어났다 끝난다. 그래서 컨테이너 수가
늘지 않는다 ([pipeline/spark/README.md](../pipeline/spark/README.md) "어떻게 도나").

## 1. 러너를 서버에 설치한다

GitLab 은 `.gitlab-ci.yml` 을 읽어 잡을 대기열에 올릴 뿐이고, 명령을 실제로 실행하는 것은
러너다. GitLab 화면에 러너가 보이더라도 상태가 `Never contacted` 면 등록만 돼 있고 서버에는
설치되지 않은 것이다. 그 상태에서는 파이프라인이 pending 에 멈춘다.

### 한 호스트에 두 벌을 등록한다

| 러너 | executor | 태그 | 맡는 잡 |
| --- | --- | --- | --- |
| 검증용 | `docker` | 없음 (untagged 허용) | `datastore:compose` · `datastore:guard` · `pipeline:verify` · `pipeline:verify-spark` |
| 배포용 | `shell` | `data-ec2` (untagged 거부) | `deploy:data-ec2` |

**검증 잡은 docker executor 여야 한다.** `.gitlab-ci.yml` 이 `image: apache/airflow:3.3.1-python3.12`
처럼 잡마다 다른 이미지를 지정하는데, shell executor 는 그 지정을 무시하고 호스트 셸에서 그대로
돌린다. 호스트에 airflow 도 pyspark 도 없으니 전부 실패한다.

**배포 잡은 shell executor 여야 한다.** docker executor 로 돌면 잡이 컨테이너 안에서 실행되는데,
compose 파일은 `./dags:/opt/airflow/dags` 처럼 상대 경로를 바인드 마운트한다. 그 경로는 도커
데몬이 사는 **호스트** 기준으로 풀리므로, 잡 컨테이너 안의 체크아웃을 가리키지 않는다. 소켓을
물려줘도 이 어긋남은 남는다. 체크아웃이 호스트 파일시스템에 있어야 마운트가 맞는다.

`gitlab-runner` 설치는 한 번이고, 그 위에 등록만 두 번 한다.

### 설치

Ubuntu 기준이다.

```sh
curl -L "https://packages.gitlab.com/install/repositories/runner/gitlab-runner/script.deb.sh" | sudo bash
sudo apt-get install -y gitlab-runner rsync
```

### 토큰을 받는다

GitLab 프로젝트의 **Settings → CI/CD → Runners** 에서 `New project runner` 를 누른다. 만들 때
화면에서 정하는 것이 둘이다.

- **Tags** — 배포용에는 `data-ec2` 를 넣고 `Run untagged jobs` 를 **끈다.** 이 러너가 검증 잡까지
  집어가면 호스트 셸에서 `pytest` 를 찾다 실패한다.
- 검증용에는 태그를 비우고 `Run untagged jobs` 를 **켠다.**

만들면 `glrt-` 로 시작하는 토큰이 **한 번만** 표시된다. 놓치면 다시 볼 수 없으니 그 러너를 지우고
새로 만든다. 이미 있는 `Never contacted` 러너의 토큰을 잃어버렸다면 지우고 다시 만드는 편이 빠르다.

### 등록

```sh
# 배포용 — shell
sudo gitlab-runner register --non-interactive \
  --url https://lab.ssafy.com/ \
  --token "glrt-<배포용 토큰>" \
  --executor shell \
  --description "data-ec2 shell (deploy)"

# 검증용 — docker
sudo gitlab-runner register --non-interactive \
  --url https://lab.ssafy.com/ \
  --token "glrt-<검증용 토큰>" \
  --executor docker \
  --docker-image alpine:3.20 \
  --description "data-ec2 docker (verify)"
```

`--docker-image` 는 `.gitlab-ci.yml` 이 `image:` 를 적지 않은 잡의 기본값일 뿐이다. 우리 검증
잡은 셋 다 자기 이미지를 지정하므로 이 값을 쓰지 않는다.

### 배포용 러너에 도커 권한을 준다

shell executor 는 `gitlab-runner` 계정으로 명령을 실행한다. 그 계정이 도커 그룹에 없으면
배포 스크립트가 첫 줄에서 "도커 데몬에 붙지 못했다" 로 멈춘다.

```sh
sudo usermod -aG docker gitlab-runner
sudo systemctl restart gitlab-runner
sudo -u gitlab-runner docker info >/dev/null && echo "도커 접근 확인"
```

도커 그룹은 사실상 root 와 같은 권한이다. 이 호스트에서 그 계정이 하는 일이 배포뿐이라
받아들이는 것이고, 아무 러너에나 주는 설정은 아니다.

### 확인

```sh
sudo gitlab-runner list
sudo systemctl status gitlab-runner
```

GitLab 화면에서 두 러너의 상태가 `Never contacted` 에서 초록불로 바뀌어야 한다.

## 2. 서버 최초 세팅

배포는 저장소 체크아웃에서 바로 띄우지 않고 `/srv/trendin` 으로 옮긴 뒤 띄운다. 러너의 빌드
디렉터리는 잡마다 지워질 수 있는데, 서버에 남아야 하는 것이 셋 있기 때문이다 — `.env` 두 벌,
530 MB 짜리 Spark jar, Airflow 로그다.

```sh
sudo mkdir -p /srv/trendin
sudo chown gitlab-runner:gitlab-runner /srv/trendin
```

`pipeline/logs` 는 배포 스크립트가 만든다. 이미 root 소유로 만들어져 있으면 스크립트가
멈추면서 고칠 명령을 알려준다. 도커가 없는 바인드 소스를 root 로 만들어 두면 Airflow 가
그 안에 못 쓰기 때문이다.

`.env` 두 벌을 만든다. **Git 에 올리지 않는다.** 값은 팀이 서버에서 만든다.

```sh
sudo -u gitlab-runner mkdir -p /srv/trendin/datastore /srv/trendin/pipeline
cd /srv/trendin

# 저장소 계층 — MinIO 계정 세 벌
sudo -u gitlab-runner sh -c '(umask 077; cp -n <저장소>/datastore/.env.example datastore/.env)'
sudoedit datastore/.env

# Airflow · Spark
sudo -u gitlab-runner sh -c '(umask 077; cp -n <저장소>/pipeline/.env.example pipeline/.env)'
sudoedit pipeline/.env
```

채워야 하는 값과 그 뜻은 각 `.env.example` 의 주석에 있다. 서로 맞춰야 하는 것 둘만 여기 적는다.

- `pipeline/.env` 의 `TRENDIN_MINIO_*` 는 `datastore/.env` 의 `MINIO_CRAWLER_*` 와 같은 값이어야
  한다. 크롤러가 쓰는 키다.
- `pipeline/.env` 의 `TRENDIN_MINIO_SPARK_*` 는 `datastore/.env` 의 `MINIO_SPARK_*` 와 같은 값이어야
  한다. 이쪽은 읽기 전용이라 권한이 다르다.

`AIRFLOW_UID` 는 `gitlab-runner` 계정의 `id -u` 값으로 둔다. 다르면 마운트한 `logs/` 에 Airflow 가
쓰지 못한다.

## 3. 배포한다

### CI 에서

dev 에 `datastore/` 나 `pipeline/` 변경이 머지되면 `deploy:data-ec2` 가 자동으로 돈다. 따로 누를
것이 없다. 문서나 백엔드만 고친 머지에서는 잡 자체가 만들어지지 않는다.

**되돌릴 수 없는 변경은 `datastore:guard` 가 MR 에서 막는다.** 재배포는 `minio-init` 을 다시
돌리고, 그것이 버킷 설정을 덮어쓴다. 아래는 적용된 뒤 커밋을 되돌려도 지워진 데이터가
돌아오지 않는다.

| 무엇 | 어디 | 되돌리면 |
| --- | --- | --- |
| `MINIO_RAW_EXPIRE_DAYS` 축소 | `datastore/compose.yaml` | 이미 만료된 원문은 안 돌아온다 |

브로커가 있던 시절에는 토픽 보존 넷도 여기서 막았다. Kafka 를 걷으면서(제거 3/3) 그 값들이
없어졌고, 남은 것은 원문 만료 하나다.

일부러 바꾸는 경우에는 커밋 메시지에 `Allow-destructive: <키>` 한 줄을 넣으면 통과한다. 그 줄이
MR 에 그대로 보여서 리뷰가 무엇을 승인하는지 안다. 값의 근거는 각 파일 주석과
[datastore/README.md](../datastore/README.md) "보관 정책" 에 있다.

서버의 `.env` 로 값을 덮으면 Git 에 안 남아 이 검사가 못 잡는다. 그때는 사람이 확인해야 한다.

### 손으로

CI 가 멈춘 날에도 같은 절차로 올릴 수 있다. CI 잡이 부르는 것이 정확히 이 스크립트다.

```sh
cd /srv/trendin
scripts/deploy-data-ec2.sh
```

스크립트가 하는 일은 다섯 단계다.

1. MinIO 를 띄우고 healthy 를 기다린다. 네트워크 `s15p21a102-data` 의 주인이라 항상 먼저다
2. Spark 런타임 jar 를 받는다. 이미 있으면 건너뛴다
3. 이미지를 두 단계로 만든다 — 런타임 이미지(JRE·pyspark·torch·GLiNER) 위에 우리 패키지
4. Airflow 를 Spark 오버레이와 함께 띄우고 healthy 를 기다린다
5. `datastore/scripts/verify.sh` 로 저장소 계약을 확인한다

끝나면 태그 없는 이미지와 오래된 빌드 캐시를 지운다. 볼륨과 태그가 붙은 이미지는 건드리지
않는다 — 남길 캐시의 양은 `BUILD_CACHE_KEEP` 으로 조절한다.

3단계에서 실제로 다시 만들어지는 것은 보통 우리 패키지 한 층(약 30초)뿐이다. 그 아래
3.5 GB 는 `spark/versions.sh` 가 바뀔 때만 다시 만든다 — 버전을 올린 날에는 이 단계가
5~6분 걸리고, 그것이 정상이다.

바꿀 수 있는 환경변수 셋이다.

| | 기본값 | 언제 바꾸나 |
| --- | --- | --- |
| `DEPLOY_ROOT` | `/srv/trendin` | 배포 디렉터리를 옮길 때 |
| `HEALTH_TIMEOUT` | `300` | 첫 배포에서 이미지 빌드가 길어 healthy 대기가 모자랄 때 |
| `SKIP_VERIFY` | `0` | 검증만 건너뛰고 빨리 올릴 때. 평소에는 켜두지 않는다 |
| `BUILD_CACHE_KEEP` | `20GB` | 배포 끝에 남길 빌드 캐시의 양. `0` 으로 두면 다음 배포가 이미지를 처음부터 만든다 |

## 4. 확인

```sh
cd /srv/trendin
docker compose -f datastore/compose.yaml ps
docker compose -f pipeline/compose.yaml -f pipeline/spark/compose.spark.yaml ps
```

`minio-init` 과 `airflow-init` 은 한 번 돌고 `Exited (0)` 으로 남는다. 정상이다.

Airflow UI 는 `127.0.0.1:8080` 에만 열려 있다. 공인망에 열지 않으므로 SSH 터널로 본다.

```sh
ssh -i "J15A102T.pem" -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:8080:127.0.0.1:8080 \
  ubuntu@<데이터 EC2>
```

### 적재할 곳에 스키마가 먼저 있어야 한다

**파이프라인은 서비스 테이블에 DDL 을 걸지 않는다.** 그 표의 소유자는 백엔드이고 Spark 는 자기
`pl_*` 만 만든다. 그래서 적재 대상 DB 에 `contents` 가 없으면 `ingest` 가 그 배치를 통째로
건너뛴다 — **`curated` 에는 파일이 쓰이고 `contents` 에는 아무것도 없는 상태로 초록불이 켜진다.**
뒤따르는 `extract` 는 그 기사의 `id` 를 찾지 못한다.

스키마는 백엔드가 Flyway 로 만든다
(`backend/src/main/resources/db/migration/V1__baseline.sql`). 기존 DB 에는 V1 이 수동으로 적용돼
있어서 첫 배포에만 `DEV_FLYWAY_BASELINE_ON_MIGRATE=true` 를 거쳐야 하고, 그 절차는
[infra/README.md](../infra/README.md) "Flyway" 절에 있다.

DAG 을 켜기 전에 기본 EC2 에서 표가 있는지 본다.

```sh
docker compose --env-file infra/.env -f infra/compose.yaml exec postgres \
  psql -U ssafy -d forever102 -c \
  "select tablename from pg_tables where schemaname='public' order by 1"
```

`contents` · `keywords` · `keyword_contents` · `keyword_metrics` · `keyword_metric_history` ·
`trends` 여섯이 보여야 한다.

데이터 EC2 에서 그 DB 로 가는 경로는 기본 EC2 쪽 설정이다 — `infra/.env` 의
`POSTGRES_BIND_IP` 와 보안 그룹을 [infra/README.md](../infra/README.md) "데이터 EC2에서 서비스
DB 접근" 절대로 맞춘다.

### DAG 은 꺼진 채로 생긴다

`AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION` 이 `true` 라, 배포가 끝나고 목록에 보여도 아무것도
돌지 않는다. 수집 둘(`fashion_collect` · `dev_collect`)과 Spark 셋(`spark_ingest` ·
`spark_extract` · `spark_aggregate`)을 UI 에서 켠다.

**Spark 셋은 한꺼번에 켜지 않는다.** `ingest` 를 켜서 `curated` 에 파일이 놓이고 `contents` 에
기사가 들어가는 것을 확인한 뒤 `extract` 를, 그 결과로 `keywords` 가 채워진 뒤 `aggregate` 를
켠다. 뒤의 둘은 앞의 결과를 입력으로 받으므로 앞이 비어 있으면 0행으로 끝나는데, **그 0행이
실패가 아니라 성공으로 보인다.**

Spark DAG 셋은 오버레이(`spark/compose.spark.yaml`)를 얹고 띄웠을 때만 돈다. 기본 compose 로만
띄우면 `submit.sh: No such file` 로 죽는다.

단계마다 행이 실제로 늘었는지 센다. Airflow 의 초록불은 0행과 구분되지 않는다.

```sh
docker compose --env-file infra/.env -f infra/compose.yaml exec postgres \
  psql -U ssafy -d forever102 -c \
  "select 'contents' t, count(*) from contents
    union all select 'keywords', count(*) from keywords
    union all select 'keyword_contents', count(*) from keyword_contents
    union all select 'keyword_metrics', count(*) from keyword_metrics
    union all select 'keyword_metric_history', count(*) from keyword_metric_history
    union all select 'trends', count(*) from trends"
```

**`keyword_metrics` 에 `24H` 행이 없는 것은 결함이 아닐 수 있다.** 기준일 D 는 어제이고, 그
하루에 **발행된** 문서가 없으면 그 구간의 지표가 만들어지지 않는다. 백필로 옛 날짜를 채운
직후에는 `7D` · `30D` 만 나오는 것이 정상이다.

## 4.1 Kafka 를 걷은 첫 배포에서 한 번만

**브로커 컨테이너는 배포가 저절로 지우지 않는다.** `docker compose up -d` 는 파일에서 사라진
서비스를 고아(orphan)로 두고 경고만 낸다. 그래서 이 변경을 배포한 뒤에도 `kafka` ·
`kafka-init` · `kafka-storage-init` 이 그대로 떠 있고, 29092 를 계속 물고 있다.

서버에서 한 번 지운다.

```sh
cd /srv/trendin
docker compose -f datastore/compose.yaml ps -a          # 고아가 보인다
docker compose -f datastore/compose.yaml up -d --remove-orphans
docker compose -f datastore/compose.yaml ps             # minio 와 minio-init 만 남는다
```

`--remove-orphans` 를 배포 스크립트에 상시로 넣지 않는 이유는, 그 플래그가 compose 파일에
없는 컨테이너를 **묻지 않고** 지우기 때문이다. 이번처럼 지울 것이 무엇인지 아는 자리에서
사람이 한 번 쓰는 편이 낫다.

볼륨은 컨테이너를 지워도 남는다. 안에 든 것은 보존 기간이 지난 옛 메시지뿐이라 지워도 된다.

```sh
docker volume ls | grep kafka
docker volume rm s15p21a102-kafka-data
```

보안 그룹에서 29092 를 열어 뒀다면 같이 닫는다. 인증 없는 PLAINTEXT 리스너였고 이제 아무도
듣지 않는다.

## 5. 내릴 때와 되돌릴 때

```sh
cd /srv/trendin
# 붙어 있는 쪽을 먼저 내린다. datastore 를 먼저 내리면 네트워크가 사라져 pipeline 이 끊긴다
docker compose -f pipeline/compose.yaml -f pipeline/spark/compose.spark.yaml stop
docker compose -f datastore/compose.yaml stop
```

**`down -v` 는 쓰지 않는다.** MinIO 원문 · Airflow 메타 DB 볼륨이 함께 사라진다.
`stop` 은 컨테이너만 세우고 볼륨을 남긴다.

이미지를 옛 커밋으로 되돌리려면 그 커밋을 체크아웃해 스크립트를 다시 돌린다. 레지스트리를 쓰지
않으므로 태그로 되감는 경로는 없다 — 서버에서 다시 빌드하는 것이 되돌리는 방법이다.

## 6. 지금 없는 것

- **파이프라인 표를 가르는 스키마.** 지금 구조로 서비스 DB 에 붙이면 `pl_*` 스물여덟 개가
  `forever102` 의 `public` 에 함께 생긴다. `pipeline` 스키마를 만들고 접속의 `search_path` 를
  `pipeline,public` 으로 두면 갈라지지만, 스키마 생성과 권한은 서비스 DB 쪽 일이다.
- **레지스트리.** 이미지를 서버에서 빌드한다. CI 에서 빌드해 올리는 경로로 바꾸려면 compose 의
  `image:` 이름을 전부 바꿔야 한다.
- **백엔드 · 프론트 CD.** 기본 EC2 쪽은 이 문서의 범위가 아니다.
- **롤백 자동화 · 무중단 배포.** `up -d` 가 바뀐 컨테이너만 재생성하므로 그 사이 잠깐 끊긴다.
