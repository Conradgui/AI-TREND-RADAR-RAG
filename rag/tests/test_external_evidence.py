"""Tests for external evidence schema and disabled web-search adapter."""

import unittest

from rag.external_evidence import (
    build_web_search_unavailable_result,
    validate_external_citation,
)


class ExternalEvidenceTests(unittest.TestCase):
    def test_valid_external_citation_passes_schema_validation(self):
        citation = {
            "evidence_type": "external",
            "source": "Google Research",
            "title": "Example paper",
            "url": "https://research.google/example",
            "retrieved_at": "2026-06-22",
            "excerpt": "A concise excerpt from the source.",
        }

        self.assertEqual(validate_external_citation(citation), [])

    def test_external_citation_requires_url_source_title_retrieved_at_and_excerpt(self):
        citation = {
            "evidence_type": "external",
            "source": "",
            "title": "Example paper",
            "url": "",
            "retrieved_at": "2026-06-22",
            "excerpt": "",
        }

        errors = validate_external_citation(citation)

        self.assertIn("missing_source", errors)
        self.assertIn("missing_url", errors)
        self.assertIn("missing_excerpt", errors)

    def test_internal_citation_is_not_valid_external_evidence(self):
        citation = {
            "evidence_type": "internal",
            "source": "ai-topic-radar",
            "title": "Internal report",
            "url": "https://conradgui.github.io/AI-TREND-RADAR",
            "retrieved_at": "2026-06-22",
            "excerpt": "Internal corpus excerpt.",
        }

        self.assertIn("invalid_evidence_type", validate_external_citation(citation))

    def test_web_search_unavailable_result_is_structured_and_non_fatal(self):
        result = build_web_search_unavailable_result("Google OKF ALM Wiki")

        self.assertFalse(result["available"])
        self.assertEqual(result["tool"], "web_search")
        self.assertEqual(result["query"], "Google OKF ALM Wiki")
        self.assertEqual(result["citations"], [])
        self.assertIn("not_enabled", result["reason"])
        self.assertIn("外部证据", result["user_message"])


if __name__ == "__main__":
    unittest.main()
