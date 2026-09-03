# datastore — 수집 계층 저장소 (Kafka · MinIO)

크롤러가 원문을 MinIO 에 올리고 그 위치를 Kafka 에 발행하면, Spark 가 이벤트를 받아 MinIO 에서 읽는다.
이 디렉터리는 그 두 저장소만 띄운다. Airflow 는 `pipeline/`, Spark 는 별도 프로젝트다.

- 계약(버킷 이름, 객체 경로, 토픽 이름, 이벤트 형식): `pipeline/docs/data-pipeline-design.md` 4·5 장
- 결정과 근거: Jira `S15P21A102-156`

## 어디에 뜨나

| EC2 | compose 프로젝트 | 담는 것 |
|---|---|---|
| 기본 `J15A102` | `infra/` · `s15p21a102-infra` | 서비스 DB `forever102` |
| 데이터 `J15A102A` | **`datastore/` · `s15p21a102-datastore`** | **Kafka · MinIO** |
| 데이터 `J15A102A` | `pipeline/` · `s15p21a102-pipeline` | Airflow · 크롤러 · Airflow 메타 DB |
| 데이터 `J15A102A` | `spark/` (예정) | Spark |

데이터 EC2 안의 세 프로젝트는 이 프로젝트가 만드는 네트워크 `s15p21a102-data` 로 이어진다.
**이 프로젝트가 네트워크 주인이라 항상 먼저 떠야 한다.** 없으면 나머지가 뜨다 실패한다.

## 구조

```
datastore/
├─ compose.yaml        kafka · kafka-storage-init · kafka-init · minio · minio-init
├─ minio-init/init.sh  버킷 · 정책 · 계정 생성 (매 up 마다 멱등)
├─ scripts/verify.sh   완료 조건 검증. 실패하면 exit 1
├─ .env.example        → .env 로 복사해 채운다
└─ README.md
```

| 서비스 | 하는 일 |
|---|---|
| `kafka` | KRaft 단일 노드 브로커. ZooKeeper 없음 |
| `kafka-storage-init` | 빈 볼륨을 브로커 uid(1000) 소유로 넘긴다. 한 번 돌고 끝 |
| `kafka-init` | 계약 토픽 `raw-file-ready` 생성. 다시 돌려도 같다 |
| `minio` | 원문 객체 저장소. S3 호환 |
| `minio-init` | 버킷 · 정책 · 계정 생성. 다시 돌려도 같다 |

## 처음 실행

```sh
(umask 077; cp -n datastore/.env.example datastore/.env)
chmod 600 datastore/.env
nano datastore/.env      # MinIO 계정 세 벌, KAFKA_EXTERNAL_HOST 를 채운다

docker compose -f datastore/compose.yaml config --quiet
docker compose -f datastore/compose.yaml up -d
docker compose -f datastore/compose.yaml ps      # 전부 healthy 인지
```

`minio-init` · `kafka-init` · `kafka-storage-init` 은 한 번 돌고 `Exited (0)` 으로 남는다. 정상이다.

## 접속 정보

| 어디서 | Kafka | MinIO |
|---|---|---|
| 같은 EC2 의 다른 compose (Airflow · Spark) | `kafka:9092` | `http://minio:9000` |
| 호스트 · 다른 EC2 | `${KAFKA_EXTERNAL_HOST}:29092` | `http://<호스트>:9000`, 콘솔 `:9001` |

붙는 쪽 compose 는 이렇게 쓴다.

```yaml
networks:
  data:
    name: s15p21a102-data
    external: true
```

## 키 세 벌

| 키 | 권한 | 쓰는 곳 |
|---|---|---|
| `MINIO_ROOT_*` | 관리자 | `minio-init` 과 운영자만 |
| `MINIO_CRAWLER_*` | 버킷 목록 · 객체 put/get · 멀티파트 | 크롤러 → `pipeline/.env` 의 `TRENDIN_MINIO_*` |
| `MINIO_SPARK_*` | 버킷 목록 · 객체 get | Spark |

크롤러 키에 삭제 권한은 없다. Spark 키로 쓰기를 시도하면 거부된다. 애플리케이션에 root 키를 주지 않는다.
`.env` 를 고쳐도 이미 만들어진 계정은 그대로다. 값을 바꿨으면 `docker compose -f datastore/compose.yaml up -d minio-init` 을 다시 돌려 반영한다.

## 기동과 중지

```sh
docker compose -f datastore/compose.yaml up -d
docker compose -f datastore/compose.yaml stop      # 중지 (재부팅해도 다시 뜨지 않는다)
docker compose -f datastore/compose.yaml start
docker compose -f datastore/compose.yaml restart kafka minio
```

`restart: unless-stopped` 라 EC2 가 재부팅해도 Docker 데몬이 뜨면서 같이 올라온다. `stop` 으로 명시적으로 내린 컨테이너는 그대로 내려가 있다.

