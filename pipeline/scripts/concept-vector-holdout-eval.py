#!/usr/bin/env python
"""Read-only recall@K test: hide one known expression, then retrieve its concept.

This checks whether vector search can recover an existing multilingual alias without
the trivial self-match. It is a proxy task, not accuracy on newly crawled terms.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trendin.spark.common.config import load_config  # noqa: E402
from trendin.spark.concept.candidates import CandidateIndex  # noqa: E402
from trendin.spark.concept.embedding import E5Encoder  # noqa: E402
from trendin.spark.io import jdbc  # noqa: E402
from trendin.spark.io.concept_vectors import vector_literal  # noqa: E402
from trendin.spark.io.concepts import ConceptSink  # noqa: E402

LANGUAGES = ("ko", "ja", "it", "fr")
SAMPLE_SQL = """
WITH eligible AS (
    SELECT e.id, e.concept_id, e.lang, e.normalized, c.canonical_name,
           row_number() OVER (PARTITION BY e.lang ORDER BY md5(e.id::text)) AS rn
      FROM pl_concept_expression e
      JOIN pl_concept c ON c.id = e.concept_id
     WHERE e.status = 'ACTIVE' AND c.status = 'ACTIVE' AND e.lang = ANY(%s)
       AND EXISTS (
           SELECT 1 FROM pl_concept_expression other
            WHERE other.concept_id = e.concept_id AND other.id <> e.id
              AND other.status = 'ACTIVE'
       )
)
SELECT id, concept_id, lang, normalized, canonical_name
  FROM eligible WHERE rn <= %s ORDER BY lang, rn
"""
SEARCH_SQL = """
SELECT c.id, c.canonical_name, min(v.embedding <=> %s::vector) AS distance
  FROM pl_concept_embedding v
  JOIN pl_concept_expression e ON e.id = v.expression_id
  JOIN pl_concept c ON c.id = e.concept_id
 WHERE v.model_id = %s AND e.id <> %s AND e.normalized <> %s
   AND e.status = 'ACTIVE' AND c.status = 'ACTIVE'
 GROUP BY c.id, c.canonical_name
 ORDER BY distance, c.id
 LIMIT %s
"""


def identity_key(value: str) -> str:
    return "".join(char.casefold() for char in value if char.isalnum())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="dev")
    parser.add_argument("--per-language", type=int, default=30)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--examples", type=int, default=4)
    args = parser.parse_args()
    if min(args.per_language, args.top_k) < 1 or args.examples < 0:
        parser.error("per-language and top-k must be positive; examples nonnegative")

    config = load_config(args.profile)
    lexical_index = CandidateIndex(ConceptSink(config).load_dictionary())
    encoder = E5Encoder()
    with jdbc.connection(config) as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute(SAMPLE_SQL, (list(LANGUAGES), max(500, args.per_language * 10)))
        samples = []
        counts: dict[str, int] = defaultdict(int)
        for row in cur.fetchall():
            lang = str(row[2])
            if (counts[lang] < args.per_language
                    and identity_key(str(row[3])) != identity_key(str(row[4]))):
                samples.append(row)
                counts[lang] += 1
        vectors = encoder.encode([str(row[3]) for row in samples], query=True)
        result: dict[str, dict] = defaultdict(
            lambda: {"tested": 0, "recall_at_1": 0, "recall_at_k": 0,
                     "lexical_recall_at_k": 0, "either_recall_at_k": 0,
                     "hits": [], "misses": []}
        )
        for (eid, cid, lang, surface, name), values in zip(samples, vectors, strict=True):
            cur.execute(SEARCH_SQL, (
                vector_literal(values), encoder.model_id, int(eid), str(surface), args.top_k,
            ))
            hits = cur.fetchall()
            ids = [int(hit[0]) for hit in hits]
            rank = ids.index(int(cid)) + 1 if int(cid) in ids else None
            lexical_ids = {
                item.concept_id for item in lexical_index.generate(str(lang), str(surface),
                                                                     limit=args.top_k)
            }
            group = result[str(lang)]
            group["tested"] += 1
            group["recall_at_1"] += rank == 1
            group["recall_at_k"] += rank is not None
            group["lexical_recall_at_k"] += int(cid) in lexical_ids
            group["either_recall_at_k"] += rank is not None or int(cid) in lexical_ids
            key = "hits" if rank is not None else "misses"
            if len(group[key]) < args.examples:
                group[key].append({
                    "surface": str(surface), "expected": str(name), "rank": rank,
                    "top": str(hits[0][1]) if hits else None,
                })
    for lang in LANGUAGES:
        result.setdefault(lang, {"tested": 0, "recall_at_1": 0,
                                 "recall_at_k": 0, "lexical_recall_at_k": 0,
                                 "either_recall_at_k": 0, "hits": [], "misses": []})
    print(json.dumps({"top_k": args.top_k, "languages": result},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
