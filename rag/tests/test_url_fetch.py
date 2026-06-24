"""Tests for safe URL fetch and source deepening."""

import unittest

from rag.url_fetch import deepen_external_citations, fetch_url


class UrlFetchTests(unittest.TestCase):
    def test_fetch_url_rejects_non_http_protocols(self):
        result = fetch_url("file:///etc/passwd")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "unsupported_url_scheme")

    def test_fetch_url_rejects_private_network_targets(self):
        def fake_resolver(hostname):
            return ["127.0.0.1"]

        result = fetch_url("https://localhost/admin", resolver=fake_resolver)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "blocked_private_or_local_address")

    def test_fetch_url_allows_public_hostname_resolved_through_managed_proxy(self):
        calls = []

        def fake_transport(url, headers, timeout, max_bytes):
            calls.append(url)
            return {
                "status_code": 200,
                "final_url": url,
                "content_type": "text/plain",
                "body": b"official source text",
            }

        result = fetch_url(
            "https://cloud.google.com/example",
            resolver=lambda hostname: ["198.18.0.66"],
            transport=fake_transport,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(calls, ["https://cloud.google.com/example"])

    def test_fetch_url_rejects_direct_managed_proxy_ip(self):
        result = fetch_url("https://198.18.0.66/example", resolver=lambda hostname: ["198.18.0.66"])

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "blocked_private_or_local_address")

    def test_fetch_url_extracts_title_and_readable_text(self):
        def fake_transport(url, headers, timeout, max_bytes):
            return {
                "status_code": 200,
                "final_url": url,
                "content_type": "text/html; charset=utf-8",
                "body": b"""
                    <html>
                      <head><title>Open Knowledge Format</title><script>ignore()</script></head>
                      <body>
                        <nav>Navigation</nav>
                        <article>
                          <h1>OKF improves data sharing</h1>
                          <p>Google Cloud describes OKF as an open format for sharing knowledge.</p>
                        </article>
                      </body>
                    </html>
                """,
            }

        result = fetch_url(
            "https://cloud.google.com/blog/products/data-analytics/okf",
            resolver=lambda hostname: ["8.8.8.8"],
            transport=fake_transport,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["title"], "Open Knowledge Format")
        self.assertIn("OKF improves data sharing", result["text_excerpt"])
        self.assertIn("Google Cloud describes OKF", result["text_excerpt"])
        self.assertNotIn("ignore()", result["text_excerpt"])

    def test_deepen_external_citations_records_success_and_preserves_original(self):
        citations = [
            {
                "evidence_type": "external",
                "provider": "tavily",
                "source": "example.com",
                "source_quality": "generic",
                "quality_score": 0.55,
                "needs_deep_fetch": True,
                "title": "Provider title",
                "url": "https://example.com/okf",
                "retrieved_at": "2026-06-22",
                "excerpt": "Provider snippet.",
            },
            {
                "evidence_type": "internal",
                "title": "Internal topic",
            },
        ]

        def fake_fetcher(url):
            return {
                "ok": True,
                "url": url,
                "final_url": url,
                "fetched_at": "2026-06-22T00:00:00+00:00",
                "title": "Fetched title",
                "text_excerpt": "Fetched page evidence.",
                "error": "",
            }

        deepened = deepen_external_citations(citations, fetcher=fake_fetcher)

        self.assertEqual(deepened[0]["excerpt"], "Provider snippet.")
        self.assertTrue(deepened[0]["deep_fetch"]["ok"])
        self.assertEqual(deepened[0]["deep_fetch"]["title"], "Fetched title")
        self.assertEqual(deepened[0]["deep_fetch"]["text_excerpt"], "Fetched page evidence.")
        self.assertNotIn("deep_fetch", deepened[1])


if __name__ == "__main__":
    unittest.main()
