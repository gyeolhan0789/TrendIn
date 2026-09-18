"""`extract` 의 내부 테이블 넷 ([08 §3](../../../../spark/docs/08-storage-schema.md)).

| 테이블 | 담는 것 | 쓰는 법 |
| --- | --- | --- |
| `pl_document_candidate` | 문서 × 후보 점수 ([04 §7]) | 처리한 문서의 옛 행을 지우고 다시 넣는다 |
| `pl_candidate` | 후보 마스터. 대표 표기 · **최초 관측일** · 승격 상태 | upsert (`LEAST`) |
| `pl_keyword_daily_stat` | 일별 원자료 — **집계의 원본** | 영향받은 날짜를 다시 센다 |
| `pl_abbreviation_observation` | `전개형 (약어)` 관측 — [05 §3] 의 결정적 증거 | upsert |
| `pl_alias` | 별칭 → 대표. **[05] 가 채우고 여기서는 읽는다** | 아래 `ALIAS` 주석 |

**서비스 테이블을 전혀 건드리지 않는다** ([08 §1], [10 §4] S4 마지막 조건). 전부 `pl_` 이고
DDL 은 우리 것이다.

**한 트랜잭션이다.** 문서 후보를 지우고 넣는 것과 일별 원자료를 다시 세는 것이 서로 다른
커밋이면, 그 사이에 죽었을 때 원자료가 지워진 문서를 세고 있게 된다. 스테이징 셋을 같은
연결에서 채우고 MERGE 까지 간다 ([08 §4], `io/jdbc.stage_and_merge` 와 같은 이유).

**일별 원자료는 저장된 문서 후보에서 다시 센다.** 한 `stat_date` 의 문서가 여러 `ingest_run_id`
에 흩어져 오므로(발행이 늦은 문서, [07 §2]) 이번 배치의 행만으로는 그 날의 값을 알 수 없다.
영향받은 날짜를 모아 `pl_document_candidate` 전체에서 다시 세고, 그 날짜에서 사라진 후보의
행은 지운다. `keyword_id` 는 [05] 가 승격할 때 채우는 칸이라 갱신에서 건드리지 않는다.

**세는 단위는 대표 비교키다** ([05 §8]). `pl_alias` 를 거쳐 별칭을 대표로 접은 뒤 문서를
센다 — 접지 않으면 병합된 두 표기가 함께 나온 문서를 두 번 세게 되고, 그러면 병합 시점에
없던 급증이 생긴다. 이 재집계가 `DAILY_STAT_RECOUNT` 한 곳에 있고 [05] 도 그것을 부른다.

**후보의 `doc_count` 는 필터를 통과한 전부를 센다** — 상위 K 만이 아니다. [04 §7] 이 내부
통계에는 "필터를 통과한 전부" 를 남기라고 했고, 승격 심사([05 §5])는 그 누적 관측을 본다.
`selected` 가 상위 K 표시라 `keyword_contents`([05]) 와 동시출현([06]) 은 그것으로 좁힌다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from trendin.spark.common.config import Config
from trendin.spark.common.countries import UNKNOWN_COUNTRY
from trendin.spark.common.logging import get_logger
from trendin.spark.io import jdbc

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

log = get_logger(__name__)

DOCUMENT_CANDIDATE = "pl_document_candidate"
CANDIDATE = "pl_candidate"
DAILY_STAT = "pl_keyword_daily_stat"
ABBREVIATION = "pl_abbreviation_observation"

# **[05] 가 채우고 여기서는 읽는다** (`registry/`, `io/keywords.py`). 그래도 DDL 이 이 모듈에
# 있는 이유는 아래 일별 원자료 재집계가 이 표 없이는 성립하지 않기 때문이다 — 병합된 두 표기의
# 언급량을 행 단위로 더하면 같은 문서를 두 번 세게 되고([05 §8]), 그걸 막는 조인이 이 표다.
# 소유가 갈리는 자리라 [08 §3] 의 모듈 표에 그렇게 적어 뒀다.
ALIAS = "pl_alias"

STAGE_DOCUMENT_CANDIDATE = "pl_stage_document_candidate"
# 이번에 처리한 문서 전부 — 후보가 0 개인 문서도. 그 문서의 옛 행을 지우는 근거다.
STAGE_EXTRACTED_DOCUMENT = "pl_stage_extracted_document"
STAGE_ABBREVIATION = "pl_stage_abbreviation_observation"

# 후보 상태. 승격([05 §5])이 바꾼다.
STATUS_CANDIDATE = "CANDIDATE"

DOCUMENT_CANDIDATE_COLUMNS = (
    "domain",
    "url_hash",
    "normalized_key",
    "surface",
    "kind",
    "ntokens",
    "tf",
    "tf_title",
    "in_title",
    "is_latin",
    "is_proper",
    "df",
    "c_value",
    "bm25",
    "score",
    "rank",
    "selected",
    "stat_date",
    "source_id",
    "source_country",
    "author",
    "is_dup",
    "ingest_run_id",
    "extract_run_id",
    "extracted_at",
)

EXTRACTED_DOCUMENT_COLUMNS = ("domain", "url_hash")

ABBREVIATION_COLUMNS = (
    "domain",
    "url_hash",
    "abbreviation_key",
    "expansion_key",
    "abbreviation",
    "expansion",
    "initials_match",
    "source_id",
    "stat_date",
    "extract_run_id",
    "observed_at",
)

DDL = f"""
CREATE TABLE IF NOT EXISTS {DOCUMENT_CANDIDATE} (
    domain          text        NOT NULL,
    url_hash        bytea       NOT NULL,
    normalized_key  text        NOT NULL,
    -- 코퍼스 대표 표기 ([04 §4]). 문서 안 표기가 아니다.
    surface         text        NOT NULL,
    -- **실체 유형** — `브랜드` · `인물` · `의류 품목` 같은 모델 라벨 (2026-09-16).
    -- 옛 경로에서는 토큰 종류(`TERM` · `NGRAM` · `HASHTAG`)였고, 그 값을 만들던 토크나이저가
    -- 없어졌다. 칸을 새로 만들지 않은 이유는 둘 다 "후보의 종류" 이고 쓰는 곳이 같기 때문이다.
    --
    -- ⚠️ **병합 키나 승격 조건에 쓰지 않는다.** 정답과 맞은 후보 기준으로 유형 정확도가
    -- 77.6% 이고 `켄달 제너` 가 브랜드로 붙는다 (`scratchpad/kwlab/RANKED.md` §6.1).
    -- 화면의 유형 필터와 유형별 순위표가 쓰는 값이다.
    kind            text        NOT NULL,
    -- 대표 표기의 공백 기준 토큰 수.
    ntokens         integer     NOT NULL,
    tf              integer     NOT NULL,
    tf_title        integer     NOT NULL,
    in_title        boolean     NOT NULL,
    -- 표기에 라틴 문자가 섞였나 · 모델이 고유명사 유형으로 보았나. **점수 축이 아니라
    -- 기록이다** (2026-09-16) — 옛 경로에서는 가중치를 갖는 축이었고, 지금은 점수가 모델에서
    -- 오므로 화면 필터와 분석에만 쓴다.
    is_latin        boolean     NOT NULL DEFAULT false,
    is_proper       boolean     NOT NULL DEFAULT false,
    -- **이번 배치에서 본 문서 빈도** (2026-09-16 에 뜻이 바뀌었다). 옛 경로는 최근 N 일
    -- 코퍼스에서 셌는데, 점수를 모델이 주면서 코퍼스 통계가 선별에 관여하지 않게 되어
    -- 대상 문서만 처리한다 (`extract/batch.py` 의 주석). 배치 크기에 따라 흔들린다.
    df              integer     NOT NULL,
    -- **항상 0 이다.** C-value 가 없어졌고(구간을 모델이 준다) 칸만 남겨 두었다.
    c_value         double precision NOT NULL,
    -- 기록용. **점수에 들어가지 않는다** (`extract/scoring.py` 의 주석).
    bm25            double precision NOT NULL,
    -- 0~1. **모델이 준 확률에 문서 안 반복 가산**을 얹은 값이다 ([04 §6]).
    score           double precision NOT NULL,
    rank            integer     NOT NULL,
    -- 상위 K 이고 하한 이상 ([04 §7]). keyword_contents 로 나갈 것.
    selected        boolean     NOT NULL,
    -- 발행 기준 KST 날짜 ([07 §2]). 일별 원자료의 축이다.
    stat_date       date        NOT NULL,
    source_id       text,
    -- **발행 매체의 나라** (`common/countries.py`). `curated.source_country` 를 그대로 받는다.
    -- 여기서 `NOT NULL` 인 이유는 아래 일별 재집계가 이 칸으로 묶고 그 결과가 기본키에
    -- 들어가기 때문이다 — 판정할 수 없으면 `NULL` 이 아니라 `XX` 다.
    source_country  text        NOT NULL DEFAULT '{UNKNOWN_COUNTRY}',
    author          text,
    -- `dup_of` 가 있는 근사 중복 문서. 언급량에서 빼고 `doc_count_with_dup` 에만 센다.
    is_dup          boolean     NOT NULL,
    ingest_run_id   text,
    extract_run_id  text        NOT NULL,
    extracted_at    timestamptz NOT NULL,
    PRIMARY KEY (domain, url_hash, normalized_key)
);
-- 일별 원자료 재계산이 (domain, stat_date) 로 훑는다.
CREATE INDEX IF NOT EXISTS pl_document_candidate_date_idx
    ON {DOCUMENT_CANDIDATE} (domain, stat_date);
