"""LLM 제안 중 기존 개념에 확실히 대응되는 표현만 반영한다."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from trendin.spark.concept.judge import UNCOUNTED, NameIndex, Verdict, usable_context

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Link:
    verdict: Verdict
    concept_id: int
    retrieval: str = "name"
    similarity: float | None = None
    evidence: dict[str, Any] | None = None


def select_links(
    verdicts: list[Verdict],
    names: NameIndex,
    contexts: Mapping[tuple[str, str], str | None],
) -> tuple[Link, ...]:
    """동일 영어 이름·분류가 유일하고 **기사 문맥이 있을 때만** 자동 연결 대상으로 고른다.

    **문맥을 여기서도 보는 이유** — 이 경로는 후보도 관문도 거치지 않고 바로 잇는다. 그런데
    사전에 이름이 하나뿐이라는 것은 그 말이 한 가지 뜻이라는 뜻이 아니다. `Coach` 는 사전에
    브랜드로만 있지만 감독이기도 하고, `rose` 는 색이면서 꽃이다. 문맥이 없으면 가릴 방법이
    없으므로 사람에게 넘긴다 — 평가 문서의 "문맥 없는 표기는 점수와 무관하게 유보한다" 다.
    """
    selected = []
    for verdict in verdicts:
        if verdict.category in UNCOUNTED:
            continue
        context = contexts.get((verdict.lang, verdict.normalized))
        if not usable_context(context, verdict.normalized, verdict.english_name):
            continue
        concept_id = names.exact_link(verdict.english_name, verdict.category)
        if concept_id is not None:
            selected.append(Link(verdict, concept_id))
    return tuple(selected)


def apply_links(
    config,
    links: tuple[Link, ...],
    *,
    model: str,
    prompt_version: str,
    run_id: str | None = None,
) -> tuple[Link, ...]:
    """한 회차의 연결을 **한 트랜잭션**에 기록하고 원장에 남긴다.

    이미 결정된 표기는 건드리지 않는다.

    반영된 연결만 돌려준다. 부른 쪽이 같은 회차 기사에 `AUTO_LLM` 표시를 붙이는 데 쓴다.

    **사전 버전은 회차당 한 번 올린다.** 전에는 부른 쪽이 연결마다 따로 불러 한 회차에 버전이
    연결 수만큼 올랐다. 그러면 버전으로 회차를 가리킬 수 없고, 유보 판정이 버전이 바뀌었다며
    매번 다시 물린다 (`concept/workflow.reusable`).

    **한 건의 실패가 나머지를 죽이지 않는다.** 연결마다 저장점을 두고, 실패한 건만 되감는다.
    """
    if not links:
        return ()
    from trendin.spark.io import jdbc
    from trendin.spark.io.concepts import (
        CHANGE,
        DECISION,
        EXPRESSION,
        UNMAPPED,
        VERSION,
        new_run_id,
    )

    run = run_id or new_run_id()
    with jdbc.connection(config) as conn, conn.cursor() as cur:
        # 여러 검수 작업이 동시에 사전 버전을 올려도 같은 번호를 만들지 않는다.
        cur.execute("SELECT pg_advisory_xact_lock(hashtext('pl_dictionary_version'))")
        cur.execute(f"SELECT coalesce(max(version), 0) FROM {VERSION}")
        version = int(cur.fetchone()[0]) + 1
        applied: list[Link] = []
        for link in links:
            cur.execute("SAVEPOINT pl_auto_link")
            try:
                done = _apply_one(
                    cur, link, model=model, prompt_version=prompt_version, version=version,
                    run=run, tables=(CHANGE, DECISION, EXPRESSION, UNMAPPED),
                )
            except Exception:
                cur.execute("ROLLBACK TO SAVEPOINT pl_auto_link")
                log.exception(
                    "자동 연결 적재 실패: %s/%s", link.verdict.lang, link.verdict.normalized
                )
                continue
            cur.execute("RELEASE SAVEPOINT pl_auto_link")
            if done:
                applied.append(link)
        if applied:
            cur.execute(
                f"INSERT INTO {VERSION} (version, note, changed_by) VALUES (%s, %s, %s)",
                (version, f"LLM 기존 개념 자동 연결 {len(applied)}건 ({run})", "auto:llm"),
            )
        return tuple(applied)


def _apply_one(
    cur, link: Link, *, model: str, prompt_version: str, version: int, run: str, tables
) -> bool:
    change, decision_table, expression_table, unmapped_table = tables
    verdict = link.verdict
    key = (verdict.lang, verdict.normalized)
    cur.execute(
        f"SELECT status, surface_sample FROM {unmapped_table} "
        "WHERE lang = %s AND normalized = %s FOR UPDATE",
        key,
    )
    row = cur.fetchone()
    if row is None or row[0] not in ("PENDING", "JUDGED", "QUEUED"):
        return False
    cur.execute(
        f"SELECT 1 FROM {expression_table} WHERE lang = %s AND normalized = %s LIMIT 1",
        key,
    )
    if cur.fetchone() is not None:
        return False  # 거부된 표현이나 다른 개념의 표현을 되살리지 않는다.
    # **사람 결정만 막는다.** 전에는 자동 `DEFER` 말고는 무엇이든 막았는데, 개념 Job 이 같은 회차의
    # 판정을 먼저 적으므로 방금 적은 자기 판정에 걸려 연결이 한 건도 들어가지 않았다
    # (2026-09-23 임시 DB 에서 확인). 되돌린 표기는 사람 보류가 남아 여기서 막힌다.
    cur.execute(
        f"SELECT 1 FROM {decision_table} "
        "WHERE lang = %s AND normalized = %s AND decided_by NOT LIKE 'auto:%%' LIMIT 1",
        key,
    )
    if cur.fetchone() is not None:
        return False  # 이전 사람 결정이 있으면 자동 판정이 덮지 않는다.
    cur.execute(
        f"INSERT INTO {expression_table} "
        "(concept_id, lang, surface, normalized, kind, source, source_id, decided_by) "
        "VALUES (%s, %s, %s, %s, 'synonym', 'llm', %s, 'auto:llm') RETURNING id",
        (link.concept_id, verdict.lang, row[1], verdict.normalized, run),
    )
    inserted = cur.fetchone()
    cur.execute(
        f"UPDATE {unmapped_table} SET status = 'RESOLVED' "
        "WHERE lang = %s AND normalized = %s",
        key,
    )
    evidence = json.dumps(
        {
            "english_name": verdict.english_name,
            "category": verdict.category,
            "retrieval": link.retrieval,
            "similarity": link.similarity,
            **(link.evidence or {}),
        },
        ensure_ascii=False,
        default=str,
    )
    cur.execute(
        f"INSERT INTO {decision_table} "
        "(lang, normalized, decision, concept_id, decided_by, model, "
        "prompt_version, evidence, dictionary_version) "
        "VALUES (%s, %s, 'LINK', %s, 'auto:llm', %s, %s, %s::jsonb, %s)",
        (verdict.lang, verdict.normalized, link.concept_id, model, prompt_version, evidence,
         version),
    )
    cur.execute(
        f"INSERT INTO {change} (run_id, action, lang, normalized, decision, concept_id, "
        "expression_id, prior_status, dictionary_version, decided_by, model, prompt_version, "
        "evidence) VALUES (%s, 'LINK', %s, %s, 'LINK', %s, %s, %s, %s, 'auto:llm', %s, %s, "
        "%s::jsonb)",
        (
            run, verdict.lang, verdict.normalized, link.concept_id,
            int(inserted[0]) if inserted else None, row[0], version, model, prompt_version,
            evidence,
        ),
    )
    return True
