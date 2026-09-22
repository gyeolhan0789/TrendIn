from __future__ import annotations

import json

from trendin.spark.concept.candidates import CandidateIndex
from trendin.spark.concept.dictionary import Concept, Dictionary, Expression
from trendin.spark.concept.judge import Question
from trendin.spark.concept.retrieval import CHANNELS, CandidateRetriever, RetrievalPolicy
from trendin.spark.concept.workflow import (
    DEFER,
    EXCLUDE,
    LINK,
    NEW_CONCEPT,
    AutomationPolicy,
    reusable,
    run_workflow,
)


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
        meaningful_candidate_threshold=0.5,
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


def test_네_결론이_모두_기록으로_남는다():
    """`LINK` 만 남기면 나머지 셋은 다음 회차에 다시 판정된다."""
    questions = [
        Question(1, "ko", "스니커즈", 6, "새 스니커즈"),
        Question(2, "ko", "요즘", 4, "요즘 유행"),
        Question(3, "ko", "제니", 5, "제니가 입었다"),
    ]
    client = FakeClient(
        [
            json.dumps(
                {
                    "r": [
                        {"i": 1, "en": "sneakers", "cat": "footwear"},
                        {"i": 2, "en": "these days", "cat": "generic"},
                        {"i": 3, "en": "Jennie", "cat": "person"},
                    ]
                }
            ),
            json.dumps({"concept_id": 1}),
        ]
    )
    result = run_workflow(
        questions, client=client, cache=MemoryCache(), retriever=_retriever(), policy=POLICY
    )
    by_key = {item.normalized: item.decision for item in result.decisions}
    assert by_key == {"스니커즈": LINK, "요즘": EXCLUDE, "제니": NEW_CONCEPT}


def test_일시적_실패는_기록하지_않는다():
    """이름 판정이 깨진 것은 결론이 아니다 — 남기면 그 표현이 영원히 유보로 굳는다."""
    questions = [Question(1, "ko", "스니커즈", 6, "새 스니커즈")]
    client = FakeClient(["JSON 이 아님", "JSON 이 아님"])
    result = run_workflow(
        questions, client=client, cache=MemoryCache(), retriever=_retriever(), policy=POLICY
    )
    assert [item.reason for item in result.deferred] == ["NAME_FAILED"]
    assert result.decisions == ()


def test_이미_결론_난_표현은_묻지_않는다():
    questions = [Question(1, "ko", "요즘", 4, "요즘 유행")]
    client = FakeClient([])
    result = run_workflow(
        questions,
        client=client,
        cache=MemoryCache(),
        retriever=_retriever(),
        policy=POLICY,
        settled={("ko", "요즘"): EXCLUDE},
    )
    assert client.calls == 0
    assert result.reused == (("ko", "요즘"),)
    assert result.decisions == ()


def test_판정_재사용_규칙():
    same = {"prompt_version": "name-v2", "dictionary_version": 4}
    # 사전 내용에 기대지 않는 결론은 사전이 자라도 그대로 쓴다.
    assert reusable(EXCLUDE, "name-v2", 1, **same) is True
    assert reusable(NEW_CONCEPT, "name-v2", 1, **same) is True
    # 유보는 사전이 자라면 없던 후보가 생기므로 다시 본다.
    assert reusable(DEFER, "name-v2", 4, **same) is True
    assert reusable(DEFER, "name-v2", 3, **same) is False
    # 프롬프트가 바뀌면 모델 판정은 믿지 않는다.
    assert reusable(EXCLUDE, "name-v1", 4, **same) is False
    # 사람 판정은 프롬프트 버전이 비어 있고 더 오래 간다.
    assert reusable(EXCLUDE, None, 1, **same) is True
    assert reusable(DEFER, None, 1, **same) is True
    # 이어진 것은 애초에 미등록이 아니다.
    assert reusable(LINK, "name-v2", 4, **same) is False


def test_매체는_일반어와_같이_세지_않는다():
    """잡지가 `generic` 과 `brand` 사이에서 흔들리던 것을 자기 칸으로 보냈다.

    2026-09-22 같은 입력 두 번에 어긋난 4건이 전부 잡지였다. 분류를 준 뒤 100% 로 붙었다.
    """
    questions = [Question(1, "la", "vogue italia", 9, "Vogue Italia 가 표지를 공개했다")]
    client = FakeClient([json.dumps({"r": [{"i": 1, "en": "Vogue Italia", "cat": "media"}]})])
    result = run_workflow(
        questions, client=client, cache=MemoryCache(), retriever=_retriever(), policy=POLICY
    )
    assert [item.decision for item in result.decisions] == [EXCLUDE]
    assert [item.reason for item in result.deferred] == ["UNCOUNTED"]
    # 후보 검색까지 가지 않는다 — 셀 대상이 아니면 이을 개념도 없다.
    assert client.calls == 1

