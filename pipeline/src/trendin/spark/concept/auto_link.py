"""LLM 제안 중 기존 개념에 확실히 대응되는 표현만 반영한다."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from trendin.spark.concept.judge import UNCOUNTED, NameIndex, Verdict, usable_context


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


def apply_links(config, links: tuple[Link, ...], *, model: str, prompt_version: str) -> int:
    """한 회차의 연결을 한 트랜잭션에 기록한다. 이미 결정된 표기는 건드리지 않는다."""
    if not links:
        return 0
    from trendin.spark.io import jdbc
    from trendin.spark.io.concepts import DECISION, EXPRESSION, UNMAPPED, VERSION

    with jdbc.connection(config) as conn, conn.cursor() as cur:
        # 여러 검수 작업이 동시에 사전 버전을 올려도 같은 번호를 만들지 않는다.
        cur.execute("SELECT pg_advisory_xact_lock(hashtext('pl_dictionary_version'))")
        cur.execute(f"SELECT coalesce(max(version), 0) FROM {VERSION}")
        version = int(cur.fetchone()[0]) + 1
        applied = 0
        for link in links:
            verdict = link.verdict
            key = (verdict.lang, verdict.normalized)
            cur.execute(
                f"SELECT status, surface_sample FROM {UNMAPPED} "
                "WHERE lang = %s AND normalized = %s FOR UPDATE",
                key,
            )
            row = cur.fetchone()
            if row is None or row[0] not in ("PENDING", "JUDGED", "QUEUED"):
                continue
            cur.execute(
                f"SELECT 1 FROM {EXPRESSION} WHERE lang = %s AND normalized = %s LIMIT 1",
                key,
            )
            if cur.fetchone() is not None:
                continue  # 거부된 표현이나 다른 개념의 표현을 되살리지 않는다.
            cur.execute(
                f"SELECT 1 FROM {DECISION} "
                "WHERE lang = %s AND normalized = %s "
                "AND NOT (decided_by = 'auto:llm' AND decision = 'DEFER') LIMIT 1",
                key,
            )
            if cur.fetchone() is not None:
                continue  # 이전 사람 결정이 있으면 자동 판정이 덮지 않는다.
            cur.execute(
                f"INSERT INTO {EXPRESSION} "
                "(concept_id, lang, surface, normalized, kind, source, decided_by) "
                "VALUES (%s, %s, %s, %s, 'synonym', 'llm', 'auto:llm')",
                (link.concept_id, verdict.lang, row[1], verdict.normalized),
            )
            cur.execute(
                f"UPDATE {UNMAPPED} SET status = 'RESOLVED' "
                "WHERE lang = %s AND normalized = %s",
                key,
            )
            cur.execute(
                f"INSERT INTO {DECISION} "
                "(lang, normalized, decision, concept_id, decided_by, model, "
                "prompt_version, evidence, dictionary_version) "
                "VALUES (%s, %s, 'LINK', %s, 'auto:llm', %s, %s, %s::jsonb, %s)",
                (
                    verdict.lang,
                    verdict.normalized,
                    link.concept_id,
                    model,
                    prompt_version,
                    json.dumps(
                        {
                            "english_name": verdict.english_name,
                            "category": verdict.category,
                            "retrieval": link.retrieval,
                            "similarity": link.similarity,
                            **(link.evidence or {}),
                        },
                        ensure_ascii=False,
                    ),
                    version,
                ),
            )
            applied += 1
        if applied:
            cur.execute(
                f"INSERT INTO {VERSION} (version, note, changed_by) VALUES (%s, %s, %s)",
                (version, f"LLM 기존 개념 자동 연결 {applied}건", "auto:llm"),
            )
        return applied