-- [05] 가 후보 하나의 관측을 모을 때.
CREATE INDEX IF NOT EXISTS pl_document_candidate_key_idx
    ON {DOCUMENT_CANDIDATE} (domain, normalized_key);

CREATE TABLE IF NOT EXISTS {CANDIDATE} (
    domain          text        NOT NULL,
    normalized_key  text        NOT NULL,
    surface         text        NOT NULL,
    -- 실체 유형. 위 `pl_document_candidate.kind` 와 같은 값이다.
    kind            text        NOT NULL,
    ntokens         integer     NOT NULL,
    -- 최초·최근 관측일 — 발행일 기준. 서비스 테이블로 옮기지 않는다 ([05 §5], [08 §3]).
    first_seen_date date        NOT NULL,
    last_seen_date  date        NOT NULL,
    status          text        NOT NULL DEFAULT '{STATUS_CANDIDATE}',
    -- 승격 뒤 [05] 가 채운다. NULL 이면 아직 후보다.
    keyword_id      bigint,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (domain, normalized_key)
);

CREATE TABLE IF NOT EXISTS {DAILY_STAT} (
    domain             text    NOT NULL,
    normalized_key     text    NOT NULL,
    stat_date          date    NOT NULL,
    -- **발행 매체의 나라이고 기본키의 넷째 칸이다** (`common/countries.py`).
    --
    -- 국가는 행을 곱하는 축이 아니라 **쪼개는** 축이다 — 문서 하나는 나라 하나에 속하므로
    -- `doc_count` 를 전 국가에 걸쳐 더하면 국가 칸이 없던 때와 같은 값이 된다. 그래서 이 표를
    -- 읽는 집계 질의는 이미 `sum` 과 `GROUP BY` 로 접고 있어 그대로 돈다
    -- (`io/metrics.DAILY_SQL` · `DAILY_VOLUME_SQL` · `COVERED_DATES_SQL`).
    --
    -- ⚠️ **아래 세 칸의 뜻이 함께 좁아졌다.** `source_count` · `author_count` ·
    -- `occurrence_count` 가 "그 날짜 그 키워드" 에서 "그 날짜 그 키워드 **그 나라**" 가 된다.
    -- 지금 그 칸을 읽는 코드는 없다 — 승격 심사는 `pl_document_candidate` 를 직접 세고
    -- (`io/keywords.OBSERVATION_SQL`), 구간 소스 수도 그 표에서 온다
    -- (`io/metrics.PERIOD_SOURCES_SQL`). 나중에 읽게 되면 국가를 먼저 접어야 한다.
    source_country     text    NOT NULL DEFAULT '{UNKNOWN_COUNTRY}',
    -- 승격 후 채운다. NULL 이면 아직 후보 ([08 §3]).
    keyword_id         bigint,
    -- 언급량. 근사 중복 제외. 서비스로 나가는 유일한 값.
    doc_count          integer NOT NULL,
    -- 출현 수 합. 이상 탐지 ([07 §8]).
    occurrence_count   integer NOT NULL,
    source_count       integer NOT NULL,
    -- 봇 방어의 핵심 ([05 §5]).
    author_count       integer NOT NULL,
    -- 크로스포스트 영향 측정.
    doc_count_with_dup integer NOT NULL,
    updated_at         timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (domain, normalized_key, stat_date, source_country)
);
-- [07] 의 기간 집계가 (domain, stat_date) 범위로 읽는다.
CREATE INDEX IF NOT EXISTS pl_keyword_daily_stat_date_idx ON {DAILY_STAT} (domain, stat_date);

