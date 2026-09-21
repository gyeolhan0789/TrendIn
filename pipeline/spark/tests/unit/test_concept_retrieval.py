"""통합 후보 생성은 채널 근거를 보존하고 분류를 반영해 재정렬한다."""

from __future__ import annotations

from dataclasses import replace

from trendin.spark.common.config import Config
from trendin.spark.concept.candidates import CandidateIndex
from trendin.spark.concept.dictionary import Concept, Dictionary, Expression
from trendin.spark.concept.retrieval import CandidateRetriever, RetrievalPolicy
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
    strict = replace(POLICY, top_k=1, min_combined_score=0.9)
    hits = {"original": (VectorHit(3, "Cartier", "brand", 0.8),)}
    result = retriever(strict).retrieve(
        original="미등록", lang="ko", english_name=None, category="brand", vector_hits=hits
    )
    assert len(result.candidates) == 1
    assert result.deferred is True
    assert result.defer_reason == "LOW_SCORE"


def test_후보가_없으면_유보한다() -> None:
    result = retriever().retrieve(
        original="완전히없는말", lang="ko", english_name=None, category="brand"
    )
    assert result.candidates == ()
    assert (result.deferred, result.defer_reason) == (True, "NO_CANDIDATE")


def test_설정에서_정책을_읽는다() -> None:
    config = Config(
        {
            "concept": {
                "retrieval": {
                    "top_k": 3,
                    "min_combined_score": 0.5,
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
    assert parsed.thresholds["vector"] == 0.7
