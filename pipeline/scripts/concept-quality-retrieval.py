#!/usr/bin/env python
"""Create reproducible retrieval predictions for the concept quality gold set.

Without ``--profile`` this builds a deterministic dictionary from repository seed files and
compares lexical retrieval using the original expression with original+English-name retrieval.
With ``--profile`` it reads the live dictionary; ``--vectors`` additionally runs the stored E5
vectors. All database work is read-only. No LLM is called and every decision is therefore DEFER.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trendin.spark.common.config import load_config  # noqa: E402
from trendin.spark.concept.candidates import CandidateIndex  # noqa: E402
from trendin.spark.concept.dictionary import Concept, Dictionary, Expression  # noqa: E402
from trendin.spark.concept.embedding import E5Encoder  # noqa: E402
from trendin.spark.concept.evaluation import load_gold  # noqa: E402
from trendin.spark.concept.normalize import concept_key  # noqa: E402
from trendin.spark.concept.retrieval import CandidateRetriever, RetrievalPolicy  # noqa: E402
from trendin.spark.concept.seed import load_seed_dir  # noqa: E402
from trendin.spark.io.concept_vectors import ConceptVectorStore  # noqa: E402
from trendin.spark.io.concepts import ConceptSink  # noqa: E402

DEFAULT_GOLD = ROOT / "spark" / "tests" / "fixtures" / "concept" / "quality-gold-v1.jsonl"
DEFAULT_SEEDS = ROOT / "spark" / "conf" / "concepts"


def main(argv: list[str] | None = None) -> int:
    _utf8_console()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--seed-dir", type=Path, default=DEFAULT_SEEDS)
    parser.add_argument("--profile", help="load the DB dictionary instead of repository seeds")
    parser.add_argument(
        "--vectors", action="store_true", help="query E5/pgvector; requires --profile"
    )
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.top_k < 1:
        parser.error("--top-k must be positive")
    if args.vectors and not args.profile:
        parser.error("--vectors requires --profile")

    gold = load_gold(args.gold)
    if args.profile:
        config = load_config(args.profile)
        dictionary = ConceptSink(config).load_dictionary()
        policy = replace(RetrievalPolicy.from_config(config), top_k=args.top_k)
    else:
        config = None
        dictionary = seed_dictionary(args.seed_dir)
        policy = RetrievalPolicy(
            top_k=args.top_k,
            min_combined_score=0.55, meaningful_candidate_threshold=0.5,
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
    retriever = CandidateRetriever(dictionary, CandidateIndex(dictionary), policy)
    vector_store = ConceptVectorStore(config) if args.vectors else None
    encoder = E5Encoder() if args.vectors else None

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as stream:
        for case in gold:
            excluded = frozenset(
                expression.expression_id
                for expression in dictionary.expressions()
                if expression.normalized == concept_key(case.surface)
            )
            vector_hits = {}
            vector_ms = 0.0
            if encoder is not None and vector_store is not None:
                values = [case.surface]
                labels = ["original"]
                if case.english_name:
                    values.append(case.english_name)
                    labels.append("english")
                started = time.perf_counter()
                vectors = encoder.encode(values, query=True)
                for label, vector in zip(labels, vectors, strict=True):
                    vector_hits[label] = vector_store.search(
                        vector,
                        model_id=encoder.model_id,
                        limit=args.top_k,
                        exclude_expression_ids=excluded,
                    )
                vector_ms = (time.perf_counter() - started) * 1000

                vector_experiments = [
                    ("vector-original", (vector_hits["original"],)),
                    (
                        "vector-original+english",
                        (vector_hits["original"], vector_hits["english"]),
                    ),
                ]
                for name, groups in vector_experiments:
                    candidates = _merge_vector_hits(groups, args.top_k)
                    _write_prediction(stream, case.case_id, name, candidates, vector_ms)

            experiments = [
                ("lexical-original", None, {}, case.category),
                ("lexical-original+english", case.english_name, {}, case.category),
                ("lexical-original+english-no-category", case.english_name, {}, None),
            ]
            if args.vectors:
                experiments.extend(
                    [
                        (
                            "combined-original",
                            None,
                            {"original": vector_hits["original"]},
                            case.category,
                        ),
                        (
                            "combined-original+english",
                            case.english_name,
                            vector_hits,
                            case.category,
                        ),
                        (
                            "combined-original+english-no-category",
                            case.english_name,
                            vector_hits,
                            None,
                        ),
                    ]
                )
            for name, english_name, vectors, category in experiments:
                started = time.perf_counter()
                result = retriever.retrieve(
                    original=case.surface,
                    lang=case.language,
                    english_name=english_name,
                    category=category,
                    vector_hits=vectors,
                    exclude_expression_ids=excluded,
                )
                elapsed = (time.perf_counter() - started) * 1000
                if vectors:
                    elapsed += vector_ms
                candidates = [
                    {
                        "name": item.name,
                        "category": item.category,
                        "score": item.score,
                        "channels": [evidence.channel for evidence in item.evidence],
                    }
                    for item in result.candidates
                ]
                _write_prediction(stream, case.case_id, name, candidates, elapsed)
    return 0


def _utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


def _merge_vector_hits(groups, limit: int) -> list[dict]:
    found = {}
    for group in groups:
        for hit in group:
            current = found.get(hit.concept_id)
            if current is None or hit.similarity > current.similarity:
                found[hit.concept_id] = hit
    ranked = sorted(found.values(), key=lambda hit: (-hit.similarity, hit.concept_id))[:limit]
    return [
        {
            "name": hit.name,
            "category": hit.category,
            "score": hit.similarity,
            "channels": ["vector"],
        }
        for hit in ranked
    ]


def _write_prediction(stream, case_id: str, experiment: str, candidates, elapsed_ms: float) -> None:
    row = {
        "case_id": case_id,
        "experiment": experiment,
        "decision": "DEFER",
        "concept": None,
        "category": None,
        "candidates": candidates,
        "elapsed_ms": round(elapsed_ms, 3),
        "llm_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
    }
    stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def seed_dictionary(seed_dir: Path) -> Dictionary:
    """Merge seed files as the DB uniqueness constraints would, using stable local ids."""
    seeds = load_seed_dir(seed_dir)
    identities = sorted({(seed.canonical_name.casefold(), seed.category) for seed in seeds})
    concept_ids = {identity: index for index, identity in enumerate(identities, start=1)}
    concepts = [
        Concept(index, canonical, category)
        for index, (canonical, category) in enumerate(identities, start=1)
    ]
    expression_rows: set[tuple[int, str, str]] = set()
    for seed in seeds:
        concept_id = concept_ids[(seed.canonical_name.casefold(), seed.category)]
        expression_rows.update(
            (concept_id, expression.lang, expression.normalized)
            for expression in seed.expressions
        )
    expressions = [
        Expression(index, concept_id, lang, normalized)
        for index, (concept_id, lang, normalized) in enumerate(
            sorted(expression_rows), start=1
        )
    ]
    return Dictionary(concepts, expressions)


if __name__ == "__main__":
    raise SystemExit(main())
