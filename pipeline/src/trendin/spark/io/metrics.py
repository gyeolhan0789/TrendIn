"""`aggregate` 의 읽기와 적재 — 서비스 테이블 둘 + 판별 이력 하나 ([07 §7], [08 §4]).

| 테이블 | 소유 | 쓰는 법 |
| --- | --- | --- |
| `keyword_metric_history` | 서비스 | 재계산 구간 W 의 버킷을 덮어쓴다 |
| `keyword_metrics` | 서비스 | 키워드 × 기간 1행. 배지도 이 줄이고, 옛 구간 행은 지운다 |
| `pl_trend_type_log` | 파이프라인 | 회차별 판별 이력 ([07 §6]) |

**`trends` 에는 대표 ID만 새로 만든다.** 배지 판정은 계속 `keyword_metrics.trend_types`
에 기간별로 싣는다. NEW/RISING/CURRENT 판정이 하나라도 있으면 AI 분석 성공 전에도
상세 진입용 `trends` 행을 생성하고, 이미 있는 행은 변경하지 않는다.

**지표 MERGE에는 `ON CONFLICT` 를 쓰지 않는다.** 규격은 그 형태를 적었지만([07 §7])
그건 유니크 제약이
있다는 전제이고, **제약은 스키마마다 다르다** — Flyway baseline 의 `keyword_metrics` UNIQUE 는
`(keyword_id, period, period_start, period_end)` 4열이다 (우리가 요청한 2열이 아니다). 백엔드
조회가 `period_start` · `period_end` 를 지정해 찾으므로 그쪽이 그 모양을 쓰는 것이고, 우리가
맞출 일이다. `ON CONFLICT` 는 인덱스와 정확히 맞아야 하므로, 제약이 무엇이든 같게 도는
형태로 짠다.

```
1. UPDATE target FROM stage    (자연 키로 맞춘 행)
2. INSERT ... WHERE NOT EXISTS (없던 행만)
3. DELETE                      (이번 회차에서 빠진 행 — 표마다 범위가 다르다)
```

**1·2 가 제약 없이도 멱등이다.** 제약이 있으면 그것이 한 겹 더 막아 주고, 없으면 이 순서가
같은 결과를 낸다. 이미 중복이 쌓여 있어도 UPDATE 가 전부를 같은 값으로 맞춘다. 그 대신
`warn_missing_constraints()` 가 없는 제약을 크게 남긴다 — 조용히 도는 것이 가장 나쁘다.

**배열·enum 컬럼의 타입을 실행 시점에 본다** ([08 §4]). 스테이징에는 `text`·`text[]` 로 넣고
MERGE 에서 **실제 컬럼 타입으로** 캐스트한다. 그 타입이 스키마마다 다르기 때문이다 —
`keyword_metrics.period` 는 양쪽 다 네이티브 enum(`metric_period`)이지만, 배열 칸은
과거 `trends.trend_types` 가 Flyway baseline 에서 `varchar(255)[]` 이고 옛 수동 스키마에서는
`trend_type[]` 이었다. 지금 배지는 `keyword_metrics.trend_types` 가 소유한다.
이 배열이 어느 쪽으로 선언되든 같게
돌아야 해서 타입을 묻고 붙인다. **배열은 varchar 계열이어도 캐스트를 뺄 수 없다** — 자세한
이유는 `_cast()` 에 적었다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Iterable, Sequence

from trendin.spark.common.config import Config
from trendin.spark.common.logging import get_logger
from trendin.spark.io import jdbc
from trendin.spark.metrics.relations import (
    RELATION_COLUMNS,
    RELATION_SQL,
    RELATIONS,
    RelationThresholds,
)

log = get_logger(__name__)

# --- 읽는 표 (원자료) ------------------------------------------------------
DAILY_STAT = "pl_keyword_daily_stat"
DOCUMENT_CANDIDATE = "pl_document_candidate"
CANDIDATE = "pl_candidate"
# 시간 버킷이 발행 시각을 되찾는 경로 ([07 §3]). `io/contents.py` 가 소유한다.
CONTENT_ID_MAP = "pl_content_id_map"
CONTENTS = "contents"

# --- 쓰는 표 ---------------------------------------------------------------
METRICS = "keyword_metrics"
HISTORY = "keyword_metric_history"
TREND_TYPE_LOG = "pl_trend_type_log"

STAGE_METRICS = "pl_stage_keyword_metrics"
STAGE_HISTORY = "pl_stage_keyword_metric_history"

# 트렌드 배지가 사는 칸. **표가 있어도 이 칸은 없을 수 있다** — 백엔드가 나중에 더한
# 칸이라 옛 스키마로 뜬 DB 에서는 비어 있고, 그때는 적재가 INSERT 에서 죽는다.
# `trend_column_ready()` 가 시작 전에 본다.
TREND_COLUMN = "trend_types"

# `trends` 는 키워드의 안정적인 상세 진입 ID다. AI 성공을 기다리지 않고, 현재
# NEW/RISING/CURRENT 판정이 하나라도 있는 키워드에 대표 행을 만든다. 기존 행은
# 저장/알림이 참조하는 ID를 유지하므로 기존 행은 갱신하지 않는다.
#
# **`keyword_id` 와 `updated_at` 만 넣는다.** 백엔드 V7(`retire_legacy_trend_analysis_
# columns`)이 `trend_types` · `description` · `summary` · `reason` 을 이 표에서 떼어냈다.
# 배지는 `keyword_metrics.trend_types` 가, AI 문구는 `trend_analyses` 가 기간별로 갖는다
# ([07 §6]). 이 표에 남은 역할은 상세 진입 ID 하나뿐이라 채울 칸도 그뿐이다.
#
# ⚠️ **한때 그 칸들을 채웠고, 그것이 파이프라인을 통째로 세웠다.** V7 이 드롭한 뒤에도
# 적재가 `trend_types` · `description` 을 넣고 있어 `UndefinedColumn` 이 났는데, 이 문장이
# 지표 병합과 **같은 트랜잭션** 안에 있어 `keyword_metrics` 까지 롤백됐다. 증상은 "AI 분석이
# 안 나온다" 로만 보였다 — aggregate 가 죽어 `METRICS` 자산이 안 나가고, 그것을 기다리는
# `spark_analyze` 가 아예 트리거되지 않았기 때문이다. 원인에서 가장 먼 자리에 증상이 뜬다.
# 스키마가 또 어긋나면 같은 방식으로 조용해지므로 `legacy_trend_columns()` 가 시작 전에 본다.
INSERT_TREND_IDENTITIES_SQL = """
INSERT INTO trends (keyword_id, updated_at)
SELECT DISTINCT m.keyword_id, now()
  FROM keyword_metrics m
 WHERE m.trend_types && ARRAY['NEW', 'RISING', 'CURRENT']::varchar[]
