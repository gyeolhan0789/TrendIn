# 데이터 EC2 배포 (J15A102A)

Kafka · MinIO · Airflow · Spark 를 데이터 EC2 한 대에 올린다. 서비스 DB `forever102` 와 Redis 는
기본 EC2 `J15A102` 의 `infra/` 가 맡는다 ([infra/README.md](../infra/README.md)).

```
데이터 EC2 ── Docker 엔진 1개
├─ [datastore]  kafka · minio                                     상시 2 + 초기화 3
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

# 저장소 계층 — MinIO 계정 세 벌과 Kafka 외부 주소
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

**되돌릴 수 없는 변경 다섯은 `datastore:guard` 가 MR 에서 막는다.** 재배포는 `kafka-init` ·
`minio-init` 을 다시 돌리고, 그것들이 토픽과 버킷 설정을 덮어쓴다. 아래 다섯은 적용된 뒤
커밋을 되돌려도 지워진 데이터가 돌아오지 않는다.

| 무엇 | 어디 | 되돌리면 |
| --- | --- | --- |
| `KAFKA_LOG_RETENTION_HOURS` 축소 | `datastore/compose.yaml` | 이미 지워진 메시지는 안 돌아온다 |
| `KAFKA_TOPIC_RETENTION_MS` 축소 | `datastore/compose.yaml` | 이미 지워진 메시지는 안 돌아온다 |
| `MINIO_RAW_EXPIRE_DAYS` 축소 | `datastore/compose.yaml` | 이미 만료된 원문은 안 돌아온다 |
| `KAFKA_TOPIC_PARTITIONS` 증가 | `datastore/compose.yaml` | 파티션은 줄이지 못한다. 토픽을 지워야 한다 |
| `KAFKA_TOPIC_CLEANUP_POLICY=compact` | `datastore/compose.yaml` | 같은 키의 옛 메시지가 정리된 뒤다 |

일부러 바꾸는 경우에는 커밋 메시지에 `Allow-destructive: <키>` 한 줄을 넣으면 통과한다. 그 줄이
MR 에 그대로 보여서 리뷰가 무엇을 승인하는지 안다. 값의 근거는 각 파일 주석과
[datastore/README.md](../datastore/README.md) "토픽 설정" · "보관 정책" 에 있다.

서버의 `.env` 로 값을 덮으면 Git 에 안 남아 이 검사가 못 잡는다. 그때는 사람이 확인해야 한다.

### 손으로

CI 가 멈춘 날에도 같은 절차로 올릴 수 있다. CI 잡이 부르는 것이 정확히 이 스크립트다.

```sh
cd /srv/trendin
scripts/deploy-data-ec2.sh
```

스크립트가 하는 일은 다섯 단계다.

1. Kafka · MinIO 를 띄우고 healthy 를 기다린다. 네트워크 `s15p21a102-data` 의 주인이라 항상 먼저다
2. Spark 런타임 jar 를 받는다. 이미 있으면 건너뛴다
3. 이미지를 두 단계로 만든다 — 팀 공용 이미지 → JRE·pyspark 를 얹은 파생 이미지
4. Airflow 를 Spark 오버레이와 함께 띄우고 healthy 를 기다린다
5. `datastore/scripts/verify.sh` 로 저장소 계약을 확인한다

바꿀 수 있는 환경변수 셋이다.

| | 기본값 | 언제 바꾸나 |
| --- | --- | --- |
| `DEPLOY_ROOT` | `/srv/trendin` | 배포 디렉터리를 옮길 때 |
| `HEALTH_TIMEOUT` | `300` | 첫 배포에서 이미지 빌드가 길어 healthy 대기가 모자랄 때 |
| `SKIP_VERIFY` | `0` | 검증만 건너뛰고 빨리 올릴 때. 평소에는 켜두지 않는다 |

## 4. 확인

```sh
cd /srv/trendin
docker compose -f datastore/compose.yaml ps
docker compose -f pipeline/compose.yaml -f pipeline/spark/compose.spark.yaml ps
```

`minio-init` · `kafka-init` · `kafka-storage-init` · `airflow-init` 은 한 번 돌고 `Exited (0)` 으로
남는다. 정상이다.

Airflow UI 는 `127.0.0.1:8080` 에만 열려 있다. 공인망에 열지 않으므로 SSH 터널로 본다.

```sh
ssh -i "J15A102T.pem" -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:8080:127.0.0.1:8080 \
  ubuntu@<데이터 EC2>
```

## 5. 내릴 때와 되돌릴 때

```sh
cd /srv/trendin
# 붙어 있는 쪽을 먼저 내린다. datastore 를 먼저 내리면 네트워크가 사라져 pipeline 이 끊긴다
docker compose -f pipeline/compose.yaml -f pipeline/spark/compose.spark.yaml stop
docker compose -f datastore/compose.yaml stop
```

**`down -v` 는 쓰지 않는다.** MinIO 원문 · Kafka 로그 · Airflow 메타 DB 볼륨이 함께 사라진다.
`stop` 은 컨테이너만 세우고 볼륨을 남긴다.

이미지를 옛 커밋으로 되돌리려면 그 커밋을 체크아웃해 스크립트를 다시 돌린다. 레지스트리를 쓰지
않으므로 태그로 되감는 경로는 없다 — 서버에서 다시 빌드하는 것이 되돌리는 방법이다.

## 6. 지금 없는 것

- **Airflow 가 Spark Job 을 부르는 DAG.** 컨테이너 안에 `spark-submit` 과 jar 는 준비되지만,
  `dags/` 에는 수집 DAG 둘뿐이고 `ingest` · `extract` · `aggregate` 를 깨우는 태스크가 아직 없다.
  이 배포로 도는 것은 수집까지다.
- **레지스트리.** 이미지를 서버에서 빌드한다. CI 에서 빌드해 올리는 경로로 바꾸려면 compose 의
  `image:` 이름을 전부 바꿔야 한다.
- **백엔드 · 프론트 CD.** 기본 EC2 쪽은 이 문서의 범위가 아니다.
- **롤백 자동화 · 무중단 배포.** `up -d` 가 바뀐 컨테이너만 재생성하므로 그 사이 잠깐 끊긴다.
