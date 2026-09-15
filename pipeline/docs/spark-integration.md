# Spark 연동 계약 — 크롤러가 내보내는 것

크롤러(담당 1)가 Kafka·MinIO 에 무엇을 어떤 모양으로 놓는지. **이 문서만 보고 consumer 와
MinIO reader 를 만들 수 있어야 한다.** 크롤러 코드를 열어야 알 수 있는 것이 남아 있으면 이
문서의 결함이므로 알려 주면 채운다.

- 결정과 근거: Jira `S15P21A102-159`. 생산 측 설계는 [`web-collect.md`](web-collect.md), 팀 전체 구조는 [`data-pipeline-design.md`](data-pipeline-design.md)
- 소비 측 계약(무엇을 DLQ 로 보내는지 등)은 [`spark/docs/02-input-contract.md`](../spark/docs/02-input-contract.md). **그 문서는 이 문서보다 낡았다** — §11 참고
- 샘플: [`spark/tests/fixtures/contract/`](../spark/tests/fixtures/contract/) (§8)

## 1. 이 문서가 보장하는 것

| 보장한다 | 보장하지 않는다 |
|---|---|
| 토픽에 흐르는 봉투의 필드 이름·타입·값 규칙 | 소비 측의 처리 방식(DLQ 기준, checkpoint, 재처리) |
| MinIO 객체의 키 규칙과 내용 | `curated` 버킷 (Spark 소유, 쓰기 권한이 아직 없다 — §6) |
| 최소 한 번 전달 (at-least-once) | 정확히 한 번. 중복은 소비 측이 `event_id` 로 거른다 |
| 이벤트가 나갔으면 그 객체는 이미 있다 | 객체가 있으면 이벤트가 나갔다 (역은 성립하지 않는다 — §5) |

## 2. Kafka

| 항목 | 값 | 어디서 오나 |
|---|---|---|
| 기사 topic | `raw-file-ready` | `TRENDIN_KAFKA_TOPIC_RAW_FILE_READY` |
| 요약 topic | `collect-run-summary` (생성 요청, 기본 비활성) | `TRENDIN_KAFKA_TOPIC_RUN_SUMMARY` |
| bootstrap (같은 EC2 의 다른 compose) | `kafka:9092` | 네트워크 `s15p21a102-data` |
| bootstrap (호스트·다른 EC2) | `${KAFKA_EXTERNAL_HOST}:29092` | `datastore/.env` |
| 직렬화 | JSON, UTF-8, 비ASCII 를 escape 하지 않는다 | `kafka_publisher.publish` |
| message key | `source_id` (UTF-8 바이트) | `flow.publish_pending` · `flow.publish_summaries` |
| 파티션 | 기사 6 · 요약 1 요청 | 요약은 datastore 담당자 생성 후 활성화 |
| `cleanup.policy` | `delete` | `compact` 면 key 가 `source_id` 라 소스당 최신 1 건만 남는다 |
| `retention.ms` | 기사 7일 · 요약 30일 요청 | MinIO 원문은 90일이다 — 부등식은 §5 |

접속 정보의 정본은 [`datastore/README.md`](../../datastore/README.md) "접속 정보" 절이다. 값이 이 표와 다르면 그쪽이 맞다.

### message key 를 `source_id` 로 둔 결과

같은 **토픽 안에서** 같은 소스의 이벤트는 한 파티션에 모인다. 기사와 요약은 다른 토픽이므로
두 토픽 사이의 도착 순서는 보장하지 않는다. 기사와 요약의 `run_id` 로 대사한다(기사 쪽은 발급 실행).

중복 판정은 key 가 아니라 `event_id` 로 한다. 같은 key 로 다른 기사가 계속 오기 때문이다.

### consumer group — 소비 측이 정한다

생산 측은 group 을 모르고 의존하지도 않는다. 다만 지금 소비 측에 이름 규칙이 **두 개** 있다:

| 어디 | 값 |
|---|---|
| [`02 §1`](../spark/docs/02-input-contract.md) | `spark-ingest` |
| `spark/conf/base.yaml` | `group_id_prefix: "trendin-spark"` (환경변수 `KAFKA_GROUP_ID_PREFIX` 로 덮인다) |

둘 다 살리려면 `{group_id_prefix}-{job}` → `trendin-spark-ingest` 가 된다. 어느 쪽이든 하나로
정하고 `02` 와 `base.yaml` 을 맞춰 주면 된다.

