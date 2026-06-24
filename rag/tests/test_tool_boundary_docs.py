"""Tests for web search tool boundary documentation."""

import json
import unittest
from pathlib import Path


BOUNDARY_DOC = Path("docs/rag-transformation/decisions/0002-web-search-tool-boundary.md")
GOLDEN_JSON = Path("docs/rag-transformation/evals/golden-questions.json")


class ToolBoundaryDocTests(unittest.TestCase):
    def test_boundary_doc_names_required_future_tools(self):
        content = BOUNDARY_DOC.read_text(encoding="utf-8")

        for tool_name in ("search_corpus", "web_search", "fetch_url", "compare_internal_and_external"):
            self.assertIn(tool_name, content)

    def test_needs_web_questions_are_not_marked_internal_only(self):
        questions = json.loads(GOLDEN_JSON.read_text(encoding="utf-8"))
        needs_web = [q for q in questions if q["answerability"] == "needs-web"]

        self.assertGreaterEqual(len(needs_web), 1)
        for question in needs_web:
            self.assertIn("external", question["web_search_policy"].lower())


if __name__ == "__main__":
    unittest.main()
