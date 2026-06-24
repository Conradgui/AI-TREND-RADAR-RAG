"""Tests for deterministic provider quality matrix scoring."""

import unittest

from rag.eval_provider_quality import (
    score_provider_quality_rows,
    summarize_provider_quality_rows,
)


class ProviderQualityEvalTests(unittest.TestCase):
    def test_internal_answer_with_graph_citation_passes(self):
        rows = [
            {
                "id": "Q1",
                "expected_answerability": "internal-only",
                "answer": "证据范围：当前回答基于 AI Trend Radar 内部语料和返回引用。",
                "citations": [
                    {
                        "evidence_type": "internal",
                        "date": "2026-06-21",
                        "source": "GitHub Search:rag",
                        "title": "HKUDS/LightRAG",
                        "citation_id": "2026-06-21/graph-topic/hkuds/lightrag",
                        "excerpt": "Graph evidence.",
                    }
                ],
                "query_understanding": {
                    "answer_policy": {"mode": "internal_grounded"},
                    "source_review": {"status": "internal_only"},
                },
            }
        ]

        scored = score_provider_quality_rows(rows)

        self.assertTrue(scored[0]["passed"])
        self.assertEqual(scored[0]["graph_citation_count"], 1)

    def test_needs_web_internal_grounded_fails(self):
        rows = [
            {
                "id": "Q5",
                "expected_answerability": "needs-web",
                "answer": "证据范围：当前回答基于 AI Trend Radar 内部语料。",
                "citations": [
                    {
                        "evidence_type": "internal",
                        "date": "2026-06-21",
                        "source": "ai-topic-radar",
                        "title": "Topic",
                        "citation_id": "c1",
                        "excerpt": "Internal evidence.",
                    }
                ],
                "query_understanding": {
                    "answer_policy": {"mode": "internal_grounded"},
                    "source_review": {"status": "internal_only"},
                },
            }
        ]

        scored = score_provider_quality_rows(rows)

        self.assertFalse(scored[0]["passed"])
        self.assertIn("needs_web_marked_internal_grounded", scored[0]["failed_checks"])

    def test_weak_external_source_must_be_reflected_in_source_review(self):
        rows = [
            {
                "id": "Q5",
                "expected_answerability": "needs-web",
                "answer": "证据范围：当前回答基于 AI Trend Radar 内部语料和外部证据。",
                "citations": [
                    {
                        "evidence_type": "internal",
                        "date": "2026-06-21",
                        "source": "ai-topic-radar",
                        "title": "Topic",
                        "citation_id": "c1",
                        "excerpt": "Internal evidence.",
                    },
                    {
                        "evidence_type": "external",
                        "provider": "brave",
                        "source": "example.com",
                        "source_quality": "generic",
                        "quality_score": 0.55,
                        "needs_deep_fetch": True,
                        "title": "Generic source",
                        "url": "https://example.com",
                        "retrieved_at": "2026-06-23",
                        "excerpt": "Generic evidence.",
                    },
                ],
                "query_understanding": {
                    "answer_policy": {"mode": "internal_and_external_grounded"},
                    "external_search": {"attempted": True},
                    "source_review": {"status": "mixed_quality", "weak_count": 0},
                },
            }
        ]

        scored = score_provider_quality_rows(rows)

        self.assertFalse(scored[0]["passed"])
        self.assertIn("weak_external_source_not_reflected_in_source_review", scored[0]["failed_checks"])

    def test_summary_counts_graph_external_and_failures(self):
        scored = [
            {"passed": True, "failed_checks": [], "graph_citation_count": 1, "external_citation_count": 0},
            {"passed": False, "failed_checks": ["missing_citations"], "graph_citation_count": 0, "external_citation_count": 1},
        ]

        self.assertEqual(
            summarize_provider_quality_rows(scored),
            {
                "total": 2,
                "passed": 1,
                "failed": 1,
                "with_graph_citations": 1,
                "with_external_citations": 1,
                "failure_counts": {"missing_citations": 1},
            },
        )


if __name__ == "__main__":
    unittest.main()
