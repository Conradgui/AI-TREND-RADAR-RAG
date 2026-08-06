"""Tests for citation-ready graph ingestion metadata."""

import unittest

from rag.graphrag.builder import KnowledgeGraphBuilder


class MockDriver:
    def __init__(self):
        self.writes = []

    async def execute_write(self, cypher: str, **params):
        self.writes.append((cypher, params))


class KnowledgeGraphBuilderTests(unittest.IsolatedAsyncioTestCase):
    async def test_ingest_date_replaces_date_projection_and_refreshes_rollups(self):
        driver = MockDriver()
        builder = KnowledgeGraphBuilder(driver)

        await builder.ingest_date(
            "2026-08-05",
            {"candidates": [{"title": "Agentic RAG", "source": "Anthropic"}]},
            {},
        )

        queries = [cypher for cypher, _ in driver.writes]
        self.assertIn("DETACH DELETE doc", queries[0])
        self.assertIn("DETACH DELETE d", queries[1])
        occurrence_query = next(query for query in queries if "APPEARED_ON" in query)
        self.assertIn("ON CREATE SET t.mentionCount", occurrence_query)
        self.assertIn("count(d)", queries[-1])

    async def test_ingest_candidate_preserves_citation_metadata(self):
        driver = MockDriver()
        builder = KnowledgeGraphBuilder(driver)

        await builder._ingest_candidate(
            {
                "title": "Claude Code Artifacts",
                "summary": "Preview and share coding work",
                "url": "https://example.com/claude-code-artifacts",
                "source": "Product Hunt",
                "category": "AI 产品与用户入口",
                "score": 80,
                "action": "深挖",
                "reason": "值得优先深挖",
                "evidence": ["来源：Product Hunt", "发布时间：2026-06-19"],
                "tags": ["Developer Tools", "Artificial Intelligence"],
            },
            "2026-06-21",
        )

        topic_write = driver.writes[0][1]
        self.assertEqual(topic_write["summary"], "Preview and share coding work")
        self.assertEqual(topic_write["url"], "https://example.com/claude-code-artifacts")
        self.assertEqual(topic_write["source"], "Product Hunt")
        self.assertEqual(topic_write["reason"], "值得优先深挖")
        self.assertEqual(topic_write["evidence"], ["来源：Product Hunt", "发布时间：2026-06-19"])

    async def test_ingest_candidate_preserves_per_date_occurrence_evidence(self):
        driver = MockDriver()
        builder = KnowledgeGraphBuilder(driver)

        await builder._ingest_candidate(
            {
                "title": "Agentic RAG",
                "summary": "Day one summary",
                "url": "https://example.com/day-one",
                "source": "Source A",
                "reason": "Day one reason",
                "evidence": ["day one evidence"],
            },
            "2026-06-20",
        )
        await builder._ingest_candidate(
            {
                "title": "Agentic RAG",
                "summary": "Day two summary",
                "url": "https://example.com/day-two",
                "source": "Source B",
                "reason": "Day two reason",
                "evidence": ["day two evidence"],
            },
            "2026-06-21",
        )

        occurrence_writes = [
            params for cypher, params in driver.writes
            if "APPEARED_ON" in cypher
        ]

        self.assertEqual(occurrence_writes[0]["date"], "2026-06-20")
        self.assertEqual(occurrence_writes[0]["summary"], "Day one summary")
        self.assertEqual(occurrence_writes[0]["url"], "https://example.com/day-one")
        self.assertEqual(occurrence_writes[0]["source"], "Source A")
        self.assertEqual(occurrence_writes[0]["reason"], "Day one reason")
        self.assertEqual(occurrence_writes[0]["evidence"], ["day one evidence"])

        self.assertEqual(occurrence_writes[1]["date"], "2026-06-21")
        self.assertEqual(occurrence_writes[1]["summary"], "Day two summary")
        self.assertEqual(occurrence_writes[1]["url"], "https://example.com/day-two")
        self.assertEqual(occurrence_writes[1]["source"], "Source B")
        self.assertEqual(occurrence_writes[1]["reason"], "Day two reason")
        self.assertEqual(occurrence_writes[1]["evidence"], ["day two evidence"])


if __name__ == "__main__":
    unittest.main()
