"""개념 층의 적재와 조회 — 서비스 표 셋을 읽고 쓰고, `pl_` 작업 표를 소유한다.

| 표 | 소유 | 여기서 |
| --- | --- | --- |
| `pl_concept` · `pl_concept_expression` | 우리 | 사전. 쓰기는 `seed.py` 와 검수 명령만 |
| `pl_article_concept` | 우리 | 기사별 개념. 스테이징 → 한 트랜잭션 병합 |
| `pl_unmapped_*` (expression · article · context) | 우리 | 미등록 표현 · 기사 집합 · 문맥 표본 |
| `pl_mapping_decision` · `pl_dictionary_version` | 우리 | 결정 이력 · 사전 버전. 검수 명령이 쓴다 |
| `pl_concept_judgement_cache` | 우리 | LLM 판정 캐시. 다음 단계가 쓴다 |

## 서비스 표는 만들지 않는다

개념 표 넷도 서비스 표가 아니다. 스프링이 읽지 않으므로 Flyway 를 거칠 이유가 없고, 거치면 백엔드
배포와 엮이기만 한다 (2026-09-17 결정). 화면이 개념을 읽게 되는 날 승격한다 — `contents` 가 걸어온
길이다. 그때까지 `contents` 에는 FK 없이 논리적 참조만 둔다 (`pl_` 규약).

## 미등록의 기사 집합을 전부 남기는 이유

문맥 표본은 20건까지만 두지만 `pl_unmapped_article` 은 (표현, 기사) 쌍을 **전부** 든다. 이게
두 가지를 준다 — `article_count` 를 어림하지 않고 세는 근거, 그리고 이 표현이 나중에 개념에
붙었을 때 **다시 처리할 기사가 정확히 어느 것들인지.** 정수 두 개짜리 행이라 싸다.

## 재처리에서 없어진 행은 지운다

같은 기사를 다시 붙였는데 사전이 바뀌어 어떤 개념이 더는 안 붙으면, 옛 `article_concept` 행이
남아 있으면 안 된다. 그래서 이번에 **처리한 기사 전부**를 스테이징에 따로 실어, 그 기사의 행 중
이번 결과에 없는 것을 지운다. upsert 만 하면 개념이 붙을 때만 고쳐지고 떨어질 때는 안 고쳐진다.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from trendin.spark.common.config import Config
from trendin.spark.common.logging import get_logger
from trendin.spark.concept.dictionary import Concept, Dictionary, Expression
from trendin.spark.concept.mapping import ConceptRow, Keyword, Unmapped
from trendin.spark.io import jdbc

log = get_logger(__name__)

# 개념 표 넷 — 우리 표다 (아래 DDL).
CATEGORY = "pl_concept_category"
CONCEPT = "pl_concept"
EXPRESSION = "pl_concept_expression"
ARTICLE_CONCEPT = "pl_article_concept"
# 우리 표.
UNMAPPED = "pl_unmapped_expression"
UNMAPPED_ARTICLE = "pl_unmapped_article"
UNMAPPED_CONTEXT = "pl_unmapped_context"
DECISION = "pl_mapping_decision"
VERSION = "pl_dictionary_version"
JUDGEMENT_CACHE = "pl_concept_judgement_cache"
# 자동 판정이 사전·순위에 한 일의 원장. 회차(`run_id`) 단위로 되돌리는 근거다
# (`concept/rollback.py`).
CHANGE = "pl_concept_change"
STAGE_ARTICLE_CONCEPT = "pl_stage_article_concept"
STAGE_PROCESSED = "pl_stage_article_processed"
STAGE_UNMAPPED = "pl_stage_unmapped"

STATUS_PENDING = "PENDING"

DDL = f"""
-- 개념 표 넷. 스프링이 읽지 않으므로 서비스 표가 아니라 우리 표다 — Flyway 를 거치지 않고
-- Job 이 만든다 (2026-09-17 결정). 화면이 개념을 읽게 되는 날 서비스 표로 승격한다
-- (`contents` 가 걸어온 길: 표가 먼저 있고 Flyway 가 뒤에 baseline 으로 받아들였다).
-- `pl_` 규약대로 서비스 표(`contents`)에는 FK 를 걸지 않고 논리적 참조만 둔다.
CREATE TABLE IF NOT EXISTS {CATEGORY} (
    code        text PRIMARY KEY,
    name_ko     text NOT NULL,
    parent_code text REFERENCES {CATEGORY}(code),
    CHECK (code ~ '^[a-z_]+$')
);
INSERT INTO {CATEGORY} (code, name_ko) VALUES
    ('apparel', '의류'), ('footwear', '신발'), ('accessory', '액세서리'), ('material', '소재'),
    ('color', '색상'), ('style', '스타일'), ('brand', '브랜드'), ('designer', '디자이너'),
    ('person', '인물'), ('generic', '일반 단어'), ('media', '매체'), ('event', '행사')
ON CONFLICT (code) DO NOTHING;

-- 개념. 정체성은 id 이고 이름은 전부 바꿀 수 있다. countable=false 는 세지 않는 일반 단어.
CREATE TABLE IF NOT EXISTS {CONCEPT} (
    id             bigserial   PRIMARY KEY,
    canonical_name text        NOT NULL,
    display_ko     text,
    description    text,
    category       text        NOT NULL REFERENCES {CATEGORY}(code),
    parent_id      bigint      REFERENCES {CONCEPT}(id),
    countable      boolean     NOT NULL DEFAULT true,
    status         text        NOT NULL DEFAULT 'ACTIVE',
    merged_into    bigint      REFERENCES {CONCEPT}(id),
    source         text        NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (canonical_name, category),
    CHECK (status IN ('ACTIVE', 'MERGED', 'RETIRED')),
    CHECK ((status = 'MERGED') = (merged_into IS NOT NULL)),
    CHECK (parent_id IS NULL OR parent_id <> id)
);
CREATE INDEX IF NOT EXISTS pl_concept_parent_idx
    ON {CONCEPT} (parent_id) WHERE parent_id IS NOT NULL;

