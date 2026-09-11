"""[05] 의 적재 — 내부 표 넷과 서비스 표 둘.

| 표 | 소유 | 담는 것 |
| --- | --- | --- |
| `pl_alias` | 우리 (DDL 은 `io/candidates.py`) | 별칭 → 대표 ([05 §3]) |
| `pl_merge_log` | 우리 | 병합 이력. **적용 시점**이 재계산 범위 판단의 근거 ([05 §8]) |
| `pl_review_queue` | 우리 | 검수 큐 ([05 §7]) |
| `pl_embedding_cache` | 우리 | 표기 → 벡터 ([01 §5]) |
| `pl_keyword_id_map` | 우리 | `(domain, normalized_key)` → `keywords.id` ([08 §3]) |
| `keywords` | **백엔드** | 승격된 키워드 ([05 §5]) |
| `keyword_contents` | **백엔드** | 키워드 ↔ 콘텐츠 ([08 §2]) |

**클래스를 둘로 나눈 것이 그 경계다** ([08 §1]).

| | 언제 도나 |
| --- | --- |
| `RegistrySink` | **늘 돈다.** 전부 `pl_` 이라 백엔드 선행 조건이 없다 |
| `KeywordSink` | 서비스 표가 있고 UNIQUE 가 걸려 있을 때만. 없으면 승격만 건너뛴다 |

## 🚫 `keywords (domain, normalized_name)` UNIQUE 가 없다

`backend/.../trend/domain/Keyword.java` 에 `@Table(name = "keywords")` 뿐이고
`uniqueConstraints` 가 없다. 같은 저장소의 `Member` · `KeywordMetric` 에는 있으니 빠뜨린
것으로 보인다. [09 §7] 항목 2 이고 **나중에 붙일 수 없는 유일한 항목**이다.

`ON CONFLICT` 는 유니크 제약을 참조하므로 아래 `PROMOTE_SQL` 은 그것이 실제로 있어야만
동작한다. 없는 채로 그냥 INSERT 하면 **매 배치마다 같은 키워드가 새 행으로 쌓인다** —
`Kubernetes` 가 100개 행이 되고, 언급량이 100 갈래로 흩어지고, 사용자가 관심 키워드로
등록한 행과 트렌드가 붙은 행이 서로 다른 `id` 가 된다 ([05 §5]).

**애플리케이션에서 SELECT 후 INSERT 로 우회하지 않는다** ([05 §5]). 경쟁 조건이 있고,
무엇보다 제약이 없으면 한 번 어긋난 데이터를 나중에 정리할 수 없다. 그래서
`unique_constraint_ready()` 가 `pg_index` 를 보고 **없으면 승격을 하지 않는다.**
`ContentsSink.service_table_ready()` 와 같은 형태이고 이유도 같다 — 조용히 건너뛰지 않고
크게 남긴다.

**Spark 는 서비스 테이블에 DDL 을 걸지 않는다** ([08 §1]). 아래 `DDL` 이 만드는 것은
`pl_*` 뿐이다. 만들어도 `ddl-auto: create` 가 다음 재배포에 다른 형태로 다시 만든다
([09 §7] 항목 1).

## 쓰기는 스테이징 + 서버사이드 MERGE

[08 §4] 그대로다. `signal` 을 스테이징에서 `text` 로 받아 MERGE 에서 `::jsonb` 로 캐스트하는
것도 그 절의 규약이다 — 최종 타입이 무엇으로 확정되든 캐스트 한 줄만 고치면 된다.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from trendin.spark.common.config import Config
from trendin.spark.common.logging import get_logger
from trendin.spark.io import jdbc
from trendin.spark.io.candidates import (
    ABBREVIATION,
    ALIAS,
    CANDIDATE,
    DAILY_STAT,
    DAILY_STAT_RECOUNT,
    DOCUMENT_CANDIDATE,
)
from trendin.spark.io.contents import MAP_TABLE as CONTENT_ID_MAP

# 상태 문자열의 정의 위치는 [05] 쪽이다 (`registry/review.py`) — 컬럼 기본값과 판정이 같은
# 값을 봐야 하고, 판정이 규격에서 나오므로 그쪽이 출처다. 그 모듈은 pyspark 도 io 도
# import 하지 않아 순환이 생기지 않는다.
from trendin.spark.registry.review import STATUS_APPROVED, STATUS_PENDING

log = get_logger(__name__)

# 우리 것.
MERGE_LOG = "pl_merge_log"
REVIEW_QUEUE = "pl_review_queue"
EMBEDDING_CACHE = "pl_embedding_cache"
KEYWORD_ID_MAP = "pl_keyword_id_map"

STAGE_ALIAS = "pl_stage_alias"
STAGE_REVIEW_QUEUE = "pl_stage_review_queue"
STAGE_KEYWORDS = "pl_stage_keywords"
STAGE_KEYWORD_CONTENT = "pl_stage_keyword_content"
STAGE_EMBEDDING = "pl_stage_embedding"

# 백엔드 소유. 읽고 쓰기만 한다.
KEYWORDS = "keywords"
KEYWORD_CONTENTS = "keyword_contents"

# `pl_candidate.status` — [05 §5] 의 관문을 통과한 것과 흡수된 것.
STATUS_PROMOTED = "PROMOTED"
STATUS_MERGED = "MERGED"

ALIAS_COLUMNS = (
    "domain",
    "alias_key",
    "canonical_key",
    "layer",
    "rule",
    "confidence",
    "signal",
    "extract_run_id",
)

REVIEW_COLUMNS = (
    "domain",
    "representative_key",
    "absorbed_key",
    "origin",
    "layer",
    "similarity",
    "npmi",
    "has_layer2_signal",
    "priority",
    "signal",
)

# `domain` 이 둘인 것이 헷갈리기 쉬운 자리다. `domain_slug` 는 우리 내부 값(`fashion`)이고
# `domain` 은 `keywords.domain` 에 들어가는 enum 상수명(`FASHION`)이다 ([01 §6]).
KEYWORD_COLUMNS = ("domain_slug", "domain", "normalized_name", "name")

KEYWORD_CONTENT_COLUMNS = ("domain", "normalized_key", "url_hash")

EMBEDDING_COLUMNS = ("model", "surface", "vector", "dim")

DDL = f"""
CREATE TABLE IF NOT EXISTS {MERGE_LOG} (
    id             bigserial   PRIMARY KEY,
    domain         text        NOT NULL,
    canonical_key  text        NOT NULL,
    alias_key      text        NOT NULL,
    -- 근거 ([05 §8]) — 층 번호 · 규칙 이름 · 신호 값. 나중에 판단을 검토하려면 필요하다.
    layer          integer     NOT NULL,
    rule           text        NOT NULL,
    confidence     double precision NOT NULL,
    signal         jsonb,
    extract_run_id text        NOT NULL,
    -- **통계 재계산 범위 판단**의 근거 ([05 §8]).
    applied_at     timestamptz NOT NULL DEFAULT now()
);
-- 재계산 범위를 물을 때 "언제 이후에 생긴 병합" 으로 훑는다.
CREATE INDEX IF NOT EXISTS pl_merge_log_applied_idx ON {MERGE_LOG} (domain, applied_at);