ON CONFLICT (keyword_id) DO NOTHING
"""

METRIC_COLUMNS = (
    "keyword_id",
    "period",
    "period_start",
    "period_end",
    "mention_count",
    "previous_mention_count",
    "growth_amount",
    "growth_rate",
    "mention_rank",
    TREND_COLUMN,
)
HISTORY_COLUMNS = ("keyword_id", "bucket_start", "bucket_end", "mention_count")

DDL = f"""
CREATE TABLE IF NOT EXISTS {TREND_TYPE_LOG} (
    -- 회차. 같은 날 다시 돌리면 다른 값이라 이력이 쌓인다 ([07 §6]).
    aggregate_run_id text        NOT NULL,
    keyword_id       bigint      NOT NULL,
    period           text        NOT NULL,
    -- 그 회차·그 기간에 받은 유형. 빈 배열이면 "이번엔 아무 유형도 아니다".
    trend_types      text[]      NOT NULL,
    reference_day    date        NOT NULL,
    judged_at        timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (aggregate_run_id, keyword_id, period)
);
-- "이 키워드가 왜 어제는 RISING 이었고 오늘은 아닌가" 를 보는 조회가 쓴다.
CREATE INDEX IF NOT EXISTS pl_trend_type_log_keyword_idx
    ON {TREND_TYPE_LOG} (keyword_id, reference_day);

-- 스테이징은 제약이 없다. 서비스 테이블을 `LIKE` 로 베끼지 않는 이유는 **그 표가 아직 없을
-- 수 있기 때문이다** — 백엔드가 기동하기 전에도 이 Job 의 스키마 확인은 돌아야 한다.
CREATE TABLE IF NOT EXISTS {STAGE_METRICS} (
    keyword_id             bigint      NOT NULL,
    period                 text        NOT NULL,
    period_start           timestamptz NOT NULL,
    period_end             timestamptz NOT NULL,
    mention_count          bigint      NOT NULL,
    previous_mention_count bigint      NOT NULL,
    growth_amount          bigint      NOT NULL,
    growth_rate            numeric,
    mention_rank           integer,
    -- 그 키워드·그 기간에 받은 유형. 빈 배열이면 "이번엔 아무 유형도 아니다" 이고, 그 값이
    -- 서비스 테이블로 그대로 건너가 배지를 뗀다.
    trend_types            text[]      NOT NULL DEFAULT '{{}}'
);
-- **지난 회차가 만든 스테이징 표에는 이 칸이 없다.** `CREATE TABLE IF NOT EXISTS` 는 있는
-- 표를 고치지 않으므로 여기서 따로 붙인다 — 없으면 적재가 INSERT 에서 죽고, 그 실패가
-- "전에는 됐는데" 로 나타난다. 표를 갓 만든 DB 에서는 아무 일도 하지 않는다.
ALTER TABLE {STAGE_METRICS}
    ADD COLUMN IF NOT EXISTS trend_types text[] NOT NULL DEFAULT '{{}}';
