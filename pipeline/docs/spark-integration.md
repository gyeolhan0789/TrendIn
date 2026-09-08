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
| topic | `raw-file-ready` | `datastore/.env` `KAFKA_TOPIC_RAW_FILE_READY` |
| bootstrap (같은 EC2 의 다른 compose) | `kafka:9092` | 네트워크 `s15p21a102-data` |
| bootstrap (호스트·다른 EC2) | `${KAFKA_EXTERNAL_HOST}:29092` | `datastore/.env` |
| 직렬화 | JSON, UTF-8, 비ASCII 를 escape 하지 않는다 | `kafka_publisher.publish` |
| message key | `source_id` (UTF-8 바이트) | `flow.publish_pending` · `flow.publish_summaries` |
| 파티션 | 6 | 늘릴 수만 있고 줄이지 못한다 |
| `cleanup.policy` | `delete` | `compact` 면 key 가 `source_id` 라 소스당 최신 1 건만 남는다 |
| `retention.ms` | 7일 | MinIO 원문은 90일이다 — 부등식은 §6 |

접속 정보의 정본은 [`datastore/README.md`](../../datastore/README.md) "접속 정보" 절이다. 값이 이 표와 다르면 그쪽이 맞다.

### message key 를 `source_id` 로 둔 결과

같은 소스의 이벤트는 한 파티션에 모여 **순서가 보장된다.** 그래서 어떤 소스의 기사 이벤트들과
뒤이어 나가는 그 소스의 실행 요약 이벤트(§3)는 순서대로 온다. 소스가 다르면 순서 보장이 없다.

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

## 3. 봉투 — 토픽에 모양이 둘 흐른다

팀 계약([`data-pipeline-design.md` §5](data-pipeline-design.md))은 배치 하나에 이벤트 하나를
전제하지만, 크롤러는 **기사 하나에 이벤트 하나**를 낸다 (`web-collect.md` §12 확정 7).
거기에 소스별 실행 요약이 하나 더 붙는다.

| | 기사 이벤트 | 실행 요약 이벤트 |
|---|---|---|
| 언제 | 기사 하나가 MinIO 에 저장된 뒤 | 소스 하나의 실행이 끝날 때마다 (0건·실패에도) |
| `event_id` | `{source_id}-{article_id}` | `{source_id}-{run_id}` |
| `object_key` | article.json 키 | **`null`** |
| `run_id` | **`null`** | `yyyyMMddTHHmmss` (KST) |
| 하루 몇 건 | 700 건 안팎 | 소스 수 × 실행 수 |

### ⚠️ 분기 기준은 `object_key` 의 null 여부다

```python
is_article_event = event["object_key"] is not None
```

**요약 이벤트는 `status: "success"` 인데도 `object_key` 가 `null` 이고 `record_count` 가 0 보다
클 수 있다.** 팀 계약 발행 규약 4 ("`success` 면 `object_key` 는 항상 유효하다")는 배치 이벤트
하나만 있던 때의 문장이라 요약 이벤트에는 적용되지 않는다. 이 조합을 계약 위반으로 읽으면
**정상 실행마다 소스당 하나씩 DLQ 가 쌓인다.**

요약 이벤트를 없애지 않는 이유는 팀 발행 규약 4·5 가 있는 이유와 같다 — 기사 이벤트만 내면
"그 소스에 새 글이 없던 것"과 "그 소스 수집이 실패한 것"이 똑같이 "아무것도 안 옴" 으로 보인다.

### 필드

`events.py` 가 정본이다. 두 모양 다 팀 봉투의 칸을 하나도 빼지 않고, 안 쓰는 칸은 `null` 로 둔다.

