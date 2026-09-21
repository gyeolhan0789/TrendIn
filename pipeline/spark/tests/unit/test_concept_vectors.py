"""Vector queries are parameterized and return one result per concept."""

from __future__ import annotations

import unittest
from contextlib import contextmanager
from unittest.mock import patch

from trendin.spark.concept.embedding import DIMENSIONS, model_key
from trendin.spark.io.concept_vectors import (
    COVERAGE_SQL,
    SEARCH_SQL,
    ConceptVectorStore,
    input_hash,
    vector_literal,
)


class FakeCursor:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params):
        assert sql == SEARCH_SQL
        vector, model, limit = params
        assert vector.startswith("[") and vector.endswith("]")
        assert model == model_key()
        assert limit == 5

    def fetchall(self):
        return [(11, "sneakers", "footwear", 0.12),
                (19, "boots", "footwear", 0.19)]


class CoverageCursor:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params):
        assert sql == COVERAGE_SQL
        assert params == (model_key(),)

    def fetchall(self):
        return [
            ("boots", input_hash("boots")),
            ("dress", "stale"),
            ("coat", None),
        ]


class FakeConnection:
    def __init__(self, cursor_type=FakeCursor):
        self.cursor_type = cursor_type

    def cursor(self):
        return self.cursor_type()


@contextmanager
def fake_connection(_config):
    yield FakeConnection()


@contextmanager
def coverage_connection(_config):
    yield FakeConnection(CoverageCursor)


class VectorStoreTest(unittest.TestCase):
    def test_search_translates_distance_to_similarity(self) -> None:
        with patch("trendin.spark.io.concept_vectors.jdbc.connection", fake_connection):
            hits = ConceptVectorStore(object()).search([0.1] * DIMENSIONS,
                                                       model_id=model_key(), limit=5)
        self.assertEqual([(hit.concept_id, hit.similarity) for hit in hits],
                         [(11, 0.88), (19, 0.81)])

    def test_wrong_dimension_is_rejected_before_query(self) -> None:
        with self.assertRaises(ValueError):
            vector_literal([0.1, 0.2])

    def test_coverage_rejects_missing_and_stale_embeddings(self) -> None:
        with patch("trendin.spark.io.concept_vectors.jdbc.connection", coverage_connection):
            coverage = ConceptVectorStore(object()).coverage(model_key())
        self.assertEqual(coverage, (3, 1))


if __name__ == "__main__":
    unittest.main()
