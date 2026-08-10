"""Tests for URL-labelled retrieval quality metrics."""

import unittest

from rag.eval_retrieval_quality import normalize_url, score_query, summarize


class RetrievalQualityEvalTests(unittest.TestCase):
    def test_normalize_url_removes_tracking_and_trailing_slash(self):
        self.assertEqual(
            normalize_url("https://Example.com/path/?utm_source=x&keep=1#part"),
            "https://example.com/path?keep=1",
        )

    def test_scores_precision_recall_f1_mrr_and_ndcg(self):
        query = {
            "id": "Q1",
            "answerable": True,
            "relevant": [
                {"url": "https://example.com/a", "grade": 3},
                {"url": "https://example.com/b", "grade": 1},
            ],
        }
        retrieved = [
            {"url": "https://example.com/noise", "title": "noise"},
            {"url": "https://example.com/a/", "title": "A"},
        ]

        score = score_query(query, retrieved, k=2)

        self.assertEqual(score["true_positive"], 1)
        self.assertEqual(score["precision_at_k"], 0.5)
        self.assertEqual(score["recall_at_k"], 0.5)
        self.assertEqual(score["f1_at_k"], 0.5)
        self.assertEqual(score["mrr"], 0.5)
        self.assertGreater(score["ndcg_at_k"], 0)
        self.assertLess(score["ndcg_at_k"], 1)

    def test_deduplicates_repeated_retrieval_identity(self):
        query = {"id": "Q1", "answerable": True, "relevant": [{"url": "https://example.com/a", "grade": 1}]}
        retrieved = [{"url": "https://example.com/a"}, {"url": "https://example.com/a/"}]

        score = score_query(query, retrieved, k=2)

        self.assertEqual(score["returned"], 1)
        self.assertEqual(score["true_positive"], 1)

    def test_unanswerable_query_requires_empty_retrieval(self):
        query = {"id": "Q0", "answerable": False, "relevant": []}

        rejected = score_query(query, [], k=10)
        hallucinated = score_query(query, [{"url": "https://example.com/noise"}], k=10)

        self.assertTrue(rejected["correct_rejection"])
        self.assertFalse(hallucinated["correct_rejection"])

    def test_summary_reports_macro_micro_and_query_success_accuracy(self):
        rows = [
            {
                "answerable": True,
                "query_success": True,
                "true_positive": 1,
                "relevant_total": 2,
                "precision_at_k": 0.1,
                "recall_at_k": 0.5,
                "f1_at_k": 0.1667,
                "mrr": 1.0,
                "ndcg_at_k": 0.8,
            },
            {"answerable": False, "query_success": True, "correct_rejection": True},
        ]

        summary = summarize(rows, k=10)

        self.assertEqual(summary["query_success_accuracy"], 1.0)
        self.assertEqual(summary["correct_rejection_rate"], 1.0)
        self.assertEqual(summary["micro"]["precision_at_k"], 0.1)
        self.assertEqual(summary["micro"]["recall_at_k"], 0.5)


if __name__ == "__main__":
    unittest.main()
