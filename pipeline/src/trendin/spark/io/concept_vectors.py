"""pgvector storage and exact Top K retrieval for concept expressions."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from trendin.spark.common.config import Config
from trendin.spark.concept.embedding import DIMENSIONS, E5Encoder
from trendin.spark.io import jdbc

TABLE = "pl_concept_embedding"
DDL = f"""
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS {TABLE} (
    expression_id bigint PRIMARY KEY REFERENCES pl_concept_expression(id) ON DELETE CASCADE,
    model_id text NOT NULL,
    input_hash text NOT NULL,
    embedding vector({DIMENSIONS}) NOT NULL,
    embedded_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS pl_concept_embedding_model_idx ON {TABLE} (model_id);
"""

EXPRESSIONS_SQL = """
SELECT e.id, e.normalized
  FROM pl_concept_expression e
  JOIN pl_concept c ON c.id = e.concept_id
 WHERE e.status = 'ACTIVE' AND c.status = 'ACTIVE'
 ORDER BY e.id
"""

SEARCH_SQL = f"""
SELECT c.id, c.canonical_name, c.category, min(v.embedding <=> %s::vector) AS distance
  FROM {TABLE} v
  JOIN pl_concept_expression e ON e.id = v.expression_id
  JOIN pl_concept c ON c.id = e.concept_id
 WHERE v.model_id = %s AND NOT (e.id = ANY(%s))
   AND e.status = 'ACTIVE' AND c.status = 'ACTIVE'
 GROUP BY c.id, c.canonical_name, c.category
 ORDER BY distance, c.id
 LIMIT %s
"""

COVERAGE_SQL = f"""
SELECT e.normalized, v.input_hash
  FROM pl_concept_expression e
  JOIN pl_concept c ON c.id = e.concept_id
  LEFT JOIN {TABLE} v ON v.expression_id = e.id AND v.model_id = %s
 WHERE e.status = 'ACTIVE' AND c.status = 'ACTIVE'
"""


def vector_literal(values: list[float]) -> str:
    if len(values) != DIMENSIONS:
        raise ValueError(f"expected {DIMENSIONS} dimensions, got {len(values)}")
    return "[" + ",".join(format(value, ".8g") for value in values) + "]"


def input_hash(normalized: str) -> str:
    return hashlib.sha256(("passage: " + normalized).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class VectorHit:
    concept_id: int
    name: str
    category: str
    similarity: float


class ConceptVectorStore:
    def __init__(self, config: Config) -> None:
        self.config = config

    def ensure_schema(self) -> None:
        with jdbc.connection(self.config) as conn, conn.cursor() as cur:
            cur.execute(DDL)

    def coverage(self, model_id: str) -> tuple[int, int]:
        with jdbc.connection(self.config) as conn, conn.cursor() as cur:
            cur.execute(COVERAGE_SQL, (model_id,))
            rows = cur.fetchall()
        current = sum(
            digest == input_hash(str(normalized))
            for normalized, digest in rows
            if digest is not None
        )
        return len(rows), current

    def sync(self, encoder: E5Encoder, *, batch_size: int = 32) -> tuple[int, int]:
        """Embed only new or changed active expressions. A batch is one transaction."""
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        from psycopg2.extras import execute_values

        with jdbc.connection(self.config) as conn, conn.cursor() as cur:
            cur.execute(EXPRESSIONS_SQL)
            expressions = [(int(eid), str(normalized)) for eid, normalized in cur.fetchall()]
            cur.execute(
                f"SELECT expression_id, input_hash FROM {TABLE} WHERE model_id = %s",
                (encoder.model_id,),
            )
            stored = {int(eid): digest for eid, digest in cur.fetchall()}
        pending = []
        for eid, value in expressions:
            digest = input_hash(value)
            if stored.get(eid) != digest:
                pending.append((eid, value, digest))
        for offset in range(0, len(pending), batch_size):
            batch = pending[offset : offset + batch_size]
            vectors = encoder.encode(
                [value for _, value, _ in batch], query=False, batch_size=batch_size
            )
            rows = [
                (eid, encoder.model_id, digest, vector_literal(vector))
                for (eid, _, digest), vector in zip(batch, vectors, strict=True)
            ]
            with jdbc.connection(self.config) as conn, conn.cursor() as cur:
                execute_values(
                    cur,
                    f"""
                        INSERT INTO {TABLE} (expression_id, model_id, input_hash, embedding)
                        VALUES %s
                        ON CONFLICT (expression_id) DO UPDATE SET
                            model_id = EXCLUDED.model_id,
                            input_hash = EXCLUDED.input_hash,
                            embedding = EXCLUDED.embedding,
                            embedded_at = now()
                    """,
                    rows,
                    template="(%s, %s, %s, %s::vector)",
                )
        return len(expressions), len(pending)

    def search(
        self, values: list[float], *, model_id: str, limit: int = 5,
        exclude_expression_ids: frozenset[int] = frozenset(),
    ) -> tuple[VectorHit, ...]:
        if limit < 1:
            raise ValueError("limit must be positive")
        with jdbc.connection(self.config) as conn, conn.cursor() as cur:
            cur.execute(
                SEARCH_SQL,
                (vector_literal(values), model_id, sorted(exclude_expression_ids), limit),
            )
            rows = cur.fetchall()
        return tuple(
            VectorHit(int(cid), str(name), str(category), round(1.0 - float(distance), 4))
            for cid, name, category, distance in rows
        )
