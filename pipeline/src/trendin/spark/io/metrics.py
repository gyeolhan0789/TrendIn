"""`aggregate` 의 읽기와 적재 — 서비스 테이블 셋 + 판별 이력 하나 ([07 §7], [08 §4]).

| 테이블 | 소유 | 쓰는 법 |
| --- | --- | --- |
| `keyword_metric_history` | 서비스 | 재계산 구간 W 의 버킷을 덮어쓴다 |
| `keyword_metrics` | 서비스 | 키워드 × 기간 1행을 덮어쓰고, 이번 구간이 아닌 행을 지운다 |
| `trends` | 서비스 | `trend_types` 만 갱신. **AI 설명 칸은 건드리지 않는다** ([00 §4]) |
| `pl_trend_type_log` | 파이프라인 | 회차별 판별 이력 ([07 §6]) |

**`ON CONFLICT` 를 쓰지 않는다.** 규격은 그 형태를 적었지만([07 §7]) 그건 유니크 제약이
있다는 전제이고, **2026-09-10 확인 결과 제약이 규격과 다르다** — 백엔드 엔티티의
`keyword_metrics` UNIQUE 는 `(keyword_id, period, period_start, period_end)` 4열이고
(우리가 요청한 2열이 아니다), `trends.keyword_id` 에는 아예 없다. `ON CONFLICT` 는 인덱스와
정확히 맞아야 하므로, 제약이 무엇이든 같게 도는 형태로 짠다.

```
1. UPDATE target FROM stage    (자연 키로 맞춘 행)
2. INSERT ... WHERE NOT EXISTS (없던 행만)
3. DELETE                      (이번 회차에서 빠진 행 — 표마다 범위가 다르다)
```

**1·2 가 제약 없이도 멱등이다.** 제약이 있으면 그것이 한 겹 더 막아 주고, 없으면 이 순서가
같은 결과를 낸다. 이미 중복이 쌓여 있어도 UPDATE 가 전부를 같은 값으로 맞춘다. 그 대신
`warn_missing_constraints()` 가 없는 제약을 크게 남긴다 — 조용히 도는 것이 가장 나쁘다.

**배열·enum 컬럼의 타입을 실행 시점에 본다** ([08 §4]). `trends.trend_types` 는 네이티브 enum
배열(`trend_type[]`)이고 `keyword_metrics.period` 는 네이티브 enum(`metric_period`)이다 —
백엔드가 `cast('CURRENT' as trend_type) = any(...)` 로 조회하는 것이 그 증거다. 스테이징에는
`text`·`text[]` 로 넣고 MERGE 에서 **실제 컬럼 타입으로** 캐스트한다. 타입이 나중에 varchar 로
바뀌어도 이 코드는 그대로 돈다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from trendin.spark.common.config import Config
from trendin.spark.common.logging import get_logger
from trendin.spark.io import jdbc

log = get_logger(__name__)

# --- 읽는 표 (원자료) ------------------------------------------------------
DAILY_STAT = "pl_keyword_daily_stat"
DOCUMENT_CANDIDATE = "pl_document_candidate"
CANDIDATE = "pl_candidate"

# --- 쓰는 표 ---------------------------------------------------------------
METRICS = "keyword_metrics"
HISTORY = "keyword_metric_history"
TRENDS = "trends"
TREND_TYPE_LOG = "pl_trend_type_log"

STAGE_METRICS = "pl_stage_keyword_metrics"
STAGE_HISTORY = "pl_stage_keyword_metric_history"
STAGE_TRENDS = "pl_stage_trends"

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
)
HISTORY_COLUMNS = ("keyword_id", "bucket_start", "bucket_end", "mention_count")
TREND_COLUMNS = ("keyword_id", "trend_types")

# `trends.description` 이 `NOT NULL` 이다 (백엔드 엔티티, 2026-09-10 확인). AI 설명은 이
# 에픽의 범위 밖이라([00 §4]) 새 행에만 빈 문자열을 넣고 **갱신에서는 건드리지 않는다.**
# 다른 회차가 채운 설명을 우리가 지우지 않는다는 것이 요점이다.
EMPTY_DESCRIPTION = ""

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
    mention_rank           integer
);
CREATE TABLE IF NOT EXISTS {STAGE_HISTORY} (
    keyword_id    bigint      NOT NULL,
    bucket_start  timestamptz NOT NULL,
    bucket_end    timestamptz NOT NULL,
    mention_count bigint      NOT NULL
);
CREATE TABLE IF NOT EXISTS {STAGE_TRENDS} (
    keyword_id  bigint NOT NULL,
    trend_types text[] NOT NULL
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
    f" AND to_regclass('{TRENDS}') IS NOT NULL"
)

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


def metrics_merge_sql(period_cast: str, *, prune: bool) -> str:
    """`keyword_metrics` — 키워드 × 기간 1행 ([07 §7]).

    **⚠️ 마지막 DELETE 가 유령 행을 지운다.** 두 구간 다 0 이 된 키워드는 스테이징에 없으므로
    갱신되지 않고 지난 회차 값이 그대로 남는다 — `period_start` 가 옛 구간을 가리키는 행이다.

    **`prune=False` 는 D 를 과거로 옮겨 돌리는 실행이다** (`--reaggregate`). 그 실행의
    `period_start` 는 옛 구간이라 이 DELETE 가 **최신 행을 전부 지운다.** 백필 보정은
    시계열을 고치는 것이 목적이므로 그 모드에서는 지우지 않는다.
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
       mention_rank           = s.mention_rank
  FROM {STAGE_METRICS} s
 WHERE m.keyword_id = s.keyword_id AND m.period = s.period{period_cast};