CREATE TABLE IF NOT EXISTS {ABBREVIATION} (
    domain           text        NOT NULL,
    url_hash         bytea       NOT NULL,
    abbreviation_key text        NOT NULL,
    expansion_key    text        NOT NULL,
    abbreviation     text        NOT NULL,
    expansion        text        NOT NULL,
    -- 약어 글자와 전개형 첫 글자의 대응 ([05 §3]). 한국어 전개형은 false.
    initials_match   boolean     NOT NULL,
    source_id        text,
    stat_date        date,
    extract_run_id   text        NOT NULL,
    observed_at      timestamptz NOT NULL,
    PRIMARY KEY (domain, url_hash, abbreviation_key, expansion_key)
);

-- 별칭 → 대표 ([05 §3]). 채우는 것은 `io/keywords.py` 이고 여기서는 재집계가 읽는다.
-- `alias_key` 가 PK 인 것이 요점이다 — 한 표기가 두 대표를 가리키면 재집계가 같은 문서를
-- 두 대표에 각각 세고, 그게 [05 §8] 이 막으려는 이중 계수다.
CREATE TABLE IF NOT EXISTS {ALIAS} (
    domain        text        NOT NULL,
    alias_key     text        NOT NULL,
    canonical_key text        NOT NULL,
    -- 근거 층 ([05 §2]·[05 §3]) 과 규칙 이름. 1=결정적 · 2=통계 증거 · 3=검수 승인.
    layer         integer     NOT NULL,
    rule          text        NOT NULL,
    confidence    double precision NOT NULL,
    signal        jsonb,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (domain, alias_key),
    -- 자기 자신을 가리키는 별칭은 대표를 지운다. 방어로 둔다.
    CHECK (alias_key <> canonical_key)
);
-- 재집계가 `alias_key` 로 조인하고, 승격 심사가 대표별로 별칭을 모은다.
CREATE INDEX IF NOT EXISTS pl_alias_canonical_idx ON {ALIAS} (domain, canonical_key);

