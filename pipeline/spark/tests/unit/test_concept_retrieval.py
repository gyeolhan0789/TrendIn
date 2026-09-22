"""통합 후보 생성은 채널 근거를 보존하고 분류를 반영해 재정렬한다."""

from __future__ import annotations

from dataclasses import replace

import pytest

from trendin.spark.common.config import Config, ConfigError
from trendin.spark.concept.candidates import CandidateIndex
from trendin.spark.concept.dictionary import Concept, Dictionary, Expression
from trendin.spark.concept.retrieval import (
    AMBIGUOUS,
    NO_MATCH,
    CandidateRetriever,
    RetrievalPolicy,
)
from trendin.spark.io.concept_vectors import VectorHit

CONCEPTS = (
    Concept(1, "Chanel", "brand"),
    Concept(2, "Chanel", "person"),
    Concept(3, "Cartier", "brand"),
)
EXPRESSIONS = (
    Expression(11, 1, "la", "chanel"),
    Expression(12, 1, "ko", "샤넬"),
    Expression(21, 2, "la", "chanel"),
    Expression(31, 3, "la", "cartier"),
    Expression(32, 3, "ko", "까르띠에"),
)
POLICY = RetrievalPolicy(
    top_k=5,
    min_combined_score=0.55,
    meaningful_candidate_threshold=0.5,
    category_mismatch_factor=0.25,
    consensus_bonus=0.05,
    thresholds={
        "exact": 1.0,
        "normalized": 1.0,
        "character": 0.8,
        "phonetic": 0.8,
        "vector": 0.7,
    },
    weights={
        "exact": 1.0,
        "normalized": 0.95,
        "character": 0.8,
        "phonetic": 0.85,
        "vector": 0.85,
    },
)


def retriever(policy: RetrievalPolicy = POLICY) -> CandidateRetriever:
    dictionary = Dictionary(CONCEPTS, EXPRESSIONS)
    return CandidateRetriever(dictionary, CandidateIndex(dictionary), policy)


def test_동명_다른_분류는_호환_개념보다_낮게_배치한다() -> None:
    result = retriever().retrieve(
        original="샤넬", lang="ko", english_name="Chanel", category="brand"
    )
    assert [item.concept_id for item in result.candidates[:2]] == [1, 2]
    assert result.candidates[0].category_compatible is True
    assert result.candidates[1].category_compatible is False
    assert result.candidates[0].score > result.candidates[1].score


def test_문자_음가_벡터_근거를_개념별로_합치고_원점수를_남긴다() -> None:
    hits = {"original": (VectorHit(3, "Cartier", "brand", 0.91),)}
    result = retriever().retrieve(
        original="까르띠에",
        lang="ko",
        english_name=None,
        category="brand",
        vector_hits=hits,
        exclude_expression_ids=frozenset({32}),
    )
    candidate = result.candidates[0]
    assert candidate.concept_id == 3
    assert candidate.raw_scores["phonetic"] >= 0.8
    assert candidate.raw_scores["vector"] == 0.91
    assert set(candidate.reasons) == {"phonetic:original", "vector:original"}


def test_top_k와_낮은_통합_점수_유보가_정책을_따른다() -> None:
    """문턱 사이에 있는 후보는 사람이 본다 — 의미는 있는데 자동으로 잇기엔 모자란 구간이다."""
    strict = replace(POLICY, top_k=1, min_combined_score=0.9, meaningful_candidate_threshold=0.5)
    hits = {"original": (VectorHit(3, "Cartier", "brand", 0.8),)}
    result = retriever(strict).retrieve(
        original="미등록", lang="ko", english_name=None, category="brand", vector_hits=hits
    )
    assert len(result.candidates) == 1
    assert (result.outcome, result.defer_reason) == (AMBIGUOUS, "LOW_SCORE")
    assert result.deferred is True
    assert result.no_match is False


def test_잡음_수준_후보는_없는_것으로_읽는다() -> None:
    """`Zendaya` 옆의 0.19 짜리 디자이너처럼 소리만 닮은 것은 애매한 것이 아니라 없는 것이다."""
    hits = {"original": (VectorHit(3, "Cartier", "brand", 0.8),)}
    result = retriever().retrieve(
        original="미등록", lang="ko", english_name=None, category="person", vector_hits=hits
    )
    assert len(result.candidates) == 1
    assert (result.outcome, result.defer_reason) == (NO_MATCH, "NO_MEANINGFUL_CANDIDATE")
    assert result.no_match is True


def test_후보가_없으면_신규_개념_경로다() -> None:
    result = retriever().retrieve(
        original="완전히없는말", lang="ko", english_name=None, category="brand"
    )
    assert result.candidates == ()
    assert (result.outcome, result.defer_reason) == (NO_MATCH, "NO_CANDIDATE")
    assert result.no_match is True


def test_의미_문턱이_연결_문턱보다_높으면_거부한다() -> None:
    """둘이 뒤집히면 애매한 구간이 사라져 사람이 볼 것이 없어진다."""
    with pytest.raises(ConfigError):
        replace(POLICY, meaningful_candidate_threshold=0.9, min_combined_score=0.55).validated()


def test_설정에서_정책을_읽는다() -> None:
    config = Config(
        {
            "concept": {
                "retrieval": {
                    "top_k": 3,
                    "min_combined_score": 0.5,
                    "meaningful_candidate_threshold": 0.4,
                    "category_mismatch_factor": 0.2,
                    "consensus_bonus": 0.1,
                    "thresholds": dict(POLICY.thresholds),
                    "weights": dict(POLICY.weights),
                }
            }
        },
        profile="test",
    )
    parsed = RetrievalPolicy.from_config(config)
    assert parsed.top_k == 3
    assert parsed.meaningful_candidate_threshold == 0.4
    assert parsed.thresholds["vector"] == 0.7
