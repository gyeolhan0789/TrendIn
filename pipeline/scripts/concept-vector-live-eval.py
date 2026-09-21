#!/usr/bin/env python
"""Read-only, bounded multilingual retrieval benchmark on selected live candidates.

Run after concept-vectors.py has completed. This measures retrieval yield and latency,
not semantic accuracy: a labeled sample is needed for recall@K and false-link rates.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trendin.spark.common.config import load_config  # noqa: E402
from trendin.spark.concept.candidates import CandidateIndex  # noqa: E402
from trendin.spark.concept.embedding import MODEL_ID, MODEL_REVISION, E5Encoder  # noqa: E402
from trendin.spark.concept.normalize import concept_key, lang_of_surface  # noqa: E402
from trendin.spark.io import jdbc  # noqa: E402
from trendin.spark.io.concept_vectors import ConceptVectorStore  # noqa: E402
from trendin.spark.io.concepts import ConceptSink  # noqa: E402

COUNTRIES = ("KR", "JP", "IT", "FR")
SELECTED_SQL = """
SELECT source_country, surface, count(*) AS occurrences
  FROM pl_document_candidate
 WHERE selected AND domain = 'fashion'
   AND stat_date >= current_date - %s
   AND source_country = ANY(%s)
 GROUP BY source_country, surface
 ORDER BY source_country, occurrences DESC, surface
"""


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * fraction))]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="dev")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--per-country", type=int, default=30)
    parser.add_argument("--show-examples", type=int, default=5)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    if min(args.days, args.per_country, args.top_k) < 1 or args.show_examples < 0:
        parser.error("days, per-country and top-k must be positive; show-examples nonnegative")

    config = load_config(args.profile)
    dictionary = ConceptSink(config).load_dictionary()
    index = CandidateIndex(dictionary)
    store = ConceptVectorStore(config)
    encoder = E5Encoder(MODEL_ID, MODEL_REVISION)
    total, embedded = store.coverage(encoder.model_id)
    if not total or embedded != total:
        parser.error(f"vector coverage incomplete: {embedded}/{total}")

    with jdbc.connection(config) as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute(SELECTED_SQL, (args.days, list(COUNTRIES)))
        selected = cur.fetchall()

    distinct: dict[str, int] = defaultdict(int)
    unmapped: dict[str, int] = defaultdict(int)
    sample: dict[str, list[tuple[str, str, int]]] = defaultdict(list)
    for country, surface, occurrences in selected:
        country, surface = str(country), str(surface)
        distinct[country] += 1
        key = concept_key(surface)
        if not key:
            continue
        lang = lang_of_surface(surface, None)
        if dictionary.lookup(lang, key):
            continue
        unmapped[country] += 1
        if len(sample[country]) < args.per_country:
            sample[country].append((key, lang, int(occurrences)))

    output = {
        "active_expressions": total,
        "days": args.days,
        "top_k": args.top_k,
        "countries": {},
    }
    for country in COUNTRIES:
        items = sample[country]
        if not items:
            output["countries"][country] = {
                "selected_distinct": distinct[country], "unmapped_distinct": unmapped[country],
                "sampled": 0,
            }
            continue
        started = time.perf_counter()
        vectors = encoder.encode([key for key, _, _ in items], query=True)
        encode_ms = (time.perf_counter() - started) * 1000 / len(items)
        latencies, vector_only, lexical_found, examples = [], 0, 0, []
        for (key, lang, occurrences), values in zip(items, vectors, strict=True):
            lexical = index.generate(lang, key)
            lexical_found += bool(lexical)
            started = time.perf_counter()
            hits = store.search(values, model_id=encoder.model_id, limit=args.top_k)
            latencies.append((time.perf_counter() - started) * 1000)
            vector_only += bool(hits) and not lexical
            if len(examples) < args.show_examples:
                examples.append({
                    "surface": key, "occurrences": occurrences,
                    "lexical_candidates": len(lexical),
                    "vector_top": [
                        {"name": hit.name, "category": hit.category,
                         "similarity": hit.similarity}
                        for hit in hits[:3]
                    ],
                })
        output["countries"][country] = {
            "selected_distinct": distinct[country],
            "unmapped_distinct": unmapped[country],
            "sampled": len(items),
            "lexical_with_candidate": lexical_found,
            "vector_only": vector_only,
            "encode_ms_per_query": round(encode_ms, 2),
            "search_ms_p50": round(statistics.median(latencies), 2),
            "search_ms_p95": round(percentile(latencies, 0.95), 2),
            "search_ms_max": round(max(latencies), 2),
            "examples": examples,
        }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
