# datastore — 수집 계층 저장소 (Kafka · MinIO)

크롤러가 원문을 MinIO 에 올리고 그 위치를 Kafka 에 발행하면, Spark 가 이벤트를 받아 MinIO 에서 읽는다.
이 디렉터리는 그 두 저장소만 띄운다. Airflow 는 `pipeline/`, Spark 는 별도 프로젝트다.

- 계약(버킷 이름, 객체 경로, 토픽 이름, 이벤트 형식): `pipeline/docs/data-pipeline-design.md` 4·5 장
- 실행 환경 결정과 근거: Jira `S15P21A102-156`
- 토픽 설정 · 보관 정책 결정과 근거: Jira `S15P21A102-157` (아래 "토픽 설정" · "보관 정책" 절)

## 어디에 뜨나

| EC2 | compose 프로젝트 | 담는 것 |
|---|---|---|
| 기본 `J15A102` | `infra/` · `s15p21a102-infra` | 서비스 DB `forever102` |
| 데이터 `J15A102A` | **`datastore/` · `s15p21a102-datastore`** | **Kafka · MinIO** |
| 데이터 `J15A102A` | `pipeline/` · `s15p21a102-pipeline` | Airflow · 크롤러 · Airflow 메타 DB |
| 데이터 `J15A102A` | Spark — 별도 프로젝트 없음 | `pipeline/spark/compose.spark.yaml` 이 Airflow 이미지에 얹는다 (S15P21A102-169) |

데이터 EC2 안의 두 프로젝트는 이 프로젝트가 만드는 네트워크 `s15p21a102-data` 로 이어진다.
**이 프로젝트가 네트워크 주인이라 항상 먼저 떠야 한다.** 없으면 나머지가 뜨다 실패한다.

## 구조

```
datastore/
├─ compose.yaml        kafka · kafka-storage-init · kafka-init · minio · minio-init
├─ kafka-init/init.sh  토픽 생성 · 보존 설정 적용 (매 up 마다 멱등)
├─ minio-init/init.sh  버킷 · 정책 · 계정 · 보관 정책 (매 up 마다 멱등)
├─ scripts/verify.sh   완료 조건 검증. 실패하면 exit 1
├─ .env.example        → .env 로 복사해 채운다
└─ README.md
```

| 서비스 | 하는 일 |
|---|---|
| `kafka` | KRaft 단일 노드 브로커. ZooKeeper 없음 |
| `kafka-storage-init` | 빈 볼륨을 브로커 uid(1000) 소유로 넘긴다. 한 번 돌고 끝 |
| `kafka-init` | 계약 토픽 `raw-file-ready` 생성 + 보존 설정 적용. 다시 돌려도 같다 |
| `minio` | 원문 객체 저장소. S3 호환 |
| `minio-init` | 버킷 · 정책 · 계정 · 수명 주기 규칙. 다시 돌려도 같다 |

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

## 토픽 설정

`raw-file-ready` 에 붙는 값과 근거다. 결정 근거: Jira `S15P21A102-157`.

| 항목 | 값 | 근거 |
|---|---|---|
| 파티션 | 6 | 소비 병렬도 상한. 늘릴 수만 있고 줄이지 못하므로 미리 여유를 둔다. 이벤트가 배치당 1 건이라 6 개를 유지하는 비용은 디렉터리 몇 개뿐이다 |
| 복제 계수 | 1 | 브로커가 한 대라 1 이 최대 |
| `cleanup.policy` | `delete` | 기본값이지만 못 박는다. `compact` 로 바뀌면 message key 가 `source_id` 라 소스당 최신 1 건만 남고 배치 이력이 사라진다 |
| `retention.ms` | `604800000` (7일) | Kafka 는 원본이 아니다. 토픽이 비어도 `metadata.json` 이 있는 디렉터리를 훑어 이벤트를 재구성할 수 있다(설계문서 5장 재발행). 7일은 소비 측이 멈춰 있어도 따라잡을 수 있는 창이다 |
| `segment.ms` | `86400000` (1일) | 아래 참고 |

