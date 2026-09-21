"""The production concept input must carry article context into unmapped records."""

from __future__ import annotations

import unittest
from contextlib import contextmanager
from unittest.mock import patch

from trendin.spark.concept.dictionary import Dictionary
from trendin.spark.concept.mapping import map_article
from trendin.spark.io.concepts import OCCURRENCES_SQL, ConceptSink


class FakeCursor:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params):
        assert sql == OCCURRENCES_SQL
        assert params == ("fashion", 30)

    def fetchall(self):
        return [(101, "バレエコア", "バレエコアの新しい着こなし"),
                (101, "Brady", "バレエコアの新しい着こなし")]


class FakeConnection:
    def cursor(self):
        return FakeCursor()


@contextmanager
def fake_connection(_config):
    yield FakeConnection()


class OccurrencesContextTest(unittest.TestCase):
    def test_article_title_reaches_unmapped_context(self) -> None:
        with patch("trendin.spark.io.concepts.jdbc.connection", fake_connection):
            grouped = ConceptSink(object()).occurrences(domain="fashion", window_days=30)
        self.assertEqual(len(grouped[101]), 2)
        result = map_article(101, None, grouped[101], Dictionary((), ()))
        self.assertEqual({item.context for item in result.unmapped},
                         {"バレエコアの新しい着こなし"})


if __name__ == "__main__":
    unittest.main()
