"""Combine lexical, phonetic and vector concept candidates into one ranked result.

The module owns ranking policy, not model or database I/O.  Callers may retrieve vector
hits in batches and pass them in by query label.  This keeps the ranking deterministic,
cheap to unit-test, and usable by both the operational command and offline evaluation.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from trendin.spark.common.config import Config, ConfigError
from trendin.spark.concept.candidates import (
    SOURCE_SOUND,
    SOURCE_SOUND_NEAR,
    SOURCE_SPACE,
    SOURCE_SPELL,
    CandidateIndex,
)
from trendin.spark.concept.dictionary import Dictionary
from trendin.spark.concept.normalize import concept_key, lang_of_surface

# 검색이 무엇을 말해 주는지 — 셋을 가른다. `NO_MATCH` 는 사람에게 넘길 일이 아니라 신규 개념
# 경로로 보낼 일이다. 이 둘을 한 칸에 담으면 `Kendall Jenner`(후보 없음)와 `Zendaya`(잡음
# 후보 0.19)가 다른 길로 가게 된다 — 둘 다 사전에 없는 사람인데도 그렇다.
STRONG = "STRONG"
AMBIGUOUS = "AMBIGUOUS"
NO_MATCH = "NO_MATCH"

EXACT = "exact"
NORMALIZED = "normalized"
CHARACTER = "character"
PHONETIC = "phonetic"
VECTOR = "vector"
CHANNELS = (EXACT, NORMALIZED, CHARACTER, PHONETIC, VECTOR)

_SOURCE_CHANNEL = {
    SOURCE_SPACE: NORMALIZED,
    SOURCE_SPELL: CHARACTER,
    SOURCE_SOUND: PHONETIC,
    SOURCE_SOUND_NEAR: PHONETIC,
}


class VectorCandidate(Protocol):
    concept_id: int
    name: str
    category: str
    similarity: float


@dataclass(frozen=True, slots=True)
class RetrievalPolicy:
    top_k: int
    min_combined_score: float
    meaningful_candidate_threshold: float
    category_mismatch_factor: float
    consensus_bonus: float
    thresholds: Mapping[str, float]
    weights: Mapping[str, float]

    @classmethod
    def from_config(cls, config: Config) -> "RetrievalPolicy":
        section = config.section("concept.retrieval")
        threshold_values = section.get("thresholds") or {}
        weight_values = section.get("weights") or {}
        missing = [
            path
            for path, value in (
                ("top_k", section.get("top_k")),
                ("min_combined_score", section.get("min_combined_score")),
                (
                    "meaningful_candidate_threshold",
                    section.get("meaningful_candidate_threshold"),
                ),
                ("category_mismatch_factor", section.get("category_mismatch_factor")),
                ("consensus_bonus", section.get("consensus_bonus")),
                *((f"thresholds.{name}", threshold_values.get(name)) for name in CHANNELS),
                *((f"weights.{name}", weight_values.get(name)) for name in CHANNELS),
            )
            if value is None
        ]
        if missing:
            raise ConfigError(
                "concept.retrieval 설정이 비어 있다: "
                + ", ".join(f"concept.retrieval.{path}" for path in missing)
            )
        return cls(
            top_k=int(section["top_k"]),
            min_combined_score=float(section["min_combined_score"]),
            meaningful_candidate_threshold=float(section["meaningful_candidate_threshold"]),
            category_mismatch_factor=float(section["category_mismatch_factor"]),
            consensus_bonus=float(section["consensus_bonus"]),
            thresholds={name: float(threshold_values[name]) for name in CHANNELS},
            weights={name: float(weight_values[name]) for name in CHANNELS},
        ).validated()

    def validated(self) -> "RetrievalPolicy":
        if self.top_k < 1:
            raise ConfigError("concept.retrieval.top_k 는 1 이상이어야 한다")
        for name, value in (
            ("min_combined_score", self.min_combined_score),
            ("meaningful_candidate_threshold", self.meaningful_candidate_threshold),
            ("category_mismatch_factor", self.category_mismatch_factor),
            ("consensus_bonus", self.consensus_bonus),
            *((f"thresholds.{key}", value) for key, value in self.thresholds.items()),
            *((f"weights.{key}", value) for key, value in self.weights.items()),
        ):
            if not 0 <= value <= 1:
                raise ConfigError(f"concept.retrieval.{name} 는 0 이상 1 이하여야 한다")
        if self.meaningful_candidate_threshold > self.min_combined_score:
            raise ConfigError(
                "concept.retrieval.meaningful_candidate_threshold 는 min_combined_score "
                "이하여야 한다 — 그 위로 두면 애매한 구간이 사라져 사람이 볼 것이 없어진다"
            )
        return self


@dataclass(frozen=True, slots=True)
class ChannelEvidence:
    channel: str
    score: float
    query: str
    expression_id: int | None = None


@dataclass(frozen=True, slots=True)
class RankedCandidate:
    concept_id: int
    name: str
    category: str
    score: float
    evidence_score: float
    category_compatible: bool | None
    evidence: tuple[ChannelEvidence, ...]

    @property
    def similarity(self) -> float:
        """Compatibility name for the existing verification and auto-link gates."""
        return self.score

    @property
    def raw_scores(self) -> dict[str, float]:
        return {item.channel: item.score for item in self.evidence}

    @property
    def reasons(self) -> tuple[str, ...]:
        return tuple(f"{item.channel}:{item.query}" for item in self.evidence)


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    """검색이 내린 결론. `outcome` 이 셋 중 무엇인지가 다음 갈림길을 정한다.

    `deferred` 는 "자동 연결로 바로 가지 않는다" 만 뜻한다. 그것이 사람을 부르는 일인지
    신규 개념을 만드는 일인지는 `outcome` 을 봐야 안다.
    """

    candidates: tuple[RankedCandidate, ...]
    outcome: str
    defer_reason: str | None = None

    @property
    def deferred(self) -> bool:
        return self.outcome != STRONG

    @property
    def no_match(self) -> bool:
        """의미 있는 후보가 없다 — 사람이 아니라 신규 개념 경로로 간다."""
        return self.outcome == NO_MATCH


class CandidateRetriever:
    def __init__(
        self, dictionary: Dictionary, lexical_index: CandidateIndex, policy: RetrievalPolicy
    ) -> None:
        self.dictionary = dictionary
        self.lexical_index = lexical_index
        self.policy = policy.validated()

    def retrieve(
        self,
        *,
        original: str,
        lang: str,
        english_name: str | None,
        category: str | None,
        vector_hits: Mapping[str, Sequence[VectorCandidate]] | None = None,
        exclude_expression_ids: frozenset[int] = frozenset(),
    ) -> RetrievalResult:
        evidence: dict[int, dict[str, ChannelEvidence]] = defaultdict(dict)
        metadata: dict[int, tuple[str, str]] = {}

        queries = [("original", original, lang)]
        if english_name and english_name.strip():
            queries.append(("english", english_name, lang_of_surface(english_name, lang)))

        for label, raw, query_lang in queries:
            key = concept_key(raw)
            if not key:
                continue
            self._add_dictionary_hits(
                evidence, metadata, label, raw, query_lang, key, exclude_expression_ids
            )
            for item in self.lexical_index.generate_all(
                query_lang,
                key,
                min_similarity=min(
                    self.policy.thresholds[CHARACTER], self.policy.thresholds[PHONETIC]
                ),
            ):
                if item.expression_id in exclude_expression_ids:
                    continue
                channel = _SOURCE_CHANNEL[item.source]
                self._add(
                    evidence,
                    item.concept_id,
                    ChannelEvidence(channel, item.score, label, item.expression_id),
                )
                concept = self.dictionary.concept(item.concept_id)
                metadata[item.concept_id] = (concept.canonical_name, concept.category)

        for label, hits in (vector_hits or {}).items():
            for hit in hits:
                self._add(
                    evidence,
                    hit.concept_id,
                    ChannelEvidence(VECTOR, round(float(hit.similarity), 4), label),
                )
                metadata[hit.concept_id] = (hit.name, hit.category)

        ranked: list[RankedCandidate] = []
        for concept_id, by_channel in evidence.items():
            eligible = tuple(
                item
                for item in by_channel.values()
                if item.score >= self.policy.thresholds[item.channel]
            )
            if not eligible:
                continue
            name, candidate_category = metadata[concept_id]
            compatible = _category_compatible(category, candidate_category)
            combined = max(
                item.score * self.policy.weights[item.channel] for item in eligible
            )
            combined = min(1.0, combined + self.policy.consensus_bonus * (len(eligible) - 1))
            # 감점 전 점수를 따로 남긴다. 분류는 LLM 의 **추측**이라 이것만으로 후보를 묻으면
            # 묻힌 쪽이 정답일 때 알 길이 없다 — `maille` 이 그랬다 (`knit` -> knitwear 1.0 이
            # material 추측에 눌려 0.25 로 떨어지고 fabric 이 이겼다).
            evidence_score = round(combined, 4)
            if compatible is False:
                combined *= self.policy.category_mismatch_factor
            ranked.append(
                RankedCandidate(
                    concept_id=concept_id,
                    name=name,
                    category=candidate_category,
                    score=round(combined, 4),
                    evidence_score=evidence_score,
                    category_compatible=compatible,
                    evidence=tuple(sorted(eligible, key=lambda item: CHANNELS.index(item.channel))),
                )
            )
        ranked.sort(key=lambda item: (-item.score, item.concept_id))
        selected = tuple(ranked[: self.policy.top_k])
        if not selected:
            return RetrievalResult((), NO_MATCH, "NO_CANDIDATE")
        top = selected[0].score
        if top < self.policy.meaningful_candidate_threshold:
            # 무언가 돌려주긴 했지만 소리만 닮은 잡음이다. 없는 것으로 읽는다.
            return RetrievalResult(selected, NO_MATCH, "NO_MEANINGFUL_CANDIDATE")
        if top < self.policy.min_combined_score:
            return RetrievalResult(selected, AMBIGUOUS, "LOW_SCORE")
        return RetrievalResult(selected, STRONG)

    def _add_dictionary_hits(
        self,
        evidence: dict[int, dict[str, ChannelEvidence]],
        metadata: dict[int, tuple[str, str]],
        label: str,
        raw: str,
        lang: str,
        key: str,
        excluded: frozenset[int],
    ) -> None:
        raw_key = raw.strip().casefold()
        for hit in self.dictionary.lookup(lang, key):
            if hit.expression.expression_id in excluded:
                continue
            channel = EXACT if raw_key == hit.expression.normalized.casefold() else NORMALIZED
            self._add(
                evidence,
                hit.concept.concept_id,
                ChannelEvidence(channel, 1.0, label, hit.expression.expression_id),
            )
            metadata[hit.concept.concept_id] = (
                hit.concept.canonical_name,
                hit.concept.category,
            )

    @staticmethod
    def _add(
        evidence: dict[int, dict[str, ChannelEvidence]],
        concept_id: int,
        item: ChannelEvidence,
    ) -> None:
        current = evidence[concept_id].get(item.channel)
        if current is None or item.score > current.score:
            evidence[concept_id][item.channel] = item


def _category_compatible(expected: str | None, actual: str) -> bool | None:
    normalized = (expected or "").strip().casefold()
    if not normalized or normalized == "generic":
        return None
    return normalized == actual.strip().casefold()
