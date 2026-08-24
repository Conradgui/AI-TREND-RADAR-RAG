"""Tests for metadata filter construction from query plans."""

import unittest
import tempfile
from pathlib import Path

from rag.query_understanding import analyze_query
from rag.retrieval_planning import build_metadata_filter, load_latest_corpus_date, source_diversity_cap


class RetrievalPlanningTests(unittest.TestCase):
    def test_recent_time_intents_select_distinct_metadata_fields(self):
        cases = [
            ("最近发布了哪些模型？", "publication_date"),
            ("最近更新了哪些项目？", "source_updated_at"),
            ("最近收录了哪些内容？", "report_date"),
            ("最近有什么热门趋势？", "effective_date"),
        ]
        for question, expected_field in cases:
            where = build_metadata_filter(analyze_query(question), "2026-08-12")
            date_clause = next(
                clause for clause in where["$and"] if expected_field in clause
            )
            self.assertEqual(date_clause[expected_field]["$in"][-1], "2026-08-12")

    def test_temporal_synonyms_never_fall_back_to_unbounded_retrieval(self):
        for question, field in [
            ("新发布了哪些模型？", "publication_date"),
            ("近期收录了哪些内容？", "report_date"),
            ("本周日报收录了什么？", "report_date"),
        ]:
            where = build_metadata_filter(analyze_query(question), "2026-08-12")
            self.assertIsNotNone(where)
            clauses = where.get("$and", [where])
            self.assertTrue(any(field in clause for clause in clauses))

    def test_github_question_builds_source_filter(self):
        plan = analyze_query("GitHub 热榜有什么值得关注的项目？")

        where = build_metadata_filter(plan, latest_corpus_date="2026-06-21")

        self.assertEqual(
            where,
            {
                "$and": [
                    {"content_type": "topic_candidate"},
                    {"source_family": "GitHub"},
                ]
            },
        )

    def test_last_seven_days_builds_date_filter_from_latest_corpus_date(self):
        plan = analyze_query("过去一周有什么值得关注的选题？")

        where = build_metadata_filter(plan, latest_corpus_date="2026-06-21")

        self.assertEqual(
            where,
            {
                "$and": [
                    {"content_type": "topic_candidate"},
                    {
                        "effective_date": {
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

    def test_recent_corpus_first_builds_recent_date_filter(self):
        plan = analyze_query("Claude 最近有没有上线什么新功能？")

        where = build_metadata_filter(plan, latest_corpus_date="2026-06-21")

        self.assertEqual(where["$and"][0], {"content_type": "topic_candidate"})
        self.assertEqual(where["$and"][1]["effective_date"]["$in"][0], "2026-06-08")
        self.assertEqual(where["$and"][1]["effective_date"]["$in"][-1], "2026-06-21")

    def test_generic_recent_trends_use_structured_topic_candidates(self):
        plan = analyze_query("最近有什么热门趋势？")

        where = build_metadata_filter(plan, latest_corpus_date="2026-08-05")

        self.assertEqual(where["$and"][0], {"content_type": "topic_candidate"})
        self.assertEqual(where["$and"][1]["effective_date"]["$in"][-1], "2026-08-05")

    def test_github_weekly_question_combines_source_and_date_filters(self):
        plan = analyze_query("过去一周 GitHub 热榜上有什么值得关注的选题？")

        where = build_metadata_filter(plan, latest_corpus_date="2026-06-21")

        self.assertEqual(
            where,
            {
                "$and": [
                    {"content_type": "topic_candidate"},
                    {"source_family": "GitHub"},
                    {
                        "effective_date": {
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
                "$and": [
                    {"content_type": "topic_candidate"},
                    {
                        "$or": [
                            {"source_family": "GitHub"},
                            {"source": "Product Hunt"},
                        ]
                    },
                ]
            },
        )

    def test_no_filter_when_plan_has_no_source_or_filterable_time_window(self):
        plan = analyze_query("RAG 是什么？")

        self.assertIsNone(build_metadata_filter(plan, latest_corpus_date="2026-06-21"))

    def test_generic_discovery_keeps_structured_filter_without_latest_date(self):
        plan = analyze_query("过去一周有什么值得关注的选题？")

        self.assertEqual(
            build_metadata_filter(plan, latest_corpus_date=None),
            {"content_type": "topic_candidate"},
        )

    def test_load_latest_corpus_date_reads_first_manifest_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "manifest.json"
            manifest.write_text('{"dates":[{"date":"2026-06-21"}]}', encoding="utf-8")

            self.assertEqual(load_latest_corpus_date(manifest), "2026-06-21")

    def test_diversity_cap_only_applies_to_unfocused_trends(self):
        broad = analyze_query("最近有什么热门趋势？")
        focused = analyze_query("OpenAI 最近有哪些重要动态？")

        self.assertEqual(source_diversity_cap(broad), 2)
        self.assertIsNone(source_diversity_cap(focused))


if __name__ == "__main__":
    unittest.main()
