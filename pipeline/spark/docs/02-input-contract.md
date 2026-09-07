# 02 — 입력 계약

`ingest` Job 이 Kafka 와 MinIO 를 다루는 방식. 상위 문서 [`data-pipeline-design.md`](../../docs/data-pipeline-design.md) §5 가 **생산자** 관점의 계약이라면, 이 문서는 같은 계약을 **소비자** 관점에서 못박는다. 이벤트가 이상할 때 무엇을 하는지가 내용의 절반이다.

## 1. Kafka 소비

| 항목 | 값 | 근거 |
| --- | --- | --- |
| topic | `raw-file-ready` | 상위 문서 §5 |
| consumer group | `spark-ingest` | Job 별로 분리. `extract`·`aggregate` 는 Kafka 를 읽지 않는다 |
| `startingOffsets` | `earliest` | 최초 실행 시. 이후는 checkpoint 가 이긴다 |
| `failOnDataLoss` | `true` | 아래 |
| 트리거 | `Trigger.AvailableNow` | [01 §1](01-architecture.md) |
| 직렬화 | JSON. `value` 를 문자열로 읽고 명시 스키마로 파싱 | |

**`failOnDataLoss=true` 인 이유** — retention 이 지나 오프셋이 사라졌는데 조용히 건너뛰면 그 배치가 통째로 유실된다. 유실은 통계에 구멍으로 나타나는데, 구멍은 몇 주 뒤에야 눈에 띄고 그때는 원인을 찾을 수 없다. 차라리 Job 을 실패시키고 사람이 [§6](#6-재처리) 의 manifest 모드로 복구하게 한다.

### 스키마를 추론하지 않는다

`from_json` 에 스키마를 명시한다. 추론을 켜면 필드가 하나 빠진 이벤트가 조용히 `null` 로 들어와 하류에서 터진다.

```python
EVENT_SCHEMA = StructType([
    StructField("event_id",       StringType(), False),
    StructField("schema_version", IntegerType(), False),
    StructField("bucket",         StringType(), True),
    StructField("object_key",     StringType(), True),
    StructField("domain",         StringType(), False),
    StructField("source_id",      StringType(), False),
    StructField("run_id",         StringType(), False),   # 기사 이벤트는 발급한 실행의 값
    StructField("collected_at",   StringType(), False),
    StructField("status",         StringType(), False),
    StructField("record_count",   LongType(),   True),
    StructField("size_bytes",     LongType(),   True),
    StructField("checksum",       StringType(), True),
    StructField("format",         StringType(), True),
    StructField("compression",    StringType(), True),
    StructField("failure_reason", StringType(), True),
])
```

`mode="FAILFAST"` 가 아니라 `PERMISSIVE` + `_corrupt_record` 로 받아서, 파싱 실패한 것만 DLQ 로 보내고 나머지는 처리한다. 이벤트 하나가 깨졌다고 배치 전체를 버릴 이유가 없다.

### `schema_version`

| 상황 | 처리 |
| --- | --- |
| 알고 있는 버전 | 정상 처리 |
| 알고 있는 것보다 **낮음** | 정상 처리. 하위 호환이 계약이다 (상위 문서 §5 필드 규약) |
| 알고 있는 것보다 **높음** | **DLQ.** 모르는 필드가 있거나 타입이 바뀐 것이다 |

높은 버전을 억지로 처리하지 않는 이유는, 상위 문서가 "제거·타입 변경은 값을 올린다"고 정의했기 때문이다. 값이 올랐다는 것은 우리가 아는 해석이 틀렸을 수 있다는 신호다.

## 2. 이벤트 상태별 처리

`status` 와 `record_count` 조합으로 갈린다.

| `status` | `record_count` | `object_key` | `event_id` 꼬리 | 처리 |
| --- | --- | --- | --- | --- |
| `success` | > 0 | 유효 | — | MinIO 조회 → [§3](#3-원문-조회와-검증) |
| `success` | 0 | 유효 (빈 파일) | — | 원문 조회 생략. 원장에 `COMPLETED`, 문서 0건 기록 |
| `failed` | 0 | `null` | — | 원문 조회 생략. 원장에 `SOURCE_FAILED` + `failure_reason` 기록 |
| `success` | ≥ 0 | `null` | `run_id` | **실행 요약.** 원문 조회 생략. 원장에 그 실행의 수집 건수만 기록 |
| `success` | > 0 | `null` | `run_id` 아님 | **계약 위반.** DLQ |
| 그 외 `status` | — | — | — | **계약 위반.** DLQ |

**넷째 줄이 기사 단위 소스의 실행 요약 이벤트다.** 상위 문서 §5 "입자가 둘이다"가 정의한다 — 기사마다 이벤트를 내는 소스는 배치 객체가 없어서, 0 건과 장애를 구분할 자리를 요약 이벤트가 맡는다. `object_key` 가 `null` 인데 `status` 가 `success` 인 것은 이 한 경우뿐이다.

다섯째 줄은 여전히 생산자 버그다. 조용히 넘기면 영영 안 드러난다.

**`failed` 이벤트를 원장에 남기는 이유** — 실패를 기록하지 않으면 "수집이 실패한 날"과 "그날 아무 일도 없던 날"을 구분할 수 없다. 서비스에는 이 구분을 내보낼 자리가 없지만([§4](#4--수집-상태를-서비스에-알릴-방법이-없다)) 운영 조회에는 반드시 필요하다.

## 3. 원문 조회와 검증

### S3A 설정

```
spark.hadoop.fs.s3a.endpoint                 ${MINIO_ENDPOINT}
spark.hadoop.fs.s3a.path.style.access        true
spark.hadoop.fs.s3a.connection.ssl.enabled   false      # 같은 호스트 내부 통신
spark.hadoop.fs.s3a.aws.credentials.provider org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider
```

`path.style.access=true` 가 필수다. MinIO 는 가상 호스트 스타일(`bucket.host`)이 아니라 경로 스타일(`host/bucket`)을 쓴다.

### 읽는 대상

`s3a://{bucket}/{object_key}`. 이벤트가 준 경로를 그대로 쓰고, 경로를 직접 조립하지 않는다. 조립하면 상위 문서의 경로 규약이 바뀔 때 두 곳을 고쳐야 한다.

`metadata.json` 은 읽지 않는다. 상위 문서 발행 규약 2번이 *"이벤트는 `metadata.json` 의 사본"* 이라고 보장하므로, 이벤트만으로 충분하다. `metadata.json` 을 읽는 것은 manifest 재처리 모드([§6](#6-재처리))뿐이다.

### 검증 세 가지

| 검증 | 방법 | 불일치 시 |
| --- | --- | --- |
| checksum | 객체 바이트의 `sha256` 을 이벤트의 `checksum`(`sha256-` 접두 제거) 과 대조 | **DLQ.** 원문이 손상됐거나 다른 파일이다 |
| `record_count` | 파싱된 줄 수와 대조. 기사 이벤트는 객체가 `article.json` 한 건이라 `1` 과 대조한다 | **DLQ.** 부분 업로드 의심 |
| `size_bytes` | 객체 크기와 대조 | 경고 로그만. checksum 이 이미 더 강한 보증이다 |

**checksum 검증을 생략하지 않는 이유** — 상위 문서가 *"소비 측이 원문 다운로드 후 대조한다"* 고 소비자 책임으로 명시했다. 그리고 부분 업로드된 gzip 은 압축 해제가 성공하면서 뒷부분만 잘려 나가는 경우가 있다. 줄 수 검증만으로는 잡히지만 checksum 이 더 빠르고 확실하다.

**비용** — 파일 전체를 읽어 해시해야 한다. 배치당 수백 KB 수준이라 무시할 만하다. 파일이 GB 급으로 커지면 이 결정을 다시 본다.

## 4. ⚠️ 수집 상태를 서비스에 알릴 방법이 없다

**현행 스키마에는 일자별 수집 상태를 담는 테이블이 없다.**

그래서 프론트에서 이 둘을 구분할 수 없다.

| 실제 상황 | 서비스가 보는 것 |
| --- | --- |
| 그날 아무도 그 키워드를 언급하지 않았다 | 언급량 0 |
| 그날 수집이 실패해 데이터 자체가 없다 | **언급량 0** |

수집이 하루 실패하면 모든 키워드의 그래프가 그날 바닥을 찍고, 사용자에게는 "트렌드가 갑자기 죽었다"로 보인다. 다음 날 회복되면 급상승으로 보인다. **둘 다 사실이 아니다.**

이건 우회할 수 없다. 저장할 자리가 없으면 알릴 방법이 없다. [00 §7](00-overview.md) 한계 1번이고, 기획 확인이 필요하다.

### 그래도 내부에는 남긴다

`ingest` 는 수집 상태를 `pl_batch_stat` 에 기록한다 ([08 §3](08-storage-schema.md)). 서비스로 나가지는 않지만 운영 조회에는 쓸 수 있다 — "9월 3일 그래프가 왜 꺾였나"에 답할 수 있어야 한다.

| 그 일자의 이벤트들 | 내부 기록 |
| --- | --- |
| 전부 `success` | `COMPLETED` |
| 일부만 `success` | `PARTIAL` |
| 전부 `failed` | `MISSING` |
| 이벤트가 하나도 없음 | 행 없음 |

수집 건수도 함께 남긴다. **배치 이벤트와 실행 요약 이벤트**의 `record_count` 합이며, 정제·중복 제거 **이전** 값이다. 기사 이벤트는 세지 않는다 — 한 실행의 기사 이벤트 건수는 그 실행의 요약 이벤트가 이미 들고 있어서, 같이 더하면 두 번 센다.

배치와 기사를 가르는 건 `format` 이다. 배치는 `jsonl`, 기사는 `json`, 요약은 `null` 이다. `event_id` 를 파싱해 가르지 않는다 — 생산·소비 양쪽이 같은 파싱을 각자 들고 있게 된다.

| `format` | 무엇 | 건수에 세나 |
| --- | --- | --- |
| `jsonl` | 배치 이벤트 | 센다 |
| `json` | 기사 이벤트 | 안 센다 |
| `null` | 실행 요약 이벤트 | 센다 | "수집이 얼마나 됐나"를 보는 것이지 "얼마나 살아남았나"가 아니다.

### 날짜 축이 두 개라는 것도 기록해둔다

수집 상태는 **수집 일자** 기준이고(`collected_at` 의 KST date, MinIO 경로의 `collected_date`), 언급량은 **발행 일자** 기준이다 ([07 §3](07-metrics-and-ranking-spec.md)). 상위 문서가 *"키워드가 언제 화제였는지는 문서별 `published_at` 으로 집계하며, `collected_at` 은 파이프라인 운영 정보로만 쓴다"* 고 못박았기 때문이다.

두 축을 잇는 근사는 이렇다 — 소스 셋이 모두 **최신 글을 수집**하므로, 수집일 D 에 들어오는 문서의 발행일은 대부분 D 또는 D-1 이다. 따라서 수집일 D 의 실패는 발행일 D 부근의 결손을 뜻한다.

나중에 상태 테이블이 생기면 이 근사를 그대로 쓰면 된다.

## 5. DLQ

계약 위반과 검증 실패는 조용히 버리지 않는다.

| 무엇을 | 어디로 |
| --- | --- |
| Kafka 메시지 원문 + 실패 사유 | DLQ 토픽 (담당 2 소유. 토픽명은 담당 2와 확정) |
| 같은 내용 | 내부 `processing_error` 테이블 ([08 §3](08-storage-schema.md)) |

**두 곳에 쓰는 이유** — DLQ 토픽은 재투입 경로이고, 테이블은 조회·집계 경로다. "지난주에 어떤 소스가 몇 번 실패했나"를 Kafka 에서 세는 것은 불편하다.

DLQ 메시지 스키마 (제안. 담당 2와 확정 필요):

```json
{
  "original_event": { "...원본 이벤트 그대로..." },
  "failed_at": "2026-09-03T01:12:44+09:00",
  "job": "ingest",
  "error_type": "CHECKSUM_MISMATCH",
  "error_detail": "expected sha256-abc..., got sha256-def...",
  "retry_count": 0
}
```

`error_type` 값: `PARSE_ERROR`, `UNKNOWN_SCHEMA_VERSION`, `CONTRACT_VIOLATION`, `OBJECT_NOT_FOUND`, `CHECKSUM_MISMATCH`, `RECORD_COUNT_MISMATCH`, `UNKNOWN_DOMAIN`, `DECOMPRESS_ERROR`.

`UNKNOWN_DOMAIN` 이 따로 있는 이유는 [01 §6](01-architecture.md) 의 도메인 표기 문제 때문이다. 매핑에 없는 `domain` 값은 처리하지 않고 DLQ 로 보낸다.

**DLQ 에서 자동 재시도하지 않는다.** 여기 오는 것들은 대부분 재시도해도 같은 결과다(체크섬은 다시 계산해도 틀리고, 스키마 버전은 저절로 안 내려간다). 사람이 원인을 보고 [§6](#6-재처리) 으로 다시 흘린다.

## 6. 재처리

두 모드를 둔다. `spark-submit` 인자로 고른다.

### 모드 A — `--source kafka` (평시)

checkpoint 기반. Airflow 가 매 스케줄에 이 모드로 부른다. 설명은 [01 §1](01-architecture.md).

### 모드 B — `--source manifest` (백필·복구)

**`Trigger.AvailableNow` 는 오프셋을 진행시키므로, 이미 소비한 이벤트는 Kafka 를 다시 읽어도 오지 않는다.** 그래서 재처리 경로가 따로 필요하다.

```
spark-submit ingest.py \
  --source manifest \
  --domain development \
  --from 2026-09-01 --to 2026-09-03 \
  --force
```

동작:

1. Kafka 를 읽지 않는다. checkpoint 를 건드리지 않는다.
2. MinIO `raw-data` 에서 해당 범위의 디렉터리를 훑어 **`metadata.json` 이 있는 것만** 고른다. 상위 문서 발행 규약 1번이 *"`metadata.json` 이 없는 디렉터리는 미완성으로 보고 읽지 않는다"* 고 정의한 그대로다.
3. `metadata.json` 에서 이벤트를 재구성한다. `event_id` 는 `{source_id}-{run_id}` 규칙으로 만든다.
4. 이후는 모드 A 와 같은 코드 경로.
5. `--force` 가 있으면 원장의 `COMPLETED` 를 무시하고 다시 처리한다.

**이 모드가 성립하는 이유** — 상위 문서 §5 재발행 절이 *"Kafka 는 원본이 아니다. 토픽이 유실되어도 `metadata.json` 이 있는 디렉터리를 훑어 이벤트를 그대로 재구성할 수 있다"* 고 보장한다. 그 보장을 코드로 옮긴 것이다.

**기사 단위 소스는 이 모드로 못 훑는다.** `metadata.json` 을 쓰지 않기 때문이다(상위 문서 발행 규약 1번의 면제). 대신 그쪽은 수집 장부 `collected_article` 이 원본이고, 재발행은 생산자가 한다 — 장부의 `event_emitted_at` 을 비우면 다음 발급 태스크가 그 행들을 다시 낸다. 소비 측이 할 일은 원장의 `COMPLETED` 를 지우고 다시 받는 것뿐이다.

### 재처리 시 지워야 할 것

`--force` 재처리는 기존 산출물을 덮어써야 한다. 삭제 범위:

| 대상 | 범위 |
| --- | --- |
| MinIO `curated` | 그 `run_id` 파티션 |
| 내부 원장 | 그 `event_id` 행 |
| `contents` | **지우지 않는다.** `url` 유니크로 upsert ([08 §2](08-storage-schema.md)) |
| `contents.body_object_key` | 파티션 파일명이 바뀌면 갱신 ([01 §3](01-architecture.md)) |
| 하류 산출물 | `extract`·`aggregate` 를 이어서 다시 돌린다 |

`contents` 를 지우지 않는 이유는 `keyword_contents` 가 매달려 있어서, 콘텐츠 한 행을 지우면 사용자에게 보이던 연결이 사라지기 때문이다.

**checkpoint 를 지워서 재처리하는 방법은 쓰지 않는다.** 그러면 토픽의 모든 이벤트를 처음부터 다시 읽게 되고, 범위를 지정할 수 없다. 모드 B 가 있는 이유다.
