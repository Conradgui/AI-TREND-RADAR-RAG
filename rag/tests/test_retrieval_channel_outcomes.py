"""Regression tests for channel-aware retrieval failure semantics."""

import unittest

from rag.citations import retrieve_citations_with_status
from rag.retriever.hybrid import HybridRetriever, RetrievalFailure


class _ReadyVector:
    def search(self, query, k=5, where=None):
        return [
            {
                "text": "OpenAI release evidence",
                "metadata": {
                    "date": "2026-08-10",
                    "source": "OpenAI",
                    "title": "Release",
                    "citation_id": "release-1",
                },
                "distance": 0.1,
            }
        ]


class _EmptyVector:
    def search(self, query, k=5, where=None):
        return []


class _FailingVector:
    def search(self, query, k=5, where=None):
        raise RuntimeError("Error finding id")


class _EmptyGraph:
    async def execute_query(self, cypher, **params):
        return []


class _FailingGraph:
    async def execute_query(self, cypher, **params):
        raise RuntimeError("Neo4j unavailable")


class RetrievalChannelOutcomeTests(unittest.IsolatedAsyncioTestCase):
    async def test_graph_failure_with_ready_vector_is_degraded_not_empty(self):
        retriever = HybridRetriever(_ReadyVector(), _FailingGraph())

        outcome = await retriever.search_with_status("OpenAI", k=5)

        self.assertEqual(outcome.status, "degraded")
        self.assertEqual(outcome.channels["vector"].status, "success")
        self.assertEqual(outcome.channels["graph"].status, "error")
        self.assertEqual(len(outcome.chunks), 1)

        citations = await retrieve_citations_with_status(retriever, "OpenAI", k=5)
        self.assertEqual(citations.status, "degraded")
        self.assertEqual(len(citations.citations), 1)
        self.assertEqual(citations.channel_status["graph"], "error")

    async def test_vector_failure_with_empty_graph_is_degraded_not_empty(self):
        retriever = HybridRetriever(_FailingVector(), _EmptyGraph())

        outcome = await retriever.search_with_status("最近有什么热门趋势？", k=5)

        self.assertEqual(outcome.status, "degraded")
        self.assertEqual(outcome.channels["vector"].status, "error")
        self.assertEqual(outcome.channels["graph"].status, "empty")
        self.assertEqual(outcome.chunks, [])

        citations = await retrieve_citations_with_status(retriever, "最近有什么热门趋势？", k=5)
        self.assertEqual(citations.status, "degraded")
        self.assertEqual(citations.citations, [])
        self.assertEqual(citations.channel_status["vector"], "error")

    async def test_all_channels_fail_is_error_and_legacy_search_raises(self):
        retriever = HybridRetriever(_FailingVector(), _FailingGraph())

        outcome = await retriever.search_with_status("RAG", k=5)

        self.assertEqual(outcome.status, "error")
        self.assertEqual(outcome.error_code, "all_channels_failed")
        with self.assertRaises(RetrievalFailure):
            await retriever.search("RAG", k=5)

    async def test_required_graph_failure_is_partial_error_and_keeps_text_clues(self):
        retriever = HybridRetriever(_ReadyVector(), _FailingGraph())

        outcome = await retriever.search_with_status(
            "OpenAI 与 Apple 有什么跨日关联？",
            k=5,
            graph_requirement="required",
        )

        self.assertEqual(outcome.status, "partial_error")
        self.assertEqual(outcome.error_code, "required_graph_unavailable")
        self.assertEqual(len(outcome.chunks), 1)

        citations = await retrieve_citations_with_status(
            retriever,
            "OpenAI 与 Apple 有什么跨日关联？",
            k=5,
            graph_requirement="required",
        )
        self.assertEqual(citations.status, "partial_error")
        self.assertEqual(citations.error_code, "required_graph_unavailable")
        self.assertEqual(len(citations.citations), 1)

    async def test_disabled_graph_is_not_called_for_plain_content_question(self):
        retriever = HybridRetriever(_ReadyVector(), _FailingGraph())

        outcome = await retriever.search_with_status(
            "Apple Is Getting This Wrong 讲了什么？",
            k=5,
            graph_requirement="disabled",
        )

        self.assertEqual(outcome.status, "ready")
        self.assertEqual(outcome.channels["graph"].status, "disabled")


if __name__ == "__main__":
    unittest.main()
