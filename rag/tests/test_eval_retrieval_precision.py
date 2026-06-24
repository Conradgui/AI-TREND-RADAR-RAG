"""Tests for deterministic retrieval precision scoring."""

import unittest

from rag.eval_retrieval_precision import (
    classify_citations_for_question,
    score_retrieval_precision_rows,
    summarize_retrieval_precision_rows,
)


class RetrievalPrecisionEvalTests(unittest.TestCase):
    def test_classifies_relevant_weak_distracting_and_redundant_citations(self):
        seed = {
            "question_id": "Q5",
            "relevant_terms_any": ["OKF", "Open Knowledge Format"],
            "distracting_terms_any": ["Vue3"],
        }
        citations = [
            {"title": "Open Knowledge Format", "source": "Google", "excerpt": "OKF evidence"},
            {"title": "Open Knowledge Format", "source": "Google", "excerpt": "Duplicate OKF evidence"},
            {"title": "Vue3 AI coding practices", "source": "Juejin", "excerpt": "Vue3"},
            {"title": "Generic AI agent note", "source": "Blog", "excerpt": "Agent standards"},
        ]

        classified = classify_citations_for_question(citations, seed)

        self.assertEqual([row["classification"] for row in classified], [
            "relevant",
            "redundant",
            "distracting",
            "weak",
        ])

    def test_score_row_passes_when_relevant_count_and_noise_rate_are_within_threshold(self):
        rows = [
            {
                "id": "Q1",
                "citations": [
                    {"title": "Graph RAG", "source": "GitHub", "excerpt": "Graph RAG"},
                    {"title": "LightRAG", "source": "GitHub", "excerpt": "RAG"},
                ],
            }
        ]
        seeds = [
            {
                "question_id": "Q1",
                "relevant_terms_any": ["RAG", "Graph"],
                "min_relevant_citations": 2,
                "max_distracting_rate": 0.25,
            }
        ]

        scored = score_retrieval_precision_rows(rows, seeds)

        self.assertTrue(scored[0]["passed"])
        self.assertEqual(scored[0]["relevant_count"], 2)

    def test_score_row_fails_when_distracting_rate_is_too_high(self):
        rows = [
            {
                "id": "Q5",
                "citations": [
                    {"title": "OKF", "source": "Google", "excerpt": "Open Knowledge Format"},
                    {"title": "Vue3 practices", "source": "Juejin", "excerpt": "Vue3"},
                    {"title": "GLM benchmark", "source": "Blog", "excerpt": "GLM"},
                ],
            }
        ]
        seeds = [
            {
                "question_id": "Q5",
                "relevant_terms_any": ["OKF", "Open Knowledge Format"],
                "distracting_terms_any": ["Vue3", "GLM"],
                "min_relevant_citations": 1,
                "max_distracting_rate": 0.25,
            }
        ]

        scored = score_retrieval_precision_rows(rows, seeds)

        self.assertFalse(scored[0]["passed"])
        self.assertIn("distracting_rate_too_high", scored[0]["failed_checks"])

    def test_summary_counts_failures_and_noise(self):
        scored = [
            {"passed": True, "failed_checks": [], "citation_count": 2, "distracting_count": 0},
            {"passed": False, "failed_checks": ["missing_relevant_citations"], "citation_count": 3, "distracting_count": 2},
        ]

        self.assertEqual(
            summarize_retrieval_precision_rows(scored),
            {
                "total": 2,
                "passed": 1,
                "failed": 1,
                "citation_count": 5,
                "distracting_count": 2,
                "failure_counts": {"missing_relevant_citations": 1},
            },
        )


if __name__ == "__main__":
    unittest.main()
