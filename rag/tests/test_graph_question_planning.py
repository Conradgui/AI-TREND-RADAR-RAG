"""Tests for graph question planning."""

import unittest

from rag.graph_question_planning import (
    build_graph_question_plan,
    build_graph_question_plans,
    is_graph_relationship_question,
)


class GraphQuestionPlanningTests(unittest.TestCase):
    def test_builds_plan_for_rag_relationship_question(self):
        plan = build_graph_question_plan("RAG 相关主题是否跨多个日期和来源反复出现？")

        self.assertIsNotNone(plan)
        self.assertEqual(plan.entity_id, "rag")
        self.assertEqual(plan.answer_mode, "graph_relationship_summary")
        self.assertIn("entity_observation_date", plan.required_paths)
        self.assertIn("entity_observation_source", plan.required_paths)
        self.assertIn("entity_repeated_content", plan.required_paths)

    def test_builds_plan_for_openai_topic_date_question(self):
        plan = build_graph_question_plan("OpenAI 相关主题是否能通过图谱关联到多个趋势主题和日期？")

        self.assertIsNotNone(plan)
        self.assertEqual(plan.entity_id, "openai")
        self.assertIn("entity_observation_date", plan.required_paths)

    def test_generic_question_is_not_graph_relationship_question(self):
        self.assertFalse(is_graph_relationship_question("Claude 最近有什么新功能？"))
        self.assertIsNone(build_graph_question_plan("Claude 最近有什么新功能？"))

    def test_timeline_wording_builds_observation_graph_plan(self):
        plan = build_graph_question_plan("OpenAI 的发展历程和变化是什么？")

        self.assertIsNotNone(plan)
        self.assertEqual(plan.entity_id, "openai")
        self.assertIn("entity_observation_date", plan.required_paths)

    def test_relation_question_builds_one_plan_per_canonical_entity(self):
        plans = build_graph_question_plans("请分析 OpenAI 与 Apple 的跨日关联")

        self.assertEqual([plan.entity_id for plan in plans], ["openai", "apple"])
        self.assertEqual([plan.entity_label for plan in plans], ["OpenAI", "Apple"])


if __name__ == "__main__":
    unittest.main()