INSERT INTO {METRICS} ({', '.join(METRIC_COLUMNS)})
SELECT s.keyword_id, s.period{period_cast}, s.period_start, s.period_end,
       s.mention_count, s.previous_mention_count, s.growth_amount, s.growth_rate, s.mention_rank
  FROM {STAGE_METRICS} s
 WHERE NOT EXISTS (
        SELECT 1 FROM {METRICS} m
         WHERE m.keyword_id = s.keyword_id AND m.period = s.period{period_cast});
{prune_sql}
TRUNCATE {STAGE_METRICS};
"""


def trends_merge_sql(array_cast: str) -> str:
    """`trends` — `trend_types` 만 쓴다 ([07 §6]).

    **행을 지우지 않는다.** `briefing_trends`·`notifications` 가 참조하고 있고, 나중에 채울
    `description`·`summary`·`reason` 도 함께 사라진다. 트렌드에서 내려오면 **빈 배열로**
    갱신한다 — 빈 배열과 `NULL` 을 섞지 않는다는 규약을 백엔드에 전달해야 한다.

    갱신 대상은 스테이징에 있는 키워드 **전부**다. 이번에 유형을 하나도 못 받은 키워드도
    빈 배열로 스테이징에 들어온다 (`metrics/batch.py`) — 그래야 배지가 실제로 떨어진다.

    **새 행은 유형이 있을 때만 만든다.** 한 번도 트렌드가 아니었던 키워드에 빈 배열 행을
    미리 깔면 `trends` 가 정규 키워드 전체로 불어난다 — 지표와 그래프는 이 표를 거치지 않으므로
    그 행이 화면에 주는 것이 없다.

    `updated_at` 은 **값이 바뀔 때만** 건드린다. 매 회차 손대면 백엔드의 `NEW` 목록 정렬
    (`order by trend.updated_at desc`)이 내용과 무관하게 흔들린다.
    """
    return f"""
UPDATE {TRENDS} t
   SET trend_types = s.trend_types{array_cast}, updated_at = now()
  FROM {STAGE_TRENDS} s
 WHERE t.keyword_id = s.keyword_id
   AND t.trend_types IS DISTINCT FROM s.trend_types{array_cast};

