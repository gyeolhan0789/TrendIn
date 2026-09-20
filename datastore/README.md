# datastore — 수집 계층 저장소 (MinIO)

크롤러가 원문을 MinIO `raw-data` 에 올리고 그 위치를 앱 DB 의 수집 이력에 적으면, Spark 가 그 이력의 뷰를 읽어 원문을
가져다 정제하고 결과를 MinIO `curated` 에 쓴다. 이 디렉터리는 그 객체 저장소만 띄운다. Airflow 는 `pipeline/`,
Spark 는 별도 프로젝트다.

**Kafka 는 걷혔다** (Kafka 제거 3/3). 브로커가 있던 시절에는 크롤러가 객체 위치를 토픽에 발행하고 Spark 가 그것을
소비했다. 지금은 그 자리를 앱 DB 의 `collected_article_event` 뷰가 대신한다 — 수집이 장부에 적으면 같은 순간 뷰에
나타나고, 소비 측은 그 뷰를 창으로 잘라 읽는다. 브로커가 하던 "저장은 됐는데 아직 안 읽힌 것" 의 보관이 사라진 대신
장부가 영구라 잃는 것이 없다. 그 시절의 결정은 Jira `S15P21A102-156` · `S15P21A102-157` 에 남아 있다.

- 계약(버킷 이름, 객체 경로): `pipeline/docs/data-pipeline-design.md` 4 장
- 실행 환경 결정과 근거: Jira `S15P21A102-156`
- 보관 정책 결정과 근거: Jira `S15P21A102-158` (아래 "보관 정책" 절)
- `curated` 버킷과 Spark 쓰기 권한: Jira `S15P21A102-243` (아래 "키 세 벌" · "보관 정책" 절)

## 어디에 뜨나

| EC2 | compose 프로젝트 | 담는 것 |
|---|---|---|
| 기본 `J15A102` | `infra/` · `s15p21a102-infra` | 서비스 DB `forever102` |
| 데이터 `J15A102A` | **`datastore/` · `s15p21a102-datastore`** | **MinIO** |
| 데이터 `J15A102A` | `pipeline/` · `s15p21a102-pipeline` | Airflow · 크롤러 · Airflow 메타 DB |
| 데이터 `J15A102A` | Spark — 별도 프로젝트 없음 | `pipeline/spark/compose.spark.yaml` 이 Airflow 이미지에 얹는다 (S15P21A102-169) |

데이터 EC2 안의 두 프로젝트는 이 프로젝트가 만드는 네트워크 `s15p21a102-data` 로 이어진다.
**이 프로젝트가 네트워크 주인이라 항상 먼저 떠야 한다.** 없으면 나머지가 뜨다 실패한다.

## 구조

```
datastore/
├─ compose.yaml        minio · minio-init
├─ minio-init/init.sh  버킷 둘 · 정책 · 계정 · 보관 정책 (매 up 마다 멱등)
├─ scripts/verify.sh   완료 조건 검증. 실패하면 exit 1
├─ .env.example        → .env 로 복사해 채운다
└─ README.md
```

| 서비스 | 하는 일 |
|---|---|
| `minio` | 객체 저장소. S3 호환. 버킷 둘 — 원문 `raw-data`, 정제 결과 `curated` |
| `minio-init` | 버킷 둘 · 정책 · 계정 · 수명 주기 규칙. 다시 돌려도 같다 |

## 처음 실행

```sh
(umask 077; cp -n datastore/.env.example datastore/.env)
chmod 600 datastore/.env
nano datastore/.env      # MinIO 계정 세 벌을 채운다

docker compose -f datastore/compose.yaml config --quiet
docker compose -f datastore/compose.yaml up -d
docker compose -f datastore/compose.yaml ps      # minio 가 healthy 인지
```

`minio-init` 은 한 번 돌고 `Exited (0)` 으로 남는다. 정상이다.

## 접속 정보

