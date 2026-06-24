"""Tests for deterministic semantic contradiction evaluation."""

import unittest

from rag.eval_semantic_contradiction import (
    score_semantic_contradiction_rows,
    summarize_semantic_contradiction_rows,
)


class SemanticContradictionEvalTests(unittest.TestCase):
    def test_weak_or_mixed_source_status_requires_uncertainty(self):
        rows = [
            {
                "id": "Q5",
                "answer": "OKF 与 ALM Wiki 的关系已经证明，并且显著提升用户偏好效率。",
                "citations": [{"evidence_type": "external", "source_quality": "generic"}],
                "query_understanding": {
                    "source_review": {"status": "mixed_quality"},
                    "answer_policy": {"mode": "internal_and_external_grounded"},
                },
            }
        ]
        checks = [
            {
                "id": "Q5-SC1",
                "question_id": "Q5",
                "label": "source_status_requires_uncertainty",
                "when_source_status_in": ["mixed_quality", "weak_only"],
            }
        ]

        scored = score_semantic_contradiction_rows(rows, checks)

        self.assertFalse(scored[0]["passed"])
        self.assertIn("missing_uncertainty_for_source_status", scored[0]["failed_checks"])
        self.assertIn("source_status_overclaim", scored[0]["failed_checks"])

    def test_mixed_source_status_passes_with_uncertainty_and_no_overclaim(self):
        rows = [
            {
                "id": "Q5",
                "answer": "现有证据不足，无法确认 OKF 与 ALM Wiki 的直接关系。",
                "citations": [{"evidence_type": "external", "source_quality": "official"}],
                "query_understanding": {
                    "source_review": {"status": "mixed_quality"},
                    "answer_policy": {"mode": "internal_and_external_grounded"},
                },
            }
        ]
        checks = [
            {
                "id": "Q5-SC1",
                "question_id": "Q5",
                "label": "source_status_requires_uncertainty",
                "when_source_status_in": ["mixed_quality", "weak_only"],
            }
        ]

        scored = score_semantic_contradiction_rows(rows, checks)

        self.assertTrue(scored[0]["passed"])

    def test_external_claim_fails_without_external_citation_or_uncertainty(self):
        rows = [
            {
                "id": "Q2",
                "answer": "RAG 的发展路线已经有论文和外部资料充分证明。",
                "citations": [{"evidence_type": "internal"}],
                "query_understanding": {
                    "source_review": {"status": "internal_only"},
                    "answer_policy": {"mode": "needs_external_evidence"},
                },
            }
        ]
        checks = [
            {
                "id": "Q2-SC1",
                "question_id": "Q2",
                "label": "external_claim_requires_external_citation",
                "external_claim_terms_any": ["论文", "外部资料"],
                "min_external_citations": 1,
            }
        ]

        scored = score_semantic_contradiction_rows(rows, checks)

        self.assertFalse(scored[0]["passed"])
        self.assertIn(
            "external_claim_without_external_citation_or_uncertainty",
            scored[0]["failed_checks"],
        )

    def test_summary_counts_failures(self):
        scored = [
            {"passed": True, "failed_checks": []},
            {"passed": False, "failed_checks": ["source_status_overclaim"]},
        ]

        self.assertEqual(
            summarize_semantic_contradiction_rows(scored),
            {
                "total": 2,
                "passed": 1,
                "failed": 1,
                "failure_counts": {"source_status_overclaim": 1},
            },
        )


if __name__ == "__main__":
    unittest.main()
