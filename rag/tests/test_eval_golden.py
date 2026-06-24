"""Tests for golden question evaluation assets."""

import unittest
from pathlib import Path

from rag.eval_golden import load_golden_questions, summarize_eval_readiness, validate_golden_questions


GOLDEN_PATH = Path("docs/rag-transformation/evals/golden-questions.json")


class GoldenQuestionEvalTests(unittest.TestCase):
    def test_actual_golden_question_file_is_valid(self):
        questions = load_golden_questions(GOLDEN_PATH)
        errors = validate_golden_questions(questions)

        self.assertEqual(errors, [])
        self.assertEqual(len(questions), 12)
        self.assertEqual([q["id"] for q in questions], [f"Q{i}" for i in range(1, 13)])

    def test_validation_rejects_missing_required_fields(self):
        questions = [{"id": "QX", "question": "missing fields"}]

        errors = validate_golden_questions(questions)

        self.assertTrue(any("answerability" in error for error in errors))
        self.assertTrue(any("citation_requirement" in error for error in errors))

    def test_summarize_eval_readiness_counts_review_needed_items(self):
        questions = [
            {"id": "Q1", "answerability": "internal-only", "needs_conrad_review": False},
            {"id": "Q2", "answerability": "needs-web", "needs_conrad_review": True},
        ]

        summary = summarize_eval_readiness(questions)

        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["answerability"]["internal-only"], 1)
        self.assertEqual(summary["answerability"]["needs-web"], 1)
        self.assertEqual(summary["needs_conrad_review"], 1)


if __name__ == "__main__":
    unittest.main()