-- 스테이징은 제약이 없다. 순수 INSERT 를 빠르게 받고 MERGE 뒤 비운다.
-- 이미 있는 표에 칸을 더한다. `CREATE TABLE IF NOT EXISTS` 는 옛 표를 고치지 않으므로
-- 컬럼을 더할 때는 이 줄이 필요하다 (2026-09-10 고유명사 축).
ALTER TABLE {DOCUMENT_CANDIDATE} ADD COLUMN IF NOT EXISTS is_latin boolean NOT NULL DEFAULT false;
ALTER TABLE {DOCUMENT_CANDIDATE} ADD COLUMN IF NOT EXISTS is_proper boolean NOT NULL DEFAULT false;
-- 국가 축 (2026-09-18). 옛 행은 `XX` 로 남는다 — 재추출이 실제 나라를 채운다.
ALTER TABLE {DOCUMENT_CANDIDATE}
    ADD COLUMN IF NOT EXISTS source_country text NOT NULL DEFAULT '{UNKNOWN_COUNTRY}';
ALTER TABLE {DAILY_STAT}
    ADD COLUMN IF NOT EXISTS source_country text NOT NULL DEFAULT '{UNKNOWN_COUNTRY}';

-- 일별 원자료의 기본키를 국가까지 넓힌다. `ADD COLUMN` 은 기본키를 바꾸지 않으므로 이미
-- 있는 표에서는 이 블록이 필요하다.
--
-- **칸 수로 판별한다.** 옛 기본키는 세 칸(`domain` · `normalized_key` · `stat_date`)이고 새
-- 것은 네 칸이라, 세 칸일 때만 갈아 끼우면 두 번 돌려도 안전하다. 이름을 조회해 지우는
-- 이유는 기본키 이름이 표를 만든 경로에 따라 다를 수 있기 때문이다.
--
-- 옛 행은 `source_country` 가 전부 `XX` 라 넷째 칸을 더해도 충돌하지 않는다. 세 칸으로
-- 유일했던 것이 네 칸으로도 유일하다.
DO $ddl$
DECLARE
    pk_name text;
    pk_width integer;