### 전달 보장

`acks=all` · `enable.idempotence=true` 로 내고, `flush()` 가 성공한 뒤에만 장부에 발급 시각을
적는다. 그래서 **발급 후 장부 기록 전에 죽으면 같은 이벤트가 다시 나간다.** at-least-once 이고,
중복 제거는 소비 측 책임이다 (`event_id` 가 그 키다).

## 3. 봉투 — 토픽별 계약

기사 이벤트는 `raw-file-ready`, 소스별 실행 요약은 `collect-run-summary` 에만 발급한다.
`object_key` 로 이벤트 종류를 분기하지 않는다. 요약 토픽이 비활성이면 기사만 발급한다.

### raw-file-ready — 기사 이벤트

기사 하나에 이벤트 하나다. 기사 객체·장부 스키마·봉투 필드 이름은 그대로다. `run_id` 의 뜻은
소비 계약([`02 §2`](../spark/docs/02-input-contract.md))과 같이 발급 실행이다.

| 필드 | 타입 | 값 |
|---|---|---|
| `event_id` | string | `{source_id}-{article_id}` |
| `schema_version` | int | `1` |
| `bucket` | string | `raw-data` |
| `object_key` | string | article.json 키 |
| `raw_object_key` | string \| null | raw 키. 회원 전용 기사는 `null` |
| `domain` | string | `fashion` \| `dev` (§11 참고) |
| `source_id` | string | 소스 키 (`vogue` 등) |
| `article_id` | string \| null | 소스의 기사 식별자 |
| `run_id` | string | 발급 실행, `yyyyMMddTHHmmss` KST. 필수 |
| `url` | string \| null | 기사 정식 URL |
| `title` | string \| null | 기사 제목 |
| `published_at` | string \| null | ISO-8601, **소스가 준 오프셋 그대로** |
| `collected_at` | string | ISO-8601 KST. 그 기사를 받은 시각 |
| `status` | string | 항상 `success` |
| `record_count` | int | 항상 `1` |
| `size_bytes` | null | `null` |
| `checksum` | string \| null | `sha256-` + article.json 의 sha256 |
| `format` | string \| null | `json` |
| `compression` | string \| null | `none` |
| `failure_reason` | string \| null | `null` |
| `members_only` | bool | 회원 전용 기사면 `true` |

`run_id` 는 **발급 실행**이다. 저장만 되고 못 나간 행은 다음 회차가 내므로 수집
실행과 달라도 정상이다. 수집 시각은 `collected_at` 에 있다. **파티션 키로 쓰지 않는다.**
재발급하면 값이 달라져 같은 기사가 다른 파티션에 갈릴 수 있다. 값도 파싱하지 않는다.
`event_id` 는 결정적인 **중복 판정 함수**다. 파싱해서 `source_id` 를 추출하지 않는다.

### collect-run-summary — 소스별 실행 요약

토픽을 활성화하면 소스 하나의 한 회차마다 논리적으로 하나를 낸다. 0건·수집 실패에도
낸다. 전달은 at-least-once라 재시도 중복은 `event_id` 로 제거한다. 공통 식별 5칸과
수집 결과·발급 통계를 담는 고정 **19개 필드**다. 안 쓰는 기사 봉투 필드는 없다.

| 필드 | 타입 | 값 | 어디서 |
|---|---|---|---|
| `schema_version` | int | `1` | 상수 |
| `event_id` | string | `{source_id}-{run_id}` | |
| `domain` | string | `fashion` \| `dev` | `SourceStatus.domain` |
| `source_id` | string | 소스 키 | |
| `run_id` | string | `yyyyMMddTHHmmss` (KST) | `flow.run_id_of` |
| `run_started_at` | string | ISO-8601 KST. **logical date** — 재시도해도 같다 | context |
| `status` | string | `success` \| `failed` | `flow.source_statuses` |
| `discovered` | int \| null | 발견한 후보 수 | `collect_source` 집계 |
| `stored` | int \| null | 이번 회차에 새로 저장한 수 | `SourceOutcome.stored` |
| `skipped` | int \| null | 장부에 이미 있어 안 받은 수 | `SourceOutcome.skipped` |
| `not_modified` | bool \| null | 조건부 요청이 304 라 목록도 안 받았다 | `SourceOutcome.not_modified` |
| `failed` | int \| null | 실패 건수 합 | `SourceOutcome.failed` |
| `failed_by_stage` | object \| null | `{"discover": n, "materialize": n, "store": n}` | `collect_source` 집계 |
| `failures` | array \| null | 표본. `{stage, article_id, reason}` 앞 10건 | 실패 표본 |
| `duration_ms` | int \| null | 수집 태스크 소요 | 단조 시계로 측정 |
| `members_only_stored` | int \| null | raw 없이 저장된 수 | `collect_source` 집계 |
| `emitted` | int | 이번 회차가 발급한 기사 이벤트 수 | 장부 (`emitted_by_run`) |
| `emitted_oldest_collected_at` | string \| null | 그중 가장 오래된 `collected_at`, KST. 0건이면 `null` | 장부의 `min(collected_at)` |
| `failure_reason` | string \| null | `status=failed` 일 때만 | `SourceStatus.failure_reason` |

