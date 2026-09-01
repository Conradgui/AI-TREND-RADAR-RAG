"""Tests for graph reasoning service helpers."""

import asyncio
import unittest

from rag.graph_question_planning import build_graph_question_plan, build_graph_question_plans
from rag.graph_reasoning_service import (
    build_entity_relation_citation,
    build_entity_relation_evidence,
    build_graph_reasoning_citation,
    build_graph_reasoning_evidence,
    format_graph_reasoning_summary,
)


class FakeGraphDriver:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    async def execute_query(self, cypher, **params):
        self.calls.append({"cypher": cypher, "params": params})
        if "repeated_content_count" in cypher:
            return [{"repeated_content_count": 2, "repeated_observation_count": 4}]
        if "previous_link_count" in cypher:
            return [{"previous_link_count": 2}]
        return self.rows


class GraphReasoningServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_entity_graph_queries_run_concurrently(self):
        plan = build_graph_question_plan("OpenAI 相关主题是否跨多个日期反复出现？")

        class ConcurrentDriver(FakeGraphDriver):
            def __init__(self):
                super().__init__([{}])
                self.active = 0
                self.max_active = 0

            async def execute_query(self, cypher, **params):
                self.active += 1
                self.max_active = max(self.max_active, self.active)
                await asyncio.sleep(0.01)
                self.active -= 1
                return await super().execute_query(cypher, **params)

        driver = ConcurrentDriver()
        await build_graph_reasoning_evidence(driver, plan)

        self.assertEqual(driver.max_active, 3)

    async def test_pairwise_relation_queries_run_concurrently(self):
        plans = build_graph_question_plans("请分析 OpenAI 与 Apple 的跨日关联")

        class ConcurrentPairDriver:
            def __init__(self):
                self.active = 0
                self.max_active = 0

            async def execute_query(self, cypher, **params):
                self.active += 1
                self.max_active = max(self.max_active, self.active)
                await asyncio.sleep(0.01)
                self.active -= 1
                return [{}]

        driver = ConcurrentPairDriver()
        await build_entity_relation_evidence(driver, plans[0], plans[1])

        self.assertEqual(driver.max_active, 3)

    async def test_builds_typed_pairwise_relation_evidence_without_claiming_causality(self):
        plans = build_graph_question_plans("请分析 OpenAI 与 Apple 的跨日关联")

        class PairDriver:
            async def execute_query(self, cypher, **params):
                self.params = params
                if "shared_observation_count" in cypher:
                    return [{
                        "shared_observation_count": 2,
                        "sample_shared_observations": [{
                            "title": "OpenAI responds to Apple",
                            "date": "2026-08-05",
                            "content_id": "content-1",
                        }],
                    }]
                if "shared_content_count" in cypher:
                    return [{"shared_content_count": 1}]
                return [{
                    "shared_category_count": 1,
                    "shared_categories": ["标杆企业动向"],
                }]

        evidence = await build_entity_relation_evidence(PairDriver(), plans[0], plans[1])
        citation = build_entity_relation_citation(evidence)

        self.assertEqual(evidence["entity_ids"], ["openai", "apple"])
        self.assertEqual(evidence["shared_observation_count"], 2)
        self.assertEqual(evidence["shared_content_count"], 1)
        self.assertEqual(evidence["shared_categories"], ["标杆企业动向"])
        self.assertEqual(citation["content_type"], "graph_relation")
        self.assertEqual(citation["citation_id"], "graph-relation/openai/apple")
        self.assertIn("只能证明图谱中的共现或共享上下文，不能单独证明因果", citation["excerpt"])

    async def test_builds_graph_evidence_from_entity_paths(self):
        plan = build_graph_question_plan("RAG 相关主题是否跨多个日期和来源反复出现？")
        driver = FakeGraphDriver([
            {
                "entity": "RAG",
                "observation_count": 8,
                "content_count": 6,
                "date_count": 4,
                "first_observed_date": "2026-06-01",
                "latest_observed_date": "2026-06-30",
                "source_count": 2,
                "category_count": 3,
                "registry_relations": [{
                    "entity_id": "anthropic", "entity": "Anthropic",
                    "relation": "developed_by", "weight": 0.55,
                    "registry_version": "2026-08-26.v1",
                }],
                "sample_paths": [
                    {
                        "entity": "RAG",
                        "title": "Graph RAG benchmark",
                        "content_id": "content-rag-benchmark",
                        "date": "2026-06-21",
                        "source": "GitHub Search:rag",
                        "category": "模型与技术突破",
                    }
                ],
            }
        ])

        evidence = await build_graph_reasoning_evidence(driver, plan)

        self.assertEqual(driver.calls[0]["params"], {"entity_id": "rag"})
        self.assertEqual(evidence["observation_count"], 8)
        self.assertEqual(evidence["content_count"], 6)
        self.assertEqual(evidence["date_count"], 4)
        self.assertEqual(evidence["latest_observed_date"], "2026-06-30")
        self.assertEqual(evidence["source_count"], 2)
        self.assertEqual(evidence["repeated_content_count"], 2)
        self.assertEqual(evidence["repeated_observation_count"], 4)
        self.assertEqual(evidence["previous_link_count"], 2)
        self.assertEqual(evidence["registry_relations"][0]["entity_id"], "anthropic")
        self.assertEqual(evidence["sample_paths"][0]["title"], "Graph RAG benchmark")
        cypher = driver.calls[0]["cypher"]
        self.assertIn("(e:Entity {id: $entity_id})-[:MENTIONS]->(o:Observation)", cypher)
        self.assertIn("(o)-[:DISCOVERED_VIA|FROM]->(s:Source)", cypher)
        self.assertIn("learned_entity_memory", cypher)
        self.assertNotIn("(t)-[:DISCOVERED_VIA]", cypher)

    async def test_filters_empty_sample_paths_and_builds_citation(self):
        plan = build_graph_question_plan("OpenAI 相关主题是否能通过图谱关联到多个趋势主题和日期？")
        driver = FakeGraphDriver([
            {
                "entity": "OpenAI",
                "observation_count": 3,
                "content_count": 2,
                "date_count": 2,
                "first_observed_date": "2026-06-20",
                "latest_observed_date": "2026-06-30",
                "source_count": 1,
                "category_count": 1,
                "sample_paths": [
                    {"entity": "OpenAI", "title": "", "date": "2026-06-20", "source": "Product Hunt"},
                    {"entity": "OpenAI", "title": "OpenAI agent update", "date": "2026-06-21", "source": "Product Hunt"},
                ],
            }
        ])

        evidence = await build_graph_reasoning_evidence(driver, plan)
        citation = build_graph_reasoning_citation(evidence)

        self.assertEqual(len(evidence["sample_paths"]), 1)
        self.assertEqual(citation["content_type"], "graph_reasoning")
        self.assertEqual(citation["citation_id"], "graph-reasoning/openai")
        self.assertEqual(citation["date"], "2026-06-30")
        self.assertIn("OpenAI 在图谱中关联", citation["excerpt"])
        self.assertIn("带有该实体标记的观察中", citation["excerpt"])
        self.assertIn("注册表主体关系", citation["excerpt"])

    async def test_summary_handles_missing_paths(self):
        summary = format_graph_reasoning_summary({
            "entity_label": "AI Agent",
            "entity_id": "ai-agent",
            "observation_count": 0,
            "content_count": 0,
            "date_count": 0,
            "source_count": 0,
            "category_count": 0,
            "sample_paths": [],
        })

        self.assertIn("暂无样例路径", summary)


if __name__ == "__main__":
    unittest.main()
