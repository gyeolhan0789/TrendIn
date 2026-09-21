"""Operational unmapped-expression workflow: name -> candidates -> verification.

This module contains no database, model-loading, or network setup.  Those dependencies are
injected so the scheduled job can keep the legacy dictionary-only path when automation is off
and unit tests can verify caching and failure isolation without spending LLM credits.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from trendin.spark.common.config import Config, ConfigError
from trendin.spark.concept import judge, vector_judge
from trendin.spark.concept.auto_link import Link
from trendin.spark.concept.judge import Question, Verdict
from trendin.spark.concept.retrieval import CandidateRetriever, RankedCandidate

VERIFY_PROMPT_VERSION = "candidate-v1"
NAME_CANDIDATE_HASH = "none"


class LlmClient(Protocol):
    model: str

    def chat(self, messages: list[dict[str, str]], *, max_tokens: int = 1200) -> str: ...


class JudgementCache(Protocol):
    def cached_judgement(
        self, *, model: str, prompt_version: str, lang: str, normalized: str,
        candidate_hash: str,
    ) -> dict[str, Any] | None: ...

    def cache_judgement(
        self, *, model: str, prompt_version: str, lang: str, normalized: str,
        candidate_hash: str, verdict: Mapping[str, Any],
    ) -> None: ...


VectorSearch = Callable[[str, str], Mapping[str, Sequence[Any]]]


@dataclass(frozen=True, slots=True)
class AutomationPolicy:
    enabled: bool
    model: str
    batch_size: int
    max_calls: int
    vector_enabled: bool

    @classmethod
    def from_config(cls, config: Config) -> "AutomationPolicy":
        section = config.section("concept.automation")
        policy = cls(
            enabled=bool(section.get("enabled", False)),
            model=str(section.get("model") or "gpt-4o-mini"),
            batch_size=int(section.get("batch_size", judge.DEFAULT_BATCH_SIZE)),
            max_calls=int(section.get("max_calls", 20)),
            vector_enabled=bool(section.get("vector_enabled", True)),
        )
        if policy.batch_size < 1:
            raise ConfigError("concept.automation.batch_size 는 1 이상이어야 한다")
        if policy.max_calls < 1:
            raise ConfigError("concept.automation.max_calls 는 1 이상이어야 한다")
        return policy


@dataclass(frozen=True, slots=True)
class DeferredDecision:
    lang: str
    normalized: str
    reason: str
    evidence: dict[str, Any]


@dataclass(frozen=True, slots=True)
class WorkflowResult:
    links: tuple[Link, ...]
    deferred: tuple[DeferredDecision, ...]
    attempted_calls: int


def run_workflow(
    questions: Sequence[Question], *, client: LlmClient, cache: JudgementCache,
    retriever: CandidateRetriever, policy: AutomationPolicy,
    vector_search: VectorSearch | None = None,
) -> WorkflowResult:
    """Judge unique expressions while isolating failures to the smallest possible item."""
    unique = _unique_questions(questions)
    calls = 0
    verdicts: list[tuple[Question, Verdict]] = []
    deferred: list[DeferredDecision] = []

    for group in judge.batches(unique, policy.batch_size):
        pending: list[Question] = []
        for question in group:
            cached = cache.cached_judgement(
                model=policy.model,
                prompt_version=judge.PROMPT_VERSION,
                lang=question.lang,
                normalized=question.normalized,
                candidate_hash=NAME_CANDIDATE_HASH,
            )
            verdict = _cached_name(question, cached)
            if verdict is None:
                pending.append(question)
            else:
                verdicts.append((question, verdict))
        if not pending:
            continue
        parsed, used, problems = _classify_with_isolation(
            pending, client=client, available=policy.max_calls - calls
        )
        calls += used
        by_key = {(item.lang, item.normalized): item for item in parsed}
        for question in pending:
            verdict = by_key.get((question.lang, question.normalized))
            if verdict is None:
                deferred.append(_defer(question, "NAME_FAILED", errors=problems))
                continue
            cache.cache_judgement(
                model=policy.model,
                prompt_version=judge.PROMPT_VERSION,
                lang=question.lang,
                normalized=question.normalized,
                candidate_hash=NAME_CANDIDATE_HASH,
                verdict={"english_name": verdict.english_name, "category": verdict.category},
            )
            verdicts.append((question, verdict))

    links: list[Link] = []
    for question, verdict in verdicts:
        base = _base_evidence(question, verdict)
        original = question.surface or question.normalized
        if verdict.category == "generic":
            deferred.append(_defer(question, "GENERIC", **base))
            continue
        vector_hits: Mapping[str, Sequence[Any]] = {}
        vector_error: str | None = None
        if vector_search is not None:
            try:
                vector_hits = vector_search(original, verdict.english_name)
            # One failed embedding/search must not stop other expressions.
            except Exception as error:
                vector_error = f"{type(error).__name__}: {error}"
        retrieval = retriever.retrieve(
            original=original,
            lang=question.lang,
            english_name=verdict.english_name,
            category=verdict.category,
            vector_hits=vector_hits,
        )
        candidates = [_candidate_evidence(item) for item in retrieval.candidates]
        evidence = {**base, "candidates": candidates}
        if vector_error:
            evidence["vector_error"] = vector_error
        if retrieval.deferred:
            deferred.append(
                _defer(question, retrieval.defer_reason or "NO_CANDIDATE", **evidence)
            )
            continue

        digest = _candidate_hash(question.context, candidates)
        cached = cache.cached_judgement(
            model=policy.model,
            prompt_version=VERIFY_PROMPT_VERSION,
            lang=question.lang,
            normalized=question.normalized,
            candidate_hash=digest,
        )
        choice: int | None
        if cached is not None and "concept_id" in cached:
            raw_choice = cached["concept_id"]
            choice = (
                raw_choice
                if isinstance(raw_choice, int) and not isinstance(raw_choice, bool)
                else None
            )
        elif calls >= policy.max_calls:
            deferred.append(_defer(question, "CALL_LIMIT", **evidence))
            continue
        else:
            calls += 1
            try:
                content = client.chat(
                    vector_judge.messages(verdict, retrieval.candidates, context=question.context)
                )
                choice = vector_judge.parse_choice(content, retrieval.candidates)
                cache.cache_judgement(
                    model=policy.model,
                    prompt_version=VERIFY_PROMPT_VERSION,
                    lang=question.lang,
                    normalized=question.normalized,
                    candidate_hash=digest,
                    verdict={"concept_id": choice},
                )
            except Exception as error:
                deferred.append(
                    _defer(
                        question,
                        "VERIFY_FAILED",
                        **evidence,
                        error=f"{type(error).__name__}: {error}",
                    )
                )
                continue
        accepted = vector_judge.eligible_choice(
            verdict,
            retrieval.candidates,
            choice,
            min_similarity=retriever.policy.min_combined_score,
            context=question.context,
        )
        if accepted is None:
            deferred.append(_defer(question, "LLM_DEFER", **evidence, choice=choice))
            continue
        selected = next(item for item in retrieval.candidates if item.concept_id == accepted)
        links.append(
            Link(
                verdict,
                accepted,
                retrieval="combined",
                similarity=selected.score,
                evidence={**evidence, "choice": accepted},
            )
        )
    return WorkflowResult(tuple(links), tuple(deferred), calls)


def _classify_with_isolation(
    questions: list[Question], *, client: LlmClient, available: int
) -> tuple[list[Verdict], int, list[str]]:
    if available <= 0:
        return [], 0, ["LLM call limit reached"]
    calls = 1
    try:
        verdicts, problems = judge.parse(client.chat(judge.messages(questions)), questions)
    except Exception as error:
        verdicts, problems = [], [f"{type(error).__name__}: {error}"]
    found = {(item.lang, item.normalized) for item in verdicts}
    missing = [q for q in questions if (q.lang, q.normalized) not in found]
    # A batch failure is retried item-by-item so one malformed expression does not poison its peers.
    if len(questions) > 1:
        for question in missing:
            if calls >= available:
                break
            calls += 1
            try:
                single, errors = judge.parse(client.chat(judge.messages([question])), [question])
                verdicts.extend(single)
                problems.extend(errors)
            except Exception as error:
                problems.append(f"{question.normalized}: {type(error).__name__}: {error}")
    return verdicts, calls, problems


def _unique_questions(questions: Sequence[Question]) -> list[Question]:
    found: dict[tuple[str, str], Question] = {}
    for question in questions:
        key = (question.lang, question.normalized)
        current = found.get(key)
        if current is None or question.article_count > current.article_count:
            found[key] = question
    return [
        Question(i, q.lang, q.normalized, q.article_count, q.context, q.surface)
        for i, q in enumerate(found.values(), start=1)
    ]


def _cached_name(question: Question, payload: Mapping[str, Any] | None) -> Verdict | None:
    if not payload:
        return None
    english = str(payload.get("english_name") or "").strip()
    category = str(payload.get("category") or "").strip()
    if not english or category not in judge.CATEGORIES:
        return None
    return Verdict(question.lang, question.normalized, english, category)


def _base_evidence(question: Question, verdict: Verdict) -> dict[str, Any]:
    return {
        "original": question.surface or question.normalized,
        "lang": question.lang,
        "context": question.context,
        "article_count": question.article_count,
        "english_name": verdict.english_name,
        "category": verdict.category,
    }


def _candidate_evidence(item: RankedCandidate) -> dict[str, Any]:
    return {
        "concept_id": item.concept_id,
        "name": item.name,
        "category": item.category,
        "score": item.score,
        "category_compatible": item.category_compatible,
        "evidence": [
            {
                "channel": evidence.channel,
                "score": evidence.score,
                "query": evidence.query,
                "expression_id": evidence.expression_id,
            }
            for evidence in item.evidence
        ],
    }


def _candidate_hash(context: str | None, candidates: list[dict[str, Any]]) -> str:
    value = json.dumps(
        {"context": context or "", "candidates": candidates},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _defer(question: Question, reason: str, **evidence: Any) -> DeferredDecision:
    return DeferredDecision(
        question.lang,
        question.normalized,
        reason,
        {
            "reason": reason,
            "original": question.surface or question.normalized,
            "lang": question.lang,
            "context": question.context,
            "article_count": question.article_count,
            **evidence,
        },
    )