BEGIN
    SELECT con.conname, array_length(con.conkey, 1)
      INTO pk_name, pk_width
      FROM pg_constraint con
      JOIN pg_class c ON c.oid = con.conrelid
     WHERE c.relname = '{DAILY_STAT}' AND con.contype = 'p';

    IF pk_name IS NOT NULL AND pk_width = 3 THEN
        EXECUTE format('ALTER TABLE {DAILY_STAT} DROP CONSTRAINT %I', pk_name);
        EXECUTE 'ALTER TABLE {DAILY_STAT}'
             || ' ADD PRIMARY KEY (domain, normalized_key, stat_date, source_country)';
    END IF;
END
$ddl$;

-- 스테이징은 본표를 베끼므로 위 ALTER 뒤에 만들어야 칸이 맞는다. 이미 있으면 함께 고친다.
CREATE TABLE IF NOT EXISTS {STAGE_DOCUMENT_CANDIDATE} (LIKE {DOCUMENT_CANDIDATE});
ALTER TABLE {STAGE_DOCUMENT_CANDIDATE}
    ADD COLUMN IF NOT EXISTS is_latin boolean NOT NULL DEFAULT false;
ALTER TABLE {STAGE_DOCUMENT_CANDIDATE}
    ADD COLUMN IF NOT EXISTS is_proper boolean NOT NULL DEFAULT false;
ALTER TABLE {STAGE_DOCUMENT_CANDIDATE}
    ADD COLUMN IF NOT EXISTS source_country text NOT NULL DEFAULT '{UNKNOWN_COUNTRY}';
CREATE TABLE IF NOT EXISTS {STAGE_EXTRACTED_DOCUMENT} (
    domain   text  NOT NULL,
    url_hash bytea NOT NULL
);
CREATE TABLE IF NOT EXISTS {STAGE_ABBREVIATION} (LIKE {ABBREVIATION});
"""

_DC = ", ".join(DOCUMENT_CANDIDATE_COLUMNS)
_AB = ", ".join(ABBREVIATION_COLUMNS)

# 대표 비교키. 별칭이 없으면 자기 자신이다 — `LEFT JOIN` 이라 [05] 가 아직 아무것도 채우지
# 않은 상태에서도 옛 동작과 같다.
_CANONICAL = "coalesce(al.canonical_key, d.normalized_key)"

# 일별 원자료를 **저장된 문서 후보 전체에서** 다시 세는 두 문장. `_affected_date`
# (`(domain, stat_date)`) 임시 테이블이 이미 있다고 전제한다.
#
# **부르는 곳이 둘이다.** 아래 `MERGE_SQL`([04] — 문서를 새로 처리했을 때)과
# `io/keywords.RegistrySink.apply_aliases`([05] — 병합이 새로 생겼을 때). 정의가 두 곳이 되면 한쪽만
# 고쳐져 같은 날짜의 값이 부른 사람에 따라 달라진다.
#
# **별칭을 대표로 접어 센다** ([05 §8]). 병합된 두 표기의 언급량을 행 단위로 더하면 두 표기가
# 함께 나온 문서를 두 번 세는데, `count(DISTINCT url_hash)` 를 대표로 묶으면 그 문서가 1 이
# 된다 — 원자료에서 다시 세는 것이 이관보다 맞는 이유가 이것이다.
#
# 뒤의 `DELETE` 가 **별칭 행을 걷어낸다.** 병합 뒤 별칭은 어느 대표 키로도 나오지 않으므로
# `NOT EXISTS` 에 걸려 사라지고, 관측은 `pl_document_candidate` 에 그대로 남는다.
#
# **국가로도 묶는다** (2026-09-18). 한 키워드가 같은 날 두 나라에서 언급되면 행이 둘이고,
# `doc_count` 를 전 국가에 걸쳐 더한 값은 국가 칸이 없던 때와 같다. `DELETE` 의 `NOT EXISTS`
# 에 국가 조건이 함께 있어야 하는데, 없으면 어느 한 나라에서라도 그 키가 나오는 동안 다른
# 나라의 낡은 행이 영구히 남는다 — 소스가 빠진 나라의 언급량이 화면에서 굳는 증상이 된다.
DAILY_STAT_RECOUNT = f"""
INSERT INTO {DAILY_STAT}
    (domain, normalized_key, stat_date, source_country, doc_count, occurrence_count, source_count,
     author_count, doc_count_with_dup, updated_at)