`retention.bytes` 는 설정하지 않는다(무제한). 이벤트 하나가 1KB 안팎이고 하루 수백 건이라 시간 기준이 항상 먼저 걸린다.

**`segment.ms` 를 낮추는 이유.** 보존 기간은 세그먼트 파일 단위로 적용되고, 쓰고 있는 세그먼트는 지우지 않는다. 세그먼트는 `segment.bytes`(1GiB) 나 `segment.ms` 중 먼저 오는 쪽으로 닫히는데, 우리 데이터량으로는 1GiB 를 채울 일이 없어 시간 조건만 남는다. `segment.ms` 가 기본값 7일이면 7일간 쌓아 닫은 뒤 다시 7일을 기다리므로 실제 삭제까지 최대 14일이 걸린다. 1일로 낮춰야 선언한 7일에 맞는다.

**브로커 기본값과의 관계.** `KAFKA_LOG_RETENTION_HOURS` 는 브로커 전체 기본값이고, 위 토픽 설정이 그 값을 덮는다. `raw-file-ready` 의 실제 보존 기간은 토픽 설정이 정한다. 브로커 값은 앞으로 만들 다른 토픽(DLQ 등)의 출발값으로만 의미가 있다.

**다중 브로커로 갈 때.** 복제 계수를 올리고 `min.insync.replicas` 와 producer `acks=all` 을 함께 잡는다. 지금은 브로커가 하나라 어느 쪽도 의미가 없다.

**이미 쓰던 `.env` 가 있으면 고쳐야 한다.** 파티션 수는 이전에 `KAFKA_TOPIC_PARTITIONS=3` 으로 잡혀 있었다. `.env` 에 그 줄이 남아 있으면 compose 기본값 6 이 적용되지 않는다. `.env.example` 과 대조해 아래 줄을 옮겨 넣는다.

```
KAFKA_TOPIC_PARTITIONS=6
KAFKA_TOPIC_CLEANUP_POLICY=delete
KAFKA_TOPIC_RETENTION_MS=604800000
KAFKA_TOPIC_SEGMENT_MS=86400000
MINIO_RAW_EXPIRE_DAYS=90
```

`KAFKA_TOPIC_PARTITIONS` 외에는 `.env` 에 없어도 compose 기본값으로 같은 값이 들어간다. 파티션만 기존 줄이 이미 있어서 예외다.

`MINIO_RAW_PREFIX` · `MINIO_VERIFY_EXPIRE_DAYS` 는 없어졌다 (`S15P21A102-158`, 아래 "보관 정책"). `.env` 에 남아 있어도 아무 데도 쓰이지 않으니 지운다.

`up -d` 를 다시 돌리면 `kafka-init` 이 파티션 수를 6 으로 늘리고 설정을 다시 적용한다. 파티션을 늘리면 message key 의 해시 매핑이 바뀌어, 이미 쌓인 메시지와 새 메시지가 같은 key 인데 다른 파티션에 놓인다. 보존 기간 7일이 지나 옛 메시지가 사라지면 정상으로 돌아온다.

## 보관 정책

MinIO 버킷 `raw-data` 쪽이다. 결정 근거: Jira `S15P21A102-157` · `S15P21A102-158`.

| 항목 | 값 | 근거 |
|---|---|---|
| 버전 관리 | off | 같은 `(source, article_id)` 를 다시 저장하면 같은 키를 덮어쓴다(설계문서 5장 멱등). 켜두면 재시도마다 옛 버전이 쌓여 용량만 는다 |
| 수명 주기 규칙 | `expire-all` 하나. 버킷 전체 90일 만료 | 아래 |

**규칙은 하나고 접두어를 보지 않는다** (`S15P21A102-158`). 버킷에 들어오는 것이 전부 수집 원문이고 만료 기간도 하나라, 접두어로 가르면 얻는 것이 없고 잃는 것이 있다 — 키 규칙이 바뀔 때마다 규칙이 조용히 어긋난다.

