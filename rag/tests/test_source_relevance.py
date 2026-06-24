"""Tests for deterministic source relevance and claim-support review."""

import unittest
from pathlib import Path

from rag.source_relevance import (
    classify_source_relevance,
    inspect_trend_brief_source_relevance,
    summarize_source_relevance,
)


class SourceRelevanceTests(unittest.TestCase):
    def test_classifies_direct_support_for_rag_evaluation_source(self):
        result = classify_source_relevance(
            {
                "evidence_type": "external",
                "source": "arxiv.org",
                "title": "Hybrid RAG benchmark",
                "url": "https://arxiv.org/html/example",
                "excerpt": "Hybrid retrieval and agentic graph RAG evaluation benchmark results.",
                "source_quality": "academic",
            },
            topic="RAG",
        )

        self.assertEqual(result["relevance_label"], "direct_support")
        self.assertGreaterEqual(result["relevance_score"], 0.8)
        self.assertIn("rag_core_match", result["relevance_reasons"])

    def test_classifies_partial_support_for_rag_tooling_context(self):
        result = classify_source_relevance(
            {
                "evidence_type": "external",
                "source": "braintrust.dev",
                "title": "Best RAG Evaluation Tools in 2026",
                "url": "https://www.braintrust.dev/articles/best-rag-evaluation-tools",
                "excerpt": "RAG evaluation tools and observability workflows.",
                "source_quality": "generic",
            },
            topic="RAG",
        )

        self.assertEqual(result["relevance_label"], "partial_support")
        self.assertIn("claim_term_match", result["relevance_reasons"])

    def test_classifies_weak_context_for_definition_only_source(self):
        result = classify_source_relevance(
            {
                "evidence_type": "external",
                "source": "en.wikipedia.org",
                "title": "Retrieval-augmented generation",
                "url": "https://en.wikipedia.org/wiki/Retrieval-augmented_generation",
                "excerpt": "Retrieval-augmented generation is a technique.",
                "source_quality": "generic",
            },
            topic="RAG",
        )

        self.assertEqual(result["relevance_label"], "weak_context")

    def test_classifies_irrelevant_context_when_rag_terms_are_absent(self):
        result = classify_source_relevance(
            {
                "evidence_type": "external",
                "source": "example.com",
                "title": "AI SOC roles",
                "url": "https://example.com/ai-soc",
                "excerpt": "Security operations roles for autonomous alert triage.",
                "source_quality": "generic",
            },
            topic="RAG",
        )

        self.assertEqual(result["relevance_label"], "irrelevant_context")

    def test_summarizes_source_relevance_counts(self):
        summary = summarize_source_relevance(
            [
                {
                    "evidence_type": "external",
                    "source": "arxiv.org",
                    "title": "Hybrid RAG benchmark",
                    "url": "https://arxiv.org/html/example",
                    "excerpt": "Hybrid retrieval and RAG evaluation benchmark.",
                    "source_quality": "academic",
                },
                {
                    "evidence_type": "external",
                    "source": "example.com",
                    "title": "AI SOC roles",
                    "url": "https://example.com/ai-soc",
                    "excerpt": "Security operations.",
                    "source_quality": "generic",
                },
            ],
            topic="RAG",
        )

        self.assertEqual(summary["external_count"], 2)
        self.assertEqual(summary["relevance_counts"]["direct_support"], 1)
        self.assertEqual(summary["relevance_counts"]["irrelevant_context"], 1)
        self.assertEqual(summary["relevance_status"], "mixed_relevance")

    def test_inspects_saved_trend_brief_without_external_api_calls(self):
        path = Path("docs/rag-transformation/briefs/trend-brief-rag-source-quality-2026-06-25.md")
        result = inspect_trend_brief_source_relevance(path.read_text(encoding="utf-8"), topic="RAG")

        self.assertEqual(result["external_count"], 3)
        self.assertGreaterEqual(result["relevance_counts"].get("direct_support", 0), 1)
        self.assertIn(result["relevance_status"], {"relevance_verified", "mixed_relevance"})


if __name__ == "__main__":
    unittest.main()