수집 결과 **9개 필드**(`discovered`, `stored`, `skipped`, `not_modified`, `failed`,
`failed_by_stage`, `failures`, `duration_ms`, `members_only_stored`)는 XCom에서 온다.
수집 태스크가 죽어 결과가 없으면 전부 `null`이다. `0`은 관측된 0건이므로 대신 쓰지 않는다.
`failed_by_stage` 는 세 단계 모두 포함하고, `failures` 는 발견→취득·저장 순서의 앞 10건,
사유는 앞 200자다. `failed` 와 단계별 건수는 표본이 아닌 전체 실패를 센다.
`duration_ms` 는 발견부터 저장 확인·장부 기록까지의 단조 시계 경과 시간이다.
`members_only_stored` 는 회원 전용 기사 중 저장 확인에 성공한 수다.

발급 통계는 장부에서 오므로 수집 실패와 독립이다. `emitted` 는 항상 0 이상의 정수이고,
0건일 때만 `emitted_oldest_collected_at` 이 `null`이다. 이월분이 있으면 `emitted > stored`
일 수 있다. 같은 실행의 재시도는 장부의 `event_run_id`로 집계하므로 통계가 유지된다.
`run_started_at` 은 실제 태스크 시작 시각이 아닌 **logical date**의 KST 표기다.
`failure_reason` 은 `failed` 일 때만 채우며, 수집 태스크 전체 실패의 상세는 Airflow 로그에 있다.
요약에는 `exclude_none`을 쓰지 않는다.

| 관측 | 해석 |
|---|---|
| `discovered=0`, `not_modified=false` | 정상 무소식 또는 구조 변경·차단 의심. 자동 이상 판정은 S15P21A102-199 |
| `discovered>0`, `skipped=discovered`, `stored=0` | 후보 전부 이미 수집함 |
| `not_modified=true` | 조건부 요청 304 |
| `failed_by_stage.discover>0` | 목록·피드 파싱 실패 |
| `failed_by_stage.materialize` 가 발견 수에 가까움 | 기사 취득·정규화 장애 의심 |
| `emitted_oldest_collected_at` 이 며칠 전 | 발급 지연. 닫힌 날짜 집계의 재계산 범위에 반영해야 함 |

### 주의할 점 셋

**`checksum` 은 `object_key` 가 가리키는 객체, 즉 article.json 의 해시다.** raw 의 해시가 아니다.
raw 의 해시는 article.json 안의 `content_sha256` 이다 (§5). 이름이 비슷한 다른 값이다.

**`record_count` 는 jsonl 줄 수가 아니다.** 기사 이벤트는 항상 `1` 이고 객체는 단일 JSON 객체다.
줄 수와 대조하는 검증은 이 계약에서 성립하지 않는다.

**`collected_at` 은 재처리해도 바뀌지 않는다.** 기사 이벤트는 그 기사를 받은 시각이라, 저장만
되고 발급 전에 죽은 행을 며칠 뒤에 내보내도 값이 그대로다. 요약의 `run_started_at`은 logical date라
재시도해도 같다.

## 4. 본문은 이벤트에 없다

봉투에 `body_text` · `summary` 가 없다 (`web-collect.md` 불변식 6). 본문은 MinIO 의
article.json 에만 있다. 이벤트 크기를 1KB 안팎으로 유지하려는 것이고, Kafka 보존 기간이
7일이라 본문을 실으면 7일 뒤 사라지는 사본이 하나 더 생긴다.

## 5. MinIO

