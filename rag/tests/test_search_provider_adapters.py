"""Tests for search provider adapter interface and registry."""

import unittest

from rag.search_provider_adapters import (
    BraveSearchProviderAdapter,
    ExaSearchProviderAdapter,
    GitHubSearchProviderAdapter,
    SearchRequest,
    SearchProviderRegistry,
    TavilySearchProviderAdapter,
    build_disabled_search_result,
    build_tavily_request_for_task,
)


class SearchProviderAdapterTests(unittest.IsolatedAsyncioTestCase):
    def test_search_request_defaults_are_provider_agnostic(self):
        request = SearchRequest(
            query="RAG evolution papers",
            task_type="research_paper",
            provider="exa",
        )

        self.assertEqual(request.max_results, 5)
        self.assertEqual(request.include_domains, [])
        self.assertEqual(request.exclude_domains, [])

    def test_disabled_search_result_is_structured(self):
        request = SearchRequest(
            query="Google OKF ALM Wiki",
            task_type="official_source_lookup",
            provider="tavily",
        )

        result = build_disabled_search_result(request, reason="missing_api_key")

        self.assertEqual(result["provider"], "tavily")
        self.assertFalse(result["available"])
        self.assertEqual(result["query"], "Google OKF ALM Wiki")
        self.assertEqual(result["citations"], [])
        self.assertEqual(result["raw_results_count"], 0)
        self.assertIn("missing_api_key", result["errors"])

    async def test_registry_returns_disabled_adapter_for_known_provider_without_key(self):
        registry = SearchProviderRegistry(configured_provider_keys={})
        request = SearchRequest(
            query="Claude latest update",
            task_type="recent_web",
            provider="brave",
        )

        result = await registry.search(request)

        self.assertEqual(result["provider"], "brave")
        self.assertFalse(result["available"])
        self.assertIn("missing_api_key", result["errors"])

    async def test_registry_rejects_unknown_provider_safely(self):
        registry = SearchProviderRegistry(configured_provider_keys={})
        request = SearchRequest(
            query="anything",
            task_type="broad_serp",
            provider="unknown_provider",
        )

        result = await registry.search(request)

        self.assertEqual(result["provider"], "unknown_provider")
        self.assertFalse(result["available"])
        self.assertIn("unknown_provider", result["errors"])

    async def test_tavily_adapter_normalizes_results_to_external_citations(self):
        calls = []

        def fake_transport(url, headers, payload):
            calls.append({"url": url, "headers": headers, "payload": payload})
            return {
                "query": payload["query"],
                "results": [
                    {
                        "title": "Official RAG Paper",
                        "url": "https://example.com/rag-paper",
                        "content": "A useful source excerpt.",
                        "score": 0.91,
                        "published_date": "2026-08-04T08:00:00Z",
                    }
                ],
                "usage": {"credits": 1},
            }

        adapter = TavilySearchProviderAdapter(api_key="test-key", transport=fake_transport)
        request = SearchRequest(
            query="RAG evolution papers",
            task_type="research_paper",
            provider="tavily",
            max_results=1,
        )

        result = await adapter.search(request)

        self.assertTrue(result["available"])
        self.assertEqual(result["provider"], "tavily")
        self.assertEqual(result["raw_results_count"], 1)
        self.assertEqual(result["usage"], {"credits": 1})
        self.assertEqual(calls[0]["url"], "https://api.tavily.com/search")
        # 高质量联网策略使用 advanced，并把默认时效窗口限制在近 10 天。
        self.assertEqual(calls[0]["payload"]["search_depth"], "advanced")
        self.assertEqual(calls[0]["payload"]["days"], 10)
        self.assertEqual(calls[0]["payload"]["max_results"], 1)
        self.assertFalse(calls[0]["payload"]["include_raw_content"])
        citation = result["citations"][0]
        self.assertEqual(citation["evidence_type"], "external")
        self.assertEqual(citation["provider"], "tavily")
        self.assertEqual(citation["title"], "Official RAG Paper")
        self.assertEqual(citation["url"], "https://example.com/rag-paper")
        self.assertEqual(citation["excerpt"], "A useful source excerpt.")
        self.assertIn("source_quality", citation)
        self.assertIn("quality_score", citation)
        self.assertEqual(citation["published_at"], "2026-08-04T08:00:00Z")

    async def test_registry_uses_tavily_adapter_when_key_exists(self):
        calls = []

        def fake_transport(url, headers, payload):
            calls.append(payload)
            return {"query": payload["query"], "results": []}

        registry = SearchProviderRegistry(
            configured_provider_keys={"tavily": "test-key"},
            transports={"tavily": fake_transport},
        )
        request = SearchRequest(
            query="Google OKF",
            task_type="official_source_lookup",
            provider="tavily",
        )

        result = await registry.search(request)

        self.assertTrue(calls)
        self.assertEqual(result["provider"], "tavily")
        self.assertTrue(result["available"])
        self.assertEqual(result["raw_results_count"], 0)

    async def test_brave_adapter_normalizes_web_results_to_external_citations(self):
        calls = []

        def fake_transport(url, headers, params):
            calls.append({"url": url, "headers": headers, "params": params})
            return {
                "web": {
                    "results": [
                        {
                            "title": "Claude release notes",
                            "url": "https://www.anthropic.com/news/example",
                            "description": "Claude shipped a new feature.",
                            "extra_snippets": ["Additional context."],
                            "rank": 1,
                            "page_age": "2026-08-03T12:00:00Z",
                        }
                    ]
                }
            }

        adapter = BraveSearchProviderAdapter(api_key="test-key", transport=fake_transport)
        request = SearchRequest(query="Claude latest update", task_type="recent_web", provider="brave", max_results=1)

        result = await adapter.search(request)

        self.assertTrue(result["available"])
        self.assertEqual(calls[0]["url"], "https://api.search.brave.com/res/v1/web/search")
        self.assertEqual(calls[0]["headers"]["X-Subscription-Token"], "test-key")
        self.assertEqual(calls[0]["params"]["freshness"], "pw")
        citation = result["citations"][0]
        self.assertEqual(citation["provider"], "brave")
        self.assertEqual(citation["title"], "Claude release notes")
        self.assertIn("Additional context", citation["excerpt"])
        self.assertEqual(citation["source_quality"], "official")
        self.assertEqual(citation["published_at"], "2026-08-03T12:00:00Z")

    async def test_exa_adapter_normalizes_search_results_to_external_citations(self):
        calls = []

        def fake_transport(url, headers, payload):
            calls.append({"url": url, "headers": headers, "payload": payload})
            return {
                "results": [
                    {
                        "title": "RAG survey",
                        "url": "https://arxiv.org/abs/2401.00001",
                        "summary": "A survey about retrieval augmented generation.",
                        "highlightScores": [0.77],
                        "publishedDate": "2026-01-01T00:00:00Z",
                    }
                ],
                "requestId": "req-1",
                "costDollars": {"total": 0.001},
            }

        adapter = ExaSearchProviderAdapter(api_key="test-key", transport=fake_transport)
        request = SearchRequest(query="RAG survey", task_type="research_paper", provider="exa", max_results=1)

        result = await adapter.search(request)

        self.assertTrue(result["available"])
        self.assertEqual(calls[0]["url"], "https://api.exa.ai/search")
        self.assertEqual(calls[0]["headers"]["x-api-key"], "test-key")
        self.assertTrue(calls[0]["payload"]["contents"]["highlights"])
        citation = result["citations"][0]
        self.assertEqual(citation["provider"], "exa")
        self.assertEqual(citation["source_quality"], "academic")
        self.assertEqual(citation["published_at"], "2026-01-01T00:00:00Z")
        self.assertEqual(result["request_id"], "req-1")

    async def test_github_adapter_normalizes_repository_results_to_external_citations(self):
        calls = []

        def fake_transport(url, headers, params):
            calls.append({"url": url, "headers": headers, "params": params})
            return {
                "total_count": 1,
                "incomplete_results": False,
                "items": [
                    {
                        "full_name": "example/agentic-rag",
                        "html_url": "https://github.com/example/agentic-rag",
                        "description": "Agentic RAG example repository.",
                        "stargazers_count": 1234,
                        "forks_count": 56,
                        "language": "Python",
                        "created_at": "2026-01-01T00:00:00Z",
                        "updated_at": "2026-06-23T00:00:00Z",
                    }
                ],
            }

        adapter = GitHubSearchProviderAdapter(api_key="test-key", transport=fake_transport)
        request = SearchRequest(query="agentic rag", task_type="github_repo", provider="github", max_results=1)

        result = await adapter.search(request)

        self.assertTrue(result["available"])
        self.assertEqual(calls[0]["url"], "https://api.github.com/search/repositories")
        self.assertEqual(calls[0]["headers"]["Authorization"], "Bearer test-key")
        self.assertIn("archived:false", calls[0]["params"]["q"])
        citation = result["citations"][0]
        self.assertEqual(citation["provider"], "github")
        self.assertEqual(citation["source_type"], "api")
        self.assertEqual(citation["title"], "example/agentic-rag")
        self.assertIn("Stars: 1234", citation["excerpt"])
        self.assertEqual(citation["source_quality"], "official")

    async def test_registry_uses_live_adapters_for_configured_non_tavily_providers(self):
        calls = []

        def fake_brave_transport(url, headers, params):
            calls.append(("brave", params))
            return {"web": {"results": []}}

        def fake_exa_transport(url, headers, payload):
            calls.append(("exa", payload))
            return {"results": []}

        def fake_github_transport(url, headers, params):
            calls.append(("github", params))
            return {"items": []}

        registry = SearchProviderRegistry(
            configured_provider_keys={"brave": "b", "exa": "e", "github": "g"},
            transports={
                "brave": fake_brave_transport,
                "exa": fake_exa_transport,
                "github": fake_github_transport,
            },
        )

        for provider in ["brave", "exa", "github"]:
            result = await registry.search(SearchRequest(query="check", task_type="broad_serp", provider=provider))
            self.assertTrue(result["available"])

        self.assertEqual([call[0] for call in calls], ["brave", "exa", "github"])

    async def test_tavily_adapter_applies_source_aware_excerpt_policy(self):
        def fake_transport(url, headers, payload):
            return {
                "query": payload["query"],
                "results": [
                    {
                        "title": "Official page",
                        "url": "https://cloud.google.com/example",
                        "content": "x" * 2000,
                        "score": 0.8,
                    },
                    {
                        "title": "Social repost",
                        "url": "https://www.linkedin.com/posts/example",
                        "content": "y" * 2000,
                        "score": 0.5,
                    }
                ],
            }

        adapter = TavilySearchProviderAdapter(api_key="test-key", transport=fake_transport)
        request = SearchRequest(query="Google OKF", task_type="official_source_lookup", provider="tavily")

        result = await adapter.search(request)

        official, social = result["citations"]
        self.assertEqual(official["source_quality"], "official")
        self.assertEqual(social["source_quality"], "social")
        self.assertGreater(len(official["excerpt"]), len(social["excerpt"]))
        self.assertTrue(social["needs_deep_fetch"])

    def test_build_tavily_request_for_google_official_lookup_adds_domain_policy(self):
        request = build_tavily_request_for_task(
            query="Google OKF ALM Wiki",
            task_type="official_source_lookup",
            entities=["Google"],
            max_results=1,
        )

        self.assertEqual(request.provider, "tavily")
        self.assertIn("cloud.google.com", request.include_domains)
        self.assertIn("linkedin.com", request.exclude_domains)


if __name__ == "__main__":
    unittest.main()