| 어디서 | MinIO |
|---|---|
| 같은 EC2 의 다른 compose (Airflow · Spark) | `http://minio:9000` |
| 호스트 · 다른 EC2 | `http://<호스트>:9000`, 콘솔 `:9001` |

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
| `MINIO_CRAWLER_*` | `raw-data` 목록 · 객체 put/get · 멀티파트 | 크롤러 → `pipeline/.env` 의 `TRENDIN_MINIO_*` |
| `MINIO_SPARK_*` | `raw-data` 읽기 + `curated` 읽기/쓰기 | Spark → `pipeline/.env` 의 `TRENDIN_MINIO_SPARK_*` |

버킷별로 갈라 보면 이렇다.

| 계정 (정책) | `raw-data` | `curated` |
|---|---|---|
| 크롤러 (`crawler-write`) | 목록 · put · get · 멀티파트 | 접근 권한 없음 |
| Spark (`spark-raw-read-curated-write`) | 목록 · get | 목록 · put · get · delete · 멀티파트 |

크롤러 키에 삭제 권한은 없다. **Spark 키로 `raw-data` 에 쓰기를 시도하면 거부된다** — 원문은 Spark 가 건드릴 것이 아니다.
`curated` 는 반대로 Spark 소유라 쓰기가 열려 있다. 거기에 삭제 권한까지 들어가는 이유는 쓰기 방식 때문이다. `ingest` 는 Parquet 을 `mode("overwrite")` + `partitionOverwriteMode=dynamic` 으로 쓰므로, 같은 `ingest_run_id` 를 재처리하면 그 파티션의 옛 part 파일을 지우고 새로 쓴다. 멀티파트와 `_temporary` 정리도 같은 권한을 쓴다. `s3:DeleteObject` 가 없으면 첫 재처리에서 죽는다.
애플리케이션에 root 키를 주지 않는다.

**Spark 정책 이름이 바뀌었다.** `spark-read` 는 `curated` 쓰기가 붙으면서 실제 권한과 어긋나 `spark-raw-read-curated-write` 가 됐다 (`S15P21A102-243`). `minio-init` 이 새 이름을 붙인 뒤 옛 `spark-read` 를 계정에서 떼고 지운다 — 이미 돌던 서버에만 남아 있고, 없으면 그냥 넘어간다.
`.env` 를 고쳐도 이미 만들어진 계정은 그대로다. 값을 바꿨으면 `docker compose -f datastore/compose.yaml up -d minio-init` 을 다시 돌려 반영한다.

## 보관 정책

결정 근거: Jira `S15P21A102-158` · `S15P21A102-243`.

| 버킷 | 버전 관리 | 수명 주기 |
|---|---|---|
| `raw-data` | off | `expire-all` 하나. 버킷 전체 90일 만료 |
| `curated` | off | **없음.** 만료를 걸지 않는다 |

**버전 관리는 두 버킷 모두 끈다.** `raw-data` 는 같은 `(source, article_id)` 를 다시 저장하면 같은 키를 덮어쓰고(설계문서 5장 멱등), `curated` 는 같은 `ingest_run_id` 를 재처리하면 그 파티션을 덮어쓴다. 어느 쪽이든 켜두면 재시도마다 옛 버전이 쌓여 용량만 는다. `minio-init` 은 누가 콘솔에서 켠 경우를 대비해 매번 `suspend` 로 되돌린다.

**`curated` 에는 만료를 걸지 않는다** (`S15P21A102-243`). 거기 있는 것은 90일 지나면 지워도 되는 수집 원문이 아니라, `extract` 가 계속 읽는 정제 결과다. 만료를 걸면 옛 `ingest_run_id` 파티션부터 사라져 재집계와 백필이 조용히 빈 구간을 만든다 — `extract` 는 입력이 없어졌다는 것을 알 방법이 없으므로 에러 없이 적게 집계한다. `verify.sh` 가 `curated` 에 규칙이 없는지 확인한다.

