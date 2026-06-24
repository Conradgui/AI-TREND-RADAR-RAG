"""Tests for external evidence readiness evaluation."""

import unittest

from rag.eval_external_evidence import build_external_evidence_readiness


class EvalExternalEvidenceTests(unittest.TestCase):
    def test_readiness_passes_when_schema_and_disabled_tool_contract_hold(self):
        result = build_external_evidence_readiness()

        self.assertTrue(result["passed"])
        self.assertEqual(result["failed_checks"], [])
        self.assertEqual(result["web_search"]["available"], False)
        self.assertEqual(result["valid_external_citation_errors"], [])


if __name__ == "__main__":
    unittest.main()