CREATE TABLE IF NOT EXISTS {REVIEW_QUEUE} (
    domain             text        NOT NULL,
    -- 쌍은 사전순으로 정규화해 저장한다 (`registry/review.py`). 안 하면 (a,b) 와 (b,a) 가
    -- 별개 행이 되어 한쪽을 REJECTED 해도 다른 쪽이 다음 배치에 다시 올라온다.
    representative_key text        NOT NULL,
    absorbed_key       text        NOT NULL,
    origin             text        NOT NULL,
    layer              integer     NOT NULL,
    similarity         double precision,
    -- [06] 이 계산한다. **다음 에픽이라 지금은 NULL** ([05 §3], `registry/embedding.py`).
    npmi               double precision,
    has_layer2_signal  boolean     NOT NULL,
    -- 두 후보의 문서 수 합 — **영향이 큰 것부터** ([05 §7]).
    priority           integer     NOT NULL,
    -- PENDING / APPROVED / REJECTED. **REJECTED 를 반드시 기록한다** ([05 §7]) — 없으면
    -- 같은 쌍이 매 배치마다 다시 올라와 검수자를 지치게 한다.
    status             text        NOT NULL DEFAULT '{STATUS_PENDING}',
    signal             jsonb,
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    decided_at         timestamptz,
    decided_by         text,
    PRIMARY KEY (domain, representative_key, absorbed_key)
);
-- 검수 화면이 "영향 큰 것부터" 로 읽는다.
CREATE INDEX IF NOT EXISTS pl_review_queue_pending_idx
    ON {REVIEW_QUEUE} (domain, status, priority DESC);

CREATE TABLE IF NOT EXISTS {EMBEDDING_CACHE} (
    -- 모델을 키에 넣는다. 모델이 바뀌면 벡터가 비교 불가라 같은 표기라도 다른 행이어야 한다.
    model      text        NOT NULL,
    surface    text        NOT NULL,
    -- `double precision[]` 이 아니라 jsonb — Spark JDBC 로 배열 컬럼에 직접 쓸 수 없다고
    -- 보고 짠다 ([08 §4]). 지금은 드라이버가 쓰지만 executor 로 옮겨도 형태를 안 바꾼다.
    vector     jsonb       NOT NULL,
    dim        integer     NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (model, surface)
);

-- `(domain, normalized_key)` → `keywords.id` ([08 §3]). `keyword_id` 에 FK 를 걸지 않는다
-- ([08 §6]) — `pl_*` 는 서비스 테이블에 논리적 참조만 둔다. `ddl-auto: create` 인 동안
-- 서비스 테이블이 재배포마다 다시 만들어지므로, FK 가 있으면 그때 이 표까지 딸려 깨진다.
CREATE TABLE IF NOT EXISTS {KEYWORD_ID_MAP} (
    domain         text        NOT NULL,
    normalized_key text        NOT NULL,
    keyword_id     bigint      NOT NULL,
    updated_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (domain, normalized_key)
);

