"""Tests for deterministic claim-level answer evaluation."""

import unittest

from rag.eval_claim_level import (
    score_claim_level_rows,
    summarize_claim_level_rows,
)


class ClaimLevelEvalTests(unittest.TestCase):
    def test_should_support_passes_with_terms_and_citations(self):
        rows = [
            {
                "id": "Q1",
                "answer": "Graph RAG 和 Agentic RAG 是近期值得关注的新方向。",
                "citations": [
                    {"evidence_type": "internal", "citation_id": "c1"},
                    {"evidence_type": "internal", "citation_id": "c2"},
                ],
            }
        ]
        claims = [
            {
                "id": "Q1-C1",
                "question_id": "Q1",
                "label": "should_support",
                "answer_must_contain_any": ["Graph RAG", "Agentic RAG"],
                "min_citations": 2,
                "required_citation_types": ["internal"],
            }
        ]

        scored = score_claim_level_rows(rows, claims)

        self.assertTrue(scored[0]["passed"])
        self.assertEqual(scored[0]["failed_checks"], [])

    def test_should_support_fails_when_external_citations_missing(self):
        rows = [
            {
                "id": "Q5",
                "answer": "OKF 需要外部证据确认。",
                "citations": [{"evidence_type": "internal", "citation_id": "c1"}],
            }
        ]
        claims = [
            {
                "id": "Q5-C1",
                "question_id": "Q5",
                "label": "should_support",
                "min_external_citations": 1,
            }
        ]

        scored = score_claim_level_rows(rows, claims)

        self.assertFalse(scored[0]["passed"])
        self.assertIn("missing_external_citations", scored[0]["failed_checks"])

    def test_should_avoid_fails_on_forbidden_overclaim(self):
        rows = [
            {
                "id": "Q5",
                "answer": "OKF 已经证明可以显著提升用户偏好效率。",
                "citations": [{"evidence_type": "external", "citation_id": "c1"}],
            }
        ]
        claims = [
            {
                "id": "Q5-C2",
                "question_id": "Q5",
                "label": "should_avoid",
                "answer_must_not_contain_any": ["已经证明", "显著提升"],
            }
        ]

        scored = score_claim_level_rows(rows, claims)

        self.assertFalse(scored[0]["passed"])
        self.assertIn("forbidden_answer_terms_present", scored[0]["failed_checks"])

    def test_should_mark_uncertain_passes_with_uncertainty_language(self):
        rows = [
            {
                "id": "Q5",
                "answer": "现有证据不足，无法确认 ALM Wiki 与 OKF 的具体关系。",
                "citations": [{"evidence_type": "external", "citation_id": "c1"}],
            }
        ]
        claims = [
            {
                "id": "Q5-C3",
                "question_id": "Q5",
                "label": "should_mark_uncertain",
            }
        ]

        scored = score_claim_level_rows(rows, claims)

        self.assertTrue(scored[0]["passed"])

    def test_summary_counts_failures(self):
        scored = [
            {"passed": True, "failed_checks": []},
            {"passed": False, "failed_checks": ["missing_external_citations"]},
        ]

        self.assertEqual(
            summarize_claim_level_rows(scored),
            {
                "total": 2,
                "passed": 1,
                "failed": 1,
                "failure_counts": {"missing_external_citations": 1},
            },
        )


if __name__ == "__main__":
    unittest.main()
