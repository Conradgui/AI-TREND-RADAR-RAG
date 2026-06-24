"""Tests for deterministic search-provider routing evaluation."""

import unittest

from rag.eval_search_provider_routing import (
    build_search_provider_routing_snapshot,
    summarize_search_provider_routing,
)


class EvalSearchProviderRoutingTests(unittest.TestCase):
    def test_snapshot_routes_needs_web_questions_to_configured_provider(self):
        questions = [
            {
                "id": "Q2",
                "question": "请帮我梳理一下 RAG 技术的发展演进路线，以及相关的论文、文章等资料。",
                "answerability": "needs-web",
            }
        ]

        snapshot = build_search_provider_routing_snapshot(questions, configured_providers={"exa", "tavily"})

        row = snapshot["rows"][0]
        self.assertTrue(row["needs_web_search"])
        self.assertEqual(row["search_task_type"], "research_paper")
        self.assertEqual(row["provider_route"]["primary_provider"], "exa")

    def test_summary_counts_needs_web_without_configured_primary(self):
        rows = [
            {"needs_web_search": True, "provider_route": {"primary_provider": None}},
            {"needs_web_search": True, "provider_route": {"primary_provider": "exa"}},
            {"needs_web_search": False, "provider_route": {"primary_provider": None}},
        ]

        self.assertEqual(
            summarize_search_provider_routing(rows),
            {
                "total": 3,
                "needs_web": 2,
                "needs_web_with_configured_primary": 1,
                "needs_web_without_configured_primary": 1,
            },
        )


if __name__ == "__main__":
    unittest.main()