-- 스테이징은 제약이 없다. 순수 INSERT 를 빠르게 받고 MERGE 뒤 비운다.
-- `signal` · `vector` 는 text 로 받아 MERGE 에서 `::jsonb` 로 캐스트한다 ([08 §4]).
CREATE TABLE IF NOT EXISTS {STAGE_ALIAS} (
    domain         text NOT NULL,
    alias_key      text NOT NULL,
    canonical_key  text NOT NULL,
    layer          integer NOT NULL,
    rule           text NOT NULL,
    confidence     double precision NOT NULL,
    signal         text,
    extract_run_id text NOT NULL
);
CREATE TABLE IF NOT EXISTS {STAGE_REVIEW_QUEUE} (
    domain             text NOT NULL,
    representative_key text NOT NULL,
    absorbed_key       text NOT NULL,
    origin             text NOT NULL,
    layer              integer NOT NULL,
    similarity         double precision,
    npmi               double precision,
    has_layer2_signal  boolean NOT NULL,
    priority           integer NOT NULL,
    signal             text
);
CREATE TABLE IF NOT EXISTS {STAGE_KEYWORDS} (
    domain_slug     text NOT NULL,
    domain          text NOT NULL,
    normalized_name text NOT NULL,
    name            text NOT NULL
);
CREATE TABLE IF NOT EXISTS {STAGE_KEYWORD_CONTENT} (
    domain         text  NOT NULL,
    normalized_key text  NOT NULL,
    url_hash       bytea NOT NULL
);
CREATE TABLE IF NOT EXISTS {STAGE_EMBEDDING} (
    model   text NOT NULL,
    surface text NOT NULL,
    vector  text NOT NULL,
    dim     integer NOT NULL
);
"""

_ALIAS_STAGE_COLUMNS = ", ".join(ALIAS_COLUMNS)

# 순서가 중요하다.
#   1. **바뀐 별칭만** 골라 둔다 — 새로 생긴 것과 대표가 달라진 것. 매 실행 같은 별칭을
#      다시 기록하면 `pl_merge_log` 가 부풀고 "적용 시점" 이 뜻을 잃는다 ([05 §8]).
#   2. 그것만 이력에 남긴다. **`pl_alias` upsert 보다 먼저다** — 뒤에 하면 비교 대상이
#      이미 갱신돼 있어 무엇이 바뀌었는지 알 수 없다.
#   3. `pl_alias` upsert. **지우지 않는다** — 증거가 이번 실행에 안 잡혔다고 병합을 되돌리면
#      언급량이 다시 갈라지고 그 계단이 사용자에게 하락으로 보인다 ([05 §8]).
#   4. 바뀐 별칭이 관측된 전 구간을 모은다. 사슬이 없으므로(아래) 별칭·대표 두 키로 충분하다.
#   5. 흡수된 후보를 `MERGED` 로 적는다. **승격과 무관하다** ([10] 의 선행 조건 표 —
#      "층 1·2 병합 · 선행 조건 없다") — `keyword_id` 만 승격이 도는 자리에서 채워진다.
#   6. 그 날짜의 일별 원자료를 다시 센다 — `io/candidates.DAILY_STAT_RECOUNT` 와 **같은 SQL**.
#
# **사슬은 생기지 않는다.** `registry/alias.resolve` 가 기존 별칭까지 쌍으로 되먹여 매 실행
# 전체 닫힘을 다시 계산하므로, 나오는 표는 늘 한 홉이다 (`a → b`, `b → c` 가 아니라
# `a → c`, `b → c`). 재집계의 `coalesce(al.canonical_key, ...)` 가 한 홉만 따라가므로
# 이 성질이 정확성 조건이다.
ALIAS_MERGE_SQL = f"""
CREATE TEMP TABLE _new_alias ON COMMIT DROP AS
SELECT s.*
  FROM (
        SELECT DISTINCT ON (domain, alias_key) {_ALIAS_STAGE_COLUMNS}
          FROM {STAGE_ALIAS}
         ORDER BY domain, alias_key, confidence DESC, layer, canonical_key
       ) s
  LEFT JOIN {ALIAS} a ON a.domain = s.domain AND a.alias_key = s.alias_key
 WHERE a.alias_key IS NULL OR a.canonical_key <> s.canonical_key;

INSERT INTO {MERGE_LOG}
    (domain, canonical_key, alias_key, layer, rule, confidence, signal, extract_run_id)
SELECT domain, canonical_key, alias_key, layer, rule, confidence, signal::jsonb, extract_run_id
  FROM _new_alias;

INSERT INTO {ALIAS} (domain, alias_key, canonical_key, layer, rule, confidence, signal, updated_at)
SELECT DISTINCT ON (domain, alias_key)
       domain, alias_key, canonical_key, layer, rule, confidence, signal::jsonb, now()
  FROM {STAGE_ALIAS}
 ORDER BY domain, alias_key, confidence DESC, layer, canonical_key
ON CONFLICT (domain, alias_key) DO UPDATE SET
    canonical_key = EXCLUDED.canonical_key,
    layer         = EXCLUDED.layer,
    rule          = EXCLUDED.rule,
    confidence    = EXCLUDED.confidence,
    signal        = EXCLUDED.signal,
    updated_at    = EXCLUDED.updated_at;

UPDATE {CANDIDATE} c
   SET status = '{STATUS_MERGED}', updated_at = now()
  FROM {ALIAS} a
 WHERE a.domain = c.domain AND a.alias_key = c.normalized_key
   AND c.status <> '{STATUS_MERGED}';

CREATE TEMP TABLE _affected_date ON COMMIT DROP AS
SELECT DISTINCT d.domain, d.stat_date
  FROM {DOCUMENT_CANDIDATE} d
  JOIN _new_alias n ON n.domain = d.domain
   AND (d.normalized_key = n.alias_key OR d.normalized_key = n.canonical_key);

{DAILY_STAT_RECOUNT}

