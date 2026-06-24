"""Tests for deterministic answer policy decisions."""

import unittest

from rag.answer_policy import apply_answer_policy, build_answer_policy
from rag.query_understanding import analyze_query


class AnswerPolicyTests(unittest.TestCase):
    def test_internal_only_question_uses_internal_grounded_mode(self):
        plan = analyze_query("Claude 最近有没有上线什么新功能？")
        policy = build_answer_policy(plan, citations=[{"citation_id": "c1"}])

        self.assertEqual(policy["mode"], "internal_grounded")
        self.assertFalse(policy["external_search_required"])
        self.assertIn("内部语料", policy["disclosure"])

    def test_needs_web_question_is_labeled_as_external_evidence_required(self):
        plan = analyze_query("请帮我梳理一下 RAG 技术的发展演进路线，以及相关的论文、文章等资料。")
        policy = build_answer_policy(plan, citations=[{"citation_id": "c1"}])

        self.assertEqual(policy["mode"], "needs_external_evidence")
        self.assertTrue(policy["external_search_required"])
        self.assertIn("外部证据", policy["disclosure"])
        self.assertIn("不要声称已经完成外部检索", policy["instruction"])

    def test_evidence_sufficiency_question_uses_sufficiency_review_mode(self):
        plan = analyze_query("当前语料中有没有足够证据说明某个 AI 产品已经取得明确商业成功？")
        policy = build_answer_policy(plan, citations=[{"citation_id": "c1"}])

        self.assertEqual(policy["mode"], "evidence_sufficiency_review")
        self.assertFalse(policy["external_search_required"])
        self.assertIn("证据是否足够", policy["disclosure"])
        self.assertIn("不要把 Product Hunt 热度", policy["instruction"])

    def test_no_citations_policy_blocks_llm_answering(self):
        plan = analyze_query("一个完全没有证据的话题")
        policy = build_answer_policy(plan, citations=[])

        self.assertEqual(policy["mode"], "evidence_insufficient")
        self.assertFalse(policy["should_call_llm"])

    def test_apply_answer_policy_adds_deterministic_disclosure_once(self):
        plan = analyze_query("Google OKF 和 ALM Wiki 有什么关系？")
        policy = build_answer_policy(plan, citations=[{"citation_id": "c1"}])

        answer = apply_answer_policy("内部语料只能说明部分背景。", policy)
        answer_again = apply_answer_policy(answer, policy)

        self.assertTrue(answer.startswith("证据范围："))
        self.assertIn("仍需要外部证据", answer)
        self.assertEqual(answer, answer_again)


if __name__ == "__main__":
    unittest.main()
