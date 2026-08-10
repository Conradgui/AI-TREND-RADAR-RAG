"""Tests for the versioned, auditable corpus publication contract."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rag.corpus_contract import (
    build_corpus_contract,
    validate_corpus_contract,
    write_corpus_contract,
)


class CorpusContractTests(unittest.TestCase):
    def _fixture(self, root: Path) -> None:
        (root / "manifest.json").write_text(
            json.dumps({"generated": "2026-08-10T00:17:00Z", "dates": []}),
            encoding="utf-8",
        )
        (root / "feed.xml").write_text("<rss />", encoding="utf-8")
        (root / "digests").mkdir()
        (root / "digests/search-index.json").write_text('{"topics":[]}', encoding="utf-8")
        dated = root / "digests/2026-08-10"
        dated.mkdir()
        (dated / "ai-topic-radar.md").write_text("# Daily", encoding="utf-8")
        (dated / "topic-pool.json").write_text('{"candidates":[]}', encoding="utf-8")
        (dated / "ai-weekly.md").write_text("# Weekly", encoding="utf-8")
        (root / "digests/web-state.json").write_text('{"internal":true}', encoding="utf-8")

    def test_contract_is_deterministic_and_marks_rollups_browse_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._fixture(root)

            first = build_corpus_contract(root, source_mode="hosted")
            second = build_corpus_contract(root, source_mode="hosted")

        self.assertEqual(first, second)
        self.assertEqual(first["schema_version"], 1)
        self.assertTrue(first["complete"])
        self.assertRegex(first["corpus_revision"], r"^[0-9a-f]{64}$")
        records = {record["path"]: record for record in first["files"]}
        self.assertTrue(records["digests/2026-08-10/ai-topic-radar.md"]["retrieval_eligible"])
        self.assertTrue(records["digests/2026-08-10/topic-pool.json"]["retrieval_eligible"])
        self.assertFalse(records["digests/2026-08-10/ai-weekly.md"]["retrieval_eligible"])
        self.assertNotIn("digests/web-state.json", records)
        for record in records.values():
            self.assertRegex(record["sha256"], r"^[0-9a-f]{64}$")
            self.assertGreater(record["size"], 0)

    def test_write_and_validate_detects_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._fixture(root)
            contract = write_corpus_contract(root, source_mode="hosted")

            self.assertEqual(validate_corpus_contract(root, contract), [])
            (root / "digests/2026-08-10/ai-topic-radar.md").write_text(
                "# Tampered", encoding="utf-8"
            )
            failures = validate_corpus_contract(root, contract)

        self.assertIn("checksum mismatch: digests/2026-08-10/ai-topic-radar.md", failures)

    def test_exact_validation_rejects_unlisted_public_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._fixture(root)
            contract = write_corpus_contract(root, source_mode="hosted")
            (root / "digests/2026-08-10/ai-monthly.md").write_text(
                "# Monthly", encoding="utf-8"
            )

            failures = validate_corpus_contract(root, contract, require_exact=True)

        self.assertIn(
            "contract does not exactly match current public corpus",
            failures,
        )

    def test_validation_rejects_invalid_revision_source_and_duplicate_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._fixture(root)
            contract = build_corpus_contract(root, source_mode="hosted")
            contract["source_mode"] = "unknown"
            contract["corpus_revision"] = "0" * 64
            contract["files"].append(dict(contract["files"][0]))

            failures = validate_corpus_contract(root, contract)

        self.assertIn("invalid source mode: unknown", failures)
        self.assertIn("corpus revision mismatch", failures)
        self.assertTrue(any(failure.startswith("duplicate file path:") for failure in failures))

    def test_validation_rejects_empty_or_incomplete_public_contract(self):
        contract = {
            "schema_version": 1,
            "source_mode": "hosted",
            "generated_at": "",
            "files": [],
            "tombstones": [],
            "corpus_revision": "0" * 64,
            "complete": True,
        }

        failures = validate_corpus_contract(Path("."), contract)

        self.assertIn("contract contains no public files", failures)
        self.assertIn("missing required public file: manifest.json", failures)
        self.assertIn("missing required public file: feed.xml", failures)
        self.assertIn("missing required public file: digests/search-index.json", failures)
        self.assertIn("contract contains no retrieval-eligible daily report", failures)


if __name__ == "__main__":
    unittest.main()