TRUNCATE {STAGE_ALIAS};
"""

# 큐는 **판단을 덮지 않는다.** `PENDING` 인 행만 우선순위·신호를 갱신하고, `APPROVED` ·
# `REJECTED` 는 그대로 둔다 — 그러지 않으면 거절한 쌍이 매 배치마다 `PENDING` 으로 되살아난다.
REVIEW_MERGE_SQL = f"""
INSERT INTO {REVIEW_QUEUE}
    (domain, representative_key, absorbed_key, origin, layer, similarity, npmi,
     has_layer2_signal, priority, signal, updated_at)
SELECT DISTINCT ON (domain, representative_key, absorbed_key)
       domain, representative_key, absorbed_key, origin, layer, similarity, npmi,
       has_layer2_signal, priority, signal::jsonb, now()
  FROM {STAGE_REVIEW_QUEUE}
 ORDER BY domain, representative_key, absorbed_key, priority DESC
ON CONFLICT (domain, representative_key, absorbed_key) DO UPDATE SET
    origin            = EXCLUDED.origin,
    layer             = EXCLUDED.layer,
    similarity        = EXCLUDED.similarity,
    npmi              = EXCLUDED.npmi,
    has_layer2_signal = EXCLUDED.has_layer2_signal,
    priority          = EXCLUDED.priority,
    signal            = EXCLUDED.signal,
    updated_at        = EXCLUDED.updated_at
 WHERE {REVIEW_QUEUE}.status = '{STATUS_PENDING}';

TRUNCATE {STAGE_REVIEW_QUEUE};
"""

EMBEDDING_MERGE_SQL = f"""
INSERT INTO {EMBEDDING_CACHE} (model, surface, vector, dim, updated_at)
SELECT DISTINCT ON (model, surface) model, surface, vector::jsonb, dim, now()
  FROM {STAGE_EMBEDDING}
 ORDER BY model, surface
ON CONFLICT (model, surface) DO UPDATE SET
    vector     = EXCLUDED.vector,
    dim        = EXCLUDED.dim,
    updated_at = EXCLUDED.updated_at;

TRUNCATE {STAGE_EMBEDDING};
"""

# `DO NOTHING` 이 아니라 `DO UPDATE` 인 것이 핵심이다 ([08 §4], [05 §5]). `DO NOTHING` 은
# 충돌한 행에 대해 `RETURNING` 을 내주지 않아서 이미 있는 키워드의 `id` 를 못 받는다 —
# 그러면 `keyword_contents` 를 만들 수 없다.
#
# **`name` 을 갱신하는 이유** ([05 §5]) — 대표 표기는 빈도로 정하므로 코퍼스가 자라면
# 바뀔 수 있다 (`ai agent` → `AI Agent`). 비교키가 같으면 같은 키워드이므로 표기만 고친다.
#
# 이어서 `pl_candidate` · `pl_keyword_daily_stat` 의 `keyword_id` 를 채운다. 별칭에는
# **대표의 `keyword_id` 를 적는다** — 운영 조회가 별칭에서 대표를 한 번에 찾아갈 수 있게
# 하려는 것이고, 그 값이 서비스로 나가지는 않는다. `MERGED` 표시 자체는 여기 없다 —
# 승격 없이도 병합은 도므로 `ALIAS_MERGE_SQL` 이 적는다 ([10] 의 선행 조건 표).
#
# 그 문장이 `LEFT JOIN` 이 아니라 `JOIN` 인 것이 조건이다. 대표가 아직 승격되지 않은 별칭은
# 지도에 없고, `LEFT JOIN` 이면 그 행의 `keyword_id` 를 `NULL` 로 덮어쓴다.
PROMOTE_SQL = f"""
CREATE TEMP TABLE _staged_keyword ON COMMIT DROP AS
SELECT DISTINCT ON (domain, normalized_name) domain_slug, domain, normalized_name, name
  FROM {STAGE_KEYWORDS}
 ORDER BY domain, normalized_name, name;

WITH upserted AS (
    INSERT INTO {KEYWORDS} (domain, name, normalized_name)
    SELECT domain, name, normalized_name FROM _staged_keyword
    ON CONFLICT (domain, normalized_name) DO UPDATE SET
        name = EXCLUDED.name
    RETURNING id, domain, normalized_name
)
INSERT INTO {KEYWORD_ID_MAP} (domain, normalized_key, keyword_id, updated_at)
SELECT s.domain_slug, s.normalized_name, u.id, now()
  FROM upserted u
  JOIN _staged_keyword s
    ON s.domain = u.domain AND s.normalized_name = u.normalized_name
ON CONFLICT (domain, normalized_key) DO UPDATE SET
    keyword_id = EXCLUDED.keyword_id,
    updated_at = EXCLUDED.updated_at;

UPDATE {CANDIDATE} c
   SET status = '{STATUS_PROMOTED}', keyword_id = m.keyword_id, updated_at = now()
  FROM {KEYWORD_ID_MAP} m
 WHERE m.domain = c.domain AND m.normalized_key = c.normalized_key
   AND (c.status <> '{STATUS_PROMOTED}' OR c.keyword_id IS DISTINCT FROM m.keyword_id);

UPDATE {CANDIDATE} c
   SET status = '{STATUS_MERGED}', keyword_id = m.keyword_id, updated_at = now()
  FROM {ALIAS} a
  JOIN {KEYWORD_ID_MAP} m
    ON m.domain = a.domain AND m.normalized_key = a.canonical_key
 WHERE a.domain = c.domain AND a.alias_key = c.normalized_key
   AND (c.status <> '{STATUS_MERGED}' OR c.keyword_id IS DISTINCT FROM m.keyword_id);

