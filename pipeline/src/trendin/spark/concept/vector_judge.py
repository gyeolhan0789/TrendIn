"""Ask whether a retrieved concept is the same referent as an unmapped expression."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import TYPE_CHECKING

from trendin.spark.concept.judge import Verdict

if TYPE_CHECKING:
    from trendin.spark.io.concept_vectors import VectorHit

SYSTEM_PROMPT = """You verify whether a fashion-media keyword denotes an existing concept.
The English rendering and category are suggestions, not ground truth.
Choose one candidate only when it has the same referent and granularity as the keyword.
Distinguish brands from founders, people from products, and broad terms from specific items.
If context is missing or multiple candidates remain plausible, choose null.
Reply with JSON only: {"concept_id": 123} or {"concept_id": null}."""


def messages(
    verdict: Verdict, candidates: Sequence[VectorHit], *, context: str | None = None
) -> list[dict[str, str]]:
    payload = {
        "domain": "fashion",
        "part_of_speech": "noun phrase",
        "surface": verdict.normalized,
        "english_suggestion": verdict.english_name,
        "category_suggestion": verdict.category,
        "context": (context or "")[:500],
        "candidates": [
            {"concept_id": hit.concept_id, "name": hit.name,
             "category": hit.category, "similarity": hit.similarity}
            for hit in candidates
        ],
    }
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def merge_hits(groups: Sequence[Sequence[VectorHit]], *, limit: int) -> tuple[VectorHit, ...]:
    """Keep the best score per concept when original and English queries overlap."""
    if limit < 1:
        raise ValueError("limit must be positive")
    found: dict[int, VectorHit] = {}
    for group in groups:
        for hit in group:
            current = found.get(hit.concept_id)
            if current is None or hit.similarity > current.similarity:
                found[hit.concept_id] = hit
    return tuple(sorted(found.values(), key=lambda hit: (-hit.similarity, hit.concept_id))[:limit])


def verification_slot_available(calls: int, remaining_batches: int, max_calls: int) -> bool:
    """Save one LLM call for each remaining name-classification batch."""
    return calls + remaining_batches < max_calls


def parse_choice(content: str, candidates: Sequence[VectorHit]) -> int | None:
    """Reject invented ids and malformed responses; null means no automatic link."""
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as error:
        raise ValueError("verification answer is not JSON") from error
    if not isinstance(payload, dict) or "concept_id" not in payload:
        raise ValueError("verification answer has no concept_id")
    choice = payload["concept_id"]
    if choice is None:
        return None
    if isinstance(choice, bool) or not isinstance(choice, int):
        raise ValueError("verification concept_id must be an integer or null")
    if choice not in {candidate.concept_id for candidate in candidates}:
        raise ValueError("verification chose a concept outside the supplied candidates")
    return choice


def eligible_choice(
    verdict: Verdict, candidates: Sequence[VectorHit], choice: int | None,
    *, min_similarity: float | None, context: str | None,
) -> int | None:
    """Require article context, matching category and calibrated similarity before a write."""
    if choice is None or min_similarity is None or not (context or "").strip():
        return None
    for candidate in candidates:
        if candidate.concept_id == choice:
            if candidate.category == verdict.category and candidate.similarity >= min_similarity:
                return choice
            return None
    return None
