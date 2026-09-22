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
    create_concepts: bool = False
    min_create_articles: int = 3
    min_create_sources: int = 2

    @classmethod
    def from_config(cls, config: Config) -> "AutomationPolicy":
        section = config.section("concept.automation")
        policy = cls(
            enabled=bool(section.get("enabled", False)),
            model=str(section.get("model") or "gpt-4o-mini"),
            batch_size=int(section.get("batch_size", judge.DEFAULT_BATCH_SIZE)),
            max_calls=int(section.get("max_calls", 20)),
            vector_enabled=bool(section.get("vector_enabled", True)),
            create_concepts=bool(section.get("create_concepts", False)),
            min_create_articles=int(section.get("min_create_articles", 3)),
            min_create_sources=int(section.get("min_create_sources", 2)),
        )
        if policy.batch_size < 1:
            raise ConfigError("concept.automation.batch_size 는 1 이상이어야 한다")
        if policy.max_calls < 1:
            raise ConfigError("concept.automation.max_calls 는 1 이상이어야 한다")
        if policy.min_create_articles < 1 or policy.min_create_sources < 1:
            raise ConfigError(
                "concept.automation.min_create_articles · min_create_sources 는 1 이상이어야 한다"
            )
        return policy


@dataclass(frozen=True, slots=True)
class DeferredDecision:
    lang: str
    normalized: str
    reason: str
    evidence: dict[str, Any]


# 다시 물어도 같은 답이 나올 이유가 없는 실패다. **기록으로 남기지 않는다** — 남기면 한 번의
# LLM 오류나 호출 한도 때문에 그 표현이 영원히 유보로 굳는다.
TRANSIENT = frozenset({"NAME_FAILED", "CALL_LIMIT", "VERIFY_FAILED", "NO_THRESHOLD", "NO_CONTEXT"})

# 판정 결과로 남길 네 가지. DDL 주석이 쓰는 낱말을 그대로 쓴다.
LINK = "LINK"
NEW_CONCEPT = "NEW_CONCEPT"
EXCLUDE = "EXCLUDE"
DEFER = "DEFER"


def reusable(
    decision: str, prompt: str | None, version: int | None,
    *, prompt_version: str, dictionary_version: int,
) -> bool:
    """지난 판정을 이번 회차에도 그대로 믿을 것인가.

    | 결론 | 언제 그대로 쓰나 |
    | --- | --- |
    | `EXCLUDE` · `NEW_CONCEPT` | 같은 프롬프트로 내렸으면 사전 버전과 무관하게 |
    | `DEFER` | 사전 버전까지 같을 때만 — 사전이 자라면 없던 후보가 생긴다 |
    | `LINK` | 쓰지 않는다. 이어졌으면 애초에 미등록이 아니다 |

    프롬프트 버전이 비어 있으면 사람이 내린 판정이다. 프롬프트를 올렸다고 사람의 결론을
    뒤집지 않는다.
    """
    if decision == LINK:
        return False
    by_human = prompt is None
    if not by_human and prompt != prompt_version:
        return False
    if decision == DEFER and not by_human and version != dictionary_version:
        return False
    return decision in (EXCLUDE, NEW_CONCEPT, DEFER)


@dataclass(frozen=True, slots=True)
class RecordedDecision:
    """한 표현에 대해 이번 회차가 내린 결론.

    **네 가지를 모두 남기는 이유** — `LINK` 만 상태로 반영하면 나머지 셋은 다음 회차에 다시
    판정된다. 같은 `Getty Images` 를 매달 LLM 에게 되묻게 되고, 그 사이에 답이 달라져도
    무엇이 달라졌는지 알 길이 없다. 근거(모델·프롬프트 버전·사전 버전)를 같이 남겨야
    나중에 "이 옛 판정을 아직 믿어도 되나" 를 따질 수 있다.
    """

    lang: str
    normalized: str
    decision: str
    concept_id: int | None
    evidence: dict[str, Any]

    @property
    def key(self) -> tuple[str, str]:
        return (self.lang, self.normalized)


@dataclass(frozen=True, slots=True)
class WorkflowResult:
    links: tuple[Link, ...]
    deferred: tuple[DeferredDecision, ...]
    attempted_calls: int
    decisions: tuple[RecordedDecision, ...] = ()
    reused: tuple[tuple[str, str], ...] = ()