| 항목 | 값 |
|---|---|
| endpoint (같은 EC2) | `http://minio:9000` |
| endpoint (호스트·다른 EC2) | `http://<호스트>:9000`, 콘솔 `:9001` |
| bucket | `raw-data` |
| 버전 관리 | **off** — 같은 키를 덮어쓴다 |
| 수명 주기 | 버킷 전체 90일 만료. **기준은 업로드 시각**이고 경로의 날짜가 아니다 |

`MinIO 90일 >= Kafka 7일` 이라 이벤트가 가리키는 원문이 먼저 사라지지 않는다.
`datastore/scripts/verify.sh` 가 이 부등식을 산술로 확인한다.

### 키 규칙

```
{domain}/{source}/{route}/{yyyy}/{mm}/{dd}/{article_id}/raw.{ext}
{domain}/{source}/{route}/{yyyy}/{mm}/{dd}/{article_id}/article.json
```

정본은 `keys.py` 다. 예: `fashion/vogue/rss/2026/09/03/854414/article.json`

| 칸 | 값 |
|---|---|
| `domain` | `fashion` \| `dev` (§11) |
| `source` | 소스 키 |
| `route` | `rss` \| `listing` \| `api`. `linked` 가 늘 예정이다 (`source-discovery.md`) |
| `yyyy/mm/dd` | **`published_at` 의 KST 날짜.** 수집일이 아니다 |
| `ext` | route 와 1:1 — `rss`→`xml`, `listing`→`html`, `api`→`json` |

**`collected_date` 세그먼트는 없다.** 팀 계약 §4 의 `domain=…/collected_date=…/run_id=…`
(Hive 스타일, 수집일)와 다르다. 날짜 파티션이 발행일인 이유는 언급량 집계가 발행일 기준이기
때문이다 (`web-collect.md` §12 항목 6).

**경로를 직접 조립하지 말고 이벤트의 `object_key` 를 그대로 써라.** 규칙이 바뀔 때 고칠 곳이
한 곳이어야 한다.

### 객체에 붙는 메타데이터

`x-amz-meta-*` 로 실린다. latin-1 헤더라 ASCII 만 들어간다.

| 이름 | 값 |
|---|---|
| `collected-at` | ISO-8601 KST |
| `content-sha256` | **그 객체 자신의** sha256. raw 객체엔 raw 의, article.json 엔 article.json 의 |

이벤트만으로 충분하므로 읽지 않아도 된다. 객체만 손에 쥔 상황에서 되짚을 수 있게 둔 값이다.

### article.json

`article.py` 의 `Article` 을 직렬화한 것이다. **compact JSON** (구분자에 공백이 없다), UTF-8.

```json
{"schema_version":1,"domain":"fashion","source":"vogue","route":"rss","article_id":"854414", ...}
```

| 필드 | 타입 | 비고 |
|---|---|---|
| `schema_version` | int | `1` |
| `domain` `source` `route` `article_id` | string | 키와 같은 값 |
| `url` `title` | string | 반드시 있다 |
| `published_at` | string | 소스가 준 오프셋 그대로 |
| `collected_at` | string | **UTC (`Z`)**. 봉투는 KST 오프셋이다 — 표기가 다르고 같은 순간이다 |
| `raw_key` | string | raw 의 키. 회원 전용이면 없다 |
| `content_sha256` | string | **raw 의** sha256. 회원 전용이면 없다 |
| `modified_at` `summary` `body_text` `author` `members_only` `extra` | | 없을 수 있다 |
| `categories` | array | 소스가 붙인 분류. 목록 소스는 발견한 섹션 슬러그 |

**⚠️ 값이 없는 필드는 `null` 이 아니라 키 자체가 없다.** `model_dump_json(exclude_none=True)`
이라서다. `doc["summary"]` 는 `KeyError` 를 낸다 — `doc.get("summary")` 를 쓰거나 스키마에
nullable 로 선언해 읽어라.

**회원 전용 기사** (`members_only: true`) 는 `body_text` 가 없고 raw 객체 자체를 저장하지 않는다.
기사 페이지 HTML 에 본문이 실려 오기 때문에 raw 를 저장하면 본문을 저장하는 것이 된다
(`web-collect.md` §12 항목 2). 제목·URL·발행일·요약은 남는다. 전체의 7.4% 다.

### 완료 판정 — `metadata.json` 은 없다

팀 계약 발행 규약 1 의 `metadata.json` 은 배치 디렉터리마다 놓는 파일이라, 기사별로 가면서
사라졌다. **`article.json` 이 그 자리를 대신한다.**

