"""Tests for citation-ready graph ingestion metadata."""

import unittest

from rag.graphrag.builder import KnowledgeGraphBuilder


class MockDriver:
    def __init__(self):
        self.writes = []
        self.queries = []

    async def execute_write(self, cypher: str, **params):
        self.writes.append((cypher, params))

    async def execute_query(self, cypher: str, **params):
        self.queries.append((cypher, params))
        if "o.date = $date" in cypher:
            return [{"content_ids": ["content-removed-from-rebuilt-day"]}]
        return [{"content_ids": ["content-recurring"]}]


class KnowledgeGraphBuilderTests(unittest.IsolatedAsyncioTestCase):
    async def test_ingest_projects_observations_into_content_category_source_and_daily_views(self):
        driver = MockDriver()
        builder = KnowledgeGraphBuilder(driver)

        await builder.ingest_date(
            "2026-08-05",
            {"candidates": [{
                "title": "OpenAI research update",
                "daily_item_id": "ATR-20260805-ABC123",
                "content_id": "content-openai-research",
                "source": "OpenAI",
                "category": "模型与技术突破",
            }]},
            {},
        )

        queries = "\n".join(cypher for cypher, _ in driver.writes)
        self.assertIn("MERGE (c:Content {id: $content_id})", queries)
        self.assertIn("MERGE (cat:Category {id: $category_id})", queries)
        self.assertIn("MERGE (o)-[:OBSERVES]->(c)", queries)
        self.assertIn("MERGE (o)-[:ABOUT]->(cat)", queries)
        self.assertIn("MERGE (o)-[:FROM]->(s)", queries)
        self.assertIn("MERGE (o)-[:PUBLISHED_IN]->(d)", queries)

    async def test_ingest_refreshes_previous_observation_chain_for_touched_content(self):
        driver = MockDriver()
        builder = KnowledgeGraphBuilder(driver)

        await builder.ingest_date(
            "2026-08-06",
            {"candidates": [{
                "title": "Recurring item",
                "daily_item_id": "ATR-20260806-ABC123",
                "content_id": "content-recurring",
            }]},
            {},
        )

        chain_writes = [
            (cypher, params) for cypher, params in driver.writes
            if "PREVIOUS_OBSERVATION" in cypher
        ]
        self.assertEqual(len(chain_writes), 2)
        expected = ["content-recurring", "content-removed-from-rebuilt-day"]
        self.assertTrue(all(params["content_ids"] == expected for _, params in chain_writes))
        self.assertIn("ORDER BY", chain_writes[1][0])
        self.assertIn("coalesce(o.reportDate, o.date)", chain_writes[1][0])
        self.assertIn("MERGE (current)-[:PREVIOUS_OBSERVATION]->(previous)", chain_writes[1][0])

    async def test_backfill_observation_views_projects_existing_graph_without_reingestion(self):
        driver = MockDriver()
        builder = KnowledgeGraphBuilder(driver)

        await builder.backfill_observation_views()

        queries = "\n".join(cypher for cypher, _ in driver.writes)
        self.assertIn("MATCH (o:Observation)", queries)
        self.assertIn("MERGE (c:Content {id: o.contentId})", queries)
        self.assertIn("MERGE (o)-[:ABOUT]->(cat)", queries)
        self.assertIn("MERGE (o)-[:FROM]->(s)", queries)
        self.assertIn("MERGE (o)-[:PUBLISHED_IN]->(d)", queries)
        self.assertIn("PREVIOUS_OBSERVATION", queries)

    async def test_rebuild_repairs_removed_content_chains_and_cleans_orphans(self):
        driver = MockDriver()
        builder = KnowledgeGraphBuilder(driver)

        await builder.ingest_date("2026-08-06", {"candidates": []}, {})

        self.assertIn("o.date = $date", driver.queries[0][0])
        cleanup = next(
            cypher for cypher, _ in driver.writes
            if "NOT (c)<-[:OBSERVES]-(:Observation)" in cypher
        )
        self.assertIn("DETACH DELETE c", cleanup)
        rollup = next(
            cypher for cypher, _ in driver.writes
            if "c.observationCount" in cypher
        )
        self.assertIn("min(coalesce(o.reportDate, o.date))", rollup)

    async def test_ingest_date_replaces_date_projection_and_refreshes_rollups(self):
        driver = MockDriver()
        builder = KnowledgeGraphBuilder(driver)

        await builder.ingest_date(
            "2026-08-05",
            {"candidates": [{"title": "Agentic RAG", "source": "Anthropic", "daily_item_id": "ATR-20260805-ABC123"}]},
            {"ai-topic-radar": "report"},
        )

        queries = [cypher for cypher, _ in driver.writes]
        self.assertIn("DETACH DELETE o", queries[0])
        self.assertIn("DETACH DELETE doc", queries[1])
        self.assertIn("DETACH DELETE d", queries[2])
        occurrence_query = next(query for query in queries if "APPEARED_ON" in query)
        self.assertIn("ON CREATE SET t.mentionCount", occurrence_query)
        self.assertTrue(all("), (" not in query for query in queries if "MATCH (" in query))
        self.assertIn("count(d)", queries[-1])

    async def test_relationship_matches_do_not_use_disconnected_cartesian_patterns(self):
        driver = MockDriver()
        builder = KnowledgeGraphBuilder(driver)

        await builder._ingest_candidate(
            {
                "title": "Agentic RAG",
                "source": "Anthropic",
                "daily_item_id": "ATR-20260805-ABC123",
                "tags": ["Anthropic"],
            },
            "2026-08-05",
        )

        relationship_queries = [
            cypher for cypher, _ in driver.writes if "MATCH (" in cypher
        ]
        self.assertTrue(relationship_queries)
        self.assertTrue(all("), (" not in query for query in relationship_queries))

    async def test_ingest_candidate_preserves_citation_metadata(self):
        driver = MockDriver()
        builder = KnowledgeGraphBuilder(driver)

        await builder._ingest_candidate(
            {
                "title": "Claude Code Artifacts",
                "daily_item_id": "ATR-20260621-ABC123",
                "content_id": "content-1",
                "summary": "Preview and share coding work",
                "url": "https://example.com/claude-code-artifacts",
                "source": "Product Hunt",
                "category": "AI 产品与用户入口",
                "score": 80,
                "action": "深挖",
                "reason": "值得优先深挖",
                "evidence": ["来源：Product Hunt", "发布时间：2026-06-19"],
                "report_date": "2026-06-21",
                "publication_date": "2026-06-19",
                "publication_date_source": "legacy_evidence",
                "observed_at": "2026-06-21",
                "ingested_at": "2026-06-21T10:00:00Z",
                "effective_date": "2026-06-19",
                "effective_date_basis": "publication_date",
                "tags": ["Developer Tools", "Artificial Intelligence"],
            },
            "2026-06-21",
        )

        topic_write = next(params for cypher, params in driver.writes if "MERGE (t:Topic" in cypher)
        self.assertEqual(topic_write["summary"], "Preview and share coding work")
        self.assertEqual(topic_write["url"], "https://example.com/claude-code-artifacts")
        self.assertEqual(topic_write["source"], "Product Hunt")
        self.assertEqual(topic_write["reason"], "值得优先深挖")
        self.assertEqual(topic_write["evidence"], ["来源：Product Hunt", "发布时间：2026-06-19"])
        observation_write = next(params for cypher, params in driver.writes if "MERGE (o:Observation" in cypher)
        self.assertEqual(observation_write["report_date"], "2026-06-21")
        self.assertEqual(observation_write["publication_date"], "2026-06-19")
        self.assertEqual(observation_write["effective_date"], "2026-06-19")
        self.assertEqual(observation_write["observed_at"], "2026-06-21")

    async def test_ingest_candidate_preserves_per_date_occurrence_evidence(self):
        driver = MockDriver()
        builder = KnowledgeGraphBuilder(driver)

        await builder._ingest_candidate(
            {
                "title": "Agentic RAG",
                "daily_item_id": "ATR-20260620-ABC123",
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
                "daily_item_id": "ATR-20260621-ABC123",
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
