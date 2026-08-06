"""Tests for deterministic tool-routing contracts."""

import unittest

from rag.answer_policy import build_answer_policy
from rag.query_understanding import analyze_query
from rag.tool_routing import build_tool_route, infer_search_task_type


class ToolRoutingTests(unittest.TestCase):
    def test_named_vendor_official_verification_uses_official_source_lookup(self):
        plan = analyze_query("请联网核实 OpenAI 过去 7 天有哪些官方技术发布")

        self.assertEqual(infer_search_task_type(plan), "official_source_lookup")

    def test_internal_only_question_routes_to_internal_corpus_only(self):
        plan = analyze_query("Claude 最近有没有上线什么新功能？")
        citations = [{"citation_id": "c1"}]
        policy = build_answer_policy(plan, citations)

        route = build_tool_route(plan, policy, citations)

        self.assertEqual(route["status"], "internal_only_ready")
        self.assertFalse(route["external_tools_required"])
        self.assertFalse(route["external_tools_available"])
        self.assertEqual(route["max_tool_calls"], 1)
        self.assertEqual([step["tool"] for step in route["steps"]], ["search_corpus"])

    def test_needs_web_question_plans_external_tools_but_marks_unavailable(self):
        plan = analyze_query("请帮我梳理一下 RAG 技术的发展演进路线，以及相关的论文、文章等资料。")
        citations = [{"citation_id": "c1"}]
        policy = build_answer_policy(plan, citations)

        route = build_tool_route(plan, policy, citations, configured_search_providers={"exa", "tavily"})

        self.assertEqual(route["status"], "external_required_not_available")
        self.assertTrue(route["external_tools_required"])
        self.assertFalse(route["external_tools_available"])
        self.assertEqual(route["max_tool_calls"], 4)
        self.assertEqual(
            [step["tool"] for step in route["steps"]],
            ["search_corpus", "web_search", "fetch_url", "compare_internal_and_external"],
        )
        self.assertEqual(route["steps"][1]["state"], "planned_unavailable")
        self.assertEqual(route["provider_route"]["primary_provider"], "exa")
        self.assertEqual(route["provider_route"]["provider_chain"][:2], ["exa", "tavily"])

    def test_no_citations_stops_after_internal_search(self):
        plan = analyze_query("一个没有内部证据的问题")
        citations = []
        policy = build_answer_policy(plan, citations)

        route = build_tool_route(plan, policy, citations)

        self.assertEqual(route["status"], "evidence_insufficient")
        self.assertEqual(route["max_tool_calls"], 1)
        self.assertEqual([step["tool"] for step in route["steps"]], ["search_corpus"])
        self.assertIn("补充语料", route["fallback"])


if __name__ == "__main__":
    unittest.main()
