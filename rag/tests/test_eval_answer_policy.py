"""Tests for answer-policy rubric scoring."""

import unittest

from rag.eval_answer_policy import score_live_chat_rows, summarize_rubric_rows


class EvalAnswerPolicyTests(unittest.TestCase):
    def test_needs_web_row_passes_when_disclosure_and_citations_exist(self):
        rows = [
            {
                "id": "Q5",
                "expected_answerability": "needs-web",
                "answer": "证据范围：当前回答只基于 AI Trend Radar 内部语料；该问题仍需要外部证据确认。\n内部语料不足以确认关系。",
                "citation_count": 2,
                "citations": [
                    {"date": "2026-06-21", "source": "ai-topic-radar", "title": "A", "citation_id": "c1", "excerpt": "x"},
                    {"date": "2026-06-20", "source": "ai-topic-radar", "title": "B", "citation_id": "c2", "excerpt": "y"},
                ],
            }
        ]

        scored = score_live_chat_rows(rows)

        self.assertTrue(scored[0]["passed"])
        self.assertEqual(scored[0]["failed_checks"], [])

    def test_row_fails_without_evidence_boundary_disclosure(self):
        rows = [
            {
                "id": "Q1",
                "expected_answerability": "internal-only",
                "answer": "最近 RAG 有很多新趋势。",
                "citation_count": 2,
                "citations": [
                    {"date": "2026-06-21", "source": "ai-topic-radar", "title": "A", "citation_id": "c1", "excerpt": "x"},
                    {"date": "2026-06-20", "source": "ai-topic-radar", "title": "B", "citation_id": "c2", "excerpt": "y"},
                ],
            }
        ]

        scored = score_live_chat_rows(rows)

        self.assertFalse(scored[0]["passed"])
        self.assertIn("missing_evidence_boundary_disclosure", scored[0]["failed_checks"])

    def test_summary_counts_passed_and_failed_rows(self):
        scored = [
            {"passed": True},
            {"passed": False},
            {"passed": False},
        ]

        self.assertEqual(
            summarize_rubric_rows(scored),
            {"total": 3, "passed": 1, "failed": 2},
        )


if __name__ == "__main__":
    unittest.main()