아래는 `raw-data` 의 만료 규칙 이야기다.

**규칙은 하나고 접두어를 보지 않는다** (`S15P21A102-158`). `raw-data` 에 들어오는 것이 전부 수집 원문이고 만료 기간도 하나라, 접두어로 가르면 얻는 것이 없고 잃는 것이 있다 — 키 규칙이 바뀔 때마다 규칙이 조용히 어긋난다.

실제로 그랬다. 규칙이 `domain=` 접두를 잡고 있었는데 계약 키는 `fashion/vogue/...` 로 시작해서 **아무것도 매칭되지 않았다.** 규칙은 유효하고 대상만 0 개라 에러도 나지 않는다. 즉 90일 만료가 도는 것처럼 보이면서 원문이 영구히 쌓인다(불변식 13 위반).

`verify.sh` 가 `raw-data` 에 남기는 `_verify/` 객체도 같이 90일을 산다. 7 바이트짜리 텍스트라 규칙을 하나 더 두는 값이 없다. `verify.sh` 는 끝에서 관리자 키로 그것들을 지운다 — 크롤러 키에는 삭제 권한이 없어 그 키로 지우려 하면 조용히 실패한다. `curated` 쪽 검증 객체는 만료가 없어 남으면 영영 남으므로, `verify.sh` 가 Spark 키로 지우는지 확인하고 그것이 실패한 경우를 대비해 관리자 키로 한 번 더 지운다.

**만료 기준은 업로드 시각이다.** 경로의 발행일이 아니다. 백필로 과거 날짜분을 지금 올려도 올린 날부터 90일을 센다.

**수집 이력과의 관계.** 장부(`collected_article`)는 지우지 않으므로(불변식 13), 90일이 지나 원문이 만료되면 없는 객체를 가리키는 행이 장부에 남는다. 그래도 되는 이유는 소비 측이 창을 잘라 읽기 때문이다 — `ingest` 의 `lookback_hours` 는 168시간이고, 90일 전 행은 이미 처리를 마쳐 처리 이력이 거른다. 되짚어야 할 만큼 오래된 구간은 원문이 있어야 하므로, 90일보다 긴 백필은 만료 전에 돌린다.

브로커가 있던 시절에는 여기에 `MinIO 90일 >= Kafka 7일` 이라는 부등식이 있었다. 이벤트가 가리키는 원문이 먼저 사라지면 안 된다는 뜻이었고, `verify.sh` 가 그것을 산술로 확인했다. 이벤트가 없어지면서 그 부등식도 없어졌다.

90일은 압축 후 하루 수십 MB 를 가정한 값이다. 실제 수집량이 확인되면 EBS 여유에 맞춰 줄여도 된다. 줄일 때는 `scripts/check-destructive-settings.sh` 가 MR 에서 막는다 — 이미 만료된 원문은 안 돌아온다.

## 기동과 중지

```sh
docker compose -f datastore/compose.yaml up -d
docker compose -f datastore/compose.yaml stop      # 중지 (재부팅해도 다시 뜨지 않는다)
docker compose -f datastore/compose.yaml start
docker compose -f datastore/compose.yaml restart minio
```

`restart: unless-stopped` 라 EC2 가 재부팅해도 Docker 데몬이 뜨면서 같이 올라온다. `stop` 으로 명시적으로 내린 컨테이너는 그대로 내려가 있다.

**`down -v` 는 쓰지 않는다.** 볼륨 `s15p21a102-minio-data` 와 그 안의 원문이 함께 사라진다.
`down` 만 해도 네트워크가 사라져 `pipeline` 이 끊기므로, 저장소를 내릴 때는 붙어 있는 쪽을 먼저 내린다.

**옛 Kafka 볼륨은 저절로 사라지지 않는다.** 브로커를 걷은 뒤에도 `s15p21a102-kafka-data` 는 돌던 서버에 남는다. 안에 든 것은 보존 기간이 지난 옛 메시지뿐이라 지워도 되지만, `down -v` 가 아니라 이름을 확인하고 지운다.