CREATE TABLE IF NOT EXISTS {STAGE_HISTORY} (
    keyword_id    bigint      NOT NULL,
    bucket_start  timestamptz NOT NULL,
    bucket_end    timestamptz NOT NULL,
    mention_count bigint      NOT NULL
);
"""

# --- 원자료 읽기 -----------------------------------------------------------
#
# **승격된 키워드만 본다** (`keyword_id IS NOT NULL`). 후보의 통계도 같은 표에 있지만
# 서비스 테이블은 `keywords` 를 참조하므로 걸 대상이 없다 ([07 §3]).
#
# `sum` 으로 접는 이유는 방어다. 병합이 정상이면 `(keyword_id, stat_date)` 에 행이 하나지만,
# 별칭 정리가 반쯤 된 상태에서는 둘이 될 수 있고 그때 조용히 하나만 세는 것이 더 나쁘다.
DAILY_SQL = f"""
SELECT s.keyword_id, s.domain, s.stat_date, sum(s.doc_count)::bigint AS mentions
  FROM {DAILY_STAT} s
 WHERE s.keyword_id IS NOT NULL
   AND s.stat_date >= %s AND s.stat_date < %s
 GROUP BY 1, 2, 3
"""

# 수집이 있었던 날 — **후보까지 포함해서** 본다 ([07 §3] "행의 존재로 0 과 데이터 없음을
# 구분한다"). 그 도메인의 그 날짜에 아무 문서도 없으면 버킷 행을 아예 만들지 않아 그래프에
# 구멍이 남는다. `(일자, 소스)` 수집 상태(`pl_batch_stat`)가 생기기 전까지의 근사다 —
# **전 소스가 죽은 날만 걸리고 일부만 죽은 날은 안 걸린다.** 하향 편향이라 방향은 안전하다.
COVERED_DATES_SQL = f"""
SELECT DISTINCT domain, stat_date
  FROM {DAILY_STAT}
 WHERE stat_date >= %s AND stat_date < %s
"""

# 날짜별 **언급 총량** — z-score 의 분모다 ([07 §6]).
#
# **원자료의 언급량을 그대로 배경과 견주면 안 된다.** 발행일별 문서량이 고정이 아니기
# 때문이다 — 2026-09-09 실데이터에서 6월은 하루 1~2건, 9월 첫 주는 하루 10~50건이었다
# (백필이 옛 날짜를 얇게 채운 결과다). 그 위에서 잰 z 는 "이 말이 떴다" 가 아니라 **"코퍼스가
# 커졌다"** 를 재고, 그러면 최근 구간의 거의 모든 키워드가 함께 튄다.
#
# 그래서 **그날 언급 총량에 대한 몫**으로 정규화한다. `요즘` 처럼 늘 일정한 비율로 나오는 말은
# 문서량이 열 배가 되어도 몫이 그대로라 z ≈ 0 이고, 실제로 새로 화제가 된 말만 몫이 오른다.
#
# **분모를 승격 여부로 거르지 않는다.** 후보까지 전부 센다 — 승격 집합이 자라면 분모가
# 계단처럼 뛰고, 그 계단이 모든 키워드의 z 에 한꺼번에 실린다.
DAILY_VOLUME_SQL = f"""
SELECT domain, stat_date, sum(doc_count)::bigint AS volume
  FROM {DAILY_STAT}
 WHERE stat_date >= %s AND stat_date < %s
 GROUP BY 1, 2
"""

# 시간별 **언급량** — `history_bucket: 1H` 일 때만 쓴다 ([07 §3]).
#
# **원자료에는 시각이 없다.** `pl_keyword_daily_stat` 도 `pl_document_candidate` 도 축이
# `stat_date`(date) 라 `extract` 단계에서 이미 날짜로 접힌다. 그런데 `contents.published_at`
# 은 시각을 온전히 들고 있으므로, 문서를 거쳐 되살린다 — 스키마를 바꾸지 않고 시간 버킷을
# 내는 유일한 길이다.
#
# **일별 집계와 같은 셈법을 쓴다** (`io/candidates.DAILY_STAT_RECOUNT`). `count(DISTINCT
# url_hash)` 로 문서를 세고 근사 중복은 뺀다. 별칭은 `pl_candidate.keyword_id` 가 대표를
# 들고 있어 조인이 겸해서 접는다 (`PERIOD_SOURCES_SQL` 과 같은 방식).
#
# `AT TIME ZONE` 을 두 번 거는 이유는 세션 시간대에 기대지 않기 위해서다 ([08 §4]). KST 는
# 정각 오프셋이라 시간 경계가 UTC 와 같지만, 그 사실에 기대는 코드는 시간대가 바뀌는 날
# 조용히 어긋난다.
#
# **⚠️ `pl_document_candidate` 는 보존 기간이 짧다** ([08 §3]). 그 지평 밖의 시간 버킷은
# 만들 수 없다 — 시간 버킷이 재계산 구간 W 전체가 아니라 최근 며칠만 채워지는 이유다.
HOURLY_SQL = f"""
SELECT c.keyword_id,
       date_trunc('hour', ct.published_at AT TIME ZONE 'Asia/Seoul')
           AT TIME ZONE 'Asia/Seoul' AS bucket_start,
       count(DISTINCT d.url_hash)::bigint AS mentions
  FROM {DOCUMENT_CANDIDATE} d
  JOIN {CANDIDATE} c ON c.domain = d.domain AND c.normalized_key = d.normalized_key
  JOIN {CONTENT_ID_MAP} m ON m.url_hash = d.url_hash
  JOIN {CONTENTS} ct ON ct.id = m.content_id
 WHERE c.keyword_id IS NOT NULL
   AND NOT d.is_dup
   AND ct.published_at >= %s AND ct.published_at < %s
 GROUP BY 1, 2