SELECT d.domain, {_CANONICAL}, d.stat_date, d.source_country,
       count(DISTINCT d.url_hash) FILTER (WHERE NOT d.is_dup),
       coalesce(sum(d.tf), 0),
       count(DISTINCT d.source_id) FILTER (WHERE NOT d.is_dup),
       count(DISTINCT d.author)
           FILTER (WHERE NOT d.is_dup AND d.author IS NOT NULL AND d.author <> ''),
       count(DISTINCT d.url_hash),
       now()
  FROM {DOCUMENT_CANDIDATE} d
  JOIN _affected_date a ON a.domain = d.domain AND a.stat_date = d.stat_date
  LEFT JOIN {ALIAS} al ON al.domain = d.domain AND al.alias_key = d.normalized_key
 GROUP BY d.domain, {_CANONICAL}, d.stat_date, d.source_country
ON CONFLICT (domain, normalized_key, stat_date, source_country) DO UPDATE SET
    doc_count          = EXCLUDED.doc_count,
    occurrence_count   = EXCLUDED.occurrence_count,
    source_count       = EXCLUDED.source_count,
    author_count       = EXCLUDED.author_count,
    doc_count_with_dup = EXCLUDED.doc_count_with_dup,
    updated_at         = EXCLUDED.updated_at;

DELETE FROM {DAILY_STAT} s
 USING _affected_date a
 WHERE s.domain = a.domain AND s.stat_date = a.stat_date
   AND NOT EXISTS (
        SELECT 1 FROM {DOCUMENT_CANDIDATE} d
         LEFT JOIN {ALIAS} al ON al.domain = d.domain AND al.alias_key = d.normalized_key
         WHERE d.domain = s.domain AND d.stat_date = s.stat_date
           AND {_CANONICAL} = s.normalized_key
           AND d.source_country = s.source_country
   );
"""

# 순서가 중요하다.
#   1. 영향받는 (domain, stat_date) 를 **지우기 전에** 모은다 — 지운 뒤에는 옛 날짜를 알 수 없다.
#   2. 처리한 문서의 옛 후보 행을 지운다 (후보가 0 개가 된 문서도 포함).
#   3. 새 후보 행을 넣는다.
#   4. 후보 마스터 upsert. 최초 관측일은 LEAST 로 지킨다 — 재실행이 앞당기지도 늦추지도 않는다.
#   5·6. 영향받은 날짜의 일별 원자료를 다시 센다 (`DAILY_STAT_RECOUNT`). keyword_id 는
#        건드리지 않는다 — [05] 가 승격할 때 채우는 칸이다.
#   7. 약어 관측 upsert.
MERGE_SQL = f"""
CREATE TEMP TABLE _affected_date ON COMMIT DROP AS
SELECT DISTINCT d.domain, d.stat_date
  FROM {DOCUMENT_CANDIDATE} d
  JOIN {STAGE_EXTRACTED_DOCUMENT} s ON s.domain = d.domain AND s.url_hash = d.url_hash
UNION
SELECT DISTINCT domain, stat_date FROM {STAGE_DOCUMENT_CANDIDATE};

DELETE FROM {DOCUMENT_CANDIDATE} d
 USING {STAGE_EXTRACTED_DOCUMENT} s
 WHERE s.domain = d.domain AND s.url_hash = d.url_hash;

INSERT INTO {DOCUMENT_CANDIDATE} ({_DC})
SELECT DISTINCT ON (domain, url_hash, normalized_key) {_DC}
  FROM {STAGE_DOCUMENT_CANDIDATE}
 ORDER BY domain, url_hash, normalized_key, extracted_at DESC;

INSERT INTO {CANDIDATE}
    (domain, normalized_key, surface, kind, ntokens, first_seen_date, last_seen_date, status)
SELECT domain, normalized_key,
       -- 스테이징의 surface 는 코퍼스 대표 표기라 행마다 같다. 혹시 갈리면 결정적으로 하나.
       min(surface), min(kind), min(ntokens), min(stat_date), max(stat_date), '{STATUS_CANDIDATE}'
  FROM {STAGE_DOCUMENT_CANDIDATE}
 GROUP BY domain, normalized_key
ON CONFLICT (domain, normalized_key) DO UPDATE SET
    surface         = EXCLUDED.surface,
    kind            = EXCLUDED.kind,
    ntokens         = EXCLUDED.ntokens,
    first_seen_date = LEAST({CANDIDATE}.first_seen_date, EXCLUDED.first_seen_date),
    last_seen_date  = GREATEST({CANDIDATE}.last_seen_date, EXCLUDED.last_seen_date),
    updated_at      = now();

