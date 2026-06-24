"""Tests for metadata filter construction from query plans."""

import unittest
import tempfile
from pathlib import Path

from rag.query_understanding import analyze_query
from rag.retrieval_planning import build_metadata_filter, load_latest_corpus_date


class RetrievalPlanningTests(unittest.TestCase):
    def test_github_question_builds_source_filter(self):
        plan = analyze_query("GitHub 热榜有什么值得关注的项目？")

        where = build_metadata_filter(plan, latest_corpus_date="2026-06-21")

        self.assertEqual(where, {"source_family": "GitHub"})

    def test_last_seven_days_builds_date_filter_from_latest_corpus_date(self):
        plan = analyze_query("过去一周有什么值得关注的选题？")

        where = build_metadata_filter(plan, latest_corpus_date="2026-06-21")

        self.assertEqual(
            where,
            {
                "date": {
                    "$in": [
                        "2026-06-15",
                        "2026-06-16",
                        "2026-06-17",
                        "2026-06-18",
                        "2026-06-19",
                        "2026-06-20",
                        "2026-06-21",
                    ]
                }
            },
        )

    def test_recent_corpus_first_builds_recent_date_filter(self):
        plan = analyze_query("Claude 最近有没有上线什么新功能？")

        where = build_metadata_filter(plan, latest_corpus_date="2026-06-21")

        self.assertEqual(where["date"]["$in"][0], "2026-06-08")
        self.assertEqual(where["date"]["$in"][-1], "2026-06-21")

    def test_github_weekly_question_combines_source_and_date_filters(self):
        plan = analyze_query("过去一周 GitHub 热榜上有什么值得关注的选题？")

        where = build_metadata_filter(plan, latest_corpus_date="2026-06-21")

        self.assertEqual(
            where,
            {
                "$and": [
                    {"source_family": "GitHub"},
                    {
                        "date": {
                            "$in": [
                                "2026-06-15",
                                "2026-06-16",
                                "2026-06-17",
                                "2026-06-18",
                                "2026-06-19",
                                "2026-06-20",
                                "2026-06-21",
                            ]
                        }
                    },
                ]
            },
        )

    def test_multi_source_question_builds_or_source_filter(self):
        plan = analyze_query("请比较 GitHub 热榜 AI 项目和 Product Hunt AI 产品三类信号的差异。")

        where = build_metadata_filter(plan, latest_corpus_date="2026-06-21")

        self.assertEqual(
            where,
            {
                "$or": [
                    {"source_family": "GitHub"},
                    {"source": "Product Hunt"},
                ]
            },
        )

    def test_no_filter_when_plan_has_no_source_or_filterable_time_window(self):
        plan = analyze_query("RAG 是什么？")

        self.assertIsNone(build_metadata_filter(plan, latest_corpus_date="2026-06-21"))

    def test_no_date_filter_without_latest_corpus_date(self):
        plan = analyze_query("过去一周有什么值得关注的选题？")

        self.assertIsNone(build_metadata_filter(plan, latest_corpus_date=None))

    def test_load_latest_corpus_date_reads_first_manifest_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "manifest.json"
            manifest.write_text('{"dates":[{"date":"2026-06-21"}]}', encoding="utf-8")

            self.assertEqual(load_latest_corpus_date(manifest), "2026-06-21")


if __name__ == "__main__":
    unittest.main()
