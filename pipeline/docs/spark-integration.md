# Spark 연동 계약 — 크롤러가 내보내는 것

크롤러(담당 1)가 앱 DB 와 MinIO 에 무엇을 어떤 모양으로 놓는지. **이 문서만 보고 reader 를
만들 수 있어야 한다.** 크롤러 코드를 열어야 알 수 있는 것이 남아 있으면 이 문서의 결함이므로
알려 주면 채운다.

**2026-09-20: 브로커가 걷혔다** (Kafka 제거 2/3 · 3/3). 봉투가 흐르던 자리를 앱 DB 의
`collected_article_event` 뷰가 대신한다 — 칸 이름과 값 규칙은 그대로고, 만드는 자리가 파이썬에서
SQL 로 옮겨졌을 뿐이다. 실행 요약 토픽은 대응하는 것 없이 없어졌다. 브로커 시절의
접속 정보는 §2 끝에 기록으로 남긴다.

- 결정과 근거: Jira `S15P21A102-159`. 생산 측 설계는 [`web-collect.md`](web-collect.md), 팀 전체 구조는 [`data-pipeline-design.md`](data-pipeline-design.md)
- 소비 측 계약(무엇을 DLQ 로 보내는지 등)은 [`spark/docs/02-input-contract.md`](../spark/docs/02-input-contract.md). **그 문서는 이 문서보다 낡았다** — §11 참고
- 샘플: [`spark/tests/fixtures/contract/`](../spark/tests/fixtures/contract/) (§8)

## 1. 이 문서가 보장하는 것

| 보장한다 | 보장하지 않는다 |
|---|---|
| 창구(`collected_article_event`)가 내는 봉투의 필드 이름·타입·값 규칙 | 소비 측의 처리 방식(DLQ 기준, 처리 이력, 재처리) |
| MinIO 객체의 키 규칙과 내용 | `curated` 버킷 (Spark 소유, 쓰기 권한이 아직 없다 — §6) |
| 창구에 보이는 행은 그 객체가 이미 있다 | 창구가 같은 행을 두 번 주지 않는다는 것. 창을 겹쳐 읽으면 겹친다 — 중복은 소비 측이 `event_id` 로 거른다 |
| 저장을 `stat` 으로 확인한 뒤에만 장부에 적는다 | 객체가 있으면 장부에 있다 (역은 성립하지 않는다 — §5) |

## 2. 창구 — `collected_article_event` 뷰

| 항목 | 값 | 어디서 오나 |
|---|---|---|
| 뷰 이름 | `collected_article_event` | `common/collect/ledger.py` 의 `DDL` |
| 어느 DB | 앱 DB (`forever102` 또는 컴포즈 안 `trendin`) | Airflow `AIRFLOW_CONN_APP_DB` · Spark `SPARK_APP_DB_URL` — **같은 DB 를 가리켜야 한다** |
| 창 자르는 칸 | `collected_at_ts` (`timestamptz`) | 전용 인덱스 `collected_article_collected_at_idx` |
| 읽는 폭 | `ingest.ledger.lookback_hours`, 기본 168시간 | `spark/conf/base.yaml` |
| 만드는 쪽 | 수집 DAG 의 첫 태스크 `ensure_schema` 가 매 회차 멱등하게 적용한다 | `PostgresLedger.ensure_schema` |

**창구는 읽기 전용이고 상태가 없다.** 무엇이 읽혔는지 기억하지 않으므로, 어디까지 처리했는지는
소비 측 처리 이력이 들고 있다. 창을 겹쳐 읽어도 되는 이유가 그것이다.

**대기 행은 창구에 없다.** 기사 페이지를 끝내 못 받아 다시 시도 중인 행(`fetch_state = 'retrying'`)은
MinIO 에 아직 아무것도 없어 뷰가 걸러 낸다 (`S15P21A102-312`). 그래서 창구의 행 수는 장부 행 수보다
적을 수 있고, 그것이 정상이다.

### 언제 새 행이 생기나

수집 DAG 이 한 회차를 마치면 마지막 태스크 `signal_collected` 가 Airflow 자산
`trendin://collected` 를 낸다. `spark_ingest` 가 그 자산으로 깨어난다 (`S15P21A102-247`).
크론 간격으로 잇지 않는 이유는 수집이 늦으면 소비가 빈손으로 돌기 때문이다.