INSERT INTO {TRENDS} (keyword_id, trend_types, description, updated_at)
SELECT s.keyword_id, s.trend_types{array_cast}, '{EMPTY_DESCRIPTION}', now()
  FROM {STAGE_TRENDS} s
 WHERE cardinality(s.trend_types) > 0
   AND NOT EXISTS (SELECT 1 FROM {TRENDS} t WHERE t.keyword_id = s.keyword_id);

TRUNCATE {STAGE_TRENDS};
"""


@dataclass(frozen=True, slots=True)
class WriteResult:
    history: int
    metrics: int
    trends: int


class MetricSink:
    """세 서비스 테이블과 판별 이력 한 곳."""

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

    def period_sources(self, *, start: str, end: str) -> dict[int, int]:
        rows = self._query(PERIOD_SOURCES_SQL, (start, end))
        return {int(keyword_id): int(sources) for keyword_id, sources in rows}

    def trending_keywords(self) -> set[int]:
        """지금 배지를 들고 있는 키워드 ([07 §6] "트렌드에서 내려오면 배열을 비운다").

        이번 회차 지표에서 **아예 빠진** 키워드(두 구간 다 0)까지 덮어야 해서 `trends` 를
        직접 읽는다. 지표 대상만 보고 비우면 조용해진 키워드의 배지가 영원히 남는다.
        """
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute(f"SELECT keyword_id FROM {TRENDS} WHERE cardinality(trend_types) > 0")
            return {int(row[0]) for row in cur.fetchall()}

    # --- 적재 ------------------------------------------------------------
    def write(
        self,
        *,
        history: Sequence[tuple],
        metrics: Sequence[tuple],
        trends: Sequence[tuple],
        history_window: tuple[str, str],
        prune_metrics: bool = True,
    ) -> WriteResult:
        """세 표를 **한 연결, 한 트랜잭션**으로 쓴다 ([08 §4]).

        상세 화면 하나가 `keyword_metric_history`(그래프)와 `keyword_metrics`(숫자)를 함께
        읽으므로 둘이 같은 회차에서 나와야 화면이 어긋나지 않는다 ([erd §4]).
        """
        from psycopg2.extras import execute_values

        page = int(self._config.get("jdbc.batch_size", jdbc.DEFAULT_BATCH_SIZE))
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            period_cast = self._cast(cur, METRICS, "period")
            array_cast = self._cast(cur, TRENDS, "trend_types")
            cur.execute(f"TRUNCATE {STAGE_HISTORY}, {STAGE_METRICS}, {STAGE_TRENDS}")
            _insert(cur, execute_values, STAGE_HISTORY, HISTORY_COLUMNS, history, page)
            _insert(cur, execute_values, STAGE_METRICS, METRIC_COLUMNS, metrics, page)
            _insert(cur, execute_values, STAGE_TRENDS, TREND_COLUMNS, trends, page)
            cur.execute(
                HISTORY_MERGE_SQL,
                {"window_start": history_window[0], "window_end": history_window[1]},
            )
            cur.execute(metrics_merge_sql(period_cast, prune=prune_metrics))
            cur.execute(trends_merge_sql(array_cast))
        log.info(
            "지표 적재: 버킷 %d · 기간지표 %d · 트렌드 %d",
            len(history),
            len(metrics),
            len(trends),
        )
        return WriteResult(len(history), len(metrics), len(trends))

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

        `text` · `varchar` 계열이면 캐스트가 필요 없고, 네이티브 enum(`metric_period`)이나
        enum 배열(`trend_type[]`)이면 붙여야 한다 ([08 §4]).
        """
        cur.execute(COLUMN_TYPE_SQL, (table, column))
        row = cur.fetchone()
        if row is None:
            return ""
        actual = str(row[0])
        base = actual.replace("[]", "").split("(")[0].strip()
        if base in ("text", "character varying", "varchar", "character"):
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
