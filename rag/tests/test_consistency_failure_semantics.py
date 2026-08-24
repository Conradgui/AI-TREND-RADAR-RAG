"""Consistency checks must fail closed when a backend cannot be inspected."""

import unittest

from rag.consistency import check_consistency


class _FailingDriver:
    async def execute_query(self, cypher, **params):
        raise RuntimeError("Neo4j unavailable")


class _ReadyCollection:
    def get(self, include=None):
        return {"metadatas": [{"date": "2026-08-10"}]}


class _FailingCollection:
    def get(self, include=None):
        raise RuntimeError("Chroma unavailable")


class _VectorStore:
    def __init__(self, collection):
        self.collection = collection


class ConsistencyFailureSemanticsTests(unittest.IsolatedAsyncioTestCase):
    async def test_neo4j_failure_is_error_not_consistent(self):
        report = await check_consistency(_FailingDriver(), _VectorStore(_ReadyCollection()))

        self.assertEqual(report.status, "error")
        self.assertEqual(report.error_code, "neo4j_unavailable")
        self.assertFalse(report.is_consistent)

    async def test_both_backend_failures_cannot_produce_false_green(self):
        report = await check_consistency(_FailingDriver(), _VectorStore(_FailingCollection()))

        self.assertEqual(report.status, "error")
        self.assertEqual(report.error_code, "multiple_backends_unavailable")
        self.assertFalse(report.is_consistent)
        self.assertEqual(report.neo4j_dates, [])
        self.assertEqual(report.chroma_dates, [])


if __name__ == "__main__":
    unittest.main()