```sh
docker volume ls | grep kafka
docker volume rm s15p21a102-kafka-data
```

## 검증 스크립트

완료 조건(Jira `S15P21A102-156` AC 1~3, `S15P21A102-158`, `S15P21A102-243` 의 `curated`) 을 한 번에 확인한다. 실패하면 `exit 1` 이다.

```sh
./datastore/scripts/verify.sh
```

Windows 는 Git Bash 에서 돌린다. PowerShell·CMD 는 `.sh` 를 실행하지 못한다.
검증은 전부 컨테이너 안에서 일어나므로 호스트에는 `docker` 만 있으면 된다.

| 확인하는 것 | AC |
|---|---|
| `minio` healthy, `restart=unless-stopped` | 1 |
| 네트워크 `s15p21a102-data` 존재, 그 안에서 `minio:9000` 도달 | 2 |
| `raw-data` — 크롤러 키 put/get, Spark 키 get, **Spark 키 write 거부** | 3 |
| `curated` — **Spark 키 put/get/delete 성공** | 3 |
| `raw-data` 수명 주기 `expire-all` 1 개(중복 없음), 버전 관리 off | 4 |
| **`curated` 수명 주기 없음**, 버전 관리 off | 4 |

검증용 객체는 `_verify/` 아래에만 만들고 끝나면 지운다. 수집 데이터는 건드리지 않는다.

`raw-data` 의 `expire-all` 이 1 개인지 세는 이유는 멱등 확인이다. `up` 을 두 번 돌린 뒤에도 1 개여야 한다. 늘어나 있으면 규칙이 교체가 아니라 누적되고 있다는 뜻이다.

`raw-data` 쓰기 거부와 `curated` 쓰기 성공은 짝으로 본다. 한쪽만 확인하면 정책이 두 버킷에 통으로 붙은 사고를 잡지 못한다.
버킷 설정 조회에는 관리자 계정이 필요하다. 크롤러·Spark 정책에는 그 권한이 없다.

**봉투가 맞는지는 여기서 보지 않는다.** 소비 측이 읽는 `collected_article_event` 뷰가 봉투 정본과 같은 값을 내는지는 진짜 PostgreSQL 이 있어야 판정되고, 그 대조는 `pipeline/tests/common/test_ledger_view.py` 가 CI 에서 한다.

## 손으로 확인할 때

스크립트가 어디서 막혔는지 볼 때 쓴다.

```sh
cd datastore

# MinIO — 크롤러 키로 put/get
docker run --rm --network s15p21a102-data \
  -e MC_HOST_crawler="http://$MINIO_CRAWLER_ACCESS_KEY:$MINIO_CRAWLER_SECRET_KEY@minio:9000" \
  --entrypoint sh minio/mc:RELEASE.2025-08-13T08-35-41Z -c \
  'echo hi > /tmp/t && mc cp /tmp/t crawler/raw-data/_healthcheck && mc cat crawler/raw-data/_healthcheck'

# MinIO — Spark 키로 raw-data 에 쓰기. Insufficient permissions 로 끝나야 한다
docker run --rm --network s15p21a102-data \
  -e MC_HOST_spark="http://$MINIO_SPARK_ACCESS_KEY:$MINIO_SPARK_SECRET_KEY@minio:9000" \
  --entrypoint sh minio/mc:RELEASE.2025-08-13T08-35-41Z -c \
  'echo hi > /tmp/t && mc cp /tmp/t spark/raw-data/should-fail'

# MinIO — Spark 키로 curated 에 쓰기. 이쪽은 put · get · delete 가 전부 성공해야 한다
docker run --rm --network s15p21a102-data \
  -e MC_HOST_spark="http://$MINIO_SPARK_ACCESS_KEY:$MINIO_SPARK_SECRET_KEY@minio:9000" \
  --entrypoint sh minio/mc:RELEASE.2025-08-13T08-35-41Z -c \
  'echo hi > /tmp/t && mc cp /tmp/t spark/curated/_healthcheck && mc cat spark/curated/_healthcheck && mc rm spark/curated/_healthcheck'

# 계정에 붙은 정책과 그 내용
docker run --rm --network s15p21a102-data \
  -e MC_HOST_admin="http://$MINIO_ROOT_USER:$MINIO_ROOT_PASSWORD@minio:9000" \
  --entrypoint sh minio/mc:RELEASE.2025-08-13T08-35-41Z -c \
  "mc admin user info admin $MINIO_SPARK_ACCESS_KEY; mc admin policy info admin spark-raw-read-curated-write"
```