def run_workflow(
    questions: Sequence[Question], *, client: LlmClient, cache: JudgementCache,
    retriever: CandidateRetriever, policy: AutomationPolicy,
    vector_search: VectorSearch | None = None,
    settled: Mapping[tuple[str, str], str] | None = None,
) -> WorkflowResult:
    """Judge unique expressions while isolating failures to the smallest possible item.

    `settled` 는 지난 회차에 이미 결론이 난 표현이다 (`(lang, normalized) -> decision`). 여기
    있는 것은 이름조차 묻지 않는다 — 다시 물어 봐야 같은 답이 나오거나, 다르게 나오면 그게 더
    곤란하다. 무엇을 아직 믿을지는 부른 쪽이 사전 버전과 프롬프트 버전을 보고 고른다.
    """
    already = settled or {}
    reused = tuple(
        question.key for question in _unique_questions(questions) if question.key in already
    )
    unique = [item for item in _unique_questions(questions) if item.key not in already]
    calls = 0
    verdicts: list[tuple[Question, Verdict]] = []
    deferred: list[DeferredDecision] = []
    decisions: list[RecordedDecision] = []

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
        if verdict.category in judge.UNCOUNTED:
            # `base` 에 이미 분류가 들어 있다 — 매체인지 일반어인지는 거기서 읽는다.
            deferred.append(_defer(question, "UNCOUNTED", **base))
            decisions.append(_decision(question, EXCLUDE, None, base))
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
            # 의미 있는 후보가 없는 것은 애매한 것이 아니다. 사람이 볼 일이 아니라 새 개념을
            # 만들 일이라, 다음 단계가 둘을 구분할 수 있게 여기서 갈라 적는다.
            reason = retrieval.defer_reason or "NO_CANDIDATE"
            deferred.append(
                _defer(
                    question,
                    reason,
                    **evidence,
                    outcome=retrieval.outcome,
                    new_concept=retrieval.no_match,
                )
            )
            decisions.append(
                _decision(
                    question,
                    NEW_CONCEPT if retrieval.no_match else DEFER,
                    None,
                    {**evidence, "reason": reason, "outcome": retrieval.outcome},
                )
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
        choice: vector_judge.Choice
        if cached is not None and "concept_id" in cached:
            raw_choice = cached["concept_id"]
            choice = vector_judge.Choice(
                raw_choice
                if isinstance(raw_choice, int) and not isinstance(raw_choice, bool)
                else None,
                exhausted=bool(cached.get("exhausted")),
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
                    verdict={"concept_id": choice.concept_id, "exhausted": choice.exhausted},
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
        # 막힌 이유를 그대로 남긴다. 어떤 관문이 실제로 무엇을 거르는지 검수 기록으로 세려면
        # 모두 `LLM_DEFER` 로 뭉뚱그려서는 알 수 없다.
        refusal = vector_judge.rejection_reason(
            verdict,
            retrieval.candidates,
            choice,
            min_similarity=retriever.policy.min_combined_score,
            context=question.context,
        )
        if refusal is not None:
            picked = choice.concept_id if isinstance(choice, vector_judge.Choice) else choice
            deferred.append(_defer(question, refusal, **evidence, choice=picked))
            if refusal == "LLM_NONE":
                # 후보를 다 보고 "이 중에 없다" 고 한 것이다. 사람이 볼 일이 아니라 새 개념이다.
                decisions.append(
                    _decision(question, NEW_CONCEPT, None, {**evidence, "reason": refusal})
                )
            elif refusal not in TRANSIENT:
                decisions.append(
                    _decision(question, DEFER, None, {**evidence, "reason": refusal})
                )
            continue
        accepted = choice.concept_id
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
        decisions.append(
            _decision(question, LINK, accepted, {**evidence, "choice": accepted})
        )
    return WorkflowResult(tuple(links), tuple(deferred), calls, tuple(decisions), reused)


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


def _decision(
    question: Question, decision: str, concept_id: int | None, evidence: dict[str, Any]
) -> RecordedDecision:
    return RecordedDecision(question.lang, question.normalized, decision, concept_id, evidence)


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
