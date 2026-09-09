"""읽고 쓰는 경계 — kafka · minio · jdbc ([02], [08]).

| 모듈 | 무엇 |
| --- | --- |
| `contract` | 이벤트 계약 판별. pyspark 를 import 하지 않는다 |
| `schema` | 메시지 봉투와 `article.json` 의 Spark 스키마 |
| `kafka` | `raw-file-ready` 소비와 파싱 |
| `objects` | MinIO 객체 조회 |
| `jdbc` | 앱 DB — Spark JDBC 와 드라이버 psycopg2 두 경로 |
| `ledger` | `pl_processing_ledger` — 멱등성 중복 차단 2 |
| `dlq` | `pl_processing_error` — 거절된 이벤트 |
| `contents` | 서비스 `contents` upsert 와 `pl_content_id_map` 으로의 `id` 회수 |
| `stats` | `pl_batch_stat` — 버린 것과 고친 것을 센다 ([03 §7]) |

`contents` 가 이 묶음에서 **서비스 테이블에 쓰는 유일한 자리**다. 나머지는 전부 `pl_` 내부
테이블이고, 그 경계가 [08 §1] 이다.
"""
