"""Tests for hybrid retriever parameter forwarding."""

import unittest

from rag.retriever.hybrid import HybridRetriever


class FakeVectorStore:
    def search(self, query, k=5, where=None):
        self.query = query
        self.k = k
        self.where = where
        return [
            {
                "text": "GitHub project evidence",
                "metadata": {"date": "2026-06-21", "source": "GitHub"},
                "distance": 0.2,
            }
        ]


class FakeNeo4jDriver:
    async def execute_query(self, cypher, **params):
        self.cypher = cypher
        self.params = params
        return []


class FakeNeo4jDriverWithHits:
    async def execute_query(self, cypher, **params):
        self.cypher = cypher
        self.params = params
        return [
            {
                "occurrenceId": "ATR-20260621-AGENT1",
                "topic": "Agentic RAG",
                "category": "AI Research",
                "totalScore": 88,
                "occurrenceUrl": "https://example.com/agentic-rag",
                "localUrl": "#2026-06-21/ai-topic-radar/item/ATR-20260621-AGENT1",
                "occurrenceSource": "GitHub Trending",
                "occurrenceSummary": "Occurrence summary",
                "occurrenceReason": "Worth tracking",
                "occurrenceEvidence": ["repo stars rising", "new agent workflow"],
                "date": "2026-06-21",
                "reportDate": "2026-06-21",
                "publicationDate": "2026-06-19",
                "publicationDateSource": "legacy_evidence",
                "observedAt": "2026-06-21",
                "effectiveDate": "2026-06-19",
                "effectiveDateBasis": "publication_date",
            }
        ]


class HybridRetrieverTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_forwards_metadata_filter_to_vector_store(self):
        vector = FakeVectorStore()
        neo4j = FakeNeo4jDriver()
        retriever = HybridRetriever(vector, neo4j)
        where = {"source": {"$in": ["GitHub", "GitHub Trending"]}}

        results = await retriever.search("GitHub AI tools", k=3, where=where)

        self.assertEqual(vector.query, "GitHub AI tools")
        self.assertEqual(vector.k, 3)
        self.assertEqual(vector.where, where)
        self.assertEqual(neo4j.params["query"], "GitHub AI tools")
        self.assertEqual(results[0].metadata["source"], "GitHub")

    async def test_graph_results_are_citation_ready(self):
        vector = FakeVectorStore()
        neo4j = FakeNeo4jDriverWithHits()
        retriever = HybridRetriever(vector, neo4j)

        results = await retriever.search("Agentic RAG", k=5)
        graph_result = [result for result in results if result.source == "graph"][0]

        self.assertIn("Observation", neo4j.cypher)
        self.assertIn("OBSERVED_ON", neo4j.cypher)
        self.assertEqual(graph_result.metadata["content_type"], "daily_observation")
        self.assertEqual(graph_result.metadata["date"], "2026-06-21")
        self.assertEqual(graph_result.metadata["publication_date"], "2026-06-19")
        self.assertEqual(graph_result.metadata["effective_date"], "2026-06-19")
        self.assertEqual(graph_result.metadata["source"], "GitHub Trending")
        self.assertEqual(graph_result.metadata["title"], "Agentic RAG")
        self.assertEqual(graph_result.metadata["url"], "https://example.com/agentic-rag")
        self.assertEqual(graph_result.metadata["citation_id"], "ATR-20260621-AGENT1")
        self.assertEqual(
            graph_result.metadata["local_url"],
            "#2026-06-21/ai-topic-radar/item/ATR-20260621-AGENT1",
        )
        self.assertIn("repo stars rising", graph_result.metadata["excerpt"])
        self.assertIn("Worth tracking", graph_result.text)

    async def test_graph_results_obey_source_filter(self):
        vector = FakeVectorStore()
        neo4j = FakeNeo4jDriverWithHits()
        retriever = HybridRetriever(vector, neo4j)

        outcome = await retriever.search_with_status(
            "Agentic RAG",
            k=5,
            where={"source": "Product Hunt"},
        )

        self.assertEqual(outcome.channels["graph"].status, "empty")
        self.assertEqual(neo4j.params["k"], 15)


if __name__ == "__main__":
    unittest.main()