UPDATE {DAILY_STAT} s
   SET keyword_id = m.keyword_id, updated_at = now()
  FROM {KEYWORD_ID_MAP} m
 WHERE m.domain = s.domain AND m.normalized_key = s.normalized_key
   AND s.keyword_id IS DISTINCT FROM m.keyword_id;

TRUNCATE {STAGE_KEYWORDS};
"""

# `keyword_contents` 는 **재추출 시 해당 문서분만** 지우고 다시 넣는다 ([08 §2] 표).
# 문서의 후보가 바뀌면 옛 연결이 남아 화면에 엉뚱한 콘텐츠가 걸리기 때문이다. 지우는 범위가
# `content_id` 단위라, 그 문서의 다른 키워드 연결도 함께 지워지고 같은 트랜잭션에서 다시
# 들어간다 — 그래서 스테이징에는 **그 문서의 `selected` 후보 전부**가 있어야 한다.
#
# 승격되지 않은 후보는 `pl_keyword_id_map` 조인에서 떨어진다. `pl_content_id_map` 에 없는
# 문서(=`contents` 적재를 건너뛴 배치)도 떨어지고, 그 건수는 부른 쪽이 통계로 남긴다.
#
# **지우는 범위는 조인 결과가 아니라 이번에 처리한 문서다** (`_touched_content`). 넣을 것을
# 담은 표(`_keyword_content`)로 지우면 조인에서 떨어진 문서가 삭제 대상에서도 빠진다 —
# 이번 회차 후보가 전부 미승격인 문서는 `content_id` 가 그 표에 아예 없어 옛 연결이 그대로
# 남고, 그게 바로 위 문단이 막으려던 경우다. 삭제만 문서 단위로 넓히면 닫힌다.
LINK_CONTENTS_SQL = f"""
CREATE TEMP TABLE _touched_content ON COMMIT DROP AS
SELECT DISTINCT c.content_id
  FROM {STAGE_KEYWORD_CONTENT} s
  JOIN {CONTENT_ID_MAP} c ON c.url_hash = s.url_hash;

CREATE TEMP TABLE _keyword_content ON COMMIT DROP AS
SELECT DISTINCT k.keyword_id, c.content_id
  FROM {STAGE_KEYWORD_CONTENT} s
  LEFT JOIN {ALIAS} a ON a.domain = s.domain AND a.alias_key = s.normalized_key
  JOIN {KEYWORD_ID_MAP} k
    ON k.domain = s.domain
   AND k.normalized_key = coalesce(a.canonical_key, s.normalized_key)
  JOIN {CONTENT_ID_MAP} c ON c.url_hash = s.url_hash;

DELETE FROM {KEYWORD_CONTENTS} kc
 USING _touched_content t
 WHERE kc.content_id = t.content_id;

INSERT INTO {KEYWORD_CONTENTS} (keyword_id, content_id)
SELECT keyword_id, content_id FROM _keyword_content
ON CONFLICT DO NOTHING;

TRUNCATE {STAGE_KEYWORD_CONTENT};
"""

# `to_regclass` 는 없으면 예외 대신 `NULL` 을 준다 — `information_schema` 조회보다 짧고
# 스키마 검색 경로를 그대로 따른다 (`io/contents.py` 와 같은 방식).
SERVICE_TABLES_SQL = (
    f"SELECT to_regclass('{KEYWORDS}') IS NOT NULL AND "
    f"to_regclass('{KEYWORD_CONTENTS}') IS NOT NULL"
)

# 이번 실행이 처리한 문서의 `selected` 후보를 스테이징으로 옮긴다. **드라이버를 왕복하지
# 않는다** — 행이 이미 DB 안에 있으므로 꺼내서 다시 넣을 이유가 없다.
#
# `extract_run_id` 로 좁히는 것이 "이번에 처리한 문서" 의 정의다. [08 §3] 대로
# `pl_document_candidate` 에는 문서당 실행 하나만 남으므로, 이 값이 곧 그 문서의 최신 후보다.
STAGE_KEYWORD_CONTENT_SQL = f"""
INSERT INTO {STAGE_KEYWORD_CONTENT} (domain, normalized_key, url_hash)
SELECT domain, normalized_key, url_hash
  FROM {DOCUMENT_CANDIDATE}
 WHERE domain = %s AND extract_run_id = %s AND selected
"""

# --- 심사 원자료 -----------------------------------------------------------
#
# **집계를 PostgreSQL 에서 한다.** [04] 는 문서 × 후보 규모라 Spark 가 필요했지만 [05] 의
# 입력은 이미 접힌 내부 테이블(후보 수천~수만)이다. 그 규모를 단일 JDBC 연결로 드라이버까지
# 끌고 와 파이썬으로 다시 접으면, DB 가 인덱스로 하는 일을 느리게 재현하는 것이 된다
# (`pl_document_candidate_key_idx`).
#
# `is_dup` 문서를 뺀 기준이다 ([05 §5] 다섯째 조건) — 크로스포스트로 부풀린 것을 막는다.
OBSERVATION_SQL = f"""
SELECT c.normalized_key,
       c.surface,
       c.status,
       c.keyword_id,
       coalesce(o.doc_count, 0)     AS doc_count,
       coalesce(o.observed_days, 0) AS observed_days,
       coalesce(o.source_count, 0)  AS source_count,
       coalesce(o.author_count, 0)  AS author_count
  FROM {CANDIDATE} c
  LEFT JOIN (
        SELECT normalized_key,
               count(DISTINCT url_hash) AS doc_count,
               count(DISTINCT stat_date) AS observed_days,
               count(DISTINCT source_id) AS source_count,
               count(DISTINCT author) FILTER (WHERE author IS NOT NULL AND author <> '')
                   AS author_count
          FROM {DOCUMENT_CANDIDATE}
         WHERE domain = %s AND NOT is_dup
         GROUP BY normalized_key
       ) o ON o.normalized_key = c.normalized_key
 WHERE c.domain = %s