자산은 **수집 태스크가 아니라 그 뒤의 신호 태스크**에 달려 있고 `ALL_DONE` 이다. 소스 하나가 죽어도
나머지가 받아 둔 기사는 처리되어야 한다.

### ~~Kafka~~ (2026-09-20 걷어냄)

브로커가 있던 시절의 접속 정보다. 기록으로 남긴다.

| 항목 | 값 |
|---|---|
| 기사 topic | `raw-file-ready` |
| 요약 topic | `collect-run-summary` (요청만 하고 끝내 만들어지지 않았다) |
| bootstrap (같은 EC2) | `kafka:9092` |
| bootstrap (호스트·다른 EC2) | `${KAFKA_EXTERNAL_HOST}:29092` |
| message key | `source_id` (UTF-8 바이트) |

message key 가 `source_id` 였으므로 같은 토픽 안에서 같은 소스의 이벤트는 한 파티션에 모였다.
그 순서 보장은 창구에서는 뜻이 없다 — SQL 이 `ORDER BY` 로 정한다.

`acks=all` · `enable.idempotence=true` 로 내고 `flush()` 가 성공한 뒤에만 장부에 발급 시각을
적었다. 그래서 발급 후 장부 기록 전에 죽으면 같은 이벤트가 다시 나갔다 (at-least-once).

접속 정보의 정본은 [`datastore/README.md`](../../datastore/README.md) "접속 정보" 절이다. 값이 이 문서와 다르면 그쪽이 맞다.

## 3. 봉투 — 창구가 내는 칸

창구에는 기사 한 건이 한 행이다. 종류가 하나뿐이라 분기할 것이 없다.

**칸 이름과 값은 브로커 시절 기사 봉투 그대로다.** 정본은 `common/collect/events.py` 의
`article_event()` 이고 — 그 함수는 이제 아무것도 발행하지 않는다 — 뷰가 같은 값을 SQL 로 낸다.
둘이 한 글자라도 다르면 `pipeline/tests/common/test_ledger_view.py` 가 진짜 PostgreSQL 에 걸어
잡는다.

**창구에 없는 칸이 둘 있다.** `run_id` 는 발급 실행이었으므로 발급과 함께 없어졌고, 소비 측이
`None` 으로 채운다 (`spark/ingest/collected.py`). `bucket` 은 장부에 없는 값이라 소비 측 설정에서
온다. 아래 표의 나머지는 뷰가 그대로 낸다.

