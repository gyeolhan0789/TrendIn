"""Verification must fail closed before a vector suggestion can be written."""

from __future__ import annotations

import json
import unittest
from types import SimpleNamespace

from trendin.spark.concept.judge import Verdict
from trendin.spark.concept.vector_judge import (
    competing_referent,
    eligible_choice,
    merge_hits,
    messages,
    parse_choice,
    rejection_reason,
    verification_slot_available,
)


def hit(concept_id: int, category: str, similarity: float):
    return SimpleNamespace(concept_id=concept_id, name=f"concept-{concept_id}",
                           category=category, similarity=similarity)


def named(concept_id: int, name: str, category: str, score: float, evidence: float | None = None):
    """검색기가 돌려주는 모양 — `score` 는 분류 감점 뒤, `evidence` 는 감점 전이다."""
    return SimpleNamespace(concept_id=concept_id, name=name, category=category,
                           similarity=score, evidence_score=score if evidence is None else evidence)


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
        self.assertEqual(parse_choice('{"concept_id":10}', self.hits).concept_id, 10)
        self.assertIsNone(parse_choice('{"concept_id":null}', self.hits).concept_id)
        for answer in ('{"concept_id":999}', '{"concept_id":true}', '{"concept_id":"10"}',
                       '{"other":10}', 'not json'):
            with self.subTest(answer=answer), self.assertRaises(ValueError):
                parse_choice(answer, self.hits)

    def test_없다와_모르겠다를_가른다(self) -> None:
        """둘을 같은 null 로 받으면 후보를 아무리 보여 줘도 답이 전부 유보로 쌓인다."""
        none = parse_choice('{"verdict":"none"}', self.hits)
        self.assertEqual((none.concept_id, none.exhausted), (None, True))

        unsure = parse_choice('{"verdict":"unsure"}', self.hits)
        self.assertEqual((unsure.concept_id, unsure.exhausted), (None, False))

        same = parse_choice('{"verdict":"same","concept_id":10}', self.hits)
        self.assertEqual((same.concept_id, same.exhausted), (10, False))

        # 옛 모양은 "모르겠다" 로 읽는다 — 없다고 단정하는 쪽이 더 위험하다.
        self.assertFalse(parse_choice('{"concept_id":null}', self.hits).exhausted)

    def test_없다는_유보가_아니라_신규_경로다(self) -> None:
        reason = rejection_reason(
            self.verdict, self.hits, parse_choice('{"verdict":"none"}', self.hits),
            min_similarity=0.9, context="디올 가방",
        )
        self.assertEqual(reason, "LLM_NONE")
        unsure = rejection_reason(
            self.verdict, self.hits, parse_choice('{"verdict":"unsure"}', self.hits),
            min_similarity=0.9, context="디올 가방",
        )
        self.assertEqual(unsure, "LLM_DEFER")

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

    def test_same_name_under_two_categories_is_never_written(self) -> None:
        """`Calvin Klein` 은 사전에 브랜드로도 사람으로도 있다. 분류 추측으로 가르지 않는다."""
        candidates = (named(10, "calvin klein", "brand", 0.86),
                      named(20, "calvin klein", "designer", 0.2125, evidence=0.85))
        verdict = Verdict("it", "calvin klein", "Calvin Klein", "brand")
        self.assertIsNotNone(competing_referent(candidates, candidates[0]))
        self.assertIsNone(eligible_choice(verdict, candidates, 10,
                                          min_similarity=0.55, context="런웨이에 섰다"))
        self.assertEqual(
            rejection_reason(verdict, candidates, 10, min_similarity=0.55, context="런웨이에 섰다"),
            "COMPETING_REFERENT",
        )

    def test_contained_name_counts_as_the_same_referent(self) -> None:
        """`Dior`(브랜드)와 `Christian Dior`(사람)은 이름이 겹친다."""
        candidates = (named(10, "dior", "brand", 0.85),
                      named(20, "christian dior", "designer", 0.2125, evidence=0.85))
        verdict = Verdict("ko", "dior", "Dior", "brand")
        self.assertIsNone(eligible_choice(verdict, candidates, 10,
                                          min_similarity=0.55, context="디올의 새 가방"))

    def test_stronger_evidence_buried_by_the_category_guess_blocks_the_write(self) -> None:
        """`maille` 은 `knit` 으로 불렸다. knitwear 증거가 fabric 보다 센데 분류 추측에 눌렸다."""
        candidates = (named(10, "fabric", "material", 0.7727),
                      named(20, "knitwear", "apparel", 0.25, evidence=1.0))
        verdict = Verdict("fr", "maille", "knit", "material")
        self.assertIsNone(eligible_choice(verdict, candidates, 10,
                                          min_similarity=0.55, context="maille fine"))

    def test_weak_mismatched_candidate_still_allows_the_write(self) -> None:
        """`stivali` 옆의 `hugo boss` 처럼 소리만 닮은 다른 분류는 막지 않는다."""
        candidates = (named(10, "boots", "footwear", 1.0),
                      named(20, "hugo boss", "brand", 0.2125, evidence=0.85))
        verdict = Verdict("it", "stivali", "boots", "footwear")
        self.assertIsNone(competing_referent(candidates, candidates[0]))
        self.assertEqual(eligible_choice(verdict, candidates, 10,
                                         min_similarity=0.55, context="stivali alti"), 10)

    def test_each_gate_reports_its_own_reason(self) -> None:
        context = "디올 가방"
        self.assertEqual(rejection_reason(self.verdict, self.hits, None,
                                          min_similarity=0.9, context=context), "LLM_DEFER")
        self.assertEqual(rejection_reason(self.verdict, self.hits, 10,
                                          min_similarity=None, context=context), "NO_THRESHOLD")
        self.assertEqual(rejection_reason(self.verdict, self.hits, 10,
                                          min_similarity=0.9, context=" "), "NO_CONTEXT")
        self.assertEqual(rejection_reason(self.verdict, self.hits, 20,
                                          min_similarity=0.8, context=context), "CATEGORY_MISMATCH")
        self.assertEqual(rejection_reason(self.verdict, self.hits, 10,
                                          min_similarity=0.95, context=context), "LOW_SCORE")
        self.assertIsNone(rejection_reason(self.verdict, self.hits, 10,
                                           min_similarity=0.9, context=context))

    def test_verification_reserves_remaining_name_batches(self) -> None:
        self.assertFalse(verification_slot_available(1, 2, 3))
        self.assertTrue(verification_slot_available(1, 2, 4))


if __name__ == "__main__":
    unittest.main()