"""

# 구간 단위 **서로 다른 소스 수** — [07 §6]·[07 §8] 의 "한 매체에서만 쏟아진 키워드" 를
# 거르는 유일한 근거다.
#
# **날짜별 `source_count` 를 더해서는 알 수 없다.** 월요일에 A, 화요일에 B 가 쓴 키워드는
# 날짜별로는 늘 1 이지만 구간으로 보면 2 다. 2026-09-09 실데이터에서 30일 구간 키워드 5,354개
# 중 **1,979개(37%)** 가 그 차이에 걸렸다 — 근사로 대신할 수 있는 크기가 아니다.
#
# `pl_candidate` 를 거치는 것이 별칭 접기를 겸한다. 병합된 표기는 `MERGED` 상태로 대표의
# `keyword_id` 를 들고 있어([05], `io/keywords.PROMOTE_SQL`) 같은 키워드로 모인다.
#
# **⚠️ 이 표만 보존 기간이 짧다** ([08 §3] "가장 빠르게 자란다. 최근 N일만 유지"). 그래서
# 소스 판별은 **현재 구간(최대 30일)** 에만 쓴다 — `NEW` 의 90일 조용함 창은 원자료가 답한다.
PERIOD_SOURCES_SQL = f"""
SELECT c.keyword_id, count(DISTINCT d.source_id)::int AS sources
  FROM {DOCUMENT_CANDIDATE} d
  JOIN {CANDIDATE} c ON c.domain = d.domain AND c.normalized_key = d.normalized_key
 WHERE c.keyword_id IS NOT NULL
   AND NOT d.is_dup
   AND d.source_id IS NOT NULL
   AND d.stat_date >= %s AND d.stat_date < %s
 GROUP BY 1
"""

# --- 적재 -----------------------------------------------------------------
#
# `keyword_metric_history` — 재계산 구간 W 의 버킷을 덮어쓴다 ([07 §7]).
#
# 마지막 DELETE 의 범위가 **W 와 같아야** 병합·임계값 변경으로 사라져야 할 행이 실제로
# 사라진다. 스테이징에 없는 그 구간의 행은 이번 회차에 대상이 아니게 된 것이다 — 언급이 0 이
# 된 것과 다르다. 0 은 스테이징에 0 으로 들어온다.
HISTORY_MERGE_SQL = f"""
UPDATE {HISTORY} h
   SET bucket_end = s.bucket_end, mention_count = s.mention_count
  FROM {STAGE_HISTORY} s
 WHERE h.keyword_id = s.keyword_id AND h.bucket_start = s.bucket_start;

INSERT INTO {HISTORY} (keyword_id, bucket_start, bucket_end, mention_count)
SELECT s.keyword_id, s.bucket_start, s.bucket_end, s.mention_count
  FROM {STAGE_HISTORY} s
 WHERE NOT EXISTS (
        SELECT 1 FROM {HISTORY} h
         WHERE h.keyword_id = s.keyword_id AND h.bucket_start = s.bucket_start);

DELETE FROM {HISTORY} h
 WHERE h.bucket_start >= %(window_start)s AND h.bucket_start < %(window_end)s
   AND NOT EXISTS (
        SELECT 1 FROM {STAGE_HISTORY} s
         WHERE s.keyword_id = h.keyword_id AND s.bucket_start = h.bucket_start);

TRUNCATE {STAGE_HISTORY};
"""

TREND_LOG_SQL = f"""
INSERT INTO {TREND_TYPE_LOG} (aggregate_run_id, keyword_id, period, trend_types, reference_day)
VALUES %s
ON CONFLICT (aggregate_run_id, keyword_id, period) DO UPDATE SET
    trend_types = EXCLUDED.trend_types,
    judged_at   = now()
"""

# `to_regclass` 는 없으면 예외 대신 `NULL` 을 준다 (`io/keywords.py` 와 같은 방식).
SERVICE_TABLES_SQL = (
    f"SELECT to_regclass('{METRICS}') IS NOT NULL"
    f" AND to_regclass('{HISTORY}') IS NOT NULL"
)

# `trends` 에 우리가 채우지 못하는 `NOT NULL` 칸이 남아 있는가.
#
# 적재는 `keyword_id` · `updated_at` 만 넣는다 (V7 이후 형태). 그 둘 말고 기본값 없는
# `NOT NULL` 칸이 있으면 **첫 행에서 `NotNullViolation` 이 나고 지표 병합까지 롤백된다.**
# V7 이 아직 안 올라간 DB 가 정확히 그 상태다 — `trends.trend_types` 가 남아 있다.
#
# 칸 이름을 박지 않고 스키마에 묻는 이유는, 박아 두면 다음에 다른 칸이 늘었을 때 또
# 런타임에서야 알게 되기 때문이다. `id` 는 identity, `keyword_id` · `updated_at` 은 우리가
# 채우므로 뺀다. 이름을 돌려주니 오류 메시지가 어느 칸인지 그대로 말해 준다.
LEGACY_TREND_COLUMNS_SQL = """
SELECT coalesce(array_agg(a.attname ORDER BY a.attname), ARRAY[]::name[])
  FROM pg_attribute a
  JOIN pg_class c ON c.oid = a.attrelid
 WHERE c.relname = 'trends'
   AND a.attnum > 0
   AND NOT a.attisdropped
   AND a.attnotnull
   AND NOT a.atthasdef
   AND a.attname <> ALL (ARRAY['id', 'keyword_id', 'updated_at'])