### 기사 봉투

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
| `paywalled` | bool | 유료 표시(`isAccessibleForFree=false`) 기사면 `true`. 2026-09-17 추가. 판별은 285 라 그 전까지 늘 `false` (`web-collect.md` #5.3) |
| `source_country` | string | 소스를 발행하는 법인이 있는 나라. ISO 3166-1 alpha-2 대문자, 판정 불가는 `XX`. `null` 없음 |

`run_id` 는 **발급 실행**이다. 저장만 되고 못 나간 행은 다음 회차가 내므로 수집
실행과 달라도 정상이다. 수집 시각은 `collected_at` 에 있다. **파티션 키로 쓰지 않는다.**
재발급하면 값이 달라져 같은 기사가 다른 파티션에 갈릴 수 있다. 값도 파싱하지 않는다.
`event_id` 는 결정적인 **중복 판정 함수**다. 파싱해서 `source_id` 를 추출하지 않는다.

### ~~collect-run-summary — 소스별 실행 요약~~ (2026-09-20 걷어냄)

**이 절은 기록이다.** 요약 토픽은 끝내 만들어지지 않았고, 브로커와 함께 계획째로 없어졌다.
수집 숫자는 이제 수집 태스크의 XCom 에만 남고, 그것을 지표로 내는 일은 `S15P21A102-199` 의 몫이다.

토픽을 활성화하면 소스 하나의 한 회차마다 논리적으로 하나를 낸다. 0건·수집 실패에도
낸다. 전달은 at-least-once라 재시도 중복은 `event_id` 로 제거한다. 공통 식별 5칸과
수집 결과·발급 통계를 담는 고정 **20개 필드**다. 안 쓰는 기사 봉투 필드는 없다.

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
| `paywalled_stored` | int \| null | 유료 표시로 raw 없이 저장된 수. 2026-09-17 추가 | `collect_source` 집계 |
| `emitted` | int | 이번 회차가 발급한 기사 이벤트 수 | 장부 (`emitted_by_run`) |
| `emitted_oldest_collected_at` | string \| null | 그중 가장 오래된 `collected_at`, KST. 0건이면 `null` | 장부의 `min(collected_at)` |
| `failure_reason` | string \| null | `status=failed` 일 때만 | `SourceStatus.failure_reason` |

수집 결과 **10개 필드**(`discovered`, `stored`, `skipped`, `not_modified`, `failed`,
`failed_by_stage`, `failures`, `duration_ms`, `members_only_stored`, `paywalled_stored`)는 XCom에서 온다.
수집 태스크가 죽어 결과가 없으면 전부 `null`이다. `0`은 관측된 0건이므로 대신 쓰지 않는다.
`failed_by_stage` 는 세 단계 모두 포함하고, `failures` 는 발견→취득·저장 순서의 앞 10건,
사유는 앞 200자다. `failed` 와 단계별 건수는 표본이 아닌 전체 실패를 센다.
`duration_ms` 는 발견부터 저장 확인·장부 기록까지의 단조 시계 경과 시간이다.
`members_only_stored` 는 회원 전용 기사 중 저장 확인에 성공한 수다. `paywalled_stored` 는 유료 표시 기사에서 같은 수를 센다.

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
article.json 에만 있다. 원래 이유는 이벤트 크기를 1KB 안팎으로 유지하는 것이었다. 브로커가 걷힌
지금은 이유가 하나 더 붙는다 — 장부는 지우지 않으므로(불변식 13), 본문을 장부에 실으면 90일에
만료되는 원문의 사본이 영구히 남는다.

## 5. MinIO

| 항목 | 값 |
|---|---|
| endpoint (같은 EC2) | `http://minio:9000` |
| endpoint (호스트·다른 EC2) | `http://<호스트>:9000`, 콘솔 `:9001` |
| bucket | `raw-data` |
| 버전 관리 | **off** — 같은 키를 덮어쓴다 |
| 수명 주기 | 버킷 전체 90일 만료. **기준은 업로드 시각**이고 경로의 날짜가 아니다 |

**창구에는 보존 기간이 없다.** 장부를 지우지 않으므로(불변식 13) 90일이 지나 원문이 만료된 뒤에도
그 행은 창구에 남는다. 그래도 되는 이유는 소비 측이 창을 잘라 읽기 때문이다 — `lookback_hours` 는
168시간이고, 만료된 구간은 이미 처리를 마쳐 처리 이력이 거른다. 90일보다 긴 백필은 원문이 있어야
하므로 만료 전에 돌린다.

~~`MinIO 90일 >= Kafka 7일` 이라 이벤트가 가리키는 원문이 먼저 사라지지 않는다~~ (2026-09-20 —
이벤트가 없어지면서 이 부등식도 없어졌다).

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
| `raw_key` | string | raw 의 키. 회원 전용이거나 유료 표시면 없다 |
| `content_sha256` | string | **raw 의** sha256. 회원 전용이거나 유료 표시면 없다 |
| `modified_at` `summary` `body_text` `author` `members_only` `paywalled` `extra` | | 없을 수 있다 |
| `categories` | array | 소스가 붙인 분류. 목록 소스는 발견한 섹션 슬러그 |

**⚠️ 값이 없는 필드는 `null` 이 아니라 키 자체가 없다.** `model_dump_json(exclude_none=True)`
이라서다. `doc["summary"]` 는 `KeyError` 를 낸다 — `doc.get("summary")` 를 쓰거나 스키마에
nullable 로 선언해 읽어라.

**`body_text` · `summary` 는 HTML 조각이다** (2026-09-17 합의, 수집 코드 변경은 285). 수집은 소스별 잡음(회원 마스크·관련기사·`figcaption`·`script` 등)만 걷어내고, 태그 제거·엔티티 디코드·공백 정리는 소비 측이 한다. 텍스트 안의 `<` `&` 는 이스케이프돼 오므로 태그를 먼저 지우고 엔티티를 나중에 풀어야 `<문라이트>` 같은 표기가 산다. 그 전에 저장된 객체는 평문이고 다시 만들지 않는다. 경계 표는 `web-collect.md` #5.3.

**기사 페이지를 못 받은 기사** (`fetch_failed: true`) 는 `body_text` 와 raw 가 없고 제목·URL·발행일·분류만 있다. 수집이 3회 또는 24시간까지 다시 시도한 뒤 포기한 것이다 (`web-collect.md` #5.4, S15P21A102-312). 봉투에는 이 칸이 없다 — 본문 없는 이유를 세는 `members_only` `paywalled` 와 달리 창구 뷰의 칸을 늘리지 않았다.

**회원 전용 기사** (`members_only: true`) 는 `body_text` 가 없고 raw 객체 자체를 저장하지 않는다.
기사 페이지 HTML 에 본문이 실려 오기 때문에 raw 를 저장하면 본문을 저장하는 것이 된다
(`web-collect.md` §12 항목 2). 제목·URL·발행일·요약은 남는다. 전체의 7.4% 다.
**유료 표시 기사** (`paywalled: true`) 도 같다 — 칸은 2026-09-17 추가, 판별은 285.

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

**창구는 앱 DB 계정으로 붙는다.** MinIO 키와 다른 자격이고, 값의 출처는 Spark 쪽 `SPARK_APP_DB_*` 다.
그 계정이 가리키는 DB 가 Airflow 의 `AIRFLOW_CONN_APP_DB` 와 달라지면 창구가 늘 비어 보인다 —
붙지 못하는 것이 아니라 **다른 DB 의 빈 뷰를 읽는다.**

**`curated` 버킷은 아직 없다.** Spark 가 정제 결과를 쓸 곳인데 버킷도 쓰기 권한도 만들어지지
않았다. `datastore/minio-init/init.sh` 가 늘어야 한다 — [`09 §7` 항목 4b](../spark/docs/09-dev-and-test.md).

## 7. 중복과 멱등

| 무엇 | 어떻게 |
|---|---|
| 같은 기사를 다시 저장 | 같은 키를 덮어쓴다. `(source, article_id)` 하나가 키 하나로 간다 |
| 같은 행을 다시 읽음 | 있을 수 있다. 창을 겹쳐 읽으면 겹친다 — `event_id` 로 거른다 |
| 같은 실행을 재시도 | 창구는 상태가 없어 같은 창이면 같은 행이 나온다 |
| 창구를 못 읽음 | `article.json` 이 있는 디렉터리를 훑어 재구성할 수 있다 (§5, `--source objects`). 창구도 원본이 아니다 — 원본은 MinIO 객체와 장부다 |

## 8. 샘플

[`spark/tests/fixtures/contract/`](../spark/tests/fixtures/contract/) 에 이벤트 3건(기사 1, 이전 봉투 요약 2)과
기사 이벤트가 가리키는 객체 2개가 있다. 저장소를 띄우지 않고 파싱·검증 코드를 테스트할 수 있다.

요약 토픽 견본 둘(`collect-run-summary-*.json`)은 2026-09-20 에 지웠다. 생산자가 없어져 대조할
기준이 사라졌기 때문이다. `run-summary-*.json` 은 남는다 — 토픽 분리 전 봉투의 기록이고, 소비 측
판별기 테스트가 그 모양을 계속 받아야 한다.

| 파일 | 무엇 |
|---|---|
| `article-event.json` | 기사 이벤트. `object_key` 가 있다. 창구가 내는 칸과 같은 값이고, `bucket` · `run_id` 만 창구에 없다 |
| `run-summary-success.json` · `run-summary-failed.json` | 토픽 분리 전 `raw-file-ready` 에 나갔던 요약 봉투의 기록. 생성 스크립트가 만들지 않는다. 소비 측 판별기(`EventShape.SUMMARY`)가 이 모양을 계속 받으므로 남긴다 — 걷어낼지는 소비 측이 정한다 |
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

`events.py` 가 발행을 그만둔 뒤에도 남아 있는 이유가 이것과 `test_ledger_view.py` 둘이다 —
견본과 뷰가 **같은 기준**을 흉내 내야 서로 어긋나지 않는다.

## 9. 계약이 실제로 지켜지는지 확인하기

브로커가 있던 시절에는 `scripts/verify-spark-integration.py` 가 fixture 를 토픽에 넣고 되읽어
확인했다. 발행할 것이 없어지면서 그 스크립트를 지웠다 (2026-09-20). 확인은 세 곳으로 나뉘어 있다.

| 무엇을 보나 | 어디서 | 언제 |
|---|---|---|
| 뷰가 봉투 정본과 같은 값을 내는가 — 칸 이름·시각 표기·`source_country` 까지 | `tests/common/test_ledger_view.py` (진짜 PostgreSQL 필요) | CI 매 MR. `pipeline:verify` 잡이 postgres 서비스를 띄운다 |
| 견본 봉투가 `events.py` · `keys.py` 와 어긋나지 않는가, `checksum` 이 실제 객체의 해시인가 | `tests/common/test_contract_fixtures.py` | CI 매 MR. 외부 서비스가 필요 없다 |
| MinIO 권한 분리 — 크롤러 키 put/get, **Spark 키 `raw-data` 쓰기 거부**, `curated` put/get/delete | `datastore/scripts/verify.sh` | 배포 뒤 손으로 |

**뷰 테스트가 건너뛰어지면 안 된다.** `TRENDIN_TEST_DB_URL` 이 없으면 파일 통째로 skip 이고,
skip 은 통과와 구분되지 않는다. 그래서 `pipeline:verify` 잡이 pytest 앞에서 그 DB 에 실제로
접속해 보고, 안 되면 거기서 멈춘다.

실제 수집 한 회차가 소비 측까지 닿았는지는 Spark 의 처리 이력에서 본다. 창구는 무엇이 읽혔는지
기억하지 않으므로 수집 쪽에서 볼 수 있는 것은 "창구에 몇 행이 있나" 까지다
(`pipeline/README.md` "결과 확인").

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
| ~~1~~ | ~~**요약 별도 토픽 이행**~~ | **2026-09-20 에 없어졌다** — 브로커를 걷으면서 요약 이벤트째로 걷혔다. 수집 숫자를 소비 측에 내는 일을 다시 연다면 `S15P21A102-199` 에서 이벤트가 아니라 지표로 만든다 |
| 2 | **`domain` 값이 `dev` 인가 `development` 인가** | 크롤러는 `dev` 를 내고, 팀 계약과 [`01 §6`](../spark/docs/01-architecture.md) 은 `development` 를 기대한다. `development` 로 통일하기로 했고 크롤러 쪽 수정이 남았다. `fashion` 은 양쪽이 같다 |
| 3 | 날짜 파티션이 발행일 | `web-collect.md` §12 항목 6 의 잠정답이 발행일이고 `keys.py` 가 그대로 구현했다. 확정 도장이 남았다 |
| ~~4~~ | ~~consumer group 이름~~ | **2026-09-20 에 없어졌다** — 소비할 토픽이 없다 |
| ~~5~~ | ~~DLQ 토픽 이름~~ | **2026-09-20 에 없어졌다** — DLQ 는 테이블 `pl_processing_error` 하나로 간다 (`spark/io/dlq.py`) |

### `02-input-contract.md` 가 이 문서보다 낡았다

[`spark/docs/02-input-contract.md`](../spark/docs/02-input-contract.md) 는 배치 이벤트를 전제로
쓰였다. 그대로 구현하면 어긋나는 자리:

| `02` 의 내용 | 실제 |
|---|---|
| §2 표: `success` + `record_count>0` + `object_key=null` → 계약 위반 DLQ | 창구에는 기사 한 종류만 있으므로 그대로 맞는 규칙이다 |
| §3 `record_count` 를 파싱된 줄 수와 대조 | 객체가 jsonl 이 아니라 단일 JSON 객체다 |
| §6 manifest 모드가 `metadata.json` 을 훑는다 | `metadata.json` 이 없다. `article.json` 이 완료 마커다 (§5) |
| `format: jsonl` · `compression: gzip` | `json` · `none` |

`02` 는 소비 측 소유 문서라 이 문서가 고치지 않는다. 위 목록을 근거로 갱신해 주면 된다.

## 12. ~~토픽 생성과 소비 측 인계~~ (2026-09-20 걷어냄)

요약 토픽 `collect-run-summary` 는 끝내 만들어지지 않았고, 브로커와 함께 계획째로 없어졌다.
이 절에 있던 생성 요청(파티션 1 · 보존 30일 · `delete` · 세그먼트 1일)과 인계 목록은
`web-collect.md` §6 · §12 의 기록으로 대신한다.

기사 토픽에 나갔던 요약 196개도 브로커와 함께 사라졌다. 그 봉투를 판별하는 소비 측 코드
(`spark/io/contract.py` 의 `EventShape.SUMMARY`)와 견본 `run-summary-*.json` 은 남아 있다 —
걷어낼지는 소비 측이 정한다.