`store_article` 의 순서가 raw put → **article.json put** → 존재 확인 → 장부 기록이므로,
article.json 이 있으면 그 기사는 완성이다. 디렉터리를 훑어 이벤트를 재구성할 때도
`article.json` 이 있는 것만 고르면 된다 — 필요한 값이 그 안에 다 있고 `checksum` 은 바이트에서
다시 계산하면 된다.

역은 성립하지 않는다. **article.json 이 있는데 이벤트가 아직 안 나간 기사가 있을 수 있다**
(저장 후 발급 전에 죽은 행. 다음 실행의 발급이 이어 낸다).

### S3A 설정

```
spark.hadoop.fs.s3a.endpoint                 ${MINIO_ENDPOINT}
spark.hadoop.fs.s3a.path.style.access        true
spark.hadoop.fs.s3a.connection.ssl.enabled   false
spark.hadoop.fs.s3a.aws.credentials.provider org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider
```

`path.style.access=true` 가 필수다. MinIO 는 가상 호스트 스타일(`bucket.host`)이 아니라 경로
스타일(`host/bucket`)을 쓴다. 읽는 대상은 `s3a://{bucket}/{object_key}` 다.

## 6. 자격증명 — read 전용

Spark 용 키는 `datastore/minio-init/init.sh` 가 만드는 `spark-read` 정책이 붙어 있다.

| 허용 | 대상 |
|---|---|
| `s3:ListBucket` · `s3:GetBucketLocation` | `raw-data` |
| `s3:GetObject` | `raw-data/*` |

**`PutObject` · `DeleteObject` 가 없다.** 쓰기를 시도하면 `Insufficient permissions` 로 거부된다.
`datastore/scripts/verify.sh` 가 매번 그 거부를 확인한다.

### 전달 절차

값은 `datastore/.env` 에서 태어난다. 그 파일은 Git 에 올라가지 않으므로 **저장소를 띄운 사람이
Spark 담당자에게 직접 전달한다.**

1. 저장소 운영자가 `datastore/.env` 의 `MINIO_SPARK_ACCESS_KEY` · `MINIO_SPARK_SECRET_KEY` 를 만든다
2. `docker compose -f datastore/compose.yaml up -d minio-init` — 계정과 정책이 붙는다
3. 그 두 값을 Spark 담당자에게 전달한다. **Git · MR · 이슈 본문에 붙이지 않는다**
4. Spark 담당자가 `spark/.env` 의 `MINIO_ACCESS_KEY` · `MINIO_SECRET_KEY` 에 넣는다
5. 아래 명령으로 read 만 되는지 확인한다

```sh
# get 은 된다
docker run --rm --network s15p21a102-data \
  -e MC_HOST_spark="http://$MINIO_SPARK_ACCESS_KEY:$MINIO_SPARK_SECRET_KEY@minio:9000" \
  --entrypoint sh minio/mc:RELEASE.2025-08-13T08-35-41Z -c 'mc ls spark/raw-data'

# put 은 Insufficient permissions 로 끝나야 한다
docker run --rm --network s15p21a102-data \
  -e MC_HOST_spark="http://$MINIO_SPARK_ACCESS_KEY:$MINIO_SPARK_SECRET_KEY@minio:9000" \
  --entrypoint sh minio/mc:RELEASE.2025-08-13T08-35-41Z -c \
  'echo hi > /tmp/t && mc cp /tmp/t spark/raw-data/should-fail'
```

키를 바꾸려면 `datastore/.env` 를 고치고 `up -d minio-init` 을 다시 돌린다. `.env` 만 고치면
이미 만들어진 계정은 그대로다.

**Kafka 에는 인증이 없다** (PLAINTEXT). 네트워크로만 막는다 — 포트를 `0.0.0.0` 으로 열면
보안 그룹에서 팀 대역만 허용한다.

**`curated` 버킷은 아직 없다.** Spark 가 정제 결과를 쓸 곳인데 버킷도 쓰기 권한도 만들어지지
않았다. `datastore/minio-init/init.sh` 가 늘어야 한다 — [`09 §7` 항목 4b](../spark/docs/09-dev-and-test.md).

## 7. 중복과 멱등

