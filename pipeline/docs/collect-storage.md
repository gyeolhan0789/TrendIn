# 수집 저장 구조 — MinIO 에 무엇이 어떻게 놓이나

기사 하나가 객체 둘(`raw` · `article.json`)로 놓이고, 저장을 `stat` 으로 확인한 뒤 장부에 적히고, 장부에 적힌 행에서 Kafka 이벤트가 나간다.

이 문서는 **경로와 정본**이다 — 어느 단계가 무엇을 쓰는지, 그 규칙을 고칠 때 어느 파일을 여는지. 왜 그렇게 정했는지는 [`web-collect.md`](web-collect.md), 소비 측이 어떻게 읽는지는 [`spark-integration.md`](spark-integration.md) 다.

## 1. 어디를 보나

| 하려는 일 | 볼 곳 |
|---|---|
| 구조를 파악한다 | #2 · #3 |
| 규칙을 고친다 | #4 — 정본과 같이 열 파일 |
| 왜 그렇게 정했는지 본다 | `web-collect.md` #5 저장 구조 · #7 불변식 · #8 확정 사항 |
| 새 소스를 붙인다 | `source-discovery.md` 프로필과 두 게이트, 그다음 #4 |
| MinIO 에서 읽는다 (소비 측) | `spark-integration.md` #5 |
| 켜고·끄고·백필하고·결과를 센다 | `pipeline/README.md` 수집 운영 |
| 버킷·계정 권한·수명주기를 만진다 | `datastore/README.md` |

## 2. 경로

도메인마다 DAG 하나, 태스크는 셋이다 — `ensure_schema` → `collect_one`(소스별 동적 매핑, `crawler_pool`) → `publish`.

| 단계 | 하는 일 | 파일 |
|---|---|---|
| 발견 | 소스에서 새 글 후보 목록을 얻는다 | `fashion/collect/rss.py` · `listing.py` |
| 거름 | 장부에 이미 있는 `(source, article_id)` 를 뺀다 | `ledger.filter_new` |
| 취득·정규화 | 원문 바이트와 `Article` 을 만든다 | 같은 어댑터 · `html_text.py` |
| 저장 | raw 와 article.json 을 put 한다 | `flow.store_article` → `minio_store.py` |
| 확인 | 그 키들이 `stat` 에 잡히는지 본다 | 같은 함수 |
| 장부 | 행을 적는다. `collect_one` 은 여기서 끝난다 | `ledger.record` |
| 발급 | 아직 안 나간 행을 전부 Kafka 에 낸다 | `flow.publish_pending` → `events.py` |

**저장과 발급이 다른 태스크인 이유는 재시도 복구다.** 저장까지 하고 발급 전에 죽은 행은 `event_emitted_at` 이 비어 있어 다음 실행의 발급이 이어 낸다. 그래서 발급은 "이번에 저장한 것"이 아니라 "아직 안 나간 것 전부"를 본다.

기사 이벤트는 `raw-file-ready`, 실행 요약은 `collect-run-summary`로 나간다. 요약 토픽 환경변수가 비면 기사만 발급한다. 수집 숫자와 장부의 발급 통계는 별개이며, 계약은 `spark-integration.md` §3·§12를 따른다.

과거분 백필도 저장까지는 같은 루프를 탄다(`flow.store_candidates`). 발급은 하지 않고 다음 주기 실행에 맡긴다.

## 3. MinIO 에 놓이는 것

버킷 하나(`raw-data`)에 기사 하나당 객체 둘. 도메인·소스·경로·날짜는 전부 키 접두어다.

```
{domain}/{source}/{route}/{yyyy}/{mm}/{dd}/{article_id}/raw.{ext}
{domain}/{source}/{route}/{yyyy}/{mm}/{dd}/{article_id}/article.json
```

`yyyy/mm/dd` 는 **발행일 KST** 다. 그래서 같은 기사를 언제 다시 받아도 같은 키로 가고, 재실행해도 객체가 늘지 않는다.

| 객체 | 내용 | content-type |
|---|---|---|
| `raw.xml` · `raw.html` · `raw.json` | 받은 바이트 그대로. 인코딩 변환·정리·압축이 없다 | `application/xml` · `text/html` · `application/json`. **charset 을 붙이지 않는다** — 소스가 EUC-KR 로 줄 수 있다 |
| `article.json` | 정규화 결과. compact JSON, UTF-8. 값이 없는 필드는 `null` 이 아니라 키 자체가 없다 | `application/json` |

