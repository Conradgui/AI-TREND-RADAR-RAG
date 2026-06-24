"""Tests for tool-routing benchmark rubric."""

import unittest

from rag.eval_tool_routing import score_tool_routing_rows, summarize_tool_routing_rows


class EvalToolRoutingTests(unittest.TestCase):
    def test_internal_only_row_passes_with_search_corpus_only(self):
        rows = [
            {
                "id": "Q1",
                "expected_answerability": "internal-only",
                "query_understanding": {
                    "tool_routing": {
                        "status": "internal_only_ready",
                        "external_tools_required": False,
                        "external_tools_available": False,
                        "steps": [{"tool": "search_corpus", "state": "executed"}],
                    }
                },
            }
        ]

        scored = score_tool_routing_rows(rows)

        self.assertTrue(scored[0]["passed"])
        self.assertEqual(scored[0]["failed_checks"], [])

    def test_needs_web_row_requires_planned_external_steps_marked_unavailable(self):
        rows = [
            {
                "id": "Q5",
                "expected_answerability": "needs-web",
                "query_understanding": {
                    "tool_routing": {
                        "status": "external_required_not_available",
                        "external_tools_required": True,
                        "external_tools_available": False,
                        "steps": [
                            {"tool": "search_corpus", "state": "executed"},
                            {"tool": "web_search", "state": "planned_unavailable"},
                            {"tool": "fetch_url", "state": "planned_unavailable"},
                            {"tool": "compare_internal_and_external", "state": "planned_unavailable"},
                        ],
                    }
                },
            }
        ]

        scored = score_tool_routing_rows(rows)

        self.assertTrue(scored[0]["passed"])

    def test_needs_web_row_fails_when_external_tools_are_missing(self):
        rows = [
            {
                "id": "Q5",
                "expected_answerability": "needs-web",
                "query_understanding": {
                    "tool_routing": {
                        "status": "internal_only_ready",
                        "external_tools_required": False,
                        "external_tools_available": False,
                        "steps": [{"tool": "search_corpus", "state": "executed"}],
                    }
                },
            }
        ]

        scored = score_tool_routing_rows(rows)

        self.assertFalse(scored[0]["passed"])
        self.assertIn("missing_planned_external_tools", scored[0]["failed_checks"])

    def test_summary_counts_passed_and_failed_rows(self):
        scored = [{"passed": True}, {"passed": True}, {"passed": False}]

        self.assertEqual(
            summarize_tool_routing_rows(scored),
            {"total": 3, "passed": 2, "failed": 1},
        )


if __name__ == "__main__":
    unittest.main()