| 무엇 | 어떻게 |
|---|---|
| 같은 기사를 다시 저장 | 같은 키를 덮어쓴다. `(source, article_id)` 하나가 키 하나로 간다 |
| 같은 이벤트가 다시 나감 | 있을 수 있다 (at-least-once). `event_id` 로 거른다 |
| 같은 실행을 재시도 | 같은 `event_id` 로 같은 내용이 나간다. 요약의 `emitted` 와 가장 오래된 수집 시각은 장부의 발급 실행에서 온다 |
| 이벤트가 유실 | `article.json` 이 있는 디렉터리를 훑어 재구성할 수 있다 (§5). Kafka 는 원본이 아니다 |

## 8. 샘플

[`spark/tests/fixtures/contract/`](../spark/tests/fixtures/contract/) 에 이벤트 5건(기사 1, 요약 토픽 2, 이전 봉투 요약 2)과
기사 이벤트가 가리키는 객체 2개가 있다. Kafka·MinIO 를 띄우지 않고 파싱·검증 코드를 테스트할 수 있다.

| 파일 | 무엇 |
|---|---|
| `article-event.json` | 기사 이벤트(`raw-file-ready`). `object_key` 가 있다 |
| `collect-run-summary-success.json` | 요약 토픽의 실행 요약(성공). `stored=1`, `emitted=12`, 취득 실패 2건과 발급 지연 표본 |
| `collect-run-summary-failed.json` | 요약 토픽의 실행 요약(실패). 수집 결과 9칸은 `null`, `emitted=0`, `failure_reason` 이 있다 |
| `run-summary-success.json` · `run-summary-failed.json` | 이전 봉투 요약. 분리 전 `raw-file-ready` 에 나간 요약(7일 보존)을 소비 측이 계속 판별하도록 남긴다. 생성 스크립트가 만들지 않고, S15P21A102-206 이 기사 토픽의 요약 분기를 걷을 때 함께 지운다 |
| `objects/fashion/vogue/rss/2026/09/03/854414/article.json` | 위 기사 이벤트의 `object_key` 가 가리키는 실물 |
| `objects/fashion/vogue/rss/2026/09/03/854414/raw.xml` | `raw_object_key` 가 가리키는 실물 |

`objects/` 아래 경로는 실제 `object_key` 와 같은 모양이라, 버킷 루트만 바꿔 끼우면 s3a 경로와
같은 코드로 읽힌다.

**`sha256(article.json)` 이 이벤트의 `checksum` 과 실제로 같다.** checksum 검증 코드를 이
fixture 로 그대로 테스트할 수 있다. 본문·요약은 저작권 때문에 합성 문장이다.

성공 요약 fixture의 발급 수를 수집 수보다 크게 두어 이월 발급을 구분하는지 확인한다.

### fixture 갱신

손으로 고치지 않는다. 생성 스크립트를 돌린다.

```sh
cd pipeline
.venv/bin/python scripts/gen-contract-fixtures.py
.venv/bin/pytest tests/common/test_contract_fixtures.py
```

`tests/common/test_contract_fixtures.py` 가 fixture 와 `events.py` · `keys.py` 가 어긋나지 않는지,
`checksum` 이 실제 객체의 해시인지, 봉투의 값이 `article.json` 의 값과 같은지 검사한다.
그래서 봉투를 고치고 fixture 를 안 고치면 크롤러 쪽 테스트가 깨진다.

## 9. 계약이 실제로 지켜지는지 확인하기

`scripts/verify-spark-integration.py` 가 이 문서에 적힌 것을 실제 저장소에 대고 확인한다.
저장소 계층 자체(토픽 존재, 권한 분리 등)는 [`datastore/scripts/verify.sh`](../../datastore/scripts/verify.sh) 가 본다.

```sh
cd pipeline
./scripts/dev-setup.sh                                        # 한 번
.venv/bin/python scripts/verify-spark-integration.py          # fixture 모드
.venv/bin/python scripts/verify-spark-integration.py --live    # 실제 수집 이벤트
```

| 모드 | 무엇을 하나 | 언제 |
|---|---|---|
| fixture (기본) | fixture 객체를 `_verify/` 아래 올리고 기사 토픽에 1건, 활성화된 요약 토픽에 2건을 발행한 뒤, **Spark read 전용 키로** 되읽어 검증한다. 끝에서 지운다 | 언제나. 크롤러를 돌리지 않는다 |
| `--live` | 토픽에 쌓인 실제 수집 이벤트를 같은 검증에 통과시킨다 | 크롤러를 한 번 돌린 뒤 |

검사 항목:

