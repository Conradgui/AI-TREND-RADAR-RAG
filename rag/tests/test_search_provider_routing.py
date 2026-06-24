"""Tests for external search provider routing strategy."""

import unittest

from rag.search_provider_routing import (
    PROVIDER_PROFILES,
    build_search_provider_route,
)


class SearchProviderRoutingTests(unittest.TestCase):
    def test_research_paper_task_prefers_exa_then_tavily(self):
        route = build_search_provider_route(
            {
                "query": "RAG evolution papers",
                "task_type": "research_paper",
            },
            configured_providers={"exa", "tavily", "brave", "serpapi"},
        )

        self.assertEqual(route["primary_provider"], "exa")
        self.assertEqual(route["provider_chain"][:3], ["exa", "tavily", "serpapi"])
        self.assertIn("research", route["rationale"])

    def test_recent_web_task_prefers_brave_then_tavily(self):
        route = build_search_provider_route(
            {
                "query": "Claude Code Artifacts latest update",
                "task_type": "recent_web",
            },
            configured_providers={"brave", "tavily", "exa"},
        )

        self.assertEqual(route["primary_provider"], "brave")
        self.assertEqual(route["provider_chain"][:2], ["brave", "tavily"])
        self.assertLessEqual(route["budget_policy"]["max_external_providers"], 2)

    def test_github_repo_task_prefers_github_api(self):
        route = build_search_provider_route(
            {
                "query": "agentic rag repositories",
                "task_type": "github_repo",
            },
            configured_providers={"github", "brave", "tavily"},
        )

        self.assertEqual(route["primary_provider"], "github")
        self.assertEqual(route["provider_chain"][:3], ["github", "brave", "tavily"])

    def test_missing_keys_return_unavailable_providers(self):
        route = build_search_provider_route(
            {
                "query": "Google OKF ALM Wiki",
                "task_type": "official_source_lookup",
            },
            configured_providers=set(),
        )

        self.assertIsNone(route["primary_provider"])
        self.assertEqual(route["available_provider_chain"], [])
        self.assertIn("tavily", route["unavailable_providers"])
        self.assertIn("brave", route["unavailable_providers"])

    def test_google_custom_search_is_not_a_default_provider(self):
        self.assertNotIn("google_custom_search", PROVIDER_PROFILES)


if __name__ == "__main__":
    unittest.main()
