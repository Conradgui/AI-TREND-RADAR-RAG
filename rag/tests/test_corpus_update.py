"""Behavior tests for the single corpus-update interface used by launchers."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rag.corpus_update import summarize_update_state, update_corpus
from rag.sync_corpus import SyncResult


class CorpusUpdateTests(unittest.IsolatedAsyncioTestCase):
    def test_public_summary_hides_internal_fingerprints_and_date_lists(self):
        summary = summarize_update_state(
            {
                "status": "updated",
                "last_success_at": "2026-08-05T10:38:35+00:00",
                "upstream_latest_date": "2026-08-05",
                "local_latest_date": "2026-08-05",
                "changed_dates": ["2026-08-04", "2026-08-05"],
                "ingested_dates": ["2026-08-04", "2026-08-05"],
                "indexed_fingerprints": {"2026-08-05": "private-internal-state"},
                "error": "",
            }
        )

        self.assertEqual(summary["changed_date_count"], 2)
        self.assertEqual(summary["ingested_date_count"], 2)
        self.assertNotIn("indexed_fingerprints", summary)
        self.assertNotIn("changed_dates", summary)

    async def test_update_ingests_only_dates_changed_by_sync(self):
        calls = []

        def syncer(**kwargs):
            return SyncResult(
                downloaded=6,
                failed=[],
                changed_files=[
                    "digests/2026-08-04/ai-topic-radar.md",
                    "digests/2026-08-05/ai-topic-radar.md",
                ],
                changed_dates=["2026-08-04", "2026-08-05"],
                upstream_latest_date="2026-08-05",
                local_latest_date="2026-08-05",
            )

        async def ingester(dates):
            calls.append(dates)
            return 2, {"is_consistent": True}

        with tempfile.TemporaryDirectory() as tmp:
            result = await update_corpus(
                syncer=syncer,
                ingester=ingester,
                state_path=Path(tmp) / "state.json",
            )

        self.assertEqual(calls, [["2026-08-05", "2026-08-04"]])
        self.assertEqual(result.status, "updated")
        self.assertEqual(result.ingested_dates, ["2026-08-05", "2026-08-04"])

    async def test_unchanged_corpus_skips_database_writes(self):
        async def ingester(dates):
            raise AssertionError("ingestion must not run when no corpus date changed")

        def syncer(**kwargs):
            return SyncResult(
                downloaded=4,
                failed=[],
                changed_files=[],
                changed_dates=[],
                upstream_latest_date="2026-08-05",
                local_latest_date="2026-08-05",
            )

        with tempfile.TemporaryDirectory() as tmp:
            result = await update_corpus(
                syncer=syncer,
                ingester=ingester,
                state_path=Path(tmp) / "state.json",
            )

        self.assertEqual(result.status, "unchanged")
        self.assertEqual(result.ingested_dates, [])

    async def test_locally_present_but_never_indexed_corpus_is_ingested(self):
        calls = []

        def syncer(**kwargs):
            return SyncResult(
                downloaded=4,
                failed=[],
                changed_files=[],
                changed_dates=[],
                synced_dates=["2026-08-05"],
                date_fingerprints={"2026-08-05": "fingerprint-v1"},
                available_dates=["2026-06-21", "2026-08-05"],
                available_fingerprints={
                    "2026-06-21": "old-fingerprint",
                    "2026-08-05": "fingerprint-v1",
                },
                upstream_latest_date="2026-08-05",
                local_latest_date="2026-08-05",
            )

        async def ingester(dates):
            calls.append(dates)
            return 1, {"is_consistent": True}

        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            result = await update_corpus(syncer=syncer, ingester=ingester, state_path=state_path)
            persisted = json.loads(state_path.read_text(encoding="utf-8"))

        self.assertEqual(calls, [["2026-08-05", "2026-06-21"]])
        self.assertEqual(result.ingested_dates, ["2026-08-05", "2026-06-21"])
        self.assertEqual(
            persisted["indexed_fingerprints"],
            {"2026-06-21": "old-fingerprint", "2026-08-05": "fingerprint-v1"},
        )

    async def test_update_persists_syncing_status_before_network_work_begins(self):
        observed = {}

        def syncer(**kwargs):
            observed.update(json.loads(state_path.read_text(encoding="utf-8")))
            return SyncResult(downloaded=1, failed=[])

        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            await update_corpus(syncer=syncer, state_path=state_path)

        self.assertEqual(observed["status"], "syncing")
        self.assertTrue(observed["checked_at"])

    async def test_matching_indexed_fingerprint_skips_reingestion(self):
        def syncer(**kwargs):
            return SyncResult(
                downloaded=4,
                failed=[],
                changed_files=[],
                changed_dates=[],
                synced_dates=["2026-08-05"],
                date_fingerprints={"2026-08-05": "fingerprint-v1"},
                upstream_latest_date="2026-08-05",
                local_latest_date="2026-08-05",
            )

        async def ingester(dates):
            raise AssertionError("matching indexed corpus must not be ingested twice")

        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            state_path.write_text(
                json.dumps({"indexed_fingerprints": {"2026-08-05": "fingerprint-v1"}}),
                encoding="utf-8",
            )
            result = await update_corpus(syncer=syncer, ingester=ingester, state_path=state_path)

        self.assertEqual(result.status, "unchanged")

    async def test_resume_only_ingests_dates_missing_from_a_partial_checkpoint(self):
        calls = []

        def syncer(**kwargs):
            return SyncResult(
                downloaded=4,
                failed=[],
                available_dates=["2026-08-04", "2026-08-05"],
                available_fingerprints={
                    "2026-08-04": "older-indexed",
                    "2026-08-05": "latest-pending",
                },
                upstream_latest_date="2026-08-05",
                local_latest_date="2026-08-05",
            )

        async def ingester(dates):
            calls.append(dates)
            return 1, {"is_consistent": True}

        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            state_path.write_text(
                json.dumps({"indexed_fingerprints": {"2026-08-04": "older-indexed"}}),
                encoding="utf-8",
            )
            result = await update_corpus(syncer=syncer, ingester=ingester, state_path=state_path)

        self.assertEqual(calls, [["2026-08-05"]])
        self.assertEqual(result.ingested_dates, ["2026-08-05"])

    async def test_sync_failure_records_failure_without_calling_ingestion(self):
        async def ingester(dates):
            raise AssertionError("ingestion must not run after sync failure")

        def syncer(**kwargs):
            return SyncResult(
                downloaded=2,
                failed=["digests/2026-08-05/topic-pool.json: unavailable"],
                upstream_latest_date="2026-08-05",
                local_latest_date="2026-08-04",
            )

        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            state_path.write_text(
                json.dumps({"last_success_at": "2026-08-04T00:00:00+00:00"}),
                encoding="utf-8",
            )

            result = await update_corpus(
                syncer=syncer,
                ingester=ingester,
                state_path=state_path,
            )
            persisted = json.loads(state_path.read_text(encoding="utf-8"))

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.last_success_at, "2026-08-04T00:00:00+00:00")
        self.assertEqual(persisted["status"], "failed")
        self.assertEqual(persisted["last_success_at"], "2026-08-04T00:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