| 층 | 무엇을 보나 |
|---|---|
| Kafka | message key == `source_id` · 토픽별로 같은 소스가 한 파티션에 모이는지 |
| 봉투 | 공통 필드 · `schema_version` · 토픽별 봉투 · 기사 `run_id`(발급 실행) · `record_count=1` · 출처 명시 · 요약 수집 결과와 발급 통계 |
| MinIO | `object_key` 와 `raw_object_key` 읽기 · `checksum` 대조 · 봉투와 `article.json` 의 값 일치 · raw 가 없으면 `members_only` 인지 |
| 권한 | **Spark 키 write 거부** |

Kafka 층을 따로 두는 이유는 봉투만 봐서는 확인할 수 없기 때문이다. 순서 보장은 message key
와 파티션 배치의 성질이라, 메시지 메타(`key` · `partition` · `offset`)를 함께 봐야 한다.

주소와 키는 `datastore/.env`, 선택적인 요약 토픽은 `pipeline/.env`의
`TRENDIN_KAFKA_TOPIC_RUN_SUMMARY`에서 읽는다. 비어 있으면 요약 검증을 건너뛴다. `--live` 는 fixture 모드가
남긴 이벤트를 걸러낸다 — 토픽에는 7일 남지만 그 객체는 검증 끝에 지워지기 때문이다.

## 10. 스키마 변경 통보 절차

### 무엇이 어느 등급인가

| 변경 | `schema_version` |
|---|---|
| 필드 추가 | 그대로. 하위 호환이다 |
| 필드 제거 · 타입 변경 · **의미 변경** | **+1** |
| 값 규칙 변경 (`checksum` 접두어, 시각 오프셋, 키 규칙) | **+1** — 타입은 같은데 해석이 달라진다 |

의미 변경을 비호환으로 두는 이유는, 타입이 같으면 소비 측이 조용히 잘못 읽고 그게 몇 주 뒤
통계의 이상으로만 나타나기 때문이다.

### 이번 변경의 예외 (2026-09-09)

기사 키 이름 변경과 요약 토픽 분리는 비호환 변경이지만, 당시 Spark Job이 뼈대이고
실제 소비자가 없어 `schema_version=1`을 유지한다. 이 예외를 이후 변경에 적용하지 않는다.

### 절차

1. 생산 측이 Jira 이슈를 만들고 소비 측 담당자를 watcher 로 넣는다
2. **이 문서와 fixture 를 같은 MR 에서 갱신한다.** MR 리뷰어에 소비 측 담당자를 지정한다
3. 소비 측이 새 버전을 처리할 수 있게 된 뒤에 생산 측을 배포한다
4. 배포 후 첫 실행의 이벤트를 소비 측과 함께 한 번 확인한다

**3번의 순서를 지키는 이유** — 소비 측은 아는 것보다 높은 `schema_version` 을 DLQ 로 보낸다
([`02 §1`](../spark/docs/02-input-contract.md)). 순서가 뒤바뀌면 그 사이에 나간 이벤트가 전부
DLQ 에 쌓이고, DLQ 는 자동 재시도하지 않으므로 사람이 되돌려야 한다.

### 잊을 수 없게 만든 것

`events.py` 나 `keys.py` 를 고치면 `tests/common/test_contract_fixtures.py` 가 깨진다. 고치려면
fixture 를 다시 만들어야 하고, 그러면 fixture diff 가 MR 에 남는다. **그 diff 가 통보의
증거다** — 봉투가 바뀌었는데 이 문서와 fixture 가 그대로인 MR 은 만들 수 없다.

## 11. 아직 정해지지 않은 것

이 문서가 못 정하는 것들이다. 소비 측 확인이 필요하다.

| # | 무엇 | 상태 |
|---|---|---|
| 1 | **요약 별도 토픽 이행** | 2026-09-09 재검토. §12의 토픽 생성·유정균 재확인·소비 측 인계가 남음 |
| 2 | **`domain` 값이 `dev` 인가 `development` 인가** | 크롤러는 `dev` 를 내고, 팀 계약과 [`01 §6`](../spark/docs/01-architecture.md) 은 `development` 를 기대한다. `development` 로 통일하기로 했고 크롤러 쪽 수정이 남았다. `fashion` 은 양쪽이 같다 |
| 3 | 날짜 파티션이 발행일 | `web-collect.md` §12 항목 6 의 잠정답이 발행일이고 `keys.py` 가 그대로 구현했다. 확정 도장이 남았다 |
| 4 | consumer group 이름 | §2. 소비 측이 정한다 |
| 5 | DLQ 토픽 이름 | 소비 측 소유. 아직 없다 ([`datastore/README.md`](../../datastore/README.md) "지금 없는 것") |