-- 표현. 조회의 핫패스는 (lang, normalized). REJECTED 를 남기는 이유는 검수가 내린 쌍이
-- 다음 초기 적재에 되살아나지 않게 하려는 것이다.
CREATE TABLE IF NOT EXISTS {EXPRESSION} (
    id         bigserial   PRIMARY KEY,
    concept_id bigint      NOT NULL REFERENCES {CONCEPT}(id),
    lang       text        NOT NULL,
    surface    text        NOT NULL,
    normalized text        NOT NULL,
    kind       text        NOT NULL,
    ambiguous  boolean     NOT NULL DEFAULT false,
    -- 어디서 왔나. `source` 는 종류(`wikidata` · `seed` · `llm`), `source_id` 는 그 안의
    -- 식별자(`Q894874` · `vocabulary-core.json`), `license` 는 그 출처의 이용 조건이다.
    -- 셋을 나눠 두는 이유는 **출처 단위로 되돌리기 위해서다** — 대량으로 부은 사전이 매핑을
    -- 깎으면 그 출처만 골라 내려야 하는데, 종류만 있으면 브랜드와 의류가 한 덩어리가 된다.
    source     text        NOT NULL,
    source_id  text,
    license    text,
    status     text        NOT NULL DEFAULT 'ACTIVE',
    decided_by text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (lang, normalized, concept_id),
    CHECK (lang ~ '^[a-z]{{2,3}}$'),
    CHECK (kind IN ('canonical', 'synonym', 'plural', 'variant', 'abbreviation')),
    CHECK (status IN ('ACTIVE', 'REJECTED'))
);
CREATE INDEX IF NOT EXISTS pl_concept_expression_lookup_idx
    ON {EXPRESSION} (lang, normalized) WHERE status = 'ACTIVE';
CREATE INDEX IF NOT EXISTS pl_concept_expression_concept_idx ON {EXPRESSION} (concept_id);

-- 기사별 개념. PK (article_id, concept_id) 가 "기사는 개념당 한 번" 과 재처리 멱등성을 구조로 준다.
-- article_id 는 contents.id 의 논리적 참조다 (FK 없음 — pl_ 규약).
CREATE TABLE IF NOT EXISTS {ARTICLE_CONCEPT} (
    article_id         bigint      NOT NULL,
    concept_id         bigint      NOT NULL REFERENCES {CONCEPT}(id),
    expression_ids     bigint[]    NOT NULL,
    method             text        NOT NULL,
    dictionary_version integer     NOT NULL,
    processed_at       timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (article_id, concept_id),
    CHECK (method IN ('DICT', 'CONTEXT', 'AUTO_LLM', 'REVIEW')),
    CHECK (cardinality(expression_ids) > 0)
);
CREATE INDEX IF NOT EXISTS pl_article_concept_concept_idx
    ON {ARTICLE_CONCEPT} (concept_id, article_id);

CREATE TABLE IF NOT EXISTS {UNMAPPED} (
    id             bigserial   PRIMARY KEY,
    lang           text        NOT NULL,
    normalized     text        NOT NULL,
    surface_sample text        NOT NULL,
    article_count  integer     NOT NULL DEFAULT 0,
    first_seen     timestamptz NOT NULL DEFAULT now(),
    last_seen      timestamptz NOT NULL DEFAULT now(),
    -- PENDING / JUDGED / QUEUED / RESOLVED / EXPIRED. 검수 명령과 다음 단계가 옮긴다.
    status         text        NOT NULL DEFAULT '{STATUS_PENDING}',
    -- LLM 제안 원문. **확정이 아니다** — 결정은 pl_mapping_decision 에만 남는다.
    proposal       jsonb,
    UNIQUE (lang, normalized)
);
CREATE INDEX IF NOT EXISTS pl_unmapped_expression_pending_idx
    ON {UNMAPPED} (status, article_count DESC);

CREATE TABLE IF NOT EXISTS {UNMAPPED_ARTICLE} (
    unmapped_id bigint NOT NULL REFERENCES {UNMAPPED}(id) ON DELETE CASCADE,
    article_id  bigint NOT NULL,
    PRIMARY KEY (unmapped_id, article_id)
);

CREATE TABLE IF NOT EXISTS {UNMAPPED_CONTEXT} (
    unmapped_id  bigint      NOT NULL REFERENCES {UNMAPPED}(id) ON DELETE CASCADE,
    article_id   bigint      NOT NULL,
    snippet      text        NOT NULL,
    observed_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (unmapped_id, article_id)
);