| 필드 | 타입 | 기사 이벤트 | 요약 이벤트 |
|---|---|---|---|
| `event_id` | string | `{source_id}-{article_id}` | `{source_id}-{run_id}` |
| `schema_version` | int | `1` | `1` |
| `bucket` | string | `raw-data` | `raw-data` |
| `object_key` | string \| null | article.json 키 | **`null`** |
| `raw_object_key` | string \| null | raw 키. 회원 전용 기사는 `null` | `null` |
| `domain` | string | `fashion` \| `dev` (§11 참고) | 같음 |
| `source_id` | string | 소스 키 (`vogue` 등) | 같음 |
| `article_id` | string \| null | 소스의 기사 식별자 | `null` |
| `run_id` | string \| null | **`null`** | `yyyyMMddTHHmmss` (KST) |
| `url` | string \| null | 기사 정식 URL | `null` |
| `title` | string \| null | 기사 제목 | `null` |
| `published_at` | string \| null | ISO-8601, **소스가 준 오프셋 그대로** | `null` |
| `collected_at` | string | ISO-8601 KST. 그 기사를 받은 시각 | ISO-8601 KST. logical date |
| `status` | string | 항상 `success` | `success` \| `failed` |
| `record_count` | int | 항상 `1` | 그 실행 구간에 발급된 기사 수 (0 이상) |
| `size_bytes` | null | `null` | `null` |
| `checksum` | string \| null | `sha256-` + article.json 의 sha256 | `null` |
| `format` | string \| null | `json` | `null` |
| `compression` | string \| null | `none` | `null` |
| `failure_reason` | string \| null | `null` | `failed` 일 때만 채운다 |
| `members_only` | bool \| null | 회원 전용 기사면 `true` | `null` |

`raw_object_key` · `article_id` · `url` · `title` · `published_at` · `members_only` 는 팀 봉투에
없던 필드다. **추가는 하위 호환이라 `schema_version` 은 그대로다** (§10).

`url` · `source_id` · `published_at` 은 저작권법 제37조 출처 명시라 기사 이벤트에서 절대 비지
않는다 (`web-collect.md` 불변식 11). 화면에 기사를 보일 때 이 셋이 필요하다.

### 주의할 점 셋

**`checksum` 은 `object_key` 가 가리키는 객체, 즉 article.json 의 해시다.** raw 의 해시가 아니다.
raw 의 해시는 article.json 안의 `content_sha256` 이다 (§5). 이름이 비슷한 다른 값이다.

**`record_count` 는 jsonl 줄 수가 아니다.** 기사 이벤트는 항상 `1` 이고 객체는 단일 JSON 객체다.
줄 수와 대조하는 검증은 이 계약에서 성립하지 않는다.

**`collected_at` 은 재처리해도 바뀌지 않는다.** 기사 이벤트는 그 기사를 받은 시각이라, 저장만
되고 발급 전에 죽은 행을 며칠 뒤에 내보내도 값이 그대로다. 요약 이벤트는 logical date 라
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
| 같은 실행을 재시도 | 같은 `event_id` 로 같은 내용이 나간다. `record_count` 는 장부에서 오므로 줄지 않는다 |
| 이벤트가 유실 | `article.json` 이 있는 디렉터리를 훑어 재구성할 수 있다 (§5). Kafka 는 원본이 아니다 |

## 8. 샘플

[`spark/tests/fixtures/contract/`](../spark/tests/fixtures/contract/) 에 이벤트 3건과 그 이벤트가
가리키는 객체 2개가 있다. Kafka·MinIO 를 띄우지 않고 파싱·검증 코드를 테스트할 수 있다.

| 파일 | 무엇 |
|---|---|
| `article-event.json` | 기사 이벤트. `object_key` 가 있다 |
| `run-summary-success.json` | 실행 요약(성공). `object_key` 가 `null` 이고 `record_count` 가 12 다 |
| `run-summary-failed.json` | 실행 요약(실패). `failure_reason` 이 있다 |
| `objects/fashion/vogue/rss/2026/09/03/854414/article.json` | 위 기사 이벤트의 `object_key` 가 가리키는 실물 |
| `objects/fashion/vogue/rss/2026/09/03/854414/raw.xml` | `raw_object_key` 가 가리키는 실물 |

`objects/` 아래 경로는 실제 `object_key` 와 같은 모양이라, 버킷 루트만 바꿔 끼우면 s3a 경로와
같은 코드로 읽힌다.

**`sha256(article.json)` 이 이벤트의 `checksum` 과 실제로 같다.** checksum 검증 코드를 이
fixture 로 그대로 테스트할 수 있다. 본문·요약은 저작권 때문에 합성 문장이다.

