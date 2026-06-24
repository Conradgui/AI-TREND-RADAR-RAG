"""Tests for keyword-based corpus availability benchmark."""

import tempfile
import unittest
from pathlib import Path

from rag.eval_corpus_availability import (
    CorpusDocument,
    build_corpus_availability_snapshot,
    load_corpus_documents,
    summarize_availability,
)
from rag.eval_golden import load_golden_questions


class CorpusAvailabilityBenchmarkTests(unittest.TestCase):
    def test_load_corpus_documents_reads_dated_markdown_and_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dated = root / "2026-06-21"
            dated.mkdir()
            (dated / "ai-topic-radar.md").write_text("RAG and Graph RAG", encoding="utf-8")
            (dated / "topic-pool.json").write_text('{"candidates":[]}', encoding="utf-8")

            documents = load_corpus_documents(root)

            self.assertEqual(len(documents), 2)
            self.assertEqual(documents[0].date, "2026-06-21")

    def test_snapshot_matches_keywords_inside_time_window(self):
        questions = [
            {
                "id": "Q4",
                "question": "过去一周 GitHub 热榜上有什么值得关注的选题？",
                "answerability": "internal-only",
                "expected_retrieval": {"keywords": ["GitHub", "repository"]},
            }
        ]
        documents = [
            CorpusDocument("2026-06-21", "topic-pool", "new", "GitHub repository AI tool"),
            CorpusDocument("2026-05-01", "topic-pool", "old", "GitHub repository old tool"),
        ]

        rows = build_corpus_availability_snapshot(questions, documents, latest_corpus_date="2026-06-21")

        self.assertTrue(rows[0]["likely_has_corpus_evidence"])
        self.assertEqual(rows[0]["coverage_level"], "strong")
        self.assertEqual(rows[0]["matched_dates"], ["2026-06-21"])
        self.assertEqual(rows[0]["matched_keyword_count"], 2)

    def test_snapshot_does_not_treat_one_generic_match_as_enough_evidence(self):
        questions = [
            {
                "id": "Q5",
                "question": "最近 Google 出了一个 OKF，它与 ALM Wiki 有什么关系？",
                "answerability": "needs-web",
                "expected_retrieval": {"keywords": ["Google", "OKF", "ALM Wiki", "knowledge framework", "user preference"]},
            }
        ]
        documents = [CorpusDocument("2026-06-21", "topic-pool", "x", "Google announced AI updates")]

        rows = build_corpus_availability_snapshot(questions, documents, latest_corpus_date="2026-06-21")

        self.assertEqual(rows[0]["coverage_level"], "weak")
        self.assertTrue(rows[0]["has_local_signals"])
        self.assertFalse(rows[0]["likely_has_corpus_evidence"])

    def test_summarize_availability_counts_rows(self):
        rows = [
            {"likely_has_corpus_evidence": True, "has_local_signals": True, "answerability": "needs-web"},
            {"likely_has_corpus_evidence": False, "has_local_signals": False, "answerability": "internal-only"},
        ]

        self.assertEqual(
            summarize_availability(rows),
            {
                "total": 2,
                "likely_has_corpus_evidence": 1,
                "likely_missing_corpus_evidence": 1,
                "needs_web_but_has_local_signals": 1,
            },
        )

    def test_actual_golden_questions_can_build_availability_snapshot(self):
        rows = build_corpus_availability_snapshot(
            load_golden_questions(),
            [CorpusDocument("2026-06-21", "topic-pool", "x", "Claude GitHub RAG Google OKF ALM Wiki")],
            latest_corpus_date="2026-06-21",
        )

        self.assertEqual(len(rows), 12)
        self.assertTrue(any(row["likely_has_corpus_evidence"] for row in rows))


if __name__ == "__main__":
    unittest.main()