**`raw-data` 에서** Spark 키 쓰기가 성공하면 정책이 잘못 붙은 것이다. 반대로 **`curated` 에서** 쓰기나 삭제가 거부되면 정책이 덜 붙은 것이고, 그 상태로는 `ingest` 가 첫 실행이나 첫 재처리에서 죽는다.
`mc admin user info` 에 `spark-read` 가 남아 있으면 옛 정책이 덜 걷힌 것이다. `up -d minio-init` 을 다시 돌린다.
콘솔(`:9001`) 은 객체 브라우저다. 계정·정책 관리는 콘솔이 아니라 `mc admin` 으로 한다.

수명 주기 규칙과 버전 관리 상태는 버킷 설정이라 관리자 계정으로 본다. `mc ls` 에는 안 나온다.

```sh
docker run --rm --network s15p21a102-data \
  -e MC_HOST_admin="http://$MINIO_ROOT_USER:$MINIO_ROOT_PASSWORD@minio:9000" \
  --entrypoint sh minio/mc:RELEASE.2025-08-13T08-35-41Z -c \
  'mc ilm rule ls admin/raw-data; mc version info admin/raw-data'
```

`curated` 는 규칙이 없는 것이 정상이라 `mc ilm rule ls admin/curated` 가 "no lifecycle configuration" 으로 끝난다. 여기에 규칙이 보이면 누가 만료를 걸어둔 것이므로 지운다.

## EC2 에서 바꾸는 것

`.env` 만 다르다.

- `MINIO_BIND` — 기본은 `127.0.0.1`. 다른 호스트가 붙어야 할 때만 `0.0.0.0` 으로 바꾼다.
- 자격증명은 서버에서 생성한다. `.env` 는 Git 에 올리지 않는다.

같은 EC2 안에서만 쓸 거면 바인드를 `127.0.0.1` 로 두는 편이 안전하다. 컨테이너끼리는 `s15p21a102-data` 로 붙으므로 호스트 포트가 없어도 된다.

포트를 `0.0.0.0` 으로 여는 경우, MinIO(9000·9001) 는 키 하나로 열린다.
보안 그룹에서 팀 대역과 필요한 인스턴스만 허용하고 공인망 전체에 열지 않는다. Docker 가 공개한 포트는 UFW 규칙을 우회할 수 있으므로 보안 그룹 쪽에서 막는다.

**브로커를 걷으면서 보안 그룹에서도 29092 를 닫는다.** 인증 없는 PLAINTEXT 리스너였고 이제 아무도 듣지 않는다.

## 지금 없는 것

MinIO TLS, 백업.
필요해질 때 이슈를 판다.

수명 주기 규칙은 `raw-data` 에 만료만 건다. 저장 등급 전환(transition)이나 미완료 멀티파트 정리는 아직 없다.
`curated` 에는 규칙이 아예 없어서, 재처리로 버려진 파티션이 있어도 저절로 지워지지 않는다. 용량이 문제가 되면 그때 이슈를 판다.

실패한 이벤트를 모으는 DLQ 는 토픽이 아니라 `spark/io/dlq.py` 가 쓰는 테이블이다. 브로커와 함께 없어진 것은 "DLQ 토픽" 계획 쪽이다.
