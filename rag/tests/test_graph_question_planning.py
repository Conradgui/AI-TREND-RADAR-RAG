"""Tests for graph question planning."""

import unittest

from rag.graph_question_planning import build_graph_question_plan, is_graph_relationship_question


class GraphQuestionPlanningTests(unittest.TestCase):
    def test_builds_plan_for_rag_relationship_question(self):
        plan = build_graph_question_plan("RAG 相关主题是否跨多个日期和来源反复出现？")

        self.assertIsNotNone(plan)
        self.assertEqual(plan.entity_id, "rag")
        self.assertEqual(plan.answer_mode, "graph_relationship_summary")
        self.assertIn("entity_topic_date", plan.required_paths)
        self.assertIn("entity_topic_source", plan.required_paths)
        self.assertIn("entity_multiple_topics", plan.required_paths)

    def test_builds_plan_for_openai_topic_date_question(self):
        plan = build_graph_question_plan("OpenAI 相关主题是否能通过图谱关联到多个趋势主题和日期？")

        self.assertIsNotNone(plan)
        self.assertEqual(plan.entity_id, "openai")
        self.assertIn("entity_topic_date", plan.required_paths)

    def test_generic_question_is_not_graph_relationship_question(self):
        self.assertFalse(is_graph_relationship_question("Claude 最近有什么新功能？"))
        self.assertIsNone(build_graph_question_plan("Claude 最近有什么新功能？"))


if __name__ == "__main__":
    unittest.main()
