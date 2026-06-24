"""Tests for search provider adapter readiness evaluation."""

import unittest

from rag.eval_search_provider_adapters import build_search_provider_adapter_readiness


class EvalSearchProviderAdaptersTests(unittest.IsolatedAsyncioTestCase):
    async def test_adapter_readiness_passes_with_all_providers_disabled_without_keys(self):
        result = await build_search_provider_adapter_readiness()

        self.assertTrue(result["passed"])
        self.assertEqual(result["failed_checks"], [])
        self.assertGreaterEqual(len(result["rows"]), 4)
        for row in result["rows"]:
            self.assertFalse(row["available"])
            self.assertIn("missing_api_key", row["errors"])


if __name__ == "__main__":
    unittest.main()
