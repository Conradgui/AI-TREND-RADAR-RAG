"""Tests for live chat benchmark helpers without calling an LLM."""

import unittest

from rag.eval_live_chat import summarize_live_chat_snapshot


class LiveChatEvalTests(unittest.TestCase):
    def test_summarize_live_chat_snapshot_counts_citations_and_web_questions(self):
        rows = [
            {"citation_count": 2, "expected_answerability": "internal-only"},
            {"citation_count": 0, "expected_answerability": "needs-web"},
        ]

        self.assertEqual(
            summarize_live_chat_snapshot(rows),
            {
                "total": 2,
                "with_citations": 1,
                "without_citations": 1,
                "needs_web_questions": 1,
            },
        )


if __name__ == "__main__":
    unittest.main()
