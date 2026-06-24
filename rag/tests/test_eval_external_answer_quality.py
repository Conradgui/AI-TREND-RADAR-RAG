"""Tests for external-evidence answer quality scoring."""

import unittest

from rag.eval_external_answer_quality import (
    score_external_answer_quality_rows,
    summarize_external_answer_quality,
)


class ExternalAnswerQualityTests(unittest.TestCase):
    def test_hybrid_answer_passes_with_internal_external_labels_and_quality_metadata(self):
        rows = [
            {
                "id": "Q5",
                "answer": "证据范围：当前回答基于 AI Trend Radar 内部语料和已检索到的外部证据。内部语料不足，外部证据显示官方信息，但关系尚不明确。",
                "citations": [
                    {
                        "evidence_type": "internal",
                        "date": "2026-06-21",
                        "source": "InfoQ 中国",
                        "title": "Google 想为 AI Agent 打造下一个 Kubernetes",
                        "citation_id": "c1",
                        "excerpt": "Internal evidence.",
                    },
                    {
                        "evidence_type": "external",
                        "provider": "tavily",
                        "source": "cloud.google.com",
                        "source_quality": "official",
                        "quality_score": 0.95,
                        "needs_deep_fetch": False,
                        "title": "How the Open Knowledge Format can improve data sharing",
                        "url": "https://cloud.google.com/example",
                        "retrieved_at": "2026-06-22",
                        "excerpt": "Official external evidence.",
                    },
                    {
                        "evidence_type": "external",
                        "provider": "tavily",
                        "source": "example.com",
                        "source_quality": "generic",
                        "quality_score": 0.55,
                        "needs_deep_fetch": True,
                        "title": "Generic analysis",
                        "url": "https://example.com/okf",
                        "retrieved_at": "2026-06-22",
                        "excerpt": "Generic external evidence.",
                    },
                ],
                "query_understanding": {
                    "answer_policy": {"mode": "internal_and_external_grounded"},
                    "external_search": {"attempted": True},
                },
            }
        ]

        scored = score_external_answer_quality_rows(rows)

        self.assertTrue(scored[0]["passed"])
        self.assertEqual(scored[0]["failed_checks"], [])

    def test_hybrid_answer_fails_without_internal_and_external_citation_mix(self):
        rows = [
            {
                "id": "Q5",
                "answer": "证据范围：当前回答基于外部证据。外部证据显示 OKF 的信息。",
                "citations": [
                    {
                        "evidence_type": "external",
                        "provider": "tavily",
                        "source": "cloud.google.com",
                        "source_quality": "official",
                        "quality_score": 0.95,
                        "needs_deep_fetch": False,
                        "title": "OKF",
                        "url": "https://cloud.google.com/example",
                        "retrieved_at": "2026-06-22",
                        "excerpt": "Official evidence.",
                    }
                ],
                "query_understanding": {
                    "answer_policy": {"mode": "internal_and_external_grounded"},
                    "external_search": {"attempted": True},
                },
            }
        ]

        scored = score_external_answer_quality_rows(rows)

        self.assertFalse(scored[0]["passed"])
        self.assertIn("missing_internal_external_citation_mix", scored[0]["failed_checks"])

    def test_weak_external_sources_require_uncertainty_language(self):
        rows = [
            {
                "id": "Q5",
                "answer": "证据范围：当前回答基于 AI Trend Radar 内部语料和外部证据。内部语料和外部证据已经证明 OKF 是 ALM Wiki 的替代方案。",
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
                        "provider": "tavily",
                        "source": "example.com",
                        "source_quality": "generic",
                        "quality_score": 0.55,
                        "needs_deep_fetch": True,
                        "title": "Generic analysis",
                        "url": "https://example.com/okf",
                        "retrieved_at": "2026-06-22",
                        "excerpt": "Generic evidence.",
                    },
                ],
                "query_understanding": {
                    "answer_policy": {"mode": "internal_and_external_grounded"},
                    "external_search": {"attempted": True},
                },
            }
        ]

        scored = score_external_answer_quality_rows(rows)

        self.assertFalse(scored[0]["passed"])
        self.assertIn("weak_external_source_without_uncertainty", scored[0]["failed_checks"])

    def test_summary_counts_rows_and_common_failures(self):
        scored = [
            {"passed": True, "failed_checks": []},
            {"passed": False, "failed_checks": ["missing_internal_external_citation_mix"]},
            {"passed": False, "failed_checks": ["missing_internal_external_citation_mix", "missing_external_label"]},
        ]

        self.assertEqual(
            summarize_external_answer_quality(scored),
            {
                "total": 3,
                "passed": 1,
                "failed": 2,
                "failure_counts": {
                    "missing_internal_external_citation_mix": 2,
                    "missing_external_label": 1,
                },
            },
        )


if __name__ == "__main__":
    unittest.main()