{DAILY_STAT_RECOUNT}

INSERT INTO {ABBREVIATION} ({_AB})
SELECT DISTINCT ON (domain, url_hash, abbreviation_key, expansion_key) {_AB}
  FROM {STAGE_ABBREVIATION}
 ORDER BY domain, url_hash, abbreviation_key, expansion_key, observed_at DESC
ON CONFLICT (domain, url_hash, abbreviation_key, expansion_key) DO UPDATE SET
    abbreviation   = EXCLUDED.abbreviation,
    expansion      = EXCLUDED.expansion,
    initials_match = EXCLUDED.initials_match,
    extract_run_id = EXCLUDED.extract_run_id,
    observed_at    = EXCLUDED.observed_at;

TRUNCATE {STAGE_DOCUMENT_CANDIDATE}, {STAGE_EXTRACTED_DOCUMENT}, {STAGE_ABBREVIATION};
"""


@dataclass(frozen=True, slots=True)
class WriteResult:
    documents: int
    document_candidates: int
    abbreviations: int


class CandidateSink:
    """네 표 한 곳. 배선을 갈아 끼우면 층 2 테스트가 진짜 DB 없이 돈다 ([09 §4])."""

    def __init__(self, config: Config) -> None:
        self._config = config

    def ensure_schema(self) -> None:
        """`pl_*` 는 우리가 만든다. 멱등."""
        jdbc.execute(self._config, DDL)
        log.info(
            "후보 스키마 확인: %s · %s · %s · %s",
            DOCUMENT_CANDIDATE,
            CANDIDATE,
            DAILY_STAT,
            ABBREVIATION,
        )

    def known_keys(self, spark: Any, *, domain: str) -> "DataFrame":
        """이미 관측된 후보의 비교키. [04 §9] "신규 후보 유입률" 의 분모다."""
        query = f"SELECT normalized_key FROM {CANDIDATE} WHERE domain = '{_safe(domain)}'"
        return jdbc.read_table(spark, query, self._config)

    def write(
        self,
        *,
        documents: "DataFrame",
        document_candidates: "DataFrame",
        abbreviations: "DataFrame",
    ) -> WriteResult:
        """세 스테이징을 채우고 MERGE 까지 **한 연결, 한 트랜잭션.**

        문서가 하나도 없으면 아무것도 하지 않는다 — 연결도 열지 않는다. 문서는 있는데 후보가
        없으면(전부 필터에 걸렸다) 옛 행을 지우고 원자료를 다시 세는 것까지는 한다.
        """
        from psycopg2.extras import execute_values

        docs = jdbc.sql_rows(documents, EXTRACTED_DOCUMENT_COLUMNS)
        if not docs:
            return WriteResult(0, 0, 0)
        rows = jdbc.sql_rows(document_candidates, DOCUMENT_CANDIDATE_COLUMNS)
        pairs = jdbc.sql_rows(abbreviations, ABBREVIATION_COLUMNS)
        page = int(self._config.get("jdbc.batch_size", jdbc.DEFAULT_BATCH_SIZE))

        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute(
                f"TRUNCATE {STAGE_DOCUMENT_CANDIDATE}, {STAGE_EXTRACTED_DOCUMENT}, "
                f"{STAGE_ABBREVIATION}"
            )
            execute_values(
                cur,
                f"INSERT INTO {STAGE_EXTRACTED_DOCUMENT} "
                f"({', '.join(EXTRACTED_DOCUMENT_COLUMNS)}) VALUES %s",
                docs,
                page_size=page,
            )
            if rows:
                execute_values(
                    cur,
                    f"INSERT INTO {STAGE_DOCUMENT_CANDIDATE} ({_DC}) VALUES %s",
                    rows,
                    page_size=page,
                )
            if pairs:
                execute_values(
                    cur,
                    f"INSERT INTO {STAGE_ABBREVIATION} ({_AB}) VALUES %s",
                    pairs,
                    page_size=page,
                )
            cur.execute(MERGE_SQL)
        log.info("후보 적재: 문서 %d · 문서후보 %d · 약어 %d", len(docs), len(rows), len(pairs))
        return WriteResult(len(docs), len(rows), len(pairs))


def _safe(domain: str) -> str:
    if not domain.replace("_", "").isalnum():
        raise ValueError(f"도메인 값에 쓸 수 없는 문자가 있다: {domain!r}")
    return domain