**`down -v` 는 쓰지 않는다.** 볼륨 `s15p21a102-kafka-data` · `s15p21a102-minio-data` 와 그 안의 원문이 함께 사라진다.
`down` 만 해도 네트워크가 사라져 `pipeline` 이 끊기므로, 저장소를 내릴 때는 붙어 있는 쪽을 먼저 내린다.

## 검증 스크립트

완료 조건(Jira `S15P21A102-156` AC 1~4) 을 한 번에 확인한다. 실패하면 `exit 1` 이다.

```sh
./datastore/scripts/verify.sh
```

Windows 는 Git Bash 에서 돌린다. PowerShell·CMD 는 `.sh` 를 실행하지 못한다.
검증은 전부 컨테이너 안에서 일어나므로 호스트에는 `docker` 만 있으면 된다.

| 확인하는 것 | AC |
|---|---|
| `kafka` · `minio` healthy, `restart=unless-stopped` | 1 |
| 네트워크 `s15p21a102-data` 존재, 그 안에서 `kafka:9092` · `minio:9000` 도달 | 2 |
| 토픽 존재, produce → consume 왕복 | 3 |
| 크롤러 키 put/get, Spark 키 get, **Spark 키 write 거부** | 4 |

검증용 객체는 `_verify/` 아래에만 만들고 끝나면 지운다. 수집 데이터는 건드리지 않는다.
Kafka 에 넣은 `_verify` 메시지는 토픽에 남는다. 보존 기간이 지나면 사라진다.

## 손으로 확인할 때

스크립트가 어디서 막혔는지 볼 때 쓴다.

```sh
cd datastore

# 토픽 목록
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list

# 테스트 메시지 발행
echo 'reddit:{"event_id":"test"}' | docker compose exec -T kafka \
  /opt/kafka/bin/kafka-console-producer.sh --bootstrap-server localhost:9092 \
  --topic raw-file-ready --property parse.key=true --property key.separator=:

# 소비
docker compose exec kafka /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 --topic raw-file-ready --from-beginning --max-messages 1

# MinIO — 크롤러 키로 put/get
docker run --rm --network s15p21a102-data \
  -e MC_HOST_crawler="http://$MINIO_CRAWLER_ACCESS_KEY:$MINIO_CRAWLER_SECRET_KEY@minio:9000" \
  --entrypoint sh minio/mc:RELEASE.2025-08-13T08-35-41Z -c \
  'echo hi > /tmp/t && mc cp /tmp/t crawler/raw-data/_healthcheck && mc cat crawler/raw-data/_healthcheck'

# MinIO — Spark 키로 쓰기. Insufficient permissions 로 끝나야 한다
docker run --rm --network s15p21a102-data \
  -e MC_HOST_spark="http://$MINIO_SPARK_ACCESS_KEY:$MINIO_SPARK_SECRET_KEY@minio:9000" \
  --entrypoint sh minio/mc:RELEASE.2025-08-13T08-35-41Z -c \
  'echo hi > /tmp/t && mc cp /tmp/t spark/raw-data/should-fail'
```

Spark 키 쓰기가 성공하면 정책이 잘못 붙은 것이다.
콘솔(`:9001`) 은 객체 브라우저다. 계정·정책 관리는 콘솔이 아니라 `mc admin` 으로 한다.

## EC2 에서 바꾸는 것

`.env` 만 다르다.

- `KAFKA_EXTERNAL_HOST` — 밖에서 붙는 클라이언트가 실제로 닿는 주소. 브로커가 이 값을 그대로 돌려주므로 틀리면 첫 연결만 되고 그 다음이 끊긴다.
- `KAFKA_EXTERNAL_BIND` · `MINIO_BIND` — 기본은 `127.0.0.1`. 다른 호스트가 붙어야 할 때만 `0.0.0.0` 으로 바꾼다.
- `KAFKA_CLUSTER_ID` — 첫 기동 때 로그 디렉터리에 새겨진다. 나중에 바꾸면 기존 볼륨을 못 읽는다.
- 자격증명은 서버에서 생성한다. `.env` 는 Git 에 올리지 않는다.

같은 EC2 안에서만 쓸 거면 바인드를 `127.0.0.1` 로 두는 편이 안전하다. 컨테이너끼리는 `s15p21a102-data` 로 붙으므로 호스트 포트가 없어도 된다.

포트를 `0.0.0.0` 으로 여는 경우, Kafka(29092) 는 인증 없는 PLAINTEXT 이고 MinIO(9000·9001) 는 키 하나로 열린다.
보안 그룹에서 팀 대역과 필요한 인스턴스만 허용하고 공인망 전체에 열지 않는다. Docker 가 공개한 포트는 UFW 규칙을 우회할 수 있으므로 보안 그룹 쪽에서 막는다.

## 지금 없는 것

Kafka 인증(SASL)·TLS, 다중 브로커, DLQ 토픽, MinIO 버전 관리·수명 주기 규칙, 백업.
DLQ 는 담당 2 의 후속 이슈, 나머지는 필요해질 때 이슈를 판다.
