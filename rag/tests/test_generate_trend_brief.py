"""Tests for trend brief generation CLI helpers."""

import unittest

from rag.generate_trend_brief import (
    build_generation_summary,
    build_trend_brief_external_search_requests,
)
from rag.query_understanding import analyze_query


class GenerateTrendBriefTests(unittest.TestCase):
    def test_build_generation_summary_exposes_artifact_and_counts(self):
        summary = build_generation_summary(
            output="docs/rag-transformation/briefs/trend-brief-rag-2026-06-24.md",
            topic="RAG",
            citation_count=3,
            external_citation_count=1,
            has_graph_summary=True,
            mode="live-external",
            policy_mode="internal_grounded",
            external_search_trace={"attempted": True, "provider": "brave"},
        )

        self.assertEqual(summary["topic"], "RAG")
        self.assertEqual(summary["citation_count"], 3)
        self.assertEqual(summary["external_citation_count"], 1)
        self.assertTrue(summary["has_graph_summary"])
        self.assertEqual(summary["mode"], "live-external")
        self.assertEqual(summary["policy_mode"], "internal_grounded")
        self.assertEqual(summary["external_search"]["provider"], "brave")
        self.assertTrue(summary["output"].endswith("trend-brief-rag-2026-06-24.md"))

    def test_build_external_search_requests_is_empty_for_local_only_mode(self):
        plan = analyze_query("最近 RAG 领域有什么值得关注的新动向？")

        requests = build_trend_brief_external_search_requests(
            topic="RAG",
            plan=plan,
            mode="local-only",
            configured_providers={"brave", "tavily"},
        )

        self.assertEqual(requests, [])

    def test_build_external_search_requests_uses_provider_route_for_live_external_mode(self):
        plan = analyze_query("最近 RAG 领域有什么值得关注的新动向？")

        requests = build_trend_brief_external_search_requests(
            topic="RAG",
            plan=plan,
            mode="live-external",
            configured_providers={"brave", "tavily"},
            max_external_citations=2,
        )

        self.assertEqual([request.provider for request in requests], ["brave", "tavily"])
        self.assertTrue(all(request.task_type == "recent_web" for request in requests))
        self.assertTrue(all(request.max_results == 2 for request in requests))
        self.assertIn("RAG", requests[0].query)


if __name__ == "__main__":
    unittest.main()
