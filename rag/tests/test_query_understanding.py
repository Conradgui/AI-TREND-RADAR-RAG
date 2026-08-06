"""Tests for deterministic query-understanding plans."""

import unittest

from rag.query_understanding import analyze_query


class QueryUnderstandingTests(unittest.TestCase):
    def test_spaced_numeric_recent_window_is_parsed(self):
        plan = analyze_query("请联网核实 OpenAI 过去 7 天有哪些官方技术发布")

        self.assertEqual(plan.time_window["label"], "last_7_days")
        self.assertEqual(plan.time_window["days"], 7)
        self.assertTrue(plan.time_window["requires_date_filter"])

    def test_recent_rag_question_prefers_recent_trend_retrieval(self):
        plan = analyze_query("最近 RAG 领域有什么值得关注的新动向？")

        self.assertEqual(plan.intent, "recent_trend")
        self.assertIn("RAG", plan.topics)
        self.assertEqual(plan.time_window["label"], "recent_corpus_first")
        self.assertIn("Graph RAG", plan.retrieval_query)
        self.assertGreaterEqual(plan.top_k, 8)
        self.assertFalse(plan.needs_web_search)

    def test_rag_learning_map_marks_external_references_needed(self):
        plan = analyze_query("请帮我梳理一下 RAG 技术的发展演进路线，以及相关的论文、文章等资料。")

        self.assertEqual(plan.intent, "learning_map")
        self.assertEqual(plan.answerability_hint, "needs-web")
        self.assertTrue(plan.needs_web_search)
        self.assertEqual(plan.time_window["label"], "not_limited")
        self.assertGreaterEqual(plan.top_k, 10)

    def test_claude_recent_update_question_extracts_entities(self):
        plan = analyze_query("Claude 最近有没有上线什么新功能？比如新的插件或者类似的功能更新。")

        self.assertEqual(plan.intent, "product_update")
        self.assertIn("Claude", plan.entities)
        self.assertIn("Anthropic", plan.entities)
        self.assertIn("Artifacts", plan.retrieval_query)
        self.assertEqual(plan.time_window["label"], "recent_corpus_first")

    def test_github_weekly_question_extracts_source_and_time_window(self):
        plan = analyze_query("过去一周 GitHub 热榜上有什么值得关注的选题？")

        self.assertEqual(plan.intent, "source_specific_discovery")
        self.assertIn("GitHub", plan.sources)
        self.assertEqual(plan.time_window["label"], "last_7_days")
        self.assertEqual(plan.time_window["days"], 7)
        self.assertIn("GitHub Trending", plan.retrieval_query)

    def test_google_okf_alm_question_marks_comparison_and_web_need(self):
        plan = analyze_query(
            "最近 Google 出了一个 OKF，它与之前提出的 ALM Wiki 知识框架有什么关系？"
        )

        self.assertEqual(plan.intent, "technical_comparison")
        self.assertIn("Google", plan.entities)
        self.assertIn("OKF", plan.topics)
        self.assertIn("ALM Wiki", plan.topics)
        self.assertTrue(plan.needs_web_search)
        self.assertEqual(plan.answerability_hint, "needs-web")

    def test_product_hunt_question_extracts_source(self):
        plan = analyze_query("最近 Product Hunt 上有哪些 AI 产品值得深挖？为什么？")

        self.assertEqual(plan.intent, "source_specific_discovery")
        self.assertIn("Product Hunt", plan.sources)
        self.assertIn("heat signal", plan.retrieval_query)
        self.assertFalse(plan.needs_web_search)

    def test_openai_trend_question_extracts_entity(self):
        plan = analyze_query("OpenAI 最近相关的趋势信号主要集中在哪些方向？")

        self.assertEqual(plan.intent, "recent_trend")
        self.assertIn("OpenAI", plan.entities)
        self.assertIn("GPT", plan.retrieval_query)

    def test_evidence_sufficiency_question_uses_sufficiency_intent(self):
        plan = analyze_query("当前语料中有没有足够证据说明某个 AI 产品已经取得明确商业成功？")

        self.assertEqual(plan.intent, "evidence_sufficiency")
        self.assertEqual(plan.answerability_hint, "insufficient-risk")
        self.assertIn("avoid inferring proof", plan.routing_notes[0])


if __name__ == "__main__":
    unittest.main()
