"""Tests for graph reasoning service helpers."""

import unittest

from rag.graph_question_planning import build_graph_question_plan
from rag.graph_reasoning_service import (
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
        return self.rows


class GraphReasoningServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_builds_graph_evidence_from_entity_paths(self):
        plan = build_graph_question_plan("RAG 相关主题是否跨多个日期和来源反复出现？")
        driver = FakeGraphDriver([
            {
                "entity": "RAG",
                "topic_count": 6,
                "date_count": 4,
                "source_count": 2,
                "sample_paths": [
                    {
                        "entity": "RAG",
                        "topic": "Graph RAG benchmark",
                        "date": "2026-06-21",
                        "source": "GitHub Search:rag",
                    }
                ],
            }
        ])

        evidence = await build_graph_reasoning_evidence(driver, plan)

        self.assertEqual(driver.calls[0]["params"], {"entity_id": "rag"})
        self.assertEqual(evidence["topic_count"], 6)
        self.assertEqual(evidence["date_count"], 4)
        self.assertEqual(evidence["source_count"], 2)
        self.assertEqual(evidence["sample_paths"][0]["topic"], "Graph RAG benchmark")

    async def test_filters_empty_sample_paths_and_builds_citation(self):
        plan = build_graph_question_plan("OpenAI 相关主题是否能通过图谱关联到多个趋势主题和日期？")
        driver = FakeGraphDriver([
            {
                "entity": "OpenAI",
                "topic_count": 3,
                "date_count": 2,
                "source_count": 1,
                "sample_paths": [
                    {"entity": "OpenAI", "topic": "", "date": "2026-06-20", "source": "Product Hunt"},
                    {"entity": "OpenAI", "topic": "OpenAI agent update", "date": "2026-06-21", "source": "Product Hunt"},
                ],
            }
        ])

        evidence = await build_graph_reasoning_evidence(driver, plan)
        citation = build_graph_reasoning_citation(evidence)

        self.assertEqual(len(evidence["sample_paths"]), 1)
        self.assertEqual(citation["content_type"], "graph_reasoning")
        self.assertEqual(citation["citation_id"], "graph-reasoning/openai")
        self.assertIn("OpenAI 在图谱中关联", citation["excerpt"])

    async def test_summary_handles_missing_paths(self):
        summary = format_graph_reasoning_summary({
            "entity_label": "AI Agent",
            "entity_id": "ai-agent",
            "topic_count": 0,
            "date_count": 0,
            "source_count": 0,
            "sample_paths": [],
        })

        self.assertIn("暂无样例路径", summary)


if __name__ == "__main__":
    unittest.main()
