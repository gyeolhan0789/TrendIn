# 02 — 입력 계약

`ingest` Job 이 Kafka 와 MinIO 를 다루는 방식. 이벤트가 이상할 때 무엇을 하는지가 내용의 절반이다.

## 0. 이 문서의 근거

**생산자 계약의 기준은 [`../../docs/web-collect.md`](../../docs/web-collect.md) #5·#6 과 그 구현이다.** 이 문서는 같은 계약을 소비자 관점에서 명시한다.

| 무엇 | 어디 |
| --- | --- |
| 이벤트 메시지 두 형태 | `web-collect.md` #6, `src/trendin/common/collect/events.py` |
| MinIO 키 규칙 | `web-collect.md` #5.1, `src/trendin/common/collect/keys.py` |
| `article.json` 스키마 | `web-collect.md` #5.3, `src/trendin/common/collect/article.py` |
| 발행 순서·멱등·전달 보장 | `web-collect.md` #7 불변식 5·7·12 |
| 발행 시점 · 요약 이벤트 생성 | `src/trendin/common/collect/dag_factory.py` 의 `publish` 태스크, `flow.publish_pending()` · `flow.publish_summaries()` |

`data-pipeline-design.md` §5 는 **배치 파일 하나에 이벤트 하나**를 전제로 쓰였고, 실제 수집은 **기사 하나에 이벤트 하나**로 갔다 (`web-collect.md` #12 열린 질문 7, 2026-09-07 확정). 필드 이름은 팀 계약 그대로 쓰고 뜻만 기사 단위로 옮겼다. 두 문서가 어긋나는 자리에서는 **`web-collect.md` 와 구현이 우선한다** — 그쪽이 실제로 발행하는 쪽이다.

### 확정 이력 — 한 번 뒤집혔다가 돌아왔다

`S15P21A102-158` 이 **새 토픽 `article-collected` + 새 메시지**로 갈아타는 안을 실제로 구현했다가 되돌렸다. `web-collect.md` #12-7:

> **유정균 확인 완료 (2026-09-07, S15P21A102-158)** — 158 에서 새 토픽·새 메시지로 갈아타는 안을 만들어 보고 되돌렸다. 소비 측(169)과 `datastore/` 를 건드리는 값이 이득보다 컸다

그래서 아래가 확정이다. 되돌린 안의 값을 표에 남기는 이유는, 그 이름이 문서·대화에 한동안 떠 있었고 다시 언급될 수 있기 때문이다.

| 항목 | 확정 | 되돌린 안 (158 중간 산출물) |
| --- | --- | --- |
| 토픽 | `raw-file-ready` | ~~`article-collected`~~ |
| 스키마 버전 | `schema_version: 1` (정수) | ~~`schema: "article.collected.v1"`~~ |
| `event_id` | `{source}-{article_id}` | ~~`{source}:{article_id}`~~ |
| message key | `source_id` | ~~`event_id`~~ |
| 객체 키 필드 | `object_key` · `raw_object_key` | ~~`article_key` · `raw_key`~~ |
| 이벤트 형태 | **둘** (기사 + 실행 요약) | ~~하나 (기사만)~~ |

근거는 `datastore/compose.yaml` 의 `KAFKA_TOPIC_RAW_FILE_READY`, `kafka_publisher.py` 의 `TRENDIN_KAFKA_TOPIC_RAW_FILE_READY`, `conf/base.yaml` 의 `kafka.topics.raw_file_ready` 가 전부 같은 값을 가리키는 것이다.

**소비 측 확인은 이 문서다.** `web-collect.md` #12-4·#12-7 은 *유정균 확인 완료 (2026-09-07)* 로 닫혔고, 분기 규칙을 소비 계약에 적는 일은 `S15P21A102-206`(강민수) 으로 넘어왔다 — [§2](#2-이벤트-두-형태) 가 그 규칙이다. 함께 열려 있던 *"기사 이벤트의 `run_id` 를 채울지"*(`S15P21A102-205`) 는 **채우는 쪽**으로 끝났다 (아래).

### 2026-09-09 대조 — 구현과 다시 맞췄다

`dag_factory.py` · `flow.py` · `events.py` · `kafka_publisher.py` 와 소비 측 코드를 이 문서와 대조했다. 어긋났던 자리와 고친 방향:

| 항목 | 이 문서의 옛 내용 | 구현 (2026-09-09) |
| --- | --- | --- |
| 기사 이벤트의 `run_id` | `null` — "기사는 실행에 속하지 않는다" | **그 기사를 발급한 실행** (`S15P21A102-204`, `events.article_event`). 수집한 실행이 아니다 — 저장만 되고 못 나간 행은 다음 실행이 내므로 둘이 갈리고, 그게 정상이다 |
| 요약 `record_count` | 발행 구간 누적 | **그 실행이 발급한 건수.** 수집 이력의 `event_run_id` 로 센다 (`ledger.emitted_by_run`) |
| `failed` 요약의 `record_count` | 늘 `0` | **0 이 아닐 수 있다** — 죽은 소스라도 이월분·죽기 전 저장분이 이번 발급에 딸려 나간다 ([§2](#요약-이벤트--처리-규칙)) |
| `ARTICLE_SCHEMA` | `categories` · `extra` 없음 | `categories` 는 있다 (171). `extra` 만 없다 |
| 수집 상태 → `pl_batch_stat` | 기록한다 | **아직 없다.** 요약 이벤트는 처리 이력(`pl_processing_ledger`)까지만 남는다 ([§4](#4-수집-상태)) |
| 모드 A 를 부르는 Airflow DAG | 매 스케줄에 부른다 | **아직 없다.** `spark/scripts/submit.sh` 로 손으로 부른다 ([09 §5](09-dev-and-test.md)) |

**요약 이벤트는 실제로 발행된다.** `fashion_collect` DAG 의 마지막 태스크 `publish` 가 매 정시에 `flow.publish_pending()` 으로 그 도메인의 밀린 기사 이벤트를 전부 낸 뒤, `flow.publish_summaries()` 로 소스 7 개마다 하나씩 낸다 — 0 건이어도, 소스 태스크가 죽었어도 (`trigger_rule=ALL_DONE`). 죽은 소스는 XCom 을 남기지 않으므로 "소스 목록 − 돌아온 소스" 가 `status: failed` 가 된다 (`flow.source_statuses`). `dev_collect` 는 `source_keys` 가 비어 있어 기사도 요약도 하나도 내지 않는다.

**`../../docs/spark-integration.md` 가 이 지점에서 낡았다.** §3 필드 표와 §9 검사 항목이 기사 이벤트의 `run_id` 를 `null` 로 적고 있고, §2 가 이 문서의 consumer group 을 `spark-ingest` 로 인용하며, §11 의 "02 가 낡았다" 표는 전부 반영된 항목이다. `events.py` · `scripts/verify-spark-integration.py` 는 이미 `run_id` 가 있는 쪽이고, 이 문서는 `trendin-spark-ingest` 접두어다. 그 문서는 담당 1 소유라 여기서 고치지 않고 요청으로 남긴다.

### 검증 해시 — 경로가 둘이고 둘 다 `article.json` 을 가리킨다

이름이 비슷한 값이 셋 있어서 헷갈리기 쉽다. **읽는 파일이 `article.json` 이므로 대조할 해시도 `article.json` 것이어야 한다.**

| 값 | 무엇의 해시 | 어디 |
| --- | --- | --- |
| 이벤트 `checksum` | **`article.json` 바이트** | 메시지. `events.py` 가 `f"sha256-{row.article_sha256}"` 로 넣는다 |
| 객체 메타데이터 `content-sha256` | **그 객체 자신** — `article.json` 객체에는 `article.json` 의 해시 | MinIO 객체 헤더 (`S15P21A102-158` 확정) |
| 수집 이력 `content_sha256` | **raw 바이트** | `collected_article` 컬럼. **이벤트 필드가 아니다** |

`web-collect.md` #5.1 이 객체 메타데이터를 확정하면서 *"`content-sha256` 은 그 객체 자신의 해시다 — raw 객체에는 raw 의 해시, article.json 에는 article.json 의 해시"* 로 명시했다. 그래서 메시지의 `checksum` 과 객체 메타데이터가 같은 값이고, **검증 경로가 둘로 늘었다.**

메시지를 쓴다. 객체 메타데이터는 메시지 없이 객체만 가진 경우([§6](#6-재처리) 모드 B)를 위한 것이고, 그 모드에서 checksum 검증을 되살릴 수 있게 해준다 — 자기 자신을 해싱해 비교하는 것이 아니라 **업로드 시점에 기록된 값**과 비교하는 것이라 손상 검출이 성립한다.

**수집 이력의 `content_sha256` 을 쓰면 전량 불일치한다.** 그건 raw 의 해시다. `ledger.py` 의 `PendingArticle` 주석이 *"이름만 비슷한 다른 값"* 이라고 따로 경고해 둔 지점이다.

### 스키마 변경 통보

`web-collect.md` #10 교체 지점 표가 *"이벤트: #6 토픽·키·메시지 스키마 v1 — 발행기와 **모든 소비자**. 스키마 버전을 올린다"* 로 정의한다. 즉 통보 경로는 `schema_version` 이다. 필드 추가는 하위 호환이라 값이 그대로고, 제거·타입 변경은 값이 오른다. 값이 오르면 [§1](#schema_version) 대로 **처리하지 않고 DLQ 로 보낸다** — 모르는 버전을 추측으로 해석하지 않는다.

## 1. Kafka 소비

| 항목 | 값 | 근거 |
| --- | --- | --- |
| topic | `raw-file-ready` | [§0](#0-이-문서의-근거) |
| message key | `source_id` | 같은 소스의 이벤트가 한 파티션에 모여 순서가 보장된다. 요약 이벤트가 그 소스의 기사들 **뒤에** 선다 |
| consumer group | `trendin-spark-ingest` **접두어** | `conf/base.yaml` 의 `kafka.group_id_prefix`(`trendin-spark`) + Job 이름을 Kafka 소스의 `groupIdPrefix` 옵션으로 넘긴다 (`io/kafka.py`). Spark 가 그 뒤에 자기 식별자를 붙이므로 실제 group 은 이 접두어로 **시작**한다. `kafka.group.id` 를 직접 박지 않는 이유는 오프셋을 checkpoint 가 관리하기 때문이다 — group 을 고정하면 브로커의 커밋 오프셋과 checkpoint 가 두 벌이 된다. 환경변수 `KAFKA_GROUP_ID_PREFIX` 가 접두어를 덮는다 |
| `startingOffsets` | `earliest` | 최초 실행 시. 이후는 checkpoint 가 우선한다 |
| `failOnDataLoss` | `true` | 아래 |
| 트리거 | `Trigger.AvailableNow` | [01 §1](01-architecture.md) |
| 직렬화 | JSON. `value` 를 문자열로 읽고 명시 스키마로 파싱 | |
| 전달 보장 | at-least-once. **중복이 정상이다** | `flow.publish_pending()` 이 발행 → 수집 이력 기록 순서라, 그 사이에서 죽으면 다음 실행이 같은 이벤트를 다시 낸다 |

**`failOnDataLoss=true` 인 이유** — retention 이 지나 오프셋이 사라졌는데 조용히 건너뛰면 그 구간이 통째로 유실된다. 유실은 통계에 구멍으로 나타나는데, 구멍은 몇 주 뒤에야 눈에 띄고 그때는 원인을 찾을 수 없다. 차라리 Job 을 실패시키고 사람이 [§6](#6-재처리) 의 objects 모드로 복구하게 한다.

**중복이 정상인 것의 결과** — 생산자가 at-least-once 이므로 `event_id` 처리 이력([01 §4](01-architecture.md) 중복 차단 2)이 선택이 아니라 필수다. checkpoint 만으로는 막을 수 없다. 생산자가 죽는 자리가 실제로 있고(발행 성공 → `mark_emitted` 전 사망), 그때 같은 `event_id` 가 다시 나온다.

### 스키마를 추론하지 않는다

`from_json` 에 스키마를 명시한다. 추론을 켜면 필드가 하나 빠진 이벤트가 조용히 `null` 로 들어와 하류에서 터진다.

```python
EVENT_SCHEMA = StructType([
    StructField("event_id",       StringType(),  False),
    StructField("schema_version", IntegerType(), False),
    StructField("bucket",         StringType(),  True),
    StructField("object_key",     StringType(),  True),   # article.json 키. 요약은 null
    StructField("raw_object_key", StringType(),  True),   # raw.{xml|html|json}. 회원 전용·요약은 null
    StructField("domain",         StringType(),  True),
    StructField("source_id",      StringType(),  True),
    StructField("article_id",     StringType(),  True),   # 요약은 null
    StructField("run_id",         StringType(),  True),   # 기사는 그 기사를 발급한 실행. 요약은 그 실행
    StructField("url",            StringType(),  True),   # 요약은 null
    StructField("title",          StringType(),  True),   # 요약은 null
    StructField("published_at",   StringType(),  True),   # 요약은 null
    StructField("collected_at",   StringType(),  True),
    StructField("status",         StringType(),  True),
    StructField("record_count",   LongType(),    True),
    StructField("size_bytes",     LongType(),    True),   # 늘 null (아래)
    StructField("checksum",       StringType(),  True),   # article.json 의 해시. 요약은 null
    StructField("format",         StringType(),  True),
    StructField("compression",    StringType(),  True),
    StructField("failure_reason", StringType(),  True),
    StructField("members_only",   BooleanType(), True),
    # PERMISSIVE 모드가 파싱 실패를 담는 칸. 스키마에 없으면 Spark 가 채우지 않는다.
    StructField("_corrupt_record", StringType(), True),
])
```

기준은 `src/trendin/spark/io/schema.py` 의 `EVENT_SCHEMA` 다. 위는 그 사본이다.

**`event_id` · `schema_version` 만 non-nullable 이다.** 나머지가 전부 nullable 인 이유는 [§2](#2-이벤트-두-형태) 의 두 형태가 같은 메시지를 쓰면서 안 쓰는 칸을 `null` 로 두기 때문이다. 스키마에서 non-nullable 로 잠그면 요약 이벤트가 파싱 단계에서 통째로 깨진다. **어느 칸이 채워져 있어야 하는지는 스키마가 아니라 [§2](#2-이벤트-두-형태) 의 분기가 판별한다.**

`mode="FAILFAST"` 가 아니라 `PERMISSIVE` + `_corrupt_record` 로 받아서, 파싱 실패한 것만 DLQ 로 보내고 나머지는 처리한다. 이벤트 하나가 깨졌다고 배치 전체를 버릴 이유가 없다.

**팀 이벤트 규격에 없는 필드 여섯** — `raw_object_key` · `article_id` · `url` · `title` · `published_at` · `members_only`. `data-pipeline-design.md` §5 의 규격은 15 칸이고 우리 것은 21 칸이다. 추가는 하위 호환이라 `schema_version` 은 1 그대로다 (`web-collect.md` #6). `url` · `published_at` 은 저작권법 제37조 출처 명시라 기사 이벤트에 **항상** 있다 (불변식 11).

**`size_bytes` 는 늘 `null` 이다.** 생산자 수집 이력이 객체 크기를 들고 있지 않다 (`events.py`: *"소비 측이 대조에 쓰는 건 checksum 이다"*). 그래서 크기 대조 검증은 없다.

### `schema_version`

| 상황 | 처리 |
| --- | --- |
| 알고 있는 버전 (현재 `1`) | 정상 처리 |
| 알고 있는 것보다 **낮음** | 정상 처리. 하위 호환이 계약이다 |
| 알고 있는 것보다 **높음** | **DLQ** (`UNKNOWN_SCHEMA_VERSION`) |

높은 버전을 억지로 처리하지 않는 이유는, 계약이 "제거·타입 변경은 값을 올린다" 고 정의했기 때문이다. 값이 올랐다는 것은 우리가 아는 해석이 틀렸을 수 있다는 신호다.

## 2. 이벤트 두 형태

**하나의 토픽에 형태가 둘 흐른다.** 분기는 소비 측 책임이다 (`web-collect.md` #12-4: *"한 토픽에 형태가 둘이라 소비 측이 분기해야 한다"*).

| | 기사 이벤트 | 실행 요약 이벤트 |
| --- | --- | --- |
| **판별** | `object_key` 가 있다 | **`object_key` 가 `null` 이다** |
| 언제 | MinIO `stat` 으로 저장을 확인한 뒤, 기사마다 하나 | 소스별 수집이 끝난 뒤, 소스·실행마다 하나 |
| `event_id` | `{source_id}-{article_id}` | `{source_id}-{run_id}` |
| `run_id` | **그 기사를 발급한 실행.** 수집한 실행이 아닐 수 있다 (이월분) | 그 실행 |
| `collected_at` | 그 기사를 받은 시각 (KST). 다시 내도 안 바뀐다 | logical date (KST). 재시도해도 같다 |
| `status` | 늘 `success` | `success` \| `failed` |
| `record_count` | 늘 `1` | 그 실행에서 발행한 기사 수 |
| `checksum` | `sha256-…` (article.json) | `null` |
| 하는 일 | MinIO 조회 → 검증 → 정제 ([03](03-normalization-spec.md)) | 객체 조회 없음. 수집 상태만 기록 ([§4](#4-수집-상태)) |

> **`object_key: null` 은 계약 위반이 아니다.** 요약 이벤트의 정상적인 식별 표지다. 배치 계약 시절의 "`success` 인데 `object_key` 가 `null` 이면 DLQ" 규칙을 그대로 남겨두면 **요약 이벤트를 전부 버린다.**

### 기사 이벤트 — 처리 규칙

| 조건 | 처리 |
| --- | --- |
| `status == "success"`, `object_key` 유효, `checksum` 있음 | MinIO 조회 → [§3](#3-객체-조회와-검증) |
| `bucket` · `article_id` · `url` · `published_at` 중 하나가 비었다 | **계약 위반.** DLQ (`CONTRACT_VIOLATION`) — 뒤 셋은 불변식 11 이 보장하는 값이고, `bucket` 이 없으면 s3a 경로를 만들 수 없다 |
| `checksum` 이 `null` | **계약 위반.** DLQ — 검증할 수 없는 객체는 받지 않는다 |
| `status != "success"` | **계약 위반.** DLQ — 기사 이벤트는 저장 확인 뒤에만 나가므로(불변식 5) `failed` 가 있을 수 없다 |
| `domain` 이 허용 목록 밖 | **DLQ** (`UNKNOWN_DOMAIN`). [01 §6](01-architecture.md) |

### 요약 이벤트 — 처리 규칙

| `status` | `record_count` | 처리 |
| --- | --- | --- |
| `success` | ≥ 0 | 처리 이력에 `COMPLETED`. 그 소스·실행이 정상 종료했다는 기록만 남긴다 |
| `failed` | ≥ 0 | 처리 이력에 `SOURCE_FAILED` + `failure_reason`. **건수가 0 이 아니어도 정상이다** (아래) |
| 둘 다 | < 0 | **계약 위반.** DLQ — 발행 건수가 음수일 수 없다 |
| 그 외 `status` | — | **계약 위반.** DLQ — `run_summary_event()` 가 `success` \| `failed` 만 허용한다 |
| `run_id` 가 비었다 | — | **계약 위반.** DLQ — 요약 이벤트의 `event_id` 가 `{source}-{run_id}` 라 `run_id` 없이는 실행을 특정할 수 없다 |
| `record_count` 가 없다 | — | **계약 위반.** DLQ — 0 과 "안 왔다" 를 구분해야 한다 |
| `failed` 인데 `failure_reason` 이 비었다 | — | **계약 위반.** DLQ — 팀 발행 규약 5 |

판별 순서는 `contract._check_summary()` 가 기준이다. `status` → `run_id` → `record_count` 존재 →
음수 → (`failed` 면) `failure_reason` 순이고, 먼저 걸린 사유 하나만 보고한다.

**`failed` 인데 `record_count > 0` 은 계약 위반이 아니다.** `publish` 태스크는 소스 성패와 무관하게 그 도메인의 밀린 기사를 **전부** 낸다 (`flow.publish_pending`). 그래서 소스 태스크가 죽어도 (a) 지난 실행에서 저장만 되고 못 나간 이월분, (b) 이번 실행에서 403·429 를 맞고 멈추기 전에 저장한 기사가 이번 `run_id` 로 나가고, `ledger.emitted_by_run` 이 그 수를 그 소스의 `record_count` 로 센다. 죽은 소스의 건수를 0 으로 못 박으면 이 두 경우가 전부 DLQ 로 가고, 그 실행의 `SOURCE_FAILED` 기록이 사라진다 — 실패를 기록하려고 만든 이벤트가 실패했을 때 버려지는 꼴이다.

`contract._check_summary()` 가 한동안 `failed` + `record_count != 0` 을 `CONTRACT_VIOLATION` 으로 보냈다 — 2026-09-09 대조에서 잡아 고쳤다. 소스가 부분 실패하지 않은 동안은 드러나지 않았을 결함이다.

**요약 이벤트를 버리지 않는 이유** — 실패를 기록하지 않으면 "수집이 실패한 날" 과 "그날 아무 일도 없던 날" 을 구분할 수 없다. 기사 이벤트만 보면 둘 다 "아무것도 안 옴" 으로 똑같이 보인다. 이게 생산자가 요약 이벤트를 따로 내는 이유이기도 하다.

**요약 이벤트도 `event_id` 처리 이력을 탄다.** `{source}-{run_id}` 라서 같은 실행이 재시도돼도 같은 값이고, 그 재시도가 중복 기록으로 남지 않는다.

## 3. 객체 조회와 검증

기사 이벤트만 이 절을 탄다.

### S3A 설정

```
spark.hadoop.fs.s3a.endpoint                 ${MINIO_ENDPOINT}
spark.hadoop.fs.s3a.endpoint.region          ${MINIO_REGION}     # SDK v2 가 요구한다
spark.hadoop.fs.s3a.path.style.access        true
spark.hadoop.fs.s3a.connection.ssl.enabled   false      # 같은 호스트 내부 통신
spark.hadoop.fs.s3a.aws.credentials.provider org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider
```

`path.style.access=true` 가 필수다. MinIO 는 가상 호스트 스타일(`bucket.host`)이 아니라 경로 스타일(`host/bucket`)을 쓴다. 리전은 MinIO 에 개념이 없지만 값이 없으면 SDK v2 가 요청을 만들기 전에 죽는다 ([01 §7](01-architecture.md)).

**Spark 용 자격증명은 read 전용이어야 한다.** `raw-data` 는 담당 1 소유이고 이 Job 은 읽기만 한다 ([01 §3](01-architecture.md)). 쓰기 권한이 붙어 있으면 정제 로직의 버그가 객체를 건드릴 수 있고, 객체는 되돌릴 수 없다. 키 발행은 담당 2 소관이며, 확인 방법은 [09 §4](09-dev-and-test.md).

### 읽는 대상

`{bucket}/{object_key}` — **`article.json` 하나뿐이다.** `bucket` 은 메시지가 준 값을 그대로 쓴다.

### ⚠️ `binaryFile` 소스를 쓰지 않는다

계약이 `OBJECT_NOT_FOUND` 를 **이벤트 하나의** DLQ 사유로 정의하는데, Spark 의 `binaryFile` 소스는 없는 경로가 하나만 섞여도 계획 단계에서 `[PATH_NOT_FOUND]` 로 **배치 전체를 죽인다.** `spark.sql.files.ignoreMissingFiles` 도 듣지 않는다 — 그 옵션은 목록을 만든 뒤 파일이 사라진 경우만 덮는다 (2026-09-08 실측).

| 시도 | 결과 |
| --- | --- |
| 있는 경로만 | 읽힌다 |
| 없는 경로가 섞임 | `[PATH_NOT_FOUND]` — 배치 전체 실패 |
| 읽기 옵션 `ignoreMissingFiles=true` | 같음 |
| `spark.sql.files.ignoreMissingFiles=true` | 같음 |

이벤트 하나가 가리키는 객체가 없다고 그 배치의 나머지 수백 건을 버릴 수는 없다. 그래서 **executor 에서 행마다 S3 클라이언트로 가져온다** (`io/objects.py`). 부수 효과로 바이트가 DataFrame 을 거치지 않는다 — 받아서 해싱하고 검증한 뒤 판별만 남기고 버리므로 배치가 가볍다.

**S3A 설정은 그대로 둔다.** `curated` 쓰기가 그 경로를 쓴다 ([01 §3](01-architecture.md)). 즉 이 Job 은 읽기에 S3 클라이언트를, 쓰기에 S3A 를 쓴다.

**404 만 `OBJECT_NOT_FOUND` 다.** 403 을 "없음" 으로 무시하면 정책이 잘못 붙은 날 배치가 통째로 DLQ 가 되고, 그게 생산자 잘못으로 보인다 — 우리 키 설정이 틀린 것인데. 나머지 오류는 그대로 올려 Job 을 실패시킨다.

**`raw_object_key` 는 읽지 않는다.** raw 는 받은 바이트 그대로(불변식 8)이고, 정규화를 다시 할 수 있게 남겨둔 것이다. 우리가 쓰는 것은 이미 정규화된 `article.json` 이다. raw 를 읽으면 소스별 HTML·XML 파싱을 소비 측에서 또 하게 되고, 그건 생산자가 이미 한 일이다.

이벤트가 준 경로를 **그대로** 쓰고 키를 직접 조립하지 않는다. 조립하면 `web-collect.md` #5.1 의 키 규약이 바뀔 때 두 곳을 고쳐야 한다. 참고로 그 규약은 이렇다 — 조립용이 아니라 [§6](#6-재처리) 의 프리픽스 스캔 범위를 이해하기 위한 것이다.

```
{bucket}/{domain}/{source}/{route}/{yyyy}/{mm}/{dd}/{article_id}/article.json
{bucket}/{domain}/{source}/{route}/{yyyy}/{mm}/{dd}/{article_id}/raw.{xml|html|json}
```

`yyyy/mm/dd` 는 **발행일 KST** 다 (불변식 10). 수집일이 아니다 — 같은 기사를 언제 다시 받아도 같은 키에 간다. `route` 와 확장자는 1:1 이다 (`rss`→`xml`, `listing`→`html`, `api`→`json`).

**Hive 스타일 파티션 이름(`domain=…/collected_date=…`)이 아니다.** 경로 조각이 키 이름 없이 값만 있으므로, Spark 로 이 프리픽스를 읽을 때 파티션 컬럼이 자동으로 붙지 않는다. 필요한 값은 이벤트나 `article.json` 에서 가져온다.

**`metadata.json` 은 없다.** 배치 계약 시절의 산출물이고, 기사 단위로 가면서 사라졌다. 그 자리를 대신하는 것은 `article.json` 자체다 ([§6](#6-재처리)).

### 검증 두 가지

| 검증 | 방법 | 불일치 시 |
| --- | --- | --- |
| 객체 존재 | 읽기 실패 | **DLQ** (`OBJECT_NOT_FOUND`). 불변식 5 가 보장하는 것이라 생산자 버그거나 보존 기간 경과다 |
| checksum | `article.json` **바이트**의 `sha256` 을 이벤트 `checksum`(`sha256-` 접두 제거)과 대조 | **DLQ** (`CHECKSUM_MISMATCH`) |
| 시각 | `article.json` 의 `published_at` · `collected_at` 이 **오프셋 있는 ISO-8601** 로 읽히는지 | **DLQ** (`ARTICLE_CONTRACT_VIOLATION`). 있기만 한 값을 통과시키면 `published_date` 없는 파티션에 쓰인다 ([03 §3](03-normalization-spec.md)) |

### 객체 메타데이터

`article.json` 객체에 두 값이 붙어 있다 (`web-collect.md` #5.1, `S15P21A102-158` 확정).

| 키 | 값 |
| --- | --- |
| `collected-at` | ISO-8601 **KST**. 객체를 받은 시각 |
| `content-sha256` | **그 객체 자신의** 해시. `article.json` 객체에는 `article.json` 의 해시 |

**평시(모드 A)에는 읽지 않는다.** 메시지의 `checksum` 이 같은 값이고, 메타데이터를 읽으려면 `HEAD` 요청이 하나 더 붙는다. 쓰는 곳은 [§6](#6-재처리) 모드 B — 메시지가 없을 때의 유일한 대조 기준이다.

**`run-id` 는 없다.** 객체는 기사의 것이고 발급 실행의 것이 아니다 — 같은 기사를 다시 발급해도 객체는 그대로다. 메시지의 `run_id` 는 그 기사를 **발급한** 실행이라 객체에 붙일 값이 아니고, 그래서 [§6](#6-재처리) 모드 B 는 그 값을 재구성하지 않는다.

**content-type 에 charset 이 없다.** raw 는 `application/xml` · `text/html` · `application/json` 이다. 소스가 EUC-KR 로 줄 수 있어 utf-8 을 단정하지 않기로 했다. `article.json` 은 생산자가 만들어 항상 utf-8 이고 그건 JSON 규격이 명시한다 — 즉 **`article.json` 은 utf-8 로 디코드해도 안전하고 raw 는 그렇지 않다.** 우리는 `article.json` 만 읽으므로 문제되지 않는다.

**해시 대상은 바이트다.** 생산자가 `article.model_dump_json(exclude_none=True).encode("utf-8")` 의 해시를 넣는다 (`flow.article_bytes`). 파싱한 뒤 다시 직렬화해서 해싱하면 키 순서·공백·유니코드 이스케이프가 달라져 **전량 불일치한다.** 받은 바이트를 먼저 해싱하고, 그다음에 파싱한다.

**`record_count` 대조는 없다.** 기사 이벤트는 늘 `1` 이므로 대조할 대상이 없다. 배치 계약에서 이 검증이 잡던 것("부분 업로드로 뒷줄이 잘림")은 파일이 문서 하나가 되면서 checksum 이 통째로 잡는다.

**압축 해제도 없다.** `compression` 이 `"none"`, `format` 이 `"json"` 이다. gzip 이 아니므로 "압축 해제는 성공하는데 뒷부분이 잘린" 사례가 성립하지 않는다.

**비용** — 파일 하나가 기사 하나라 수십 KB 다. 하루 약 700건이면 전체가 수십 MB 수준이고 해싱 비용은 무시할 만하다.

**작은 객체가 많다는 것은 감수한다.** 배치 파일이었다면 하루 객체 수가 소스 수만큼이었는데, 기사 단위면 하루 700개다. S3A 요청 수가 그만큼 늘지만 [00 §3](00-overview.md) 규모에서 감당된다. 커지면 `curated` 쪽에서 묶어 흡수한다 — 객체 레이아웃은 담당 1 소유라 우리가 바꿀 자리가 아니다.

### `article.json` 스키마와 필수 필드

**`exclude_none=True` 로 직렬화되므로 값이 없는 필드는 `null` 이 아니라 아예 없다.** 명시 스키마로 읽으면 없는 키가 `null` 로 채워지므로 결과는 같지만, 키 존재를 조건으로 쓰는 코드를 쓰면 안 된다.

| 필드 | 필수 | 값 |
| --- | --- | --- |
| `schema_version` | ✓ | `1` |
| `domain` · `source` · `route` · `article_id` | ✓ | 이벤트의 같은 이름 값과 일치한다 |
| `url` · `title` | ✓ | 공백만 있어도 생산자 쪽에서 거부된다 |
| `published_at` | ✓ | 소스가 준 오프셋 **그대로**. UTC 로 바뀌어 있지 않다 |
| `collected_at` | ✓ | **UTC.** 이벤트의 `collected_at` 은 KST 오프셋이라 표기가 다르다 (같은 순간) |
| `raw_key` · `content_sha256` | | 회원 전용 기사는 **둘 다 없다** |
| `body_text` | | **회원 전용 기사와 `hn` 에는 없다** (아래) |
| `summary` · `author` · `modified_at` · `extra` | | 소스마다 다르다 |
| `categories` | | 목록 소스는 어느 섹션에서 봤는지가 들어온다. 없으면 `[]` |
| `members_only` | | 이벤트의 같은 이름 값과 일치한다 |

**`ARTICLE_SCHEMA` 는 `extra` 를 안 받는다.** `src/trendin/spark/io/schema.py` 의 `ARTICLE_SCHEMA` 에 그 칸이 없어서 값이 있어도 버려진다. 일부러다 — `extra` 는 `dict[str, Any]` 라 값 타입이 섞여 있어(`hn` 은 `score` 가 int, `by` 가 str) `MapType` 으로 받으면 한쪽이 깨진다. 필요해지는 [04](04-keyword-extraction-spec.md) 에서 소스별 struct 로 좁혀 받는다. `categories` 는 `S15P21A102-171` 에서 `ArrayType(StringType())` 으로 더했고 [03 §1](03-normalization-spec.md) 의 표준 문서가 쓴다.

검증은 **필수 필드 존재**와 **시각 두 칸의 형식**까지다. 없거나 못 읽으면 DLQ (`ARTICLE_CONTRACT_VIOLATION`). 불변식 9 가 *"필수 필드가 하나라도 비면 그 기사는 저장하지 않는다"* 를 생산자 쪽에서 이미 걸지만, 이벤트가 다른 파일을 가리키는 경우는 checksum 이 잡고 못 잡는 나머지를 이게 잡는다.

### ⚠️ 본문이 없는 기사가 정상적으로 들어온다

| 경우 | 규모 | 이벤트에서 아는 법 |
| --- | --- | --- |
| 회원 전용 (`harpersbazaar` · `cosmopolitan`) | 목록 기준 **7.4%** | `members_only == true` |
| `hn` | dev 도메인 **전량** | **알 수 없다** — 아래 |

회원 전용 기사는 불변식 2 에 따라 본문을 저장하지 않는다. `hn` 은 공식 API 메타데이터만 저장하고 링크된 외부 객체를 받지 않는다 (`web-collect.md` #8 확정 3). 둘 다 제목·URL·발행일은 있다.

**⚠️ `hn` 은 아직 이벤트를 하나도 안 낸다.** 어댑터가 `S15P21A102-165` 대기 중이라 `dags/dev/dev_collect.py` 의 `source_keys` 가 빈 튜플이고, 수집 태스크가 한 번도 돌지 않는다. 즉 **지금 토픽에 흐르는 것은 fashion 뿐**이고 아래의 dev 관련 결론은 어댑터가 붙는 날 실측으로 확인해야 한다.

**결과 — dev 도메인은 제목만으로 키워드를 뽑아야 한다.** [04](04-keyword-extraction-spec.md) 가 본문 기반 통계를 전제하는데 dev 쪽 입력에는 본문이 없다. 임계값 조정으로 덮을 문제가 아니라 도메인별로 추출 경로가 갈리는 문제다. [00 §7](00-overview.md) 한계 항목으로 올렸다.

**`body_withheld` 를 이벤트에서 못 받는다.** `web-collect.md` #6 은 이 필드를 *"소비 측이 소스 목록을 참조하지 않고 기사 하나만 보고 본문 유무를 판별할 수 있어야 해서 있다"* 고 적었지만, `events.py` 는 `members_only` 만 싣고 `body_withheld` 는 싣지 않는다. **생산 측 문서와 구현이 어긋난 자리다** — 고칠 권한이 이쪽에 없으므로 담당 1 에게 알린다. 그래서 지금은 본문 유무를 이벤트만으로 판별할 수 없고, `article.json` 을 읽어 `body_text` 존재를 본다 — `contract.has_body()` 가 그 판별이다.

기사 이벤트는 어차피 객체를 읽으므로 실질적 비용은 없다. 다만 "이벤트만 보고 건너뛴다" 는 최적화는 못 한다. 담당 1 에게 `body_withheld` 발행을 요청할지는 그 최적화가 필요해질 때 정한다.

## 4. 수집 상태

`ingest` 는 수집 상태를 `pl_batch_stat` 에 기록한다 ([08 §3](08-storage-schema.md)) — 가 이 절의 설계고, **2026-09-09 현재 그 집계는 아직 없다.** 지금 남는 것은 처리 이력(`pl_processing_ledger`)의 요약 이벤트 행까지다 — `event_shape = SUMMARY`, `status` 가 `COMPLETED` | `SOURCE_FAILED`, 그리고 `source_id` · `run_id` · `record_count` · `collected_at` (`ingest/routing.py`, `ingest/batch.ledger_rows`). `(일자, 소스)` 로 접는 인덱스(`pl_processing_ledger_collected_idx`)는 미리 걸어 뒀다. 그 행을 `pl_batch_stat` 의 지표 계열로 접는 것이 후속 작업이다 ([10 §5](10-delivery-plan.md)). 아래는 그 집계의 규격이다.

### 무엇을 무엇으로 세나

| 값 | 근거 |
| --- | --- |
| 수집 건수 | **기사 이벤트 수.** `collected_at` 의 KST date 로 묶어 센다 |
| 성패 | **요약 이벤트.** `(date, source)` 별로 접는다 |

건수를 요약 이벤트의 `record_count` 합이 아니라 기사 이벤트 수로 세는 이유는, 요약의 `record_count` 는 **그 실행이 발급한 건수**(수집 이력의 `event_run_id` 로 센다)라 이월분을 포함한다 — 지난 실행에서 저장만 되고 못 나간 기사가 이번 요약에 잡힌다. 같은 이유로 `failed` 요약에도 0 이 아닌 건수가 붙을 수 있다 ([§2](#요약-이벤트--처리-규칙)). 기사 이벤트를 직접 세면 `collected_at` 기준으로 정확히 나뉜다.

### `(date, source)` 상태 판별

**수집 주기가 소스마다 시간 단위다** — fashion 7 소스는 1시간, `hn` 은 30분 (`web-collect.md` #9). 즉 하루에 한 소스가 24~48 개의 요약 이벤트를 낸다. 하루 = 실행 하나가 아니다.

| 그 일자·소스의 요약 이벤트 | 상태 |
| --- | --- |
| 전부 `success` | `COMPLETED` |
| `success` 와 `failed` 가 섞임 | `PARTIAL` |
| 전부 `failed` | `MISSING` |
| 하나도 없음 | 행 없음 |

**`PARTIAL` 의 뜻이 배치 계약 때와 다르다.** 배치 시절엔 "소스 일부만 성공" 이었고 지금은 "그 소스의 실행 일부만 성공" 이다. 시간 주기라서 24 회 중 1 회 실패도 `PARTIAL` 이 되는데, 실제 결손은 그 소스 하루치의 1/24 에 가깝다. 그래서 상태와 함께 **실패한 실행 수**도 남긴다. 상태 하나로 심각도를 판별할 수 없다.

### ⚠️ 수집 상태를 서비스에 알릴 방법이 없다

**현행 스키마에는 일자별 수집 상태를 담는 테이블이 없다.** 그래서 프론트에서 이 둘을 구분할 수 없다.

| 실제 상황 | 서비스가 보는 것 |
| --- | --- |
| 그날 아무도 그 키워드를 언급하지 않았다 | 언급량 0 |
| 그날 수집이 실패해 데이터 자체가 없다 | **언급량 0** |

[07 §2](07-metrics-and-ranking-spec.md) 에 행의 유무로 구분하는 부분 우회안이 있고 프론트 합의가 필요하다. [00 §7](00-overview.md) 한계 1번이다.

시간 주기 수집은 이 문제를 **완화한다** — 한 소스가 하루 24 번 시도하므로 하루가 통째로 비는 일은 브로커나 MinIO 가 죽지 않으면 드물다. 대신 `PARTIAL` 이 흔해져서, "값이 조금 적은 날" 이 조용히 섞인다.

### 날짜 축이 두 개다

수집 상태는 **수집 일자** 기준(`collected_at` 의 KST date)이고, 언급량은 **발행 일자** 기준이다 ([07 §3](07-metrics-and-ranking-spec.md)). MinIO 키의 `yyyy/mm/dd` 도 발행일이라 수집 일자와 무관하다.

두 축을 잇는 근사는 이렇다 — 소스 셋이 모두 최신 글을 수집하므로, 수집일 D 에 들어오는 문서의 발행일은 대부분 D 또는 D-1 이다. 예외는 **과거분 백필**이다. 두산 4곳과 `marieclaire` 는 소스당 한 번 30 페이지(vogue 기준 약 6주)를 훑으므로, 그 실행에서는 수집일 D 에 6주 전 발행분이 들어온다 (`web-collect.md` #9). 백필은 소스당 한 번이라 상시 왜곡은 아니지만, 그 날짜의 `PARTIAL` 을 읽을 때 알고 있어야 한다.

## 5. DLQ

계약 위반과 검증 실패는 조용히 버리지 않는다.

| 무엇을 | 어디로 |
| --- | --- |
| Kafka 메시지 원본 + 실패 사유 | DLQ 토픽 (담당 2 소유. **토픽명 미확정**) |
| 같은 내용 | 내부 `pl_processing_error` 테이블 ([08 §3](08-storage-schema.md)) |

**두 곳에 쓰는 이유** — DLQ 토픽은 재투입 경로이고, 테이블은 조회·집계 경로다. "지난주에 어떤 소스가 몇 번 실패했나" 를 Kafka 에서 세는 것은 불편하다.

**⚠️ DLQ 토픽이 아직 없다.** `datastore/README.md` 가 "DLQ 는 담당 2 의 후속 이슈" 로 미뤄 뒀다. 그래서 **싱크를 인터페이스로 두고 지금은 테이블만 쓴다.** 토픽이 생기면 구현 하나를 더한다. 이렇게 나눈 이유는 검증 로직과 `error_type` 분기가 싱크와 무관하고, 토픽을 기다리면 [§2](#2-이벤트-두-형태)·[§3](#3-객체-조회와-검증) 전체가 막히기 때문이다. 그 사이 재투입 경로는 없고, 복구는 [§6](#6-재처리) 으로 한다.

DLQ 메시지 스키마 (토픽 쪽은 제안. 담당 2와 확정 필요):

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

### 테이블 쪽은 구현됐다

`pl_processing_error` 는 `io/dlq.py` 의 `TableDlqSink` 가 쓴다. 컬럼이 위 JSON 을 편 것이다 — `event_id` · `job` · `error_type` · `error_detail` · `original_event` · `topic_partition` · `topic_offset` · `retry_count` · `failed_at`.

| 결정 | 왜 |
| --- | --- |
| 충돌 키가 `(event_id, job)` | 재실행이 같은 행을 덮는다. append 만 하면 재처리마다 같은 실패가 쌓여 "몇 건이 막혔나" 를 셀 수 없다 |
| `retry_count` 를 덮지 않고 **+1** | 같은 이벤트가 또 막혔다는 것이 사람이 볼 신호다. `EXCLUDED` 로 덮으면 늘 0 이라 신호가 죽는다 |
| `original_event` 는 **받은 문자열 그대로** | 파싱에 실패한 것도 남아야 사람이 볼 수 있다. 파싱된 값을 다시 직렬화하면 깨진 메시지는 아무것도 안 남는다 |
| 쓰기는 스테이징 + MERGE | [08 §4](08-storage-schema.md). Spark JDBC 는 upsert 를 못 한다 |

**거절된 이벤트는 처리 이력에도 `FAILED` 로 남는다** ([08 §3](08-storage-schema.md)). 안 남기면 재실행마다 같은 이벤트가 다시 DLQ 로 가고, 사람이 손대지 않았는데 `retry_count` 가 올라간다.

**⚠️ 파싱조차 안 된 메시지는 예외다.** `event_id` 가 없어 이력 키를 `_unparseable-{partition}-{offset}` 으로 만들기 때문에, 같은 깨진 바이트가 새 오프셋에 다시 오면 처리 이력이 못 걸러 DLQ 행이 하나 더 는다. 의도한 것이다 — 생산자가 깨진 메시지를 또 냈다는 사실 자체가 신호이고, 내용으로 묶으면 그 반복이 보이지 않는다.

### `error_type` 값

| 값 | 언제 |
| --- | --- |
| `PARSE_ERROR` | 이벤트 JSON 이 깨졌다 (`_corrupt_record`) |
| `UNKNOWN_SCHEMA_VERSION` | 아는 것보다 높은 버전 |
| `CONTRACT_VIOLATION` | 이벤트 필드 조합이 [§2](#2-이벤트-두-형태) 의 두 형태 어디에도 안 맞는다 |
| `UNKNOWN_DOMAIN` | `domain` 이 허용 목록 밖 ([01 §6](01-architecture.md)) |
| `OBJECT_NOT_FOUND` | `object_key` 가 가리키는 객체가 없다 |
| `CHECKSUM_MISMATCH` | `article.json` 바이트 해시 불일치 |
| `ARTICLE_CONTRACT_VIOLATION` | `article.json` 에 필수 필드가 없다 |

**배치 계약에서 없어진 값 둘** — `RECORD_COUNT_MISMATCH`(대조 대상이 없다), `DECOMPRESS_ERROR`(압축을 쓰지 않는다). 남겨두면 영영 발생하지 않는 분기가 코드에 남는다.

**일곱 가지가 전부 실제로 발생한다.** 2026-09-08 에 실제 Kafka·MinIO 를 상대로 확인했다 — 객체 단계 셋(`OBJECT_NOT_FOUND` · `CHECKSUM_MISMATCH` · `ARTICLE_CONTRACT_VIOLATION`)도 [§3](#3-객체-조회와-검증) 이 붙으면서 살아났다.

**DLQ 에서 자동 재시도하지 않는다.** 여기 오는 것들은 대부분 재시도해도 같은 결과다(체크섬은 다시 계산해도 틀리고, 스키마 버전은 저절로 안 내려간다). 사람이 원인을 보고 [§6](#6-재처리) 으로 다시 다시 처리한다.

## 6. 재처리

두 모드를 둔다. `spark-submit` 인자로 고른다.

### 모드 A — `--source kafka` (평시)

checkpoint 기반. Airflow 가 매 스케줄에 이 모드로 부르는 것이 설계다 — **그 DAG 은 아직 없다** ([09 §5](09-dev-and-test.md)). 지금은 `spark/scripts/submit.sh ingest` 로 손으로 부른다. 설명은 [01 §1](01-architecture.md).

### 모드 B — `--source objects` (백필·복구)

**`Trigger.AvailableNow` 는 오프셋을 진행시키므로, 이미 소비한 이벤트는 Kafka 를 다시 읽어도 오지 않는다.** 그래서 재처리 경로가 따로 필요하다.

```
spark-submit ingest.py \
  --source objects \
  --domain fashion \
  --from 2026-09-01 --to 2026-09-03 \
  --force
```

동작:

1. Kafka 를 읽지 않는다. checkpoint 를 건드리지 않는다.
2. MinIO `raw-data` 에서 `{domain}/*/*/{yyyy}/{mm}/{dd}/*/article.json` 프리픽스를 훑는다. `--from`·`--to` 는 **발행일** 범위다 — 키의 날짜가 발행일이기 때문이다.
3. 객체 키에서 이벤트를 재구성한다. `article_id` 는 키의 마지막 디렉터리, `event_id` 는 `{source}-{article_id}` 규칙으로 만든다. 나머지 필드는 `article.json` 안에 있다.
4. 이후는 모드 A 와 같은 코드 경로. 단 **봉투 계약 판별(`classify`)은 타지 않는다** — 재구성한 봉투에 `url`·`published_at` 이 없어 전부 `CONTRACT_VIOLATION` 이 되기 때문이다. 검증은 객체 쪽(존재 · checksum · 필수 필드 · 도메인 허용 목록)에 그대로 남는다 (`ingest/backfill.py`).
5. `--force` 가 있으면 처리 이력의 `COMPLETED` 를 무시하고 다시 처리한다.

**이 모드가 성립하는 이유** — 불변식 5 가 *"이벤트는 MinIO 에 raw·article.json 이 있음을 `stat` 으로 확인한 뒤에만 낸다"* 를 보장하므로, 객체가 있는 것은 곧 이벤트가 나갔던 것이다. 그리고 `article.json` 은 자기 완결적이라(불변식 9 가 필수 필드를 보장) 메시지를 재구성하는 데 다른 파일이 필요하지 않다.

**배치 계약의 `metadata.json` 스캔을 대체한다.** 그쪽은 "`metadata.json` 이 있는 디렉터리만 완성으로 본다" 는 규칙에 의존했는데, 기사 단위에서는 그 파일이 없다. 대신 프리픽스 자체가 발행일로 잘려 있어서 **범위 스캔이 오히려 더 정확하다** — 배치 시절엔 수집일 파티션을 훑고 발행일로 다시 걸러야 했다.

**`checksum` 은 객체 메타데이터에서 가져온다.** 메시지가 없으니 이벤트의 `checksum` 도 없지만, `article.json` 객체 자체가 `content-sha256` 메타데이터를 달고 있다 (`web-collect.md` #5.1, `S15P21A102-158` 확정). 그 값은 **업로드 시점에 기록된 것**이라 지금 계산한 해시와 비교하면 손상 검출이 성립한다 — 자기 자신을 해싱해 자기와 비교하는 것이 아니다.

메타데이터가 없는 객체(그 규약이 확정되기 전에 올라간 것)는 검증을 건너뛰고 [03 §7](03-normalization-spec.md) 의 집계에 센다. 없는 값을 통과로 처리하는 것과 실패로 처리하는 것 중, 옛 객체를 재처리에서 통째로 버리는 쪽이 더 나쁘다.

**요약 이벤트는 재구성할 수 없다.** 객체가 없으므로 흔적이 MinIO 에 남지 않는다. 즉 이 모드로는 [§4](#4-수집-상태) 의 수집 상태를 복구할 수 없고, 문서만 복구된다. 상태까지 복구하려면 생산자 수집 이력을 읽어야 하는데 그건 아래 이유로 하지 않는다.

**생산자 수집 이력(`collected_article`)를 읽는 대안은 쓰지 않는다.** 그쪽이 더 정확하지만(회원 전용 여부·발행 시각까지 있다) 담당 1 소유의 앱 DB 테이블을 소비 측이 직접 읽는 결합이 생긴다. 컬럼이 하나 바뀌면 이쪽이 조용히 깨진다. MinIO 는 이미 읽는 대상이라 새 결합이 없다.

### 재처리 시 지워야 할 것

`--force` 재처리는 기존 산출물을 덮어써야 한다. 삭제 범위:

| 대상 | 범위 |
| --- | --- |
| MinIO `curated` | 그 `ingest_run_id` 파티션 ([01 §3](01-architecture.md)) |
| 내부 처리 이력 | 그 `event_id` 행 |
| `contents` | **지우지 않는다.** `url` 유니크로 upsert ([08 §2](08-storage-schema.md)) |
| `contents.body_object_key` | 파티션 파일명이 바뀌면 갱신 ([01 §3](01-architecture.md)) |
| 하류 산출물 | `extract`·`aggregate` 를 이어서 다시 돌린다 |

`contents` 를 지우지 않는 이유는 `keyword_contents` 가 딸려 있어서, 콘텐츠 한 행을 지우면 사용자에게 보이던 연결이 사라지기 때문이다.

**checkpoint 를 지워서 재처리하는 방법은 쓰지 않는다.** 그러면 토픽의 모든 이벤트를 처음부터 다시 읽게 되고, 범위를 지정할 수 없다. 모드 B 가 있는 이유다.

**보존 기간이 재처리 범위를 자른다.** MinIO 객체는 90일 뒤 삭제되고 수집 이력만 남는다 (`web-collect.md` #9, 열린 질문 1). 90일보다 오래된 구간은 모드 B 로도 복구할 수 없다 — 객체가 없다. 정제 로직을 크게 고쳐 전 구간을 다시 돌리고 싶어지면 그때는 이미 늦다.