`run-summary-success.json` 의 `record_count` 가 0 이 아닌 것은 일부러다. §3 의 분기를 안 하면
이 파일에서 걸린다.

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
| fixture (기본) | fixture 객체를 `_verify/` 아래 올리고 이벤트 3건을 발행한 뒤, **Spark read 전용 키로** 되읽어 검증한다. 끝에서 지운다 | 언제나. 크롤러를 돌리지 않는다 |
| `--live` | 토픽에 쌓인 실제 수집 이벤트를 같은 검증에 통과시킨다 | 크롤러를 한 번 돌린 뒤 |

검사 항목:

| 층 | 무엇을 보나 |
|---|---|
| Kafka | message key == `source_id` · 소스별로 한 파티션에 모이는지 · **요약 이벤트가 그 소스의 기사들 뒤에 오는지** (§2 의 순서 보장) |
| 봉투 | 공통 필드 · `schema_version` · 기사/요약 분기 · 기사의 `run_id` 가 `null` · `record_count=1` · 출처 명시 3종 · 요약의 `failure_reason` |
| MinIO | `object_key` 와 `raw_object_key` 읽기 · `checksum` 대조 · 봉투와 `article.json` 의 값 일치 · raw 가 없으면 `members_only` 인지 |
| 권한 | **Spark 키 write 거부** |

Kafka 층을 따로 두는 이유는 봉투만 봐서는 확인할 수 없기 때문이다. 순서 보장은 message key
와 파티션 배치의 성질이라, 메시지 메타(`key` · `partition` · `offset`)를 함께 봐야 한다.

주소와 키는 `datastore/.env` 에서 읽으므로 포트를 바꿔도 따라간다. `--live` 는 fixture 모드가
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
| 1 | **기사별 이벤트 + 요약 이벤트 구조** | `web-collect.md` §12 항목 4·7 에서 결정. 유정균 확인 완료, **소비 측 확인 남음** |
| 2 | **`domain` 값이 `dev` 인가 `development` 인가** | 크롤러는 `dev` 를 내고, 팀 계약과 [`01 §6`](../spark/docs/01-architecture.md) 은 `development` 를 기대한다. `development` 로 통일하기로 했고 크롤러 쪽 수정이 남았다. `fashion` 은 양쪽이 같다 |
| 3 | 날짜 파티션이 발행일 | `web-collect.md` §12 항목 6 의 잠정답이 발행일이고 `keys.py` 가 그대로 구현했다. 확정 도장이 남았다 |
| 4 | consumer group 이름 | §2. 소비 측이 정한다 |
| 5 | DLQ 토픽 이름 | 소비 측 소유. 아직 없다 ([`datastore/README.md`](../../datastore/README.md) "지금 없는 것") |

### `02-input-contract.md` 가 이 문서보다 낡았다

[`spark/docs/02-input-contract.md`](../spark/docs/02-input-contract.md) 는 배치 이벤트를 전제로
쓰였다. 그대로 구현하면 어긋나는 자리:

| `02` 의 내용 | 실제 |
|---|---|
| `EVENT_SCHEMA` | `raw_object_key` · `article_id` · `url` · `title` · `published_at` · `members_only` 6 개가 없다. `from_json` 이 버린다 |
| `run_id` 가 `nullable=False` | 기사 이벤트는 항상 `null` 이다 |
| §2 표: `success` + `record_count>0` + `object_key=null` → 계약 위반 DLQ | 실행 요약 이벤트가 정확히 그 모양이다 (§3) |
| §3 `record_count` 를 파싱된 줄 수와 대조 | 객체가 jsonl 이 아니라 단일 JSON 객체다 |
| §6 manifest 모드가 `metadata.json` 을 훑는다 | `metadata.json` 이 없다. `article.json` 이 완료 마커다 (§5) |
| `format: jsonl` · `compression: gzip` | `json` · `none` |

`02` 는 소비 측 소유 문서라 이 문서가 고치지 않는다. 위 목록을 근거로 갱신해 주면 된다.