### `02-input-contract.md` 가 이 문서보다 낡았다

[`spark/docs/02-input-contract.md`](../spark/docs/02-input-contract.md) 는 배치 이벤트를 전제로
쓰였다. 그대로 구현하면 어긋나는 자리:

| `02` 의 내용 | 실제 |
|---|---|
| §2 표: `success` + `record_count>0` + `object_key=null` → 계약 위반 DLQ | 이제 기사 토픽에는 맞는 규칙이다. 요약은 별도 토픽으로 읽는다 |
| §3 `record_count` 를 파싱된 줄 수와 대조 | 객체가 jsonl 이 아니라 단일 JSON 객체다 |
| §6 manifest 모드가 `metadata.json` 을 훑는다 | `metadata.json` 이 없다. `article.json` 이 완료 마커다 (§5) |
| `format: jsonl` · `compression: gzip` | `json` · `none` |

`02` 는 소비 측 소유 문서라 이 문서가 고치지 않는다. 위 목록을 근거로 갱신해 주면 된다.

## 12. 토픽 생성과 소비 측 인계

**머지 전 유정균 재확인이 필요하다.** 2026-09-07(S15P21A102-158)에 함께 접은 토픽 분리
결정을 다시 여는 작업이다. 근거 넷은 `web-collect.md` §12에 기록했다. 토픽 생성 완료까지
구현을 기다릴 필요는 없지만 재확인을 받은 것으로 간주하지 않는다.

| collect-run-summary 생성 요청 | 값 |
|---|---|
| partitions | 1 (7소스 × 24회, 하루 168건 기준) |
| retention.ms | 2592000000 (30일) |
| cleanup.policy | delete (compact면 소스별 최신 1건만 남음) |
| segment.ms | 86400000 |

`datastore/` 담당자가 `kafka-init/init.sh`에 토픽별 파티션·보존 설정을 적용하고,
`.env.example`에 `KAFKA_TOPIC_RUN_SUMMARY` 및 전용 설정을 추가하고 README를 갱신한다.
`KAFKA_AUTO_CREATE_TOPICS_ENABLE=false`이므로 먼저 토픽이 있어야 한다.

생산 측은 기본 비활성(`TRENDIN_KAFKA_TOPIC_RUN_SUMMARY=`)으로 배포할 수 있다.
이때 기사 이벤트는 그대로 발급되고, 요약은 발급하지 않으며 로그와
publish 결과의 `summaries=0`, `summary_enabled=false`로 표시한다. 토픽 생성 후
`.env`를 `TRENDIN_KAFKA_TOPIC_RUN_SUMMARY=collect-run-summary`로 채우고
`docker compose up -d`하면 다음 회차부터 요약을 낸다. 비활성 기간의 요약을 소급 발급하지 않는다.

강민수의 S15P21A102-206에 넘길 변경은 다음과 같다.

- 기사 토픽의 `object_key` 기반 기사/요약 분기를 제거한다. 기사 `run_id`는 이름과 뜻(발급 실행)이
  그대로다. 기사 `record_count`는 항상 1이며, 수집 건수는 요약의 `stored` 합이다.
- 재계산 창 W는 `처리일 − published_date`를 기준으로 잡는다.
  `처리일 − collected_date`(발급·처리 지연)와 `collected_date − published_date`(수집 지연)를
  함께 고려하며, `emitted_oldest_collected_at`이 오래된 수집분의 늦은 도착을 알려 준다.
- 수집 상태 원장은 닫힌 날짜에도 늦게 도착한 이벤트로 다시 열릴 수 있어야 한다.
- 문서와 fixture가 들어 있는 MR을 인계하고, 배포 후 첫 회차 이벤트를 함께 확인한다.

기존 기사 토픽에 나간 요약 196개는 삭제하지 않는다. 기존 7일 보존으로 만료된다.
그동안 과거 이벤트를 처음부터 읽는 `--live` 검증에는 이전 봉투가 섞여 실패할 수 있다.
장부 출처 열(주기/백필), 불투명 UUID, status 확장, 소비 측 문서 직접 수정은 이번 범위 밖이다.