"""

# 연관([06])이 읽는 표와 쓰는 표. **`keyword_contents` 가 재료다** — 원자료에는 문서
# 정체성이 없어 동시출현을 물을 수 없다 (`metrics/relations.py`).
KEYWORD_CONTENTS = "keyword_contents"
RELATION_TABLES_SQL = (
    f"SELECT to_regclass('{RELATIONS}') IS NOT NULL"
    f" AND to_regclass('{KEYWORD_CONTENTS}') IS NOT NULL"
)

# 국가별 일 언급량 (`V4__keyword_country_daily_metrics.sql`).
COUNTRY_METRICS = "keyword_country_daily_metrics"
COUNTRY_TABLE_SQL = f"SELECT to_regclass('{COUNTRY_METRICS}') IS NOT NULL"

# 원자료의 국가 칸을 그대로 국가 축 지표로 옮긴다 (2026-09-18).
#
# **전에는 전 키워드를 설정값 한 나라로 채웠다.** 봉투와 `curated` 에는 `source_country` 가
# 이미 있었는데 추출이 읽는 칸 목록에 없어서 뒤로 흐르지 못했고, 그래서 `aggregate.country
# .code` 라는 임시 설정이 표를 비워 두지 않는 역할을 하고 있었다. 이제 원자료가 나라를 알아
# 그 설정이 없어졌다.
#
# `metric_date` 와 `stat_date` 가 둘 다 KST 달력일이라 변환이 없다. 국가 코드도 원자료에서
# 이미 `^[A-Z]{{2}}$` 모양으로 접혀 있다 (`common/countries.py`).
#
# **창 안에서만 갈아 쓴다** — 다른 두 표와 같은 `UPDATE → INSERT → 창 안 DELETE` 규약이다.
# 전에는 날짜 조건이 하나도 없어 매 회차 전 기간을 지우고 다시 넣었다. 읽는 쪽이 최대 30일
# (`TrendRegionJourneyService` 가 `DAYS_30`)이므로 창의 하한이 그 30일이고, 값은
# `recompute_window_days` 가 준다.
#
# 마지막 `DELETE` 가 있어야 소스가 빠졌거나 병합으로 사라진 `(키워드, 날짜, 나라)` 행이
# 실제로 없어진다. 창 밖은 건드리지 않는다 — 원자료 지평 밖의 옛 행을 이 회차가 0 으로
# 덮어쓰거나 지우면, 화면의 옛 구간이 이유 없이 비어 버린다.
COUNTRY_SQL = f"""
CREATE TEMP TABLE _country_stat ON COMMIT DROP AS
SELECT keyword_id,
       source_country       AS country_code,
       stat_date            AS metric_date,
       sum(doc_count)::bigint AS mention_count
  FROM {DAILY_STAT}
 WHERE keyword_id IS NOT NULL
   AND stat_date >= %(window_start)s AND stat_date < %(window_end)s
 GROUP BY keyword_id, source_country, stat_date;

UPDATE {COUNTRY_METRICS} m
   SET mention_count = s.mention_count
  FROM _country_stat s
 WHERE m.keyword_id = s.keyword_id
   AND m.metric_date = s.metric_date
   AND m.country_code = s.country_code;

INSERT INTO {COUNTRY_METRICS} (keyword_id, country_code, metric_date, mention_count)
SELECT s.keyword_id, s.country_code, s.metric_date, s.mention_count
  FROM _country_stat s
 WHERE NOT EXISTS (
        SELECT 1 FROM {COUNTRY_METRICS} m
         WHERE m.keyword_id = s.keyword_id
           AND m.metric_date = s.metric_date
           AND m.country_code = s.country_code);

DELETE FROM {COUNTRY_METRICS} m
 WHERE m.metric_date >= %(window_start)s AND m.metric_date < %(window_end)s
   AND NOT EXISTS (
        SELECT 1 FROM _country_stat s
         WHERE s.keyword_id = m.keyword_id
           AND s.metric_date = m.metric_date
           AND s.country_code = m.country_code);
"""

# 창 안에서 쓴 행 수. `rowcount` 는 마지막 문장(`DELETE`)의 것이라 쓴 행을 세지 못한다.
COUNTRY_STAT_COUNT_SQL = "SELECT count(*) FROM _country_stat"

# 컬럼의 실제 타입. 배열이면 `trend_type[]` 같은 형태로 온다.
COLUMN_TYPE_SQL = """
SELECT format_type(a.atttypid, a.atttypmod)
  FROM pg_attribute a
  JOIN pg_class c ON c.oid = a.attrelid
 WHERE c.relname = %s AND a.attname = %s AND a.attnum > 0 AND NOT a.attisdropped
