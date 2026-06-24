"""Tests for deterministic source review guidance."""

import unittest

from rag.source_review import build_source_review, format_source_review_for_prompt


class SourceReviewTests(unittest.TestCase):
    def test_internal_only_review_has_no_external_conflict(self):
        review = build_source_review([
            {"evidence_type": "internal", "source": "ai-topic-radar"}
        ])

        self.assertEqual(review["status"], "internal_only")
        self.assertEqual(review["external_count"], 0)
        self.assertEqual(review["source_roles"], [])

    def test_mixed_quality_sources_prioritize_primary_evidence(self):
        review = build_source_review([
            {
                "evidence_type": "external",
                "source": "cloud.google.com",
                "source_quality": "official",
                "title": "Official OKF",
                "url": "https://cloud.google.com/okf",
            },
            {
                "evidence_type": "external",
                "source": "example.blog",
                "source_quality": "generic",
                "title": "OKF commentary",
                "url": "https://example.blog/okf",
                "needs_deep_fetch": True,
            },
        ])

        self.assertEqual(review["status"], "mixed_quality")
        self.assertEqual(review["primary_count"], 1)
        self.assertEqual(review["weak_count"], 1)
        self.assertEqual(review["source_roles"][0]["role"], "primary_evidence")
        self.assertEqual(review["source_roles"][1]["role"], "weak_context")
        self.assertIn("primary", review["instruction"])

    def test_weak_only_sources_require_uncertainty(self):
        review = build_source_review([
            {
                "evidence_type": "external",
                "source": "social.example",
                "source_quality": "social",
                "title": "Repost",
                "url": "https://social.example/post",
            }
        ])

        self.assertEqual(review["status"], "weak_only")
        self.assertEqual(review["weak_count"], 1)
        self.assertIn("weak", review["instruction"])

    def test_format_source_review_for_prompt_includes_roles(self):
        review = build_source_review([
            {
                "evidence_type": "external",
                "source": "arxiv.org",
                "source_quality": "academic",
                "title": "RAG Survey",
                "url": "https://arxiv.org/abs/example",
            }
        ])

        prompt = format_source_review_for_prompt(review)

        self.assertIn("来源审查", prompt)
        self.assertIn("primary_evidence", prompt)
        self.assertIn("arxiv.org", prompt)


if __name__ == "__main__":
    unittest.main()