"""

# 대표별 누적 관측 — **별칭을 접은 뒤**의 값이다. 위 질의와 따로 있는 이유는 셈의 단위가
# 다르기 때문이다. 문서 수는 합이 아니라 **합집합의 크기**라, 별칭별 값을 더하면 두 표기가
# 함께 나온 문서를 두 번 센다 ([05 §8]).
GROUP_OBSERVATION_SQL = f"""
SELECT coalesce(a.canonical_key, d.normalized_key) AS canonical_key,
       count(DISTINCT d.url_hash) AS doc_count,
       count(DISTINCT d.stat_date) AS observed_days,
       count(DISTINCT d.source_id) AS source_count,
       count(DISTINCT d.author) FILTER (WHERE d.author IS NOT NULL AND d.author <> '')
           AS author_count
  FROM {DOCUMENT_CANDIDATE} d
  LEFT JOIN {ALIAS} a ON a.domain = d.domain AND a.alias_key = d.normalized_key
 WHERE d.domain = %s AND NOT d.is_dup
 GROUP BY coalesce(a.canonical_key, d.normalized_key)
"""

# 약어 ↔ 전개형 관측을 쌍 단위로 접는다 ([05 §3]). `bool_and` 인 이유는 한 문서라도 초성
# 대응이 아니면 그 쌍의 증거가 약해지기 때문이다 — `min` 과 같은 뜻이고 의도가 더 읽힌다.
ABBREVIATION_EVIDENCE_SQL = f"""
SELECT abbreviation_key,
       expansion_key,
       bool_and(initials_match)  AS initials_match,
       count(DISTINCT url_hash)  AS document_count,
       count(DISTINCT source_id) AS source_count
  FROM {ABBREVIATION}
 WHERE domain = %s
 GROUP BY abbreviation_key, expansion_key
