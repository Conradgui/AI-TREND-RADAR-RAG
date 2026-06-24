"""Tests for optional external search provider configuration."""

import unittest

from rag import config


class SearchProviderConfigTests(unittest.TestCase):
    def test_search_provider_api_keys_are_optional_config_values(self):
        self.assertTrue(hasattr(config, "BRAVE_SEARCH_API_KEY"))
        self.assertTrue(hasattr(config, "TAVILY_API_KEY"))
        self.assertTrue(hasattr(config, "EXA_API_KEY"))
        self.assertTrue(hasattr(config, "SERPAPI_API_KEY"))
        self.assertTrue(hasattr(config, "GITHUB_TOKEN"))

    def test_get_configured_search_providers_returns_names_for_present_keys(self):
        providers = config.get_configured_search_providers(
            {
                "BRAVE_SEARCH_API_KEY": "brave-key",
                "TAVILY_API_KEY": "",
                "EXA_API_KEY": "exa-key",
                "SERPAPI_API_KEY": "",
                "GITHUB_TOKEN": "github-token",
            }
        )

        self.assertEqual(providers, {"brave", "exa", "github"})

    def test_deep_fetch_runtime_toggle_is_explicitly_enabled(self):
        self.assertFalse(config.is_deep_fetch_enabled({"RAG_ENABLE_DEEP_FETCH": ""}))
        self.assertFalse(config.is_deep_fetch_enabled({"RAG_ENABLE_DEEP_FETCH": "false"}))
        self.assertFalse(config.is_deep_fetch_enabled({"RAG_ENABLE_DEEP_FETCH": "0"}))
        self.assertTrue(config.is_deep_fetch_enabled({"RAG_ENABLE_DEEP_FETCH": "true"}))
        self.assertTrue(config.is_deep_fetch_enabled({"RAG_ENABLE_DEEP_FETCH": "1"}))


if __name__ == "__main__":
    unittest.main()
