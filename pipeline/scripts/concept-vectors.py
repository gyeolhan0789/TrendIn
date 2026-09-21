#!/usr/bin/env python
"""Build the pgvector index for active concept expressions.

Run after the PostgreSQL image with pgvector is deployed and the concept tables exist:
  python scripts/concept-vectors.py --profile dev

This command enables the vector extension, creates pl_concept_embedding,
and embeds new/changed expressions.
It never changes concept identities or article mappings.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trendin.spark.common.config import load_config  # noqa: E402
from trendin.spark.concept.embedding import MODEL_ID, MODEL_REVISION, E5Encoder  # noqa: E402
from trendin.spark.io.concept_vectors import ConceptVectorStore  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="local")
    parser.add_argument("--model", default=MODEL_ID)
    parser.add_argument("--revision", default=MODEL_REVISION)
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()
    store = ConceptVectorStore(load_config(args.profile))
    store.ensure_schema()
    encoder = E5Encoder(args.model, args.revision)
    total, updated = store.sync(encoder, batch_size=args.batch_size)
    print(f"개념 표현 {total:,}개 중 임베딩 신규·변경 {updated:,}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
