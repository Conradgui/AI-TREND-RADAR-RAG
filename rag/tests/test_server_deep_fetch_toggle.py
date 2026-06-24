"""Tests for runtime deep-fetch toggle wiring."""

import unittest

from rag.runtime_tools import select_external_deep_fetcher
from rag.url_fetch import fetch_url


class ServerDeepFetchToggleTests(unittest.TestCase):
    def test_select_external_deep_fetcher_is_none_when_disabled(self):
        self.assertIsNone(select_external_deep_fetcher(False))

    def test_select_external_deep_fetcher_returns_fetch_url_when_enabled(self):
        self.assertIs(select_external_deep_fetcher(True), fetch_url)


if __name__ == "__main__":
    unittest.main()