CREATE TABLE IF NOT EXISTS {DECISION} (
    id                 bigserial   PRIMARY KEY,
    lang               text        NOT NULL,
    normalized         text        NOT NULL,
    -- LINK / NEW_CONCEPT / EXCLUDE / DEFER / UNLINK / MERGE
    decision           text        NOT NULL,
    concept_id         bigint,
    -- auto:layer1 / auto:llm / human:<id> / seed:<file>
    decided_by         text        NOT NULL,
    model              text,
    prompt_version     text,
    evidence           jsonb       NOT NULL DEFAULT '{{}}'::jsonb,
    dictionary_version integer     NOT NULL,
    decided_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS pl_mapping_decision_key_idx
    ON {DECISION} (lang, normalized, decided_at DESC);

-- 자동 판정의 원장. **사람이 한 일은 적지 않는다** — 되돌리기 명령이 사람의 결론을 건드리지
-- 않게 하려는 것이다. 한 줄이 한 표기에 대해 한 일 하나이고, `run_id` 가 한 회차를 묶는다.
--   DECISION  판정 표에 결론을 적었다 (EXCLUDE 는 적히는 순간 순위에서 빠진다)
--   LINK      기존 개념에 표현을 붙였다
--   MINT      세지 않는 새 개념과 그 표현을 만들었다
-- 되돌리면 지우지 않고 `reverted_at` 을 채운다. 무엇이 있었고 누가 내렸는지가 같이 남는다.
CREATE TABLE IF NOT EXISTS {CHANGE} (
    id                 bigserial   PRIMARY KEY,
    run_id             text        NOT NULL,
    action             text        NOT NULL,
    lang               text        NOT NULL,
    normalized         text        NOT NULL,
    decision           text,
    concept_id         bigint,
    expression_id      bigint,
    decision_id        bigint,
    -- 바꾸기 전 미등록 상태. 참고로만 남긴다 — 되돌리기는 늘 검수 대기(PENDING)로 보낸다.
    prior_status       text,
    dictionary_version integer,
    decided_by         text        NOT NULL,
    model              text,
    prompt_version     text,
    evidence           jsonb       NOT NULL DEFAULT '{{}}'::jsonb,
    created_at         timestamptz NOT NULL DEFAULT now(),
    reverted_at        timestamptz,
    reverted_by        text,
    CHECK (action IN ('DECISION', 'LINK', 'MINT'))
);
CREATE INDEX IF NOT EXISTS pl_concept_change_run_idx ON {CHANGE} (run_id);
CREATE INDEX IF NOT EXISTS pl_concept_change_key_idx ON {CHANGE} (lang, normalized);

CREATE TABLE IF NOT EXISTS {VERSION} (
    version    integer     PRIMARY KEY,
    changed_at timestamptz NOT NULL DEFAULT now(),
    note       text        NOT NULL,
    changed_by text        NOT NULL
);
-- 버전 0 = 빈 사전. 첫 초기 사전 적재가 1 을 만든다.
INSERT INTO {VERSION} (version, note, changed_by)
SELECT 0, '빈 사전', 'system' WHERE NOT EXISTS (SELECT 1 FROM {VERSION});

CREATE TABLE IF NOT EXISTS {JUDGEMENT_CACHE} (
    model          text        NOT NULL,
    prompt_version text        NOT NULL,
    lang           text        NOT NULL,
    normalized     text        NOT NULL,
    candidate_hash text        NOT NULL,
    verdict        jsonb       NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (model, prompt_version, lang, normalized, candidate_hash)
);

-- 스테이징. 제약 없이 빨리 받고 병합 뒤 비운다.
CREATE TABLE IF NOT EXISTS {STAGE_ARTICLE_CONCEPT} (
    article_id         bigint   NOT NULL,
    concept_id         bigint   NOT NULL,
    expression_ids     bigint[] NOT NULL,
    method             text     NOT NULL,
    dictionary_version integer  NOT NULL
);
CREATE TABLE IF NOT EXISTS {STAGE_PROCESSED} (
    article_id bigint NOT NULL
);
CREATE TABLE IF NOT EXISTS {STAGE_UNMAPPED} (
    lang       text   NOT NULL,
    normalized text   NOT NULL,
    surface    text   NOT NULL,
    article_id bigint NOT NULL,
    snippet    text
);

-- 이미 있는 표에 칸을 더한다. `CREATE TABLE IF NOT EXISTS` 는 옛 표를 고치지 않는다
-- (`io/candidates.py` 와 같은 사정). 옛 행은 비어 있다 — 그때는 종류만 적었다.
-- 개념의 `source` 에는 `wikidata:Q894874` 처럼 식별자가 붙어 있으므로 **표현이 개념과 같은
-- 출처에서 온 경우에 한해** 그쪽에서 되짚을 수 있다. 사람이 나중에 더한 표현은 되짚지 못한다.
ALTER TABLE {EXPRESSION} ADD COLUMN IF NOT EXISTS source_id text;
ALTER TABLE {EXPRESSION} ADD COLUMN IF NOT EXISTS license text;
-- 출처 단위로 내리려면 그 출처의 행만 빨리 찾아야 한다.
CREATE INDEX IF NOT EXISTS pl_concept_expression_source_idx
    ON {EXPRESSION} (source, source_id);
"""

CONCEPTS_SQL = f"""
SELECT id, canonical_name, category, parent_id, countable
  FROM {CONCEPT}
 WHERE status = 'ACTIVE'
"""

# `ambiguous` 는 칸을 믿지 않고 여기서 다시 센다 — 두 개념에 같은 (lang, normalized) 가 걸리면
# 어느 쪽 행이 먼저 들어왔든 둘 다 모호하다.
# PostgreSQL 은 창 함수 안의 DISTINCT 를 지원하지 않아(2026-09-17 실 DB 에서 확인) 모호 여부를
# 따로 세어 붙인다.
EXPRESSIONS_SQL = f"""
WITH active AS (
    SELECT e.id, e.concept_id, e.lang, e.normalized, e.ambiguous
      FROM {EXPRESSION} e
      JOIN {CONCEPT} c ON c.id = e.concept_id
     WHERE e.status = 'ACTIVE' AND c.status = 'ACTIVE'
), multi AS (
    SELECT lang, normalized
      FROM active
     GROUP BY lang, normalized
    HAVING count(DISTINCT concept_id) > 1
)
SELECT a.id, a.concept_id, a.lang, a.normalized,
       a.ambiguous OR (m.lang IS NOT NULL)
  FROM active a
  LEFT JOIN multi m ON m.lang = a.lang AND m.normalized = a.normalized
"""

# 검수가 내린 쌍. 사전 적재의 `ON CONFLICT DO NOTHING` 이 REJECTED 행에도 걸려 되살리지
# 않으므로, 적재하지 않고 메모리로만 재보는 쪽(`concept/seed.apply_seed_in_memory`)도
# 같은 것을 빼야 실제 적재와 같은 수가 나온다.
REJECTED_EXPRESSIONS_SQL = f"""
SELECT lang, normalized, concept_id
  FROM {EXPRESSION}
 WHERE status = 'REJECTED'
"""

# 승격된 키워드의 기사별 발생 — MVP 의 계약 A 를 DB 에서 만든다. 추출이 언어·문맥을 실어 주기
# 전까지의 자리이고, 그때는 이 질의 대신 파일을 읽는다 (`docs/concept-layer.md` 계약 A).
#
# ## 별칭을 거쳐서 승격 여부를 본다
#
# `pl_document_candidate.normalized_key` 는 **별칭을 접지 않은 원표기**다
# (`registry/batch.py` 1단계).
# 승격은 대표 키로만 일어나 `pl_keyword_id_map` 에는 대표만 들어간다 (8단계). 그래서 별칭으로
# 흡수된 표기의 문서 행은 대표 키로 바꿔 보지 않으면 조인에서 전부 떨어진다 — 개념도 안 붙고
# 미등록에도 안 남아서, 무엇을 놓쳤는지 물어볼 자리조차 없어진다.
#
# `keyword_contents` 를 잇는 질의가 이미 같은 홉을 거친다 (`io/keywords.LINK_CONTENTS_SQL`).
# `pl_alias` 는 `(domain, alias_key)` 기본키라 왼쪽 조인이 행을 늘리지 않는다.
#
# **조회에 쓰는 표기는 대표가 아니라 기사에 나온 원표기다.** 별칭 홉은 "이 표기가 승격된
# 키워드인가" 만 본다. 개념 사전은 자기 표현 목록을 따로 들고 있어서(`스니커` 도 `sneakers` 의
# 표현이다) 원표기가 더 많은 것을 알려 주고, 사전에 없으면 미등록으로 드러난다.
# 표기별 기사 수와 매체 수. 한 매체의 일회성 표기를 개념으로 만들지 않기 위한 근거다.
EXPRESSION_EVIDENCE_SQL = """
SELECT d.normalized_key, count(DISTINCT d.url_hash), count(DISTINCT d.source_id)
  FROM pl_document_candidate d
 WHERE d.selected AND d.domain = %s AND d.stat_date >= current_date - %s
 GROUP BY 1
"""

OCCURRENCES_SQL = """
SELECT m.content_id, d.surface, c.title
  FROM pl_document_candidate d
  LEFT JOIN pl_alias       a ON a.domain = d.domain AND a.alias_key = d.normalized_key
  JOIN pl_keyword_id_map   k ON k.domain = d.domain
                            AND k.normalized_key = coalesce(a.canonical_key, d.normalized_key)
  JOIN pl_content_id_map   m ON m.url_hash = d.url_hash
  LEFT JOIN contents      c ON c.id = m.content_id
 WHERE d.selected
   AND d.domain = %s
   AND d.stat_date >= current_date - %s
"""

# 병합: 이번 결과를 upsert 하고, 이번에 처리한 기사에서 사라진 행을 지운다. 마지막 TRUNCATE 는
# `jdbc.stage_and_merge` 규약이 아니라 우리가 직접 트랜잭션을 여니 여기서 한다.
ARTICLE_CONCEPT_MERGE_SQL = f"""
INSERT INTO {ARTICLE_CONCEPT}
    (article_id, concept_id, expression_ids, method, dictionary_version, processed_at)
SELECT article_id, concept_id, expression_ids, method, dictionary_version, now()
  FROM {STAGE_ARTICLE_CONCEPT}
ON CONFLICT (article_id, concept_id) DO UPDATE
   SET expression_ids     = EXCLUDED.expression_ids,
       method             = EXCLUDED.method,
       dictionary_version = EXCLUDED.dictionary_version,
       processed_at       = now();

DELETE FROM {ARTICLE_CONCEPT} a
 USING {STAGE_PROCESSED} p
 WHERE a.article_id = p.article_id
   AND NOT EXISTS (
        SELECT 1 FROM {STAGE_ARTICLE_CONCEPT} s
         WHERE s.article_id = a.article_id AND s.concept_id = a.concept_id);

TRUNCATE {STAGE_ARTICLE_CONCEPT}, {STAGE_PROCESSED};
"""

# 사전에 새로 등록되어 이번 실행에서 모호하지 않게 붙은 원표기는 검수 대기에서 내린다.
# 기사 이력은 재처리 근거로 남겨 두고 상태만 바꾼다. 라틴 표기는 사전의 언어 칸과
# 입력의 언어 칸이 다를 수 있어 표현 테이블 대신 매핑이 확인한 입력 키를 받는다.
RESOLVE_MAPPED_SQL = f"""
UPDATE {UNMAPPED} u
   SET status = 'RESOLVED'
  FROM (VALUES %s) AS mapped(lang, normalized)
 WHERE u.status IN ('PENDING', 'JUDGED', 'QUEUED')
   AND u.lang = mapped.lang
   AND u.normalized = mapped.normalized;
"""

# 표기별로 이미 쌓인 문맥 표본의 수와 그중 첫 문장. 본문을 다시 읽을지 고르는 데 쓴다.
STORED_CONTEXT_SQL = f"""
SELECT lang, normalized, samples, snippet FROM (
  SELECT u.lang, u.normalized,
         count(*) OVER (PARTITION BY u.id) AS samples,
         row_number() OVER (PARTITION BY u.id ORDER BY c.article_id) AS rn,
         c.snippet
    FROM {UNMAPPED} u
    JOIN {UNMAPPED_CONTEXT} c ON c.unmapped_id = u.id
   WHERE u.article_count >= %s AND u.status <> 'RESOLVED'
) ranked WHERE rn = 1
"""


# 미등록: 표현 upsert → 기사 집합 → 문맥 표본(N건 상한) → article_count 재계산.
UNMAPPED_MERGE_SQL = f"""
INSERT INTO {UNMAPPED} (lang, normalized, surface_sample)
SELECT DISTINCT ON (lang, normalized) lang, normalized, surface
  FROM {STAGE_UNMAPPED}
 ORDER BY lang, normalized, surface
ON CONFLICT (lang, normalized) DO UPDATE
   SET last_seen = now(),
       status = CASE WHEN {UNMAPPED}.status = 'EXPIRED'
                     THEN '{STATUS_PENDING}' ELSE {UNMAPPED}.status END;

INSERT INTO {UNMAPPED_ARTICLE} (unmapped_id, article_id)
SELECT u.id, s.article_id
  FROM {STAGE_UNMAPPED} s
  JOIN {UNMAPPED} u ON u.lang = s.lang AND u.normalized = s.normalized
ON CONFLICT DO NOTHING;

INSERT INTO {UNMAPPED_CONTEXT} (unmapped_id, article_id, snippet)
SELECT unmapped_id, article_id, snippet
  FROM (
    SELECT u.id AS unmapped_id, s.article_id, s.snippet,
           row_number() OVER (PARTITION BY u.id ORDER BY s.article_id) AS rn,
           (SELECT count(*) FROM {UNMAPPED_CONTEXT} c WHERE c.unmapped_id = u.id) AS existing
      FROM {STAGE_UNMAPPED} s
      JOIN {UNMAPPED} u ON u.lang = s.lang AND u.normalized = s.normalized
     WHERE s.snippet IS NOT NULL
  ) ranked
 WHERE existing + rn <= %(context_samples)s
ON CONFLICT DO NOTHING;

UPDATE {UNMAPPED} u
   SET article_count = (SELECT count(*) FROM {UNMAPPED_ARTICLE} a WHERE a.unmapped_id = u.id)
 WHERE u.id IN (SELECT DISTINCT u2.id FROM {STAGE_UNMAPPED} s JOIN {UNMAPPED} u2
                 ON u2.lang = s.lang AND u2.normalized = s.normalized);

TRUNCATE {STAGE_UNMAPPED};
"""

# 미등록의 기사 이력은 지우지 않는다. 새 사전으로 실제 매핑된 표현의 상태만 위에서
# RESOLVED 로 바꾼다. 이번 창에 다시 등장하지 않은 표현은 그대로 검수 대상으로 남는다.


def new_run_id() -> str:
    """자동 판정 한 회차의 이름. 명령줄에 옮겨 적기 쉽게 짧고, 시각 순으로 정렬된다."""
    from datetime import datetime, timezone

    return "auto-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


@dataclass(frozen=True, slots=True)
class WriteResult:
    upserted: int
    processed_articles: int
    unmapped_rows: int


class ConceptSink:
    def __init__(self, config: Config) -> None:
        self._config = config

    # --- 스키마 ------------------------------------------------------------
    def ensure_schema(self) -> None:
        """개념 표 넷과 작업 표 전부를 만든다. 서비스 표는 없다 — 스프링이 읽지 않는다."""
        jdbc.execute(self._config, DDL)
        log.info(
            "개념 스키마 확인: %s · %s · %s · %s · %s · %s",
            CONCEPT, EXPRESSION, ARTICLE_CONCEPT, UNMAPPED, DECISION, VERSION,
        )

    # --- 사전 --------------------------------------------------------------
    def load_dictionary(self) -> Dictionary:
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute(CONCEPTS_SQL)
            concepts = [
                Concept(int(i), str(n), str(c), None if p is None else int(p), bool(k))
                for i, n, c, p, k in cur.fetchall()
            ]
            cur.execute(EXPRESSIONS_SQL)
            expressions = [
                Expression(int(i), int(c), str(lang), str(n), bool(a))
                for i, c, lang, n, a in cur.fetchall()
            ]
        dictionary = Dictionary(concepts, expressions)
        log.info("사전 적재: 개념 %d · 표현 %d", len(concepts), len(dictionary))
        return dictionary

    def rejected_expression_keys(self) -> frozenset[tuple[str, str, int]]:
        """검수가 내린 `(lang, normalized, concept_id)`. 사전이 되살리지 않는 쌍이다."""
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute(REJECTED_EXPRESSIONS_SQL)
            return frozenset(
                (str(lang), str(normalized), int(concept_id))
                for lang, normalized, concept_id in cur.fetchall()
            )

    def current_version(self) -> int:
        return int(self._scalar(f"SELECT max(version) FROM {VERSION}") or 0)

    def bump_version(self, *, note: str, changed_by: str) -> int:
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO {VERSION} (version, note, changed_by) "
                f"SELECT coalesce(max(version), 0) + 1, %s, %s FROM {VERSION} RETURNING version",
                (note, changed_by),
            )
            return int(cur.fetchone()[0])

    # --- 입력 --------------------------------------------------------------
    def occurrences(self, *, domain: str, window_days: int) -> dict[int, list[Keyword]]:
        """기사 → 선별된 표기 목록. 별칭은 대표로 바꿔 승격 여부를 본다 (`OCCURRENCES_SQL`).

        `domain` 은 **슬러그**(`fashion`)다. `pl_document_candidate` 와 `pl_keyword_id_map` 은 둘 다
        슬러그로 저장한다 — `keywords.domain` 의 상수명(`FASHION`)이 아니다. 2026-09-17 실 DB 에서
        상수명을 넘겼다가 0행이 나와 확인했다.
        """
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute(OCCURRENCES_SQL, (domain, window_days))
            grouped: dict[int, list[Keyword]] = {}
            for content_id, surface, title in cur.fetchall():
                grouped.setdefault(int(content_id), []).append(
                    Keyword(str(surface), str(title) if title else None)
                )
        return grouped

    def expression_evidence(self, *, domain: str, window_days: int) -> dict[str, tuple[int, int]]:
        """표기 → (기사 수, 매체 수). 새 개념을 만들 근거다.

        판정 하나로 사전에 개념을 만들지 않고, **기사가 스스로 증명한 것**을 함께 본다
        (`concept/minting.py`).
        """
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute(EXPRESSION_EVIDENCE_SQL, (domain, window_days))
            return {str(key): (int(articles), int(sources)) for key, articles, sources in cur}

    def mint_concepts(
        self,
        mints: Sequence[Any],
        *,
        decided_by: str,
        run_id: str | None = None,
        uncounted: Iterable[str] = (),
    ) -> int:
        """새 개념과 그 표기를 **한 트랜잭션**으로 넣고 원장에 남긴다.

        **세는 개념으로 넣는다.** `uncounted` 에 든 분류만 `countable=false` 다. 전에는 전부
        세지 않게 만들었는데, 세지 않는 개념에 붙은 키워드는 순위에서 빠지므로
        (`metrics/concepts.build_grouping`) 그때까지 키워드로 순위에 오르던 것을 숨기게
        됐다. 자동으로 만든 개념인지는 `source` 로 가린다.

        하나라도 만들면 사전 버전을 한 번 올린다. 후보 목록이 바뀌므로 유보 판정을 다시 믿으면
        안 되고(`concept/workflow.reusable`), 되돌릴 때도 어느 버전에서 생겼는지가 남아야 한다.
        """
        if not mints:
            return 0
        run = run_id or new_run_id()
        hidden = set(uncounted)
        made = 0
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(hashtext('pl_dictionary_version'))")
            cur.execute(f"SELECT coalesce(max(version), 0) FROM {VERSION}")
            version = int(cur.fetchone()[0]) + 1
            for mint in mints:
                cur.execute(
                    f"""
                    INSERT INTO {CONCEPT} (canonical_name, category, countable, source)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (canonical_name, category) DO NOTHING
                    RETURNING id
                    """,
                    (mint.canonical_name, mint.category, mint.category not in hidden, decided_by),
                )
                row = cur.fetchone()
                if row is None:
                    # 같은 이름·분류가 이미 있다 — 되돌려 `RETIRED` 가 된 것도 여기 걸린다. 이번
                    # 회차에 만들 것이 아니라 다음 회차가 사전 조회로 붙일 것이다.
                    continue
                concept_id = int(row[0])
                cur.execute(
                    f"""
                    INSERT INTO {EXPRESSION}
                        (concept_id, lang, surface, normalized, kind, source, source_id, decided_by)
                    VALUES (%s, %s, %s, %s, 'canonical', %s, %s, %s)
                    ON CONFLICT (lang, normalized, concept_id) DO NOTHING
                    RETURNING id
                    """,
                    (
                        concept_id, mint.lang, mint.surface, mint.normalized,
                        decided_by, run, decided_by,
                    ),
                )
                expression = cur.fetchone()
                cur.execute(
                    f"SELECT status FROM {UNMAPPED} WHERE lang = %s AND normalized = %s",
                    (mint.lang, mint.normalized),
                )
                prior = cur.fetchone()
                cur.execute(
                    f"INSERT INTO {CHANGE} (run_id, action, lang, normalized, decision, "
                    "concept_id, expression_id, prior_status, dictionary_version, decided_by, "
                    "evidence) VALUES (%s, 'MINT', %s, %s, 'NEW_CONCEPT', %s, %s, %s, %s, %s, "
                    "%s::jsonb)",
                    (
                        run, mint.lang, mint.normalized, concept_id,
                        int(expression[0]) if expression else None,
                        prior[0] if prior else None, version, decided_by,
                        json.dumps(
                            {
                                "canonical_name": mint.canonical_name,
                                "category": mint.category,
                                "articles": mint.articles,
                                "sources": mint.sources,
                            },
                            ensure_ascii=False,
                        ),
                    ),
                )
                made += 1
            if made:
                cur.execute(
                    f"INSERT INTO {VERSION} (version, note, changed_by) VALUES (%s, %s, %s)",
                    (version, f"LLM 새 개념 잠정 {made}건 ({run})", decided_by),
                )
        return made

    # --- 적재 --------------------------------------------------------------
    def write(
        self,
        *,
        rows: Sequence[ConceptRow],
        processed_article_ids: Iterable[int],
        unmapped: Sequence[Unmapped],
        resolved_keys: Iterable[tuple[str, str]],
        dictionary_version: int,
        context_samples: int,
    ) -> WriteResult:
        """기사별 개념과 미등록을 **한 연결, 한 트랜잭션**으로 쓴다.

        둘이 갈리면 안 되는 이유 — 개념은 들어갔는데 미등록이 안 남으면 "안 붙은 것이 무엇이었나"
        가 사라지고, 반대면 붙은 것이 미등록으로도 올라온다.
        """
        from psycopg2.extras import execute_values

        processed = sorted(set(processed_article_ids))
        resolved = sorted(set(resolved_keys))
        page = int(self._config.get("jdbc.batch_size", jdbc.DEFAULT_BATCH_SIZE))
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute(f"TRUNCATE {STAGE_ARTICLE_CONCEPT}, {STAGE_PROCESSED}, {STAGE_UNMAPPED}")
            if rows:
                execute_values(
                    cur,
                    f"INSERT INTO {STAGE_ARTICLE_CONCEPT} "
                    "(article_id, concept_id, expression_ids, method, dictionary_version) "
                    "VALUES %s",
                    [
                        (
                            r.article_id,
                            r.concept_id,
                            list(r.expression_ids),
                            r.method,
                            dictionary_version,
                        )
                        for r in rows
                    ],
                    page_size=page,
                )
            if processed:
                execute_values(
                    cur,
                    f"INSERT INTO {STAGE_PROCESSED} (article_id) VALUES %s",
                    [(a,) for a in processed],
                    page_size=page,
                )
            if processed:
                cur.execute(ARTICLE_CONCEPT_MERGE_SQL)
            if resolved:
                execute_values(cur, RESOLVE_MAPPED_SQL, resolved, page_size=page)
            if unmapped:
                execute_values(
                    cur,
                    f"INSERT INTO {STAGE_UNMAPPED} "
                    "(lang, normalized, surface, article_id, snippet) VALUES %s",
                    [(u.lang, u.normalized, u.surface, u.article_id, u.context) for u in unmapped],
                    page_size=page,
                )
                cur.execute(UNMAPPED_MERGE_SQL, {"context_samples": context_samples})
        log.info(
            "개념 적재: 행 %d · 처리 기사 %d · 미등록 %d", len(rows), len(processed), len(unmapped)
        )
        return WriteResult(len(rows), len(processed), len(unmapped))

    def record_decision(
        self,
        *,
        lang: str,
        normalized: str,
        decision: str,
        concept_id: int | None,
        decided_by: str,
        dictionary_version: int,
        evidence: str = "{}",
        model: str | None = None,
        prompt_version: str | None = None,
    ) -> None:
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO {DECISION} "
                "(lang, normalized, decision, concept_id, decided_by, model, "
                "prompt_version, evidence, dictionary_version) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)",
                (
                    lang,
                    normalized,
                    decision,
                    concept_id,
                    decided_by,
                    model,
                    prompt_version,
                    evidence,
                    dictionary_version,
                ),
            )

    def settled_decisions(
        self, *, prompt_version: str, dictionary_version: int
    ) -> dict[tuple[str, str], str]:
        """다시 묻지 않아도 되는 표현 — `(lang, normalized) -> decision`.

        무엇을 아직 믿을지는 `concept.workflow.reusable` 이 정한다. 여기서는 표현별 최신
        판정만 꺼내 그 규칙에 넘긴다.
        """
        rows = self._rows(
            f"SELECT DISTINCT ON (lang, normalized) lang, normalized, decision, "
            f"dictionary_version, prompt_version FROM {DECISION} "
            "ORDER BY lang, normalized, decided_at DESC"
        )
        from trendin.spark.concept.workflow import reusable

        settled: dict[tuple[str, str], str] = {}
        for lang, normalized, decision, version, prompt in rows:
            if reusable(
                str(decision),
                None if prompt is None else str(prompt),
                None if version is None else int(version),
                prompt_version=prompt_version,
                dictionary_version=dictionary_version,
            ):
                settled[(str(lang), str(normalized))] = str(decision)
        return settled

    def record_decisions(
        self,
        decisions: Sequence[Any],
        *,
        decided_by: str,
        model: str,
        prompt_version: str,
        dictionary_version: int,
        run_id: str | None = None,
    ) -> int:
        """한 회차의 판정을 **한 트랜잭션**으로 남기고, 같은 트랜잭션에서 원장에도 적는다.

        네 결론을 모두 적는다. `LINK` 만 남기면 나머지 셋은 다음 회차에 다시 판정되고, 같은
        표현을 매달 LLM 에게 되묻게 된다.

        **원장에 같이 적는 이유** — 판정 표에 적힌 `EXCLUDE` 는 그 자체로 순위에서 표기를
        뺀다 (`io/metrics.SILENCED_SQL`). 사전 행이 하나도 안 생겨도 화면이 바뀌는 자리라,
        되돌릴 수 있으려면 이것도 회차에 묶여 있어야 한다.
        """
        if not decisions:
            return 0
        from psycopg2.extras import execute_values

        rows = [
            (
                item.lang,
                item.normalized,
                item.decision,
                item.concept_id,
                decided_by,
                model,
                prompt_version,
                json.dumps(item.evidence, ensure_ascii=False, default=str),
                dictionary_version,
            )
            for item in decisions
        ]
        run = run_id or new_run_id()
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            # `execute_values` 는 VALUES 한 자리만 채우므로 회차 번호는 미리 인용해 박는다.
            run_literal = cur.mogrify("%s", (run,)).decode("utf-8")
            execute_values(
                cur,
                f"WITH written AS (INSERT INTO {DECISION} "
                "(lang, normalized, decision, concept_id, decided_by, model, "
                "prompt_version, evidence, dictionary_version) VALUES %s "
                "RETURNING id, lang, normalized, decision, concept_id, decided_by, model, "
                "prompt_version, dictionary_version) "
                f"INSERT INTO {CHANGE} (run_id, action, lang, normalized, decision, concept_id, "
                "decision_id, prior_status, dictionary_version, decided_by, model, prompt_version) "
                f"SELECT {run_literal}, 'DECISION', w.lang, w.normalized, w.decision, "
                "w.concept_id, w.id, u.status, w.dictionary_version, w.decided_by, w.model, "
                f"w.prompt_version FROM written w LEFT JOIN {UNMAPPED} u "
                "ON u.lang = w.lang AND u.normalized = w.normalized",
                rows,
                template="(%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)",
            )
        return len(rows)

    # --- 자동 판정 ---------------------------------------------------------
    def cached_judgement(
        self,
        *,
        model: str,
        prompt_version: str,
        lang: str,
        normalized: str,
        candidate_hash: str,
    ) -> dict[str, Any] | None:
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT verdict FROM {JUDGEMENT_CACHE} "
                "WHERE model = %s AND prompt_version = %s AND lang = %s "
                "AND normalized = %s AND candidate_hash = %s",
                (model, prompt_version, lang, normalized, candidate_hash),
            )
            row = cur.fetchone()
        if row is None:
            return None
        payload = row[0]
        if isinstance(payload, str):
            payload = json.loads(payload)
        return dict(payload) if isinstance(payload, dict) else None

    def cache_judgement(
        self,
        *,
        model: str,
        prompt_version: str,
        lang: str,
        normalized: str,
        candidate_hash: str,
        verdict: dict[str, Any],
    ) -> None:
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO {JUDGEMENT_CACHE} "
                "(model, prompt_version, lang, normalized, candidate_hash, verdict) "
                "VALUES (%s, %s, %s, %s, %s, %s::jsonb) "
                "ON CONFLICT (model, prompt_version, lang, normalized, candidate_hash) "
                "DO UPDATE SET verdict = EXCLUDED.verdict, created_at = now()",
                (
                    model,
                    prompt_version,
                    lang,
                    normalized,
                    candidate_hash,
                    json.dumps(verdict, ensure_ascii=False),
                ),
            )

    def record_auto_defer(
        self,
        *,
        lang: str,
        normalized: str,
        evidence: dict[str, Any],
        model: str,
        prompt_version: str,
        dictionary_version: int,
        run_id: str | None = None,
        write_decision: bool = True,
    ) -> None:
        """검수 대기에 최신 제안을 남기고, **결정이 아직 없는 표기에만** 자동 유보를 한 줄 적는다.

        **결정이 적힌 표기에는 유보를 덧쓰지 않는다** (`write_decision=False`). 판정 표는 표기마다
        최신 결정만 읽힌다. 제외·새 개념으로 적힌 표기 위에 유보를 덧쓰면 그 결론이 지워진다 —
        2026-09-23 첫 자동 반영 회차에서 제외 183건이 전부 이렇게 덮여 순위에 적용되지 않았다
        (`io/metrics.SILENCED_SQL`). 여기 남는 것은 `NAME_FAILED` 처럼 결론 없이 끝난 표기다.

        적은 유보는 원장에도 남긴다. 되돌리기가 회차 번호 하나로 이것까지 찾을 수 있어야 한다.
        """
        encoded = json.dumps(evidence, ensure_ascii=False, default=str)
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {UNMAPPED} SET status = 'QUEUED', proposal = %s::jsonb "
                "WHERE lang = %s AND normalized = %s AND status <> 'RESOLVED'",
                (encoded, lang, normalized),
            )
            if not write_decision:
                return
            cur.execute(
                f"INSERT INTO {DECISION} "
                "(lang, normalized, decision, concept_id, decided_by, model, "
                "prompt_version, evidence, dictionary_version) "
                "SELECT %s, %s, 'DEFER', NULL, 'auto:llm', %s, %s, %s::jsonb, %s "
                "WHERE NOT EXISTS ("
                f"SELECT 1 FROM {DECISION} WHERE lang = %s AND normalized = %s "
                "AND decision = 'DEFER' AND decided_by = 'auto:llm' "
                "AND model = %s AND prompt_version = %s AND dictionary_version = %s) "
                "RETURNING id",
                (
                    lang,
                    normalized,
                    model,
                    prompt_version,
                    encoded,
                    dictionary_version,
                    lang,
                    normalized,
                    model,
                    prompt_version,
                    dictionary_version,
                ),
            )
            written = cur.fetchone()
            if written is None:
                return
            cur.execute(
                f"INSERT INTO {CHANGE} (run_id, action, lang, normalized, decision, decision_id, "
                "dictionary_version, decided_by, model, prompt_version, evidence) "
                "VALUES (%s, 'DECISION', %s, %s, 'DEFER', %s, %s, 'auto:llm', %s, %s, %s::jsonb)",
                (
                    run_id or new_run_id(), lang, normalized, int(written[0]),
                    dictionary_version, model, prompt_version, encoded,
                ),
            )

    def stored_contexts(self, *, min_articles: int) -> dict[tuple[str, str], tuple[int, str]]:
        """표기 → (쌓인 문맥 표본 수, 첫 문장). 표본이 없는 표기는 빠진다.

        **본문을 다시 읽지 않기 위한 것이다.** 표본은 표현당 상한이 있고 찬 뒤에는 새 문장이
        들어가지 못하므로(`UNMAPPED_MERGE_SQL`), 이미 찬 표기의 기사를 또 읽으면 뽑은 문장이
        그대로 버려진다. 30일 창을 매 회차 다시 읽던 것이 여기서 갈린다.

        첫 문장을 같이 돌려주는 이유는 건너뛴 표기도 판정에는 문맥이 필요해서다. 새로 뽑는
        대신 저장된 것을 쓴다 — 기사 제목으로 되돌아가면 `judge.usable_context` 가 막는다.
        """
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute(STORED_CONTEXT_SQL, (min_articles,))
            return {
                (str(lang), str(normalized)): (int(samples), str(snippet))
                for lang, normalized, samples, snippet in cur
                if snippet
            }

    def record_proposals(
        self,
        proposals: Sequence[Any],
        *,
        model: str,
        prompt_version: str,
        dictionary_version: int,
    ) -> int:
        """이번 회차 판정을 **제안으로만** 남긴다. 사전은 건드리지 않는다.

        **`pl_mapping_decision` 에 적지 않는 것이 요점이다.** 그 표는 사람이 내린 결론을 담고,
        거기 적힌 것은 `concept/workflow.reusable` 이 다시 묻지 않는다. LLM 판단을 거기 넣으면
        나중에 반영을 켜도 이미 "결론 난" 표현은 영영 다시 보지 않는다 — 특히 `NEW_CONCEPT`
        이 그렇다. 제안은 회차마다 덮어써야 하는 것이라 자리가 다르다 (표 주석: "LLM 제안
        원문. 확정이 아니다").

        **상태는 건드리지 않는다.** `QUEUED` 는 "사람이 이번엔 넘어갔다" 는 뜻이고, 검수
        내보내기가 그것을 뒤로 민다. 제안이 달렸다고 그 자리로 보내면 정작 미리 채워 준 줄이
        맨 아래로 간다. 제안은 상태가 아니라 딸린 자료다.

        `RESOLVED` 는 아예 제외한다. 이미 붙은 표기에 제안을 덮으면 끝난 일이 다시 올라온다.
        """
        if not proposals:
            return 0
        from psycopg2.extras import execute_values

        rows = [
            (
                item.lang,
                item.normalized,
                json.dumps(
                    {
                        "decision": item.decision,
                        "concept_id": item.concept_id,
                        "model": model,
                        "prompt_version": prompt_version,
                        "dictionary_version": dictionary_version,
                        **item.evidence,
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            )
            for item in proposals
        ]
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            execute_values(
                cur,
                f"UPDATE {UNMAPPED} u SET proposal = v.proposal::jsonb "
                "FROM (VALUES %s) AS v(lang, normalized, proposal) "
                "WHERE u.lang = v.lang AND u.normalized = v.normalized "
                "AND u.status <> 'RESOLVED'",
                rows,
            )
        return len(rows)

    # --- 원장 --------------------------------------------------------------
    def changes(
        self, *, run_id: str | None = None, key: tuple[str, str] | None = None
    ) -> list[Any]:
        """원장에서 회차 하나 또는 표기 하나의 줄을 `concept/rollback.Change` 로 돌려준다."""
        from trendin.spark.concept.rollback import Change

        where, params = [], []
        if run_id is not None:
            where.append("run_id = %s")
            params.append(run_id)
        if key is not None:
            where.append("lang = %s AND normalized = %s")
            params.extend(key)
        if not where:
            return []
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, run_id, action, lang, normalized, decision, concept_id, "
                f"expression_id, reverted_at IS NOT NULL FROM {CHANGE} "
                f"WHERE {' AND '.join(where)} ORDER BY id",
                params,
            )
            return [
                Change(
                    id=int(row[0]), run_id=str(row[1]), action=str(row[2]),
                    lang=str(row[3]), normalized=str(row[4]),
                    decision=None if row[5] is None else str(row[5]),
                    concept_id=None if row[6] is None else int(row[6]),
                    expression_id=None if row[7] is None else int(row[7]),
                    reverted=bool(row[8]),
                )
                for row in cur.fetchall()
            ]

    def auto_runs(self, *, limit: int = 20) -> list[tuple]:
        """최근 회차 — `(run_id, 처음 시각, LINK, MINT, EXCLUDE, 전체, 되돌린 수)`."""
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT run_id, min(created_at), "
                "count(*) FILTER (WHERE action = 'LINK'), "
                "count(*) FILTER (WHERE action = 'MINT'), "
                "count(*) FILTER (WHERE action = 'DECISION' AND decision = 'EXCLUDE'), "
                "count(*), count(reverted_at) "
                f"FROM {CHANGE} GROUP BY run_id ORDER BY min(created_at) DESC LIMIT %s",
                (limit,),
            )
            return list(cur.fetchall())

    def revert(self, plan: Any, *, by: str, note: str) -> dict[str, Any]:
        """`concept/rollback.Plan` 을 **한 트랜잭션**으로 되돌린다. 지우지 않고 상태를 내린다.

        **사람이 손댄 개념은 내리지 않는다.** 새 개념에 검수가 표현을 더 붙였으면 그건 이미 사람의
        결론이다. 그런 개념은 건너뛰고 돌려주는 값에 적는다 — 표기 쪽(보류·검수 대기)은 그대로
        되돌린다. 세는지 여부로는 가리지 않는다. 새 개념은 이제 처음부터 세는 개념이다.
        """
        if plan.empty:
            return {"changes": 0}
        concepts = list(plan.concepts)
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(hashtext('pl_dictionary_version'))")
            kept: list[int] = []
            if concepts:
                cur.execute(
                    f"SELECT DISTINCT c.id FROM {CONCEPT} c LEFT JOIN {EXPRESSION} e "
                    "ON e.concept_id = c.id AND e.status = 'ACTIVE' "
                    "AND e.source NOT IN ('llm', 'auto:llm') "
                    "WHERE c.id = ANY(%s) AND e.id IS NOT NULL",
                    (concepts,),
                )
                kept = sorted(int(row[0]) for row in cur.fetchall())
                concepts = [item for item in concepts if item not in kept]
            cur.execute(
                f"UPDATE {EXPRESSION} SET status = 'REJECTED', decided_by = %s "
                "WHERE status = 'ACTIVE' AND (id = ANY(%s) OR concept_id = ANY(%s)) "
                "AND concept_id <> ALL(%s) RETURNING id",
                (by, list(plan.expressions), concepts, kept),
            )
            rejected = sorted(int(row[0]) for row in cur.fetchall())
            if concepts:
                cur.execute(
                    f"UPDATE {CONCEPT} SET status = 'RETIRED', updated_at = now() "
                    "WHERE id = ANY(%s) AND status = 'ACTIVE'",
                    (concepts,),
                )
            # 기사에 붙은 행도 내린다. 창 밖 기사는 다음 회차가 다시 붙이지 않으므로 여기서 치워야
            # 한다. 되돌린 표현만으로 붙은 행은 지우고, 다른 표현과 함께 붙은 행은 그 표현만 뺀다.
            cur.execute(
                f"DELETE FROM {ARTICLE_CONCEPT} "
                "WHERE concept_id = ANY(%s) OR expression_ids <@ %s::bigint[]",
                (concepts, rejected),
            )
            removed = cur.rowcount
            if rejected:
                cur.execute(
                    f"UPDATE {ARTICLE_CONCEPT} SET expression_ids = ARRAY("
                    "SELECT x FROM unnest(expression_ids) AS x WHERE x <> ALL(%s::bigint[])) "
                    "WHERE expression_ids && %s::bigint[]",
                    (rejected, rejected),
                )
            cur.execute(
                f"INSERT INTO {VERSION} (version, note, changed_by) "
                f"SELECT coalesce(max(version), 0) + 1, %s, %s FROM {VERSION} RETURNING version",
                (note, by),
            )
            version = int(cur.fetchone()[0])
            evidence = json.dumps(
                {"rollback": note, "changes": list(plan.change_ids)}, ensure_ascii=False
            )
            for lang, normalized in plan.keys:
                # 사람 보류가 최신 결정이 된다 — 순위 제외가 풀리고, 자동 판정이 다시 손대지 않는다.
                cur.execute(
                    f"INSERT INTO {DECISION} (lang, normalized, decision, decided_by, evidence, "
                    "dictionary_version) VALUES (%s, %s, 'DEFER', %s, %s::jsonb, %s)",
                    (lang, normalized, by, evidence, version),
                )
                cur.execute(
                    f"UPDATE {UNMAPPED} SET status = %s WHERE lang = %s AND normalized = %s",
                    (STATUS_PENDING, lang, normalized),
                )
            cur.execute(
                f"UPDATE {CHANGE} SET reverted_at = now(), reverted_by = %s "
                "WHERE id = ANY(%s) AND reverted_at IS NULL",
                (by, list(plan.change_ids)),
            )
        return {
            "changes": len(plan.change_ids),
            "expressions": len(rejected),
            "concepts": len(concepts),
            "kept_concepts": kept,
            "article_rows": removed,
            "keys": len(plan.keys),
            "version": version,
        }

    # --- 내부 --------------------------------------------------------------
    def _rows(self, statement: str) -> list[tuple]:
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute(statement)
            return list(cur.fetchall())

    def _scalar(self, statement: str):
        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute(statement)
            row = cur.fetchone()
        return None if row is None else row[0]