"""

# 있는 유니크 제약의 컬럼 조합. 없는 것을 크게 남기려고 본다 ([08 §5] 티어 1).
UNIQUE_COLUMNS_SQL = """
SELECT array_agg(a.attname ORDER BY a.attname)
  FROM pg_index i
  JOIN pg_class c ON c.oid = i.indrelid
  JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = ANY (i.indkey)
 WHERE c.relname = %s AND i.indisunique
 GROUP BY i.indexrelid
"""

# [08 §5] 티어 1 의 2·3번. 없어도 위 MERGE 는 돌지만, 다른 경로로 들어온 중복을 DB 가
# 막아주지 못한다 — 그래프에 같은 날짜가 두 번 나오면 화면에 바로 보인다.
WANTED_UNIQUE = {
    METRICS: ["keyword_id", "period"],
    HISTORY: ["bucket_start", "keyword_id"],
}


def metrics_merge_sql(period_cast: str, trend_cast: str, *, prune: bool) -> str:
    """`keyword_metrics` — 키워드 × 기간 1행 ([07 §7]). 트렌드 배지도 이 행에 실린다.

    **배지를 떼는 일이 따로 없다.** 스테이징이 그 회차의 모든 지표 행을 들고 오고 유형을
    하나도 못 받은 행은 빈 배열로 오므로, 이 UPDATE 가 배지를 다는 일과 떼는 일을 함께
    한다. 지표 행이 아예 사라진 키워드(두 구간 다 0)는 아래 DELETE 가 행째로 걷어낸다 —
    `trends` 를 쓰던 때 "지금 배지를 든 키워드를 따로 읽어 빈 배열로 덮는" 단계가 있었는데,
    그 단계가 통째로 필요 없어졌다.

    **⚠️ 마지막 DELETE 가 유령 행을 지운다.** 두 구간 다 0 이 된 키워드는 스테이징에 없으므로
    갱신되지 않고 지난 회차 값이 그대로 남는다 — `period_start` 가 옛 구간을 가리키는 행이다.

    **`prune=False` 는 D 를 과거로 옮겨 돌리는 실행이다** (`--reaggregate`). 그 실행의
    `period_start` 는 옛 구간이라 이 DELETE 가 **최신 행을 전부 지운다.** 백필 보정은
    시계열을 고치는 것이 목적이므로 그 모드에서는 지우지 않는다.

    **⚠️ 지우지 않을 뿐, UPDATE 는 그대로 돈다.** 자연 키가 `(keyword_id, period)` 라
    겹치는 행은 옛 구간의 값으로 덮인다 — `period_start` 도 배지도 그렇다 (2026-09-15
    `trendin_baseline` 에서 확인: `7D` 1,577행 중 907행이 옛 구간으로 덮였다). 재집계로
    시계열을 고친 뒤에는 **최신 D 로 한 번 더 돌려야** 지표와 배지가 제자리로 온다.
    """
    prune_sql = (
        f"""
DELETE FROM {METRICS} m
 USING (SELECT DISTINCT period, period_start FROM {STAGE_METRICS}) s
 WHERE m.period = s.period{period_cast} AND m.period_start <> s.period_start;
"""
        if prune
        else ""
    )
    return f"""
UPDATE {METRICS} m
   SET period_start           = s.period_start,
       period_end             = s.period_end,
       mention_count          = s.mention_count,
       previous_mention_count = s.previous_mention_count,
       growth_amount          = s.growth_amount,
       growth_rate            = s.growth_rate,
       mention_rank           = s.mention_rank,
       trend_types            = s.trend_types{trend_cast}
  FROM {STAGE_METRICS} s
 WHERE m.keyword_id = s.keyword_id AND m.period = s.period{period_cast};