실제로 그랬다. 규칙이 `domain=` 접두를 잡고 있었는데 계약 키는 `fashion/vogue/...` 로 시작해서 **아무것도 매칭되지 않았다.** 규칙은 유효하고 대상만 0 개라 에러도 나지 않는다. 즉 90일 만료가 도는 것처럼 보이면서 원문이 영구히 쌓인다(불변식 13 위반).

`verify.sh` 가 남기는 `_verify/` 객체도 같이 90일을 산다. 7 바이트짜리 텍스트라 규칙을 하나 더 두는 값이 없다. `verify.sh` 는 끝에서 관리자 키로 그것들을 지운다 — 크롤러 키에는 삭제 권한이 없어 그 키로 지우려 하면 조용히 실패한다.

**만료 기준은 업로드 시각이다.** 경로의 발행일이 아니다. 백필로 과거 날짜분을 지금 올려도 올린 날부터 90일을 센다.

**Kafka 와의 정합성.**

```
MinIO 90일  >=  Kafka 7일
```

원문이 이벤트보다 먼저 사라지면 이벤트의 `object_key` 가 없는 객체를 가리키게 된다. 그래서 원문 보관 기간을 토픽 보존 기간 이상으로 잡는다. `verify.sh` 가 이 부등식을 산술로 확인한다.

90일은 압축 후 하루 수십 MB 를 가정한 값이다. 실제 수집량이 확인되면 EBS 여유에 맞춰 줄여도 되지만, Kafka 보존 기간 아래로는 내리지 않는다.

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

완료 조건(Jira `S15P21A102-156` AC 1~4, `S15P21A102-157` AC 5) 을 한 번에 확인한다. 실패하면 `exit 1` 이다.

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
| 파티션 수, `cleanup.policy` · `retention.ms` · `segment.ms` 실제 값 | 5 |
| 수명 주기 규칙 2 개(중복 없음), 버전 관리 off, MinIO 보관 ≥ Kafka 보존 | 5 |

검증용 객체는 `_verify/` 아래에만 만들고 끝나면 지운다. 수집 데이터는 건드리지 않는다.
Kafka 에 넣은 `_verify` 메시지는 토픽에 남는다. 보존 기간이 지나면 사라진다.

수명 주기 규칙이 각각 1 개인지 세는 이유는 멱등 확인이다. `up` 을 두 번 돌린 뒤에도 2 개여야 한다. 늘어나 있으면 규칙이 교체가 아니라 누적되고 있다는 뜻이다.
버킷 설정 조회에는 관리자 계정이 필요하다. 크롤러·Spark 정책에는 그 권한이 없다.

## 손으로 확인할 때

스크립트가 어디서 막혔는지 볼 때 쓴다.

```sh
cd datastore

# 토픽 목록
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list

# 파티션 수 · 리더 배치
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 --describe --topic raw-file-ready

# 토픽에 실제로 붙은 설정값
docker compose exec kafka /opt/kafka/bin/kafka-configs.sh \
  --bootstrap-server localhost:9092 --entity-type topics --entity-name raw-file-ready --describe

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

수명 주기 규칙과 버전 관리 상태는 버킷 설정이라 관리자 계정으로 본다. `mc ls` 에는 안 나온다.

```sh
docker run --rm --network s15p21a102-data \
  -e MC_HOST_admin="http://$MINIO_ROOT_USER:$MINIO_ROOT_PASSWORD@minio:9000" \
  --entrypoint sh minio/mc:RELEASE.2025-08-13T08-35-41Z -c \
  'mc ilm rule ls admin/raw-data; mc version info admin/raw-data'
```

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

Kafka 인증(SASL)·TLS, 다중 브로커, DLQ 토픽, 백업.
DLQ 는 담당 2 의 후속 이슈, 나머지는 필요해질 때 이슈를 판다.

수명 주기 규칙은 만료만 건다. 저장 등급 전환(transition)이나 미완료 멀티파트 정리는 아직 없다.