"""

# `(domain, normalized_name)` UNIQUE 가 실제로 있는지. **컬럼 집합이 정확히 그 둘**이어야
# 한다 — `normalized_name` 단독이면 개발의 `모델` 과 패션의 `모델` 이 충돌해 한쪽이 못
# 들어가고([05 §6]), 셋 이상이면 `ON CONFLICT (domain, normalized_name)` 이 그 인덱스를
# 추론하지 못한다.
UNIQUE_CONSTRAINT_SQL = f"""
SELECT EXISTS (
    SELECT 1
      FROM pg_index i
      JOIN pg_class c ON c.oid = i.indrelid
      JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = ANY (i.indkey)
     WHERE c.relname = '{KEYWORDS}' AND i.indisunique
     GROUP BY i.indexrelid
    -- `attname` 은 `name` 타입이라 `text[]` 와 바로 비교되지 않는다 (`operator does not
    -- exist: name[] = text[]`). 2026-09-10 에 제약이 실제로 생긴 DB 에서 처음 드러났다 —
    -- 그전에는 `keywords` 가 없어 이 경로가 돈 적이 없다.
    HAVING array_agg(a.attname::text ORDER BY a.attname::text)
           = ARRAY['domain', 'normalized_name']
)
"""


@dataclass(frozen=True, slots=True)
class AliasResult:
    aliases: int
    new_or_changed: int
    recounted_dates: int


class RegistrySink:
    """`pl_` 내부 표만. **백엔드 선행 조건 없이 돈다** ([08 §1])."""

    def __init__(self, config: Config) -> None:
        self._config = config

    def ensure_schema(self) -> None:
        """**우리 테이블만** 만든다. `pl_alias` 는 `io/candidates.py` 가 만든다."""
        jdbc.execute(self._config, DDL)
        log.info(
            "레지스트리 스키마 확인: %s · %s · %s · %s",
            MERGE_LOG,
            REVIEW_QUEUE,
            EMBEDDING_CACHE,
            KEYWORD_ID_MAP,
        )

    # --- 별칭 ------------------------------------------------------------
    def apply_aliases(self, rows: Sequence[tuple], *, domain: str) -> AliasResult:
        """별칭을 반영하고 영향받은 날짜를 다시 센다 — **한 연결, 한 트랜잭션.**

        둘이 갈리면 안 되는 이유가 [05 §8] 이다. 별칭만 들어가고 재집계가 죽으면 언급량이
        여전히 표기별로 갈려 있는데 `pl_alias` 는 합쳐졌다고 말한다 — 다음 실행의
        `_new_alias` 가 비어 재집계가 다시 트리거되지도 않으므로, 그 상태가 영구히 남는다.

        빈 목록이면 아무것도 하지 않는다. 별칭이 없는 것과 별칭을 지우는 것은 다르다 —
        **지우지 않는다** ([05 §1] 의 정신).
        """
        if not rows:
            return AliasResult(0, 0, 0)
        from psycopg2.extras import execute_values

        page = int(self._config.get("jdbc.batch_size", jdbc.DEFAULT_BATCH_SIZE))
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute(f"TRUNCATE {STAGE_ALIAS}")
            execute_values(
                cur,
                f"INSERT INTO {STAGE_ALIAS} ({_ALIAS_STAGE_COLUMNS}) VALUES %s",
                list(rows),
                page_size=page,
            )
            cur.execute(ALIAS_MERGE_SQL)
            # 임시 테이블은 `ON COMMIT DROP` 이라 커밋 전까지 살아 있다. 시각으로 어림하지
            # 않고 그것을 직접 센다 — 어림하면 같은 초에 두 번 돌 때 값이 겹친다.
            cur.execute(
                "SELECT (SELECT count(*) FROM _new_alias), (SELECT count(*) FROM _affected_date)"
            )
            changed, dates = (int(value) for value in (cur.fetchone() or (0, 0)))
        log.info(
            "[%s] 별칭 %d건 반영 (새로 기록 %d · 재집계 %d 일자)", domain, len(rows), changed, dates
        )
        return AliasResult(aliases=len(rows), new_or_changed=changed, recounted_dates=dates)

    # --- 검수 큐 ---------------------------------------------------------
    def enqueue_review(self, rows: Sequence[tuple]) -> int:
        """검수 큐 upsert. `PENDING` 이 아닌 행은 건드리지 않는다."""
        if not rows:
            return 0
        return _stage_rows(
            self._config,
            table=STAGE_REVIEW_QUEUE,
            columns=REVIEW_COLUMNS,
            rows=rows,
            merge_sql=REVIEW_MERGE_SQL,
        )

    def decided_pairs(self, *, domain: str) -> tuple[tuple[str, str, str], ...]:
        """`APPROVED` · `REJECTED` 가 붙은 쌍. **`PENDING` 은 안 준다** — 그건 우선순위가
        갱신되는 것이 맞고, 판단이 끝난 것만 다시 올리지 않아야 한다 ([05 §7])."""
        rows = self._query(
            f"SELECT representative_key, absorbed_key, status FROM {REVIEW_QUEUE} "
            f"WHERE domain = %s AND status <> '{STATUS_PENDING}'",
            (domain,),
        )
        return tuple((domain, row[0], row[1]) for row in rows)

    def approved_pairs(self, *, domain: str) -> tuple[tuple[str, str, str], ...]:
        """`APPROVED` 쌍. **다음 `extract` 실행부터 적용된다** ([05 §7])."""
        rows = self._query(
            f"SELECT representative_key, absorbed_key FROM {REVIEW_QUEUE} "
            f"WHERE domain = %s AND status = '{STATUS_APPROVED}'",
            (domain,),
        )
        return tuple((domain, row[0], row[1]) for row in rows)

    # --- 임베딩 캐시 -----------------------------------------------------
    def cached_vectors(self, *, model: str) -> dict[str, str]:
        """`표기 → 벡터 JSON`. 드라이버에서 인코딩하므로 여기서도 드라이버로 읽는다
        (`registry/embedding.py` 의 배치 추론 절)."""
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT surface, vector::text FROM {EMBEDDING_CACHE} WHERE model = %s",
                (model,),
            )
            return {row[0]: row[1] for row in cur.fetchall()}

    def cache_vectors(self, rows: Sequence[tuple]) -> int:
        """새로 계산한 벡터만 넣는다. **표기가 바뀌지 않으면 다시 계산하지 않는다** ([01 §5])."""
        if not rows:
            return 0
        return _stage_rows(
            self._config,
            table=STAGE_EMBEDDING,
            columns=EMBEDDING_COLUMNS,
            rows=rows,
            merge_sql=EMBEDDING_MERGE_SQL,
        )

    # --- 심사 원자료 -----------------------------------------------------
    #
    # 넷 다 **드라이버에서 읽는다.** 집계가 DB 쪽에서 끝나 결과가 후보 수준(수천~수만 행)이고,
    # 소비하는 곳이 순수 파이썬(`registry/*.py`)이라 Spark 프레임을 거칠 이유가 없다.
    # [04] 가 Spark 를 쓴 것은 문서 × 후보 규모였기 때문이고, [05] 는 그 규모를 보지 않는다.
    def observations(self, *, domain: str) -> tuple[tuple, ...]:
        """후보별 누적 관측. `(key, surface, status, keyword_id, 문서·일수·소스·저자)`.

        **별칭을 접지 않은 원표기 단위다.** 층 1·2 의 판정(DF 압도·편집 거리)이 표기별
        빈도를 보기 때문이다 — 접은 값으로 보면 이미 합쳐진 것끼리 다시 비교하게 된다.
        """
        return self._query(OBSERVATION_SQL, (domain, domain))

    def group_observations(self, *, domain: str) -> tuple[tuple, ...]:
        """대표별 누적 관측 — **별칭을 접은 뒤**. 승격 심사가 이것을 본다 ([05 §5])."""
        return self._query(GROUP_OBSERVATION_SQL, (domain,))

    def abbreviation_evidence(self, *, domain: str) -> tuple[tuple, ...]:
        """`전개형 (약어)` 관측을 쌍 단위로 접은 것 ([05 §3])."""
        return self._query(ABBREVIATION_EVIDENCE_SQL, (domain,))

    def aliases(self, *, domain: str) -> tuple[tuple, ...]:
        """이미 있는 별칭 전부. **`registry/alias.resolve` 에 쌍으로 되먹인다** — 그래야
        사슬이 생기지 않는다 (`ALIAS_MERGE_SQL` 의 주석).

        **`signal` 을 함께 읽는 것이 중요하다.** 되먹인 쌍이 다시 기록될 때 원래 근거를
        잃으면, 처음 병합한 이유가 `pl_alias` 에서 지워진다 ([05 §8] "근거를 남긴다")."""
        return self._query(
            f"SELECT alias_key, canonical_key, layer, rule, confidence, signal::text "
            f"FROM {ALIAS} WHERE domain = %s",
            (domain,),
        )

    def _query(self, statement: str, params: tuple) -> tuple[tuple, ...]:
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute(statement, params)
            return tuple(cur.fetchall())


class KeywordSink:
    """서비스 표 둘. **UNIQUE 가 없으면 승격하지 않는다** (모듈 docstring)."""

    def __init__(self, config: Config) -> None:
        self._config = config

    def service_tables_ready(self) -> bool:
        """`keywords` 와 `keyword_contents` 가 실제로 있는지. 없으면 만들지 않는다 ([08 §1])."""
        return self._boolean(SERVICE_TABLES_SQL)

    def unique_constraint_ready(self) -> bool:
        """`keywords (domain, normalized_name)` UNIQUE 가 있는지.

        **없으면 승격을 건너뛴다.** 없는 채로 INSERT 하면 되돌릴 수 없는 중복이 쌓이고,
        그 청소는 `keyword_contents` · `member_interest_keywords` · `trends` 가 서로 다른
        `id` 를 가리키는 상태에서 사람이 판별할 수 없다 ([05 §5]).
        """
        return self._boolean(UNIQUE_CONSTRAINT_SQL)

    def promote(self, rows: Sequence[tuple]) -> int:
        """승격 — `keywords` upsert 후 `RETURNING id` 를 `pl_keyword_id_map` 에 담는다.

        **되돌릴 수 없는 지점이다** ([05 §1]). 여기까지 온 행은 `registry/promote.judge` 를
        전부 통과한 것이다.
        """
        if not rows:
            return 0
        return _stage_rows(
            self._config,
            table=STAGE_KEYWORDS,
            columns=KEYWORD_COLUMNS,
            rows=rows,
            merge_sql=PROMOTE_SQL,
        )

    def id_map(self, *, domain: str) -> dict[str, int]:
        """`비교키 → keywords.id`. 승격 뒤 그 값이 실제로 발급됐는지 보는 데 쓴다."""
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT normalized_key, keyword_id FROM {KEYWORD_ID_MAP} WHERE domain = %s",
                (domain,),
            )
            return {row[0]: int(row[1]) for row in cur.fetchall()}

    def stage_and_link_contents(self, *, domain: str, extract_run_id: str) -> int:
        """이번 실행이 처리한 문서의 `selected` 후보로 `keyword_contents` 를 채운다.

        **드라이버를 왕복하지 않는다** — 행이 이미 `pl_document_candidate` 에 있다. 한
        연결, 한 트랜잭션으로 스테이징 적재부터 서비스 표 갱신까지 간다 ([08 §4]).

        돌려주는 것은 **실제로 걸린 연결 수**다. 스테이징 행 수보다 적을 수 있다 — 승격되지
        않은 후보와 `contents` 에 없는 문서가 조인에서 떨어지기 때문이고, 그 차이가 곧
        "관련 콘텐츠가 비어 있다" 의 원인이라 통계로 남긴다.
        """
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute(f"TRUNCATE {STAGE_KEYWORD_CONTENT}")
            cur.execute(STAGE_KEYWORD_CONTENT_SQL, (domain, extract_run_id))
            staged = cur.rowcount
            if not staged:
                return 0
            cur.execute(LINK_CONTENTS_SQL)
            cur.execute("SELECT count(*) FROM _keyword_content")
            linked = int((cur.fetchone() or (0,))[0])
        log.info("[%s] keyword_contents: 스테이징 %d → 연결 %d", domain, staged, linked)
        return linked

    def linked_count(self) -> int:
        """`keyword_contents` 전체 행 수. 종단 검증과 통계에 쓴다."""
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) FROM {KEYWORD_CONTENTS}")
            return int((cur.fetchone() or (0,))[0])

    def _boolean(self, statement: str) -> bool:
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute(statement)
            row = cur.fetchone()
        return bool(row and row[0])


def _stage_rows(
    config: Config,
    *,
    table: str,
    columns: Iterable[str],
    rows: Sequence[tuple],
    merge_sql: str,
) -> int:
    """스테이징에 넣고 병합한다 — 한 연결, 한 트랜잭션 ([08 §4]).

    `io/jdbc.stage_and_merge` 와 같은 일을 하지만 DataFrame 이 아니라 튜플 목록을 받는다.
    [05] 의 산출물은 순수 파이썬(`registry/*.py`)에서 나오므로 Spark 프레임을 거칠 이유가
    없다 — 거치면 스키마를 두 번 적게 된다.
    """
    from psycopg2.extras import execute_values

    names = ", ".join(columns)
    page = int(config.get("jdbc.batch_size", jdbc.DEFAULT_BATCH_SIZE))
    with jdbc.connection(config) as conn, conn.cursor() as cur:
        cur.execute(f"TRUNCATE {table}")
        execute_values(cur, f"INSERT INTO {table} ({names}) VALUES %s", list(rows), page_size=page)
        cur.execute(merge_sql)
    return len(rows)