INSERT INTO {METRICS} ({', '.join(METRIC_COLUMNS)})
SELECT s.keyword_id, s.period{period_cast}, s.period_start, s.period_end,
       s.mention_count, s.previous_mention_count, s.growth_amount, s.growth_rate,
       s.mention_rank, s.trend_types{trend_cast}
  FROM {STAGE_METRICS} s
 WHERE NOT EXISTS (
        SELECT 1 FROM {METRICS} m
         WHERE m.keyword_id = s.keyword_id AND m.period = s.period{period_cast});
{prune_sql}
TRUNCATE {STAGE_METRICS};
"""


@dataclass(frozen=True, slots=True)
class WriteResult:
    history: int
    metrics: int


class MetricSink:
    """두 서비스 테이블과 판별 이력 한 곳."""

    def __init__(self, config: Config) -> None:
        self._config = config

    def ensure_schema(self) -> None:
        """`pl_*` 만 만든다. 서비스 테이블은 백엔드 소유라 DDL 권한이 없다 ([08 §1])."""
        jdbc.execute(self._config, DDL)
        log.info("지표 스키마 확인: %s + 스테이징 셋", TREND_TYPE_LOG)

    def service_tables_ready(self) -> bool:
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute(SERVICE_TABLES_SQL)
            return bool(cur.fetchone()[0])

    def trend_column_ready(self) -> bool:
        """`keyword_metrics.trend_types` 가 있는가 ([07 §6]).

        **표가 있다고 칸이 있는 것은 아니다.** 배지가 이 칸으로 옮겨온 것이 나중이라, 그전
        마이그레이션까지만 올라간 DB 에는 표만 있고 칸이 없다. 그 상태로 적재하면 스테이징을
        다 채운 뒤 INSERT 에서 `column ... does not exist` 로 죽어서, 실패 지점이 원인과
        멀어진다. 시작 전에 한 번 묻는다.
        """
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute(COLUMN_TYPE_SQL, (METRICS, TREND_COLUMN))
            return cur.fetchone() is not None

    def legacy_trend_columns(self) -> tuple[str, ...]:
        """`trends` 에서 우리가 채우지 못하는 `NOT NULL` 칸들. 비어 있으면 정상이다.

        `trend_column_ready()` 와 짝이지만 **방향이 반대다.** 그쪽은 칸이 생겼는지를 묻고
        이쪽은 칸이 아직 안 사라졌는지를 묻는다. 둘 다 "표는 있는데 형태가 다른" DB 를
        시작 전에 걸러 내려는 것이고, 그 형태 차이가 지표 병합과 한 트랜잭션에서 터지면
        증상이 `spark_analyze` 까지 흘러가 "AI 분석이 안 나온다" 로만 보인다.
        """
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute(LEGACY_TREND_COLUMNS_SQL)
            row = cur.fetchone()
        return tuple(row[0]) if row and row[0] else ()

    def relations_ready(self) -> bool:
        """연관 표와 그 재료가 있는가 ([06]). `keyword_contents` 는 [05] 승격이 채운다."""
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute(RELATION_TABLES_SQL)
            return bool(cur.fetchone()[0])

    def rebuild_relations(
        self, *, since: datetime, until: datetime, thresholds: RelationThresholds
    ) -> int:
        """창 안의 동시출현을 다시 세어 `keyword_relations` 를 통째로 바꾼다. 쓴 행 수.

        **다른 표처럼 MERGE 하지 않고 지우고 다시 넣는다.** `keyword_metrics` 는 키워드마다
        한 행이라 이번 회차에 없는 행이 예외이지만, 연관은 **창이 하루 밀릴 때마다 쌍의
        상당수가 바뀐다.** 남은 옛 쌍을 골라 지우는 일이 결국 전량 비교라, 지우고 넣는 것과
        비용이 같으면서 코드만 길어진다.

        한 트랜잭션 안에서 한다 — 중간에 조회가 들어와도 빈 표를 보지 않는다.
        """
        from psycopg2.extras import execute_values

        params = {
            "since": since,
            "until": until,
            "min_co": thresholds.min_co_occurrence,
            "top_n": thresholds.top_n,
        }
        page = int(self._config.get("jdbc.batch_size", jdbc.DEFAULT_BATCH_SIZE))
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute(RELATION_SQL, params)
            now = datetime.now(timezone.utc)
            rows = [(src, tgt, score, co, now) for src, tgt, score, co in cur.fetchall()]
            cur.execute(f"DELETE FROM {RELATIONS}")
            _insert(cur, execute_values, RELATIONS, RELATION_COLUMNS, rows, page)
            conn.commit()
        return len(rows)

    def country_table_ready(self) -> bool:
        """국가별 일 언급량 표가 있는가. 백엔드 마이그레이션 V4 가 만든다."""
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute(COUNTRY_TABLE_SQL)
            return bool(cur.fetchone()[0])

    def rebuild_country_metrics(self, *, window_start: date, window_end: date) -> int:
        """`pl_keyword_daily_stat` → `keyword_country_daily_metrics`. 창 안에 쓴 행 수.

        **창 안에서만 갈아 쓴다** (`COUNTRY_SQL` 의 주석). 전에는 전 기간을 지우고 다시
        넣었는데, 그러면 원자료 지평 밖의 옛 행이 회차마다 사라진다.

        한 트랜잭션 안에서 한다 — 조회가 빈 표를 보지 않는다. 임시 테이블이
        `ON COMMIT DROP` 이라 행 수를 커밋 **전에** 센다.
        """
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute(COUNTRY_SQL, {"window_start": window_start, "window_end": window_end})
            cur.execute(COUNTRY_STAT_COUNT_SQL)
            written = int(cur.fetchone()[0])
            conn.commit()
        return written

    def warn_missing_constraints(self) -> list[str]:
        """없는 유니크 제약을 크게 남긴다. 돌기는 돌지만 방어가 한 겹 없다."""
        missing: list[str] = []
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            for table, wanted in WANTED_UNIQUE.items():
                cur.execute(UNIQUE_COLUMNS_SQL, (table,))
                found = [sorted(row[0]) for row in cur.fetchall()]
                if sorted(wanted) not in found:
                    missing.append(f"{table} ({', '.join(wanted)})")
                    log.warning(
                        "유니크 제약이 없다: %s (%s) — 적재는 UPDATE→INSERT 로 돌지만 다른 "
                        "경로의 중복을 DB 가 막지 못한다 ([08 §5] 티어 1). 지금 있는 것: %s",
                        table,
                        ", ".join(wanted),
                        found or "없음",
                    )
        return missing

    # --- 원자료 ----------------------------------------------------------
    def daily_mentions(self, *, start: str, end: str) -> tuple[tuple, ...]:
        """`(keyword_id, domain, stat_date, mentions)` — 반열린 `[start, end)`."""
        return self._query(DAILY_SQL, (start, end))

    def covered_dates(self, *, start: str, end: str) -> tuple[tuple, ...]:
        return self._query(COVERED_DATES_SQL, (start, end))

    def daily_volume(self, *, start: str, end: str) -> tuple[tuple, ...]:
        """`(domain, stat_date, volume)` — z-score 의 분모."""
        return self._query(DAILY_VOLUME_SQL, (start, end))

    def hourly_mentions(self, *, start: str, end: str) -> tuple[tuple, ...]:
        """`(keyword_id, bucket_start, mentions)` — 발행 시각 기준 반열린 `[start, end)`.

        언급이 있는 시간만 돌아온다. 없는 시간의 0 행은 만들지 않는다 — 백엔드가 버킷을
        스스로 세우고 저장 행이 없으면 0 으로 그리므로(`TrendHistoryService.getHistory`)
        화면이 같고, 활성 키워드 × 720 칸을 대부분 0 으로 채우지 않아도 된다.
        """
        return self._query(HOURLY_SQL, (start, end))

    def period_sources(self, *, start: str, end: str) -> dict[int, int]:
        rows = self._query(PERIOD_SOURCES_SQL, (start, end))
        return {int(keyword_id): int(sources) for keyword_id, sources in rows}

    # --- 적재 ------------------------------------------------------------
    def write(
        self,
        *,
        history: Sequence[tuple],
        metrics: Sequence[tuple],
        history_window: tuple[str, str],
        prune_metrics: bool = True,
    ) -> WriteResult:
        """두 표를 **한 연결, 한 트랜잭션**으로 쓴다 ([08 §4]).

        상세 화면 하나가 `keyword_metric_history`(그래프)와 `keyword_metrics`(숫자·배지)를
        함께 읽으므로 둘이 같은 회차에서 나와야 화면이 어긋나지 않는다 ([erd §4]).
        """
        from psycopg2.extras import execute_values

        page = int(self._config.get("jdbc.batch_size", jdbc.DEFAULT_BATCH_SIZE))
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            period_cast = self._cast(cur, METRICS, "period")
            trend_cast = self._cast(cur, METRICS, TREND_COLUMN)
            cur.execute(f"TRUNCATE {STAGE_HISTORY}, {STAGE_METRICS}")
            _insert(cur, execute_values, STAGE_HISTORY, HISTORY_COLUMNS, history, page)
            _insert(cur, execute_values, STAGE_METRICS, METRIC_COLUMNS, metrics, page)
            cur.execute(
                HISTORY_MERGE_SQL,
                {"window_start": history_window[0], "window_end": history_window[1]},
            )
            cur.execute(metrics_merge_sql(period_cast, trend_cast, prune=prune_metrics))
            if prune_metrics:
                cur.execute(INSERT_TREND_IDENTITIES_SQL)
        log.info("지표 적재: 버킷 %d · 기간지표 %d", len(history), len(metrics))
        return WriteResult(len(history), len(metrics))

    def log_verdict(self, rows: Sequence[tuple]) -> int:
        """회차별 판별 이력. 서비스로 나가지 않는다 ([07 §6])."""
        if not rows:
            return 0
        from psycopg2.extras import execute_values

        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            execute_values(cur, TREND_LOG_SQL, rows, page_size=len(rows))
        return len(rows)

    # --- 내부 ------------------------------------------------------------
    def _cast(self, cur: Any, table: str, column: str) -> str:
        """컬럼의 실제 타입으로 캐스트하는 조각. 표가 없으면 빈 문자열이다.

        스칼라 `text` · `varchar` 계열은 캐스트가 필요 없고, 네이티브 enum(`metric_period`)
        이나 enum 배열(`trend_type[]`)이면 붙여야 한다 ([08 §4]).

        **배열은 varchar 계열이어도 붙인다.** PostgreSQL 에 `varchar[] = text[]` 연산자가
        없어서, 스테이징의 `text[]` 와 비교하는 순간 "operator does not exist" 로 죽는다.
        스칼라에서는 같은 조합이 암묵 캐스트로 지나가기 때문에 배열만 예외가 된다 —
        옛 `trends.trend_types` 경로에서도 실제로 걸렸고, 현재의
        `keyword_metrics.trend_types` 도 어느 쪽으로 선언되든 같은 이유로 붙인다.
        """
        cur.execute(COLUMN_TYPE_SQL, (table, column))
        row = cur.fetchone()
        if row is None:
            return ""
        actual = str(row[0])
        base = actual.replace("[]", "").split("(")[0].strip()
        scalar_text = base in ("text", "character varying", "varchar", "character")
        if scalar_text and not actual.endswith("[]"):
            return ""
        return f"::{actual}"

    def _query(self, statement: str, params: tuple) -> tuple[tuple, ...]:
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute(statement, params)
            return tuple(cur.fetchall())


def _insert(
    cur: Any,
    execute_values: Any,
    table: str,
    columns: tuple[str, ...],
    rows: Iterable[tuple],
    page: int,
) -> None:
    staged = list(rows)
    if not staged:
        return
    execute_values(
        cur, f"INSERT INTO {table} ({', '.join(columns)}) VALUES %s", staged, page_size=page
    )
