"""Tests for local-only hybrid structural chat benchmark summary."""

import unittest

from rag.eval_hybrid_structural_chat import summarize_hybrid_structural_rows


class HybridStructuralChatEvalTests(unittest.TestCase):
    def test_summary_counts_citation_and_policy_modes(self):
        rows = [
            {
                "expected_answerability": "internal-only",
                "citation_count": 2,
                "citations": [
                    {"evidence_type": "internal", "citation_id": "2026-06-21/graph-topic/rag/0"}
                ],
                "query_understanding": {"answer_policy": {"mode": "internal_grounded"}},
            },
            {
                "expected_answerability": "needs-web",
                "citation_count": 1,
                "citations": [{"evidence_type": "internal", "citation_id": "c1"}],
                "query_understanding": {"answer_policy": {"mode": "needs_external_evidence"}},
            },
            {
                "expected_answerability": "insufficient",
                "citation_count": 1,
                "citations": [{"evidence_type": "internal", "citation_id": "c2"}],
                "query_understanding": {"answer_policy": {"mode": "evidence_sufficiency_review"}},
            },
        ]

        self.assertEqual(
            summarize_hybrid_structural_rows(rows),
            {
                "total": 3,
                "with_citations": 3,
                "with_graph_citations": 1,
                "with_external_citations": 0,
                "needs_web_questions": 1,
                "evidence_sufficiency_review": 1,
                "answer_policy_modes": {
                    "evidence_sufficiency_review": 1,
                    "internal_grounded": 1,
                    "needs_external_evidence": 1,
                },
            },
        )


if __name__ == "__main__":
    unittest.main()
