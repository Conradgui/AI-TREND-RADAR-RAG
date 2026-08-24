"""Tests for request-scoped evidence and answer marker validation."""

import unittest

from rag.evidence_ledger import EvidenceLedger, validate_evidence_markers


def _citation(citation_id: str, title: str) -> dict:
    return {
        "evidence_type": "internal",
        "date": "2026-06-21",
        "source": "Product Hunt",
        "title": title,
        "citation_id": citation_id,
        "excerpt": f"{title} evidence",
    }


class EvidenceLedgerTests(unittest.TestCase):
    def test_admit_assigns_request_scoped_ids_and_deduplicates(self):
        ledger = EvidenceLedger()

        admitted = ledger.admit([
            _citation("2026-06-21/topic-pool/0", "Claude Code Artifacts"),
            _citation("2026-06-21/topic-pool/0", "Claude Code Artifacts"),
            _citation("2026-06-21/topic-pool/1", "Zernio WhatsApp API"),
        ])

        self.assertEqual([item["evidence_id"] for item in admitted], ["E1", "E2"])
        self.assertEqual(len(ledger.records), 2)

    def test_validate_returns_claim_evidence_for_known_markers(self):
        ledger = EvidenceLedger()
        records = ledger.admit([_citation("2026-06-21/topic-pool/0", "Claude Code Artifacts")])

        validation = validate_evidence_markers(
            "Claude Code Artifacts 是当天的高分选题。[E1]",
            records,
        )

        self.assertTrue(validation["is_valid"])
        self.assertEqual(validation["unknown_evidence_ids"], [])
        self.assertEqual(validation["claim_evidence"][0]["evidence_ids"], ["E1"])

    def test_validate_rejects_unknown_or_missing_markers(self):
        ledger = EvidenceLedger()
        records = ledger.admit([_citation("2026-06-21/topic-pool/0", "Claude Code Artifacts")])

        unknown = validate_evidence_markers("不存在的引用。[E99]", records)
        missing = validate_evidence_markers("没有引用标记的结论。", records)

        self.assertFalse(unknown["is_valid"])
        self.assertEqual(unknown["unknown_evidence_ids"], ["E99"])
        self.assertFalse(missing["is_valid"])
        self.assertTrue(missing["missing_evidence_markers"])

    def test_graph_reasoning_evidence_gets_a_request_local_marker(self):
        ledger = EvidenceLedger()

        admitted = ledger.admit([{
            "evidence_type": "internal",
            "content_type": "graph_reasoning",
            "source": "Neo4j graph",
            "title": "OpenAI graph relationship evidence",
            "citation_id": "graph-reasoning/openai",
            "excerpt": "OpenAI 跨多个日期出现。",
        }])

        self.assertEqual(admitted[0]["evidence_id"], "E1")
        self.assertTrue(validate_evidence_markers("OpenAI 跨日出现。[E1]", admitted)["is_valid"])
