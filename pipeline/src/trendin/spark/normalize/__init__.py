"""객체 → 표준 문서. 규격은 [03](../../../../spark/docs/03-normalization-spec.md).

| 모듈 | 무엇 |
| --- | --- |
| `urls` | URL 정규화와 `url_hash`. **출력이 곧 `contents.url` 의 유일성 기준이다** |
| `text` | 텍스트 정제 일곱 단계. 코드 분리가 태그 제거보다 먼저다 |
| `lang` | 문자 비율로 `ko`·`en`·`mixed`·`unknown` 판별 |
| `simhash` | 근사 중복의 지문 |
| `adapters` | 소스별 어댑터. `route` 로 고른다 — `media` · `hackernews` |
| `documents` | `article.json` 하나 → 표준 문서 하나 |
| `filters` | 품질 필터. **본문 유무로 분기한다** |
| `dedup` | 중복 제거 3단계. 지우지 않고 표시한다 |
| `schema` | 표준 문서의 Spark 스키마와 `curated` 파티션 |
| `curated` | MinIO `curated` Parquet 쓰기 |

**`curated` 와 `schema` 를 뺀 전부가 pyspark 를 import 하지 않는다** — 순수 함수라
SparkSession 없이 검사할 수 있다 ([09 §4] 층 1). Spark 배선은 `ingest/normalize.py` 가
UDF 로 감싼다.
"""
