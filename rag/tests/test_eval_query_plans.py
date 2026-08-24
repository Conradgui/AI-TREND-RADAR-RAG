"""Tests for query-plan benchmark snapshot."""

import unittest

from rag.eval_golden import load_golden_questions
from rag.eval_query_plans import build_query_plan_snapshot, summarize_snapshot


class QueryPlanBenchmarkTests(unittest.TestCase):
    def test_build_query_plan_snapshot_has_one_row_per_question(self):
        questions = [
            {
                "id": "Q1",
                "question": "最近 RAG 领域有什么值得关注的新动向？",
                "answerability": "internal-only",
            },
            {
                "id": "Q4",
                "question": "过去一周 GitHub 热榜上有什么值得关注的选题？",
                "answerability": "internal-only",
            },
        ]

        rows = build_query_plan_snapshot(questions, latest_corpus_date="2026-06-21")

        self.assertEqual([row["id"] for row in rows], ["Q1", "Q4"])
        self.assertEqual(rows[0]["planned_intent"], "recent_trend")
        self.assertEqual(rows[1]["planned_intent"], "source_specific_discovery")
        clauses = rows[1]["metadata_filter"]["$and"]
        date_clause = next(
            clause["effective_date"]
            for clause in clauses
            if "effective_date" in clause
        )
        self.assertEqual(date_clause["$in"][0], "2026-06-15")

    def test_summarize_snapshot_counts_filters_and_web_need(self):
        rows = [
            {"planned_needs_web_search": False, "metadata_filter": None, "planned_intent": "recent_trend"},
            {"planned_needs_web_search": True, "metadata_filter": {"source": "GitHub"}, "planned_intent": "learning_map"},
        ]

        self.assertEqual(
            summarize_snapshot(rows),
            {
                "total": 2,
                "needs_web_search": 1,
                "with_metadata_filter": 1,
                "intents": {"learning_map": 1, "recent_trend": 1},
            },
        )

    def test_actual_golden_questions_can_build_snapshot(self):
        rows = build_query_plan_snapshot(load_golden_questions(), latest_corpus_date="2026-06-21")

        self.assertEqual(len(rows), 12)
        self.assertEqual(rows[3]["id"], "Q4")
        self.assertIn("GitHub", rows[3]["planned_sources"])
        self.assertIsNotNone(rows[3]["metadata_filter"])
        self.assertEqual(rows[7]["id"], "Q8")
        self.assertIn("Product Hunt", rows[7]["planned_sources"])
        self.assertEqual(rows[10]["id"], "Q11")
        self.assertEqual(rows[10]["planned_intent"], "evidence_sufficiency")


if __name__ == "__main__":
    unittest.main()
