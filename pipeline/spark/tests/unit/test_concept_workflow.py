from __future__ import annotations

import json

from trendin.spark.concept.candidates import CandidateIndex
from trendin.spark.concept.dictionary import Concept, Dictionary, Expression
from trendin.spark.concept.judge import Question
from trendin.spark.concept.retrieval import CHANNELS, CandidateRetriever, RetrievalPolicy
from trendin.spark.concept.workflow import AutomationPolicy, run_workflow


class MemoryCache:
    def __init__(self):
        self.values = {}

    def cached_judgement(self, **key):
        return self.values.get(tuple(key.values()))

    def cache_judgement(self, *, verdict, **key):
        self.values[tuple(key.values())] = dict(verdict)


class FakeClient:
    model = "test-model"

    def __init__(self, answers):
        self.answers = iter(answers)
        self.calls = 0

    def chat(self, _messages, *, max_tokens=1200):
        self.calls += 1
        answer = next(self.answers)
        if isinstance(answer, Exception):
            raise answer
        return answer


def _retriever():
    dictionary = Dictionary(
        (
            Concept(1, "sneakers", "footwear"),
            Concept(2, "Chanel", "brand"),
        ),
        (
            Expression(11, 1, "en", "sneakers"),
            Expression(12, 2, "en", "chanel"),
        ),
    )
    policy = RetrievalPolicy(
        top_k=5,
        min_combined_score=0.5,
        category_mismatch_factor=0.25,
        consensus_bonus=0.05,
        thresholds={name: 0.5 for name in CHANNELS},
        weights={name: 1.0 for name in CHANNELS},
    )
    return CandidateRetriever(dictionary, CandidateIndex(dictionary), policy)


POLICY = AutomationPolicy(True, "test-model", 20, 10, True)


def test_duplicate_expression_is_batched_once_and_cached_on_rerun():
    questions = [
        Question(1, "ko", "스니커즈", 6, "새 스니커즈"),
        Question(2, "ko", "스니커즈", 9, "중복 문맥"),
    ]
    cache = MemoryCache()
    client = FakeClient(
        [
            json.dumps({"r": [{"i": 1, "en": "sneakers", "cat": "footwear"}]}),
            json.dumps({"concept_id": 1}),
        ]
    )
    first = run_workflow(
        questions, client=client, cache=cache, retriever=_retriever(), policy=POLICY
    )
    assert client.calls == 2
    assert [link.concept_id for link in first.links] == [1]

    rerun_client = FakeClient([])
    second = run_workflow(
        questions, client=rerun_client, cache=cache, retriever=_retriever(), policy=POLICY
    )
    assert rerun_client.calls == 0
    assert [link.concept_id for link in second.links] == [1]


def test_vector_failure_is_isolated_and_lexical_candidates_continue():
    questions = [
        Question(1, "ko", "스니커즈", 8, "스니커즈 룩"),
        Question(2, "ko", "샤넬", 7, "샤넬 컬렉션"),
    ]
    client = FakeClient(
        [
            json.dumps(
                {"r": [
                    {"i": 1, "en": "sneakers", "cat": "footwear"},
                    {"i": 2, "en": "Chanel", "cat": "brand"},
                ]}
            ),
            json.dumps({"concept_id": 1}),
            json.dumps({"concept_id": 2}),
        ]
    )

    def broken_vectors(original, _english):
        if original == "스니커즈":
            raise RuntimeError("encoder failed")
        return {}

    result = run_workflow(
        questions,
        client=client,
        cache=MemoryCache(),
        retriever=_retriever(),
        policy=POLICY,
        vector_search=broken_vectors,
    )
    assert {link.concept_id for link in result.links} == {1, 2}
    first = next(link for link in result.links if link.concept_id == 1)
    assert "encoder failed" in first.evidence["vector_error"]


def test_one_failed_name_is_deferred_without_losing_the_other():
    questions = [
        Question(1, "ko", "스니커즈", 8, "스니커즈 룩"),
        Question(2, "ko", "알수없음", 7, "문맥"),
    ]
    client = FakeClient(
        [
            RuntimeError("batch failed"),
            json.dumps({"r": [{"i": 1, "en": "sneakers", "cat": "footwear"}]}),
            RuntimeError("single failed"),
            json.dumps({"concept_id": 1}),
        ]
    )
    result = run_workflow(
        questions,
        client=client,
        cache=MemoryCache(),
        retriever=_retriever(),
        policy=POLICY,
    )
    assert [link.concept_id for link in result.links] == [1]
    assert [(item.normalized, item.reason) for item in result.deferred] == [
        ("알수없음", "NAME_FAILED")
    ]
