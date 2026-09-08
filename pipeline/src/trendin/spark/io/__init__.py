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
"""