route 와 확장자는 1:1 이다 — `rss`→`xml`, `listing`→`html`, `api`→`json`.

객체에는 메타데이터 둘이 붙는다. `collected-at`(ISO-8601 KST)과 `content-sha256`(**그 객체 자신의** 해시 — raw 에는 raw 의, article.json 에는 article.json 의). `x-amz-meta-*` 헤더가 latin-1 이라 ASCII 만 들어가고, 아니면 저장 전에 예외가 난다.

**회원 전용 기사는 raw 객체가 없다.** 기사 페이지 HTML 에 본문이 실려 와서, raw 를 저장하면 본문을 저장하는 것이 된다. `article.json` 하나만 놓이고 그 안에 `raw_key` · `content_sha256` · `body_text` 가 없다.

## 4. 규칙의 정본

| 규칙 | 정본 | 같이 여는 것 |
|---|---|---|
| 키 모양 · 발행일 파티션 | `common/collect/keys.py` | 어댑터의 `raw_key` 계산. `store_article` 이 규칙으로 다시 만들어 대조하므로 어긋나면 예외로 드러난다 |
| route ↔ 확장자 | `keys.ROUTE_EXT` | `sinks.CONTENT_TYPES` · `fashion/collect/runner.py` 의 `ADAPTERS` |
| article.json 필드와 필수 여부 | `common/collect/article.py` | `spark-integration.md` #5, 소비 측 `EVENT_SCHEMA`(S15P21A102-206) |
| 저장 순서와 `stat` 확인 | `flow.store_article` | 여기 하나뿐이다. 주기 실행과 백필이 같은 함수를 탄다 |
| 객체 메타데이터 | `flow.object_metadata` | `minio_store._ascii_only` 가 ASCII 를 강제한다 |
| 장부 컬럼 | `ledger.DDL` | `ledger.PendingArticle` · `events.article_event` — 발급이 장부만 읽고 봉투를 채운다 |
| 기사·요약 토픽별 이벤트 봉투 | `common/collect/events.py` | 견본 `spark/tests/fixtures/contract/` · `scripts/gen-contract-fixtures.py` |
| 버킷 · 계정 권한 · 수명주기 | `datastore/minio-init/init.sh` | `datastore/README.md`, `pipeline/.env` 의 `TRENDIN_MINIO_*` |
| 접속 주소와 자격증명 | 환경변수 `TRENDIN_MINIO_ENDPOINT` · `_BUCKET` · `_ACCESS_KEY` · `_SECRET_KEY` | 코드에 주소를 적지 않는다 |

## 5. 코드에 없는 것

세 자리는 "빠뜨린 것"이 아니라 다른 것이 그 일을 한다. 팀 문서(`data-pipeline-design.md` #4·#5)를 먼저 읽고 오면 여기서 어긋난다 — 차이 표는 `web-collect.md` #14 다.

| 없는 것 | 대신 하는 것 |
|---|---|
| `metadata.json` (배치 완료 마커) | `article.json` 이 완료 표시다. `store_article` 이 그것을 마지막에 쓰고 `stat` 으로 확인한 뒤 장부에 적는다. 토픽이 비었을 때의 재구성은 장부가 맡는다 (S15P21A102-204 에서 면제 확정) |
| 객체 삭제 | 90일 만료는 버킷 수명주기 규칙(ILM)이 건다. 크롤러 키에 `s3:DeleteObject` 권한 자체가 없다 |
| 수집일 파티션 `collected_date=` | 발행일 KST 로 자른다. 언급량 집계가 발행일 기준이고, 수집일이면 재수집마다 키가 늘어난다 |

## 6. 아직 없는 것

| 무엇 | 지금 상태 |
|---|---|
| dev 도메인 어댑터 (S15P21A102-165) | 소스 목록이 비어 `dev_collect` 은 켜도 수집 태스크가 돌지 않는다 |
| `linked` route — HN 이 링크한 외부 원문 (`source-discovery.md` #5.1) | `keys.ROUTE_EXT` 에 아직 없다. 넣으면 확장자도 함께 정한다 |
| 수집 중단 탐지 (S15P21A102-199) | 사람이 `README` 의 질의로 본다 |
