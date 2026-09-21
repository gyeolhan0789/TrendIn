"""Verification must fail closed before a vector suggestion can be written."""

from __future__ import annotations

import json
import unittest
from types import SimpleNamespace

from trendin.spark.concept.judge import Verdict
from trendin.spark.concept.vector_judge import (
    eligible_choice,
    merge_hits,
    messages,
    parse_choice,
    verification_slot_available,
)


def hit(concept_id: int, category: str, similarity: float):
    return SimpleNamespace(concept_id=concept_id, name=f"concept-{concept_id}",
                           category=category, similarity=similarity)


class VectorJudgeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.verdict = Verdict("ko", "디올", "Dior", "brand")
        self.hits = (hit(10, "brand", 0.91), hit(20, "designer", 0.89))

    def test_prompt_carries_context_and_candidates(self) -> None:
        prompt = messages(self.verdict, self.hits, context="디올의 새 가방 공개")
        body = json.loads(prompt[1]["content"])
        self.assertEqual(body["context"], "디올의 새 가방 공개")
        self.assertEqual([item["concept_id"] for item in body["candidates"]], [10, 20])

    def test_only_supplied_integer_id_is_accepted(self) -> None:
        self.assertEqual(parse_choice('{"concept_id":10}', self.hits), 10)
        self.assertIsNone(parse_choice('{"concept_id":null}', self.hits))
        for answer in ('{"concept_id":999}', '{"concept_id":true}', '{"concept_id":"10"}',
                       '{"other":10}', 'not json'):
            with self.subTest(answer=answer), self.assertRaises(ValueError):
                parse_choice(answer, self.hits)

    def test_category_and_similarity_gate_writes(self) -> None:
        self.assertEqual(eligible_choice(self.verdict, self.hits, 10,
                                         min_similarity=0.9, context="디올 가방"), 10)
        self.assertIsNone(eligible_choice(self.verdict, self.hits, 20,
                                          min_similarity=0.8, context="디올 가방"))
        self.assertIsNone(eligible_choice(self.verdict, self.hits, 10,
                                          min_similarity=0.95, context="디올 가방"))
        self.assertIsNone(eligible_choice(self.verdict, self.hits, 10,
                                          min_similarity=None, context="디올 가방"))
        self.assertIsNone(eligible_choice(self.verdict, self.hits, 10,
                                          min_similarity=0.9, context=None))

    def test_original_and_english_search_collapse_by_concept(self) -> None:
        merged = merge_hits(((hit(10, "brand", 0.84), hit(20, "designer", 0.8)),
                             (hit(10, "brand", 0.92), hit(30, "brand", 0.88))), limit=2)
        self.assertEqual([(item.concept_id, item.similarity) for item in merged],
                         [(10, 0.92), (30, 0.88)])

    def test_verification_reserves_remaining_name_batches(self) -> None:
        self.assertFalse(verification_slot_available(1, 2, 3))
        self.assertTrue(verification_slot_available(1, 2, 4))


if __name__ == "__main__":
    unittest.main()
