"""Tests for external source quality and excerpt policy."""

import unittest

from rag.external_source_quality import (
    apply_excerpt_policy,
    classify_source_quality,
    official_lookup_domain_policy,
)


class ExternalSourceQualityTests(unittest.TestCase):
    def test_google_domain_is_official_for_google_official_lookup(self):
        quality = classify_source_quality(
            "https://cloud.google.com/blog/products/ai-machine-learning/example",
            task_type="official_source_lookup",
            entities=["Google"],
        )

        self.assertEqual(quality["source_quality"], "official")
        self.assertGreaterEqual(quality["quality_score"], 0.9)
        self.assertFalse(quality["needs_deep_fetch"])

    def test_linkedin_is_social_and_needs_primary_source_replacement(self):
        quality = classify_source_quality(
            "https://www.linkedin.com/posts/google-cloud_example",
            task_type="official_source_lookup",
            entities=["Google"],
        )

        self.assertEqual(quality["source_quality"], "social")
        self.assertLess(quality["quality_score"], 0.5)
        self.assertTrue(quality["needs_deep_fetch"])
        self.assertIn("primary", " ".join(quality["quality_notes"]))

    def test_excerpt_policy_preserves_more_official_context_than_social_context(self):
        text = "x" * 3000

        official = apply_excerpt_policy(text, {"source_quality": "official"})
        social = apply_excerpt_policy(text, {"source_quality": "social"})

        self.assertGreater(len(official), len(social))
        self.assertGreater(len(official), 600)
        self.assertLessEqual(len(social), 600)

    def test_official_lookup_domain_policy_prefers_google_and_excludes_social(self):
        policy = official_lookup_domain_policy(["Google"])

        self.assertIn("google.com", policy["include_domains"])
        self.assertIn("cloud.google.com", policy["include_domains"])
        self.assertIn("linkedin.com", policy["exclude_domains"])
        self.assertIn("x.com", policy["exclude_domains"])


if __name__ == "__main__":
    unittest.main()
