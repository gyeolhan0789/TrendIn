"""Ask whether a retrieved concept is the same referent as an unmapped expression."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from trendin.spark.concept.judge import Verdict, usable_context


class VerificationCandidate(Protocol):
    concept_id: int
    name: str
    category: str
    similarity: float


SYSTEM_PROMPT = """You verify whether a fashion-media keyword denotes an existing concept.
The English rendering and category are suggestions, not ground truth.
Choose one candidate only when it has the same referent and granularity as the keyword.
Distinguish brands from founders, people from products, and broad terms from specific items.
Reply with JSON only, one of these three:
  {"verdict":"same","concept_id":123}  - that candidate is the same thing
  {"verdict":"none"}                   - none of them is; this keyword is something else
  {"verdict":"unsure"}                 - you cannot tell from what you were given
"none" and "unsure" are NOT the same. Say "none" when the candidates are simply other things -
that is a useful answer. Say "unsure" only when the context is too thin to decide, or when two
candidates stay equally plausible."""


def messages(
    verdict: Verdict, candidates: Sequence[VerificationCandidate], *, context: str | None = None
) -> list[dict[str, str]]:
    payload = {
        "domain": "fashion",
        "part_of_speech": "noun phrase",
        "surface": verdict.normalized,
        "english_suggestion": verdict.english_name,
        "category_suggestion": verdict.category,
        "context": (context or "")[:500],
        "candidates": [_candidate_payload(hit) for hit in candidates],
    }
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def _candidate_payload(hit: VerificationCandidate) -> dict:
    payload = {
        "concept_id": hit.concept_id,
        "name": hit.name,
        "category": hit.category,
        "combined_score": hit.similarity,
    }
    evidence = getattr(hit, "evidence", ())
    if evidence:
        payload["evidence"] = [
            {"channel": item.channel, "score": item.score, "query": item.query}
            for item in evidence
        ]
    return payload


def merge_hits(
    groups: Sequence[Sequence[VerificationCandidate]], *, limit: int
) -> tuple[VerificationCandidate, ...]:
    """Keep the best score per concept when original and English queries overlap."""
    if limit < 1:
        raise ValueError("limit must be positive")
    found: dict[int, VerificationCandidate] = {}
    for group in groups:
        for hit in group:
            current = found.get(hit.concept_id)
            if current is None or hit.similarity > current.similarity:
                found[hit.concept_id] = hit
    return tuple(sorted(found.values(), key=lambda hit: (-hit.similarity, hit.concept_id))[:limit])


def verification_slot_available(calls: int, remaining_batches: int, max_calls: int) -> bool:
    """Save one LLM call for each remaining name-classification batch."""
    return calls + remaining_batches < max_calls


@dataclass(frozen=True, slots=True)
class Choice:
    """검증의 답. `concept_id` 가 비었을 때 **왜** 비었는지가 중요하다.

    "이 중에 없다" 와 "모르겠다" 는 다른 말이다. 앞은 새 개념을 만들 근거이고 뒤는 사람이 볼
    일이다. 둘을 같은 `null` 로 받으면 후보를 아무리 많이 보여 줘도 답이 전부 유보로 쌓인다 —
    그래서 벡터 후보를 켜지 못하고 있었다.
    """

    concept_id: int | None
    exhausted: bool = False

    @property
    def matched(self) -> bool:
        return self.concept_id is not None


def parse_choice(content: str, candidates: Sequence[VerificationCandidate]) -> Choice:
    """Reject invented ids and malformed responses.

    옛 모양(`{"concept_id": ...}` 만 오는 답)도 읽는다. 그때는 판단 근거가 없으므로 "모르겠다"
    쪽으로 둔다 — 없다고 단정하는 것이 더 위험하다.
    """
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as error:
        raise ValueError("verification answer is not JSON") from error
    if not isinstance(payload, dict):
        raise ValueError("verification answer is not an object")
    verdict = payload.get("verdict")
    if verdict == "none":
        return Choice(None, exhausted=True)
    if verdict == "unsure":
        return Choice(None)
    if "concept_id" not in payload:
        raise ValueError("verification answer has no concept_id")
    choice = payload["concept_id"]
    if choice is None:
        return Choice(None)
    if isinstance(choice, bool) or not isinstance(choice, int):
        raise ValueError("verification concept_id must be an integer or null")
    if choice not in {candidate.concept_id for candidate in candidates}:
        raise ValueError("verification chose a concept outside the supplied candidates")
    return Choice(choice)


def _evidence_score(candidate: VerificationCandidate) -> float:
    """분류 감점 이전 점수. 그것을 모르는 호출자에게는 최종 점수를 쓴다."""
    value = getattr(candidate, "evidence_score", None)
    return float(value) if value is not None else float(candidate.similarity)


def _name_tokens(name: str | None) -> frozenset[str]:
    return frozenset((name or "").casefold().replace("-", " ").split())


def competing_referent(
    candidates: Sequence[VerificationCandidate], chosen: VerificationCandidate
) -> VerificationCandidate | None:
    """고른 후보와 대상이 겹치는 다른 분류의 후보를 돌려준다. 없으면 None.

    `NameIndex.exact_link` 는 한 이름이 두 개념에 걸리면 잇지 않고 사람에게 넘긴다. 검증 경로는
    그 규칙을 지나쳐서 `Dior`(브랜드)와 `Christian Dior`(사람), `Calvin Klein`(브랜드/사람)을
    분류 추측 하나로 갈랐다. 같은 규칙을 여기에도 둔다.

    이름이 겹치지 않아도, 분류가 어긋났다는 이유로 감점되기 전 증거가 고른 쪽보다 세면 역시
    넘긴다. 프롬프트는 분류를 '제안' 이라고 말해 놓고 순위에서는 정답처럼 쓰고 있었다.
    """
    chosen_score = _evidence_score(chosen)
    chosen_tokens = _name_tokens(chosen.name)
    for candidate in candidates:
        if candidate.concept_id == chosen.concept_id or candidate.category == chosen.category:
            continue
        tokens = _name_tokens(candidate.name)
        if tokens and chosen_tokens and (tokens <= chosen_tokens or chosen_tokens <= tokens):
            return candidate
        if _evidence_score(candidate) >= chosen_score:
            return candidate
    return None


def rejection_reason(
    verdict: Verdict, candidates: Sequence[VerificationCandidate], choice: int | None,
    *, min_similarity: float | None, context: str | None,
) -> str | None:
    """자동 반영을 막는 이유를 돌려준다. 막을 이유가 없으면 None."""
    if choice is None:
        return "LLM_DEFER"
    if isinstance(choice, Choice):
        if choice.exhausted:
            # "이 중에 없다" 는 유보가 아니라 새 개념 경로다. 부른 쪽이 그렇게 읽는다.
            return "LLM_NONE"
        if choice.concept_id is None:
            return "LLM_DEFER"
        choice = choice.concept_id
    if min_similarity is None:
        return "NO_THRESHOLD"
    # 비어 있지 않은 것만으로는 모자란다. `Coach` 의 문맥이 `Coach` 한 낱말이면 브랜드인지
    # 감독인지 가릴 근거가 없다.
    if not usable_context(context, verdict.normalized, verdict.english_name):
        return "NO_CONTEXT"
    picked = next((item for item in candidates if item.concept_id == choice), None)
    if picked is None:
        return "CHOICE_NOT_IN_CANDIDATES"
    if picked.category != verdict.category:
        return "CATEGORY_MISMATCH"
    if picked.similarity < min_similarity:
        return "LOW_SCORE"
    if competing_referent(candidates, picked) is not None:
        return "COMPETING_REFERENT"
    return None


def eligible_choice(
    verdict: Verdict, candidates: Sequence[VerificationCandidate], choice: int | None,
    *, min_similarity: float | None, context: str | None,
) -> int | None:
    """Require article context, an unambiguous referent and calibrated similarity before a write."""
    reason = rejection_reason(
        verdict, candidates, choice, min_similarity=min_similarity, context=context
    )
    return None if reason is not None else choice
