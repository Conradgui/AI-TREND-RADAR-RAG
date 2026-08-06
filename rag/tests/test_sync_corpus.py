"""Tests for syncing published AI Trend Radar Pages corpus."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from rag.sync_corpus import (
    build_sync_plan,
    fetch_url,
    normalize_base_url,
    sync_corpus,
)


class SyncCorpusTests(unittest.TestCase):
    @patch("rag.sync_corpus.time.sleep")
    @patch("rag.sync_corpus.urlopen")
    def test_fetch_url_retries_transient_network_failures(self, mock_urlopen, _sleep):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b"ok"
        mock_urlopen.side_effect = [OSError("temporary TLS failure"), response]

        self.assertEqual(fetch_url("https://example.com/report"), b"ok")
        self.assertEqual(mock_urlopen.call_count, 2)

    def test_normalize_base_url_removes_trailing_slash(self):
        self.assertEqual(
            normalize_base_url("https://example.com/project/"),
            "https://example.com/project",
        )

    def test_build_sync_plan_includes_manifest_search_index_reports_and_topic_pools(self):
        manifest = {
            "dates": [
                {"date": "2026-06-21", "reports": ["ai-topic-radar"]},
                {"date": "2026-06-20", "reports": ["ai-topic-radar", "ai-weekly"]},
            ]
        }

        plan = build_sync_plan(manifest, days=1, report_types=("ai-topic-radar",))

        self.assertEqual(
            [item.relative_path for item in plan],
            [
                "manifest.json",
                "digests/search-index.json",
                "digests/2026-06-21/ai-topic-radar.md",
                "digests/2026-06-21/topic-pool.json",
            ],
        )

    def test_sync_corpus_writes_files_from_fetcher(self):
        manifest = {
            "generated": "2026-06-21T05:07:03.937Z",
            "dates": [{"date": "2026-06-21", "reports": ["ai-topic-radar"]}],
        }
        payloads = {
            "https://example.com/radar/manifest.json": json.dumps(manifest),
            "https://example.com/radar/digests/search-index.json": '{"topics":[]}',
            "https://example.com/radar/digests/2026-06-21/ai-topic-radar.md": "# Report",
            "https://example.com/radar/digests/2026-06-21/topic-pool.json": '{"candidates":[]}',
        }

        def fetcher(url: str) -> bytes:
            return payloads[url].encode("utf-8")

        with tempfile.TemporaryDirectory() as tmp:
            result = sync_corpus(
                base_url="https://example.com/radar",
                output_root=Path(tmp),
                days=1,
                fetcher=fetcher,
            )

            self.assertEqual(result.downloaded, 4)
            self.assertEqual(result.failed, [])
            self.assertEqual(result.synced_dates, ["2026-06-21"])
            self.assertRegex(result.date_fingerprints["2026-06-21"], r"^[0-9a-f]{64}$")
            self.assertEqual(
                json.loads((Path(tmp) / "manifest.json").read_text(encoding="utf-8")),
                manifest,
            )
            self.assertEqual(
                (Path(tmp) / "digests/2026-06-21/ai-topic-radar.md").read_text(encoding="utf-8"),
                "# Report",
            )

    def test_sync_corpus_catches_up_every_date_after_local_latest_beyond_recent_window(self):
        """A long offline gap must not be truncated by the recent recheck window."""
        remote_dates = ["2026-06-25", "2026-06-24", "2026-06-23", "2026-06-22", "2026-06-21"]
        manifest = {
            "generated": "2026-06-25T03:20:50.526Z",
            "dates": [
                {"date": date, "reports": ["ai-topic-radar"]}
                for date in remote_dates
            ],
        }
        payloads = {
            "https://example.com/radar/manifest.json": json.dumps(manifest),
            "https://example.com/radar/digests/search-index.json": '{"topics":[]}',
        }
        for date in remote_dates:
            payloads[f"https://example.com/radar/digests/{date}/ai-topic-radar.md"] = f"# {date} report"
            payloads[f"https://example.com/radar/digests/{date}/topic-pool.json"] = '{"candidates":[]}'

        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            local_report = output_root / "digests/2026-06-21/ai-topic-radar.md"
            local_report.parent.mkdir(parents=True)
            local_report.write_text("# Existing report", encoding="utf-8")

            result = sync_corpus(
                base_url="https://example.com/radar",
                output_root=output_root,
                days=2,
                fetcher=lambda url: payloads[url].encode("utf-8"),
                dry_run=True,
            )

        self.assertEqual(
            result.synced_dates,
            ["2026-06-22", "2026-06-23", "2026-06-24", "2026-06-25"],
        )
        self.assertEqual(result.available_dates, remote_dates[::-1])

    def test_sync_failure_preserves_the_last_complete_local_corpus(self):
        manifest = {
            "generated": "2026-08-05T03:20:50.526Z",
            "dates": [{"date": "2026-08-05", "reports": ["ai-topic-radar"]}],
        }
        payloads = {
            "https://example.com/radar/manifest.json": json.dumps(manifest),
            "https://example.com/radar/digests/search-index.json": '{"topics":[]}',
            "https://example.com/radar/digests/2026-08-05/ai-topic-radar.md": "# New report",
        }

        def fetcher(url: str) -> bytes:
            if url.endswith("topic-pool.json"):
                raise OSError("upstream interrupted")
            return payloads[url].encode("utf-8")

        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            old_report = output_root / "digests/2026-08-05/ai-topic-radar.md"
            old_report.parent.mkdir(parents=True)
            old_report.write_text("# Last known good report", encoding="utf-8")
            old_manifest = output_root / "manifest.json"
            old_manifest.write_text('{"generated":"old","dates":[]}', encoding="utf-8")

            result = sync_corpus(
                base_url="https://example.com/radar",
                output_root=output_root,
                days=1,
                fetcher=fetcher,
            )

            self.assertEqual(len(result.failed), 1)
            self.assertEqual(old_report.read_text(encoding="utf-8"), "# Last known good report")
            self.assertEqual(old_manifest.read_text(encoding="utf-8"), '{"generated":"old","dates":[]}')

    def test_sync_manifest_lists_only_reports_available_on_local_disk(self):
        remote_manifest = {
            "generated": "2026-08-05T03:20:50.526Z",
            "dates": [
                {"date": "2026-08-05", "reports": ["ai-topic-radar"]},
                {"date": "2026-08-04", "reports": ["ai-topic-radar"]},
            ],
        }
        payloads = {
            "https://example.com/radar/manifest.json": json.dumps(remote_manifest),
            "https://example.com/radar/digests/search-index.json": '{"topics":[]}',
            "https://example.com/radar/digests/2026-08-05/ai-topic-radar.md": "# New report",
            "https://example.com/radar/digests/2026-08-05/topic-pool.json": '{"candidates":[]}',
            "https://example.com/radar/digests/2026-08-04/ai-topic-radar.md": "# Previous report",
            "https://example.com/radar/digests/2026-08-04/topic-pool.json": '{"candidates":[]}',
        }

        def fetcher(url: str) -> bytes:
            return payloads[url].encode("utf-8")

        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            existing = output_root / "digests/2026-06-21/ai-topic-radar.md"
            existing.parent.mkdir(parents=True)
            existing.write_text("# Existing report", encoding="utf-8")

            sync_corpus(
                base_url="https://example.com/radar",
                output_root=output_root,
                days=1,
                fetcher=fetcher,
            )

            local_manifest = json.loads((output_root / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(
                local_manifest["dates"],
                [
                    {"date": "2026-08-05", "reports": ["ai-topic-radar"]},
                    {"date": "2026-08-04", "reports": ["ai-topic-radar"]},
                    {"date": "2026-06-21", "reports": ["ai-topic-radar"]},
                ],
            )

    def test_dry_run_reports_changed_dates_without_writing_files(self):
        manifest = {
            "generated": "2026-08-05T03:20:50.526Z",
            "dates": [{"date": "2026-08-05", "reports": ["ai-topic-radar"]}],
        }
        payloads = {
            "https://example.com/radar/manifest.json": json.dumps(manifest),
            "https://example.com/radar/digests/search-index.json": '{"topics":[]}',
            "https://example.com/radar/digests/2026-08-05/ai-topic-radar.md": "# Changed report",
            "https://example.com/radar/digests/2026-08-05/topic-pool.json": '{"candidates":[]}',
        }

        def fetcher(url: str) -> bytes:
            return payloads[url].encode("utf-8")

        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            existing = output_root / "digests/2026-08-05/ai-topic-radar.md"
            existing.parent.mkdir(parents=True)
            existing.write_text("# Last known good report", encoding="utf-8")

            result = sync_corpus(
                base_url="https://example.com/radar",
                output_root=output_root,
                days=1,
                fetcher=fetcher,
                dry_run=True,
            )

            self.assertEqual(result.changed_dates, ["2026-08-05"])
            self.assertIn("digests/2026-08-05/ai-topic-radar.md", result.changed_files)
            self.assertEqual(result.upstream_latest_date, "2026-08-05")
            self.assertEqual(existing.read_text(encoding="utf-8"), "# Last known good report")
            self.assertFalse((output_root / "manifest.json").exists())

    def test_dry_run_reports_actual_local_latest_date_not_projected_date(self):
        manifest = {
            "generated": "2026-08-05T03:20:50.526Z",
            "dates": [{"date": "2026-08-05", "reports": ["ai-topic-radar"]}],
        }
        payloads = {
            "https://example.com/radar/manifest.json": json.dumps(manifest),
            "https://example.com/radar/digests/search-index.json": '{"topics":[]}',
            "https://example.com/radar/digests/2026-08-05/ai-topic-radar.md": "# New report",
            "https://example.com/radar/digests/2026-08-05/topic-pool.json": '{"candidates":[]}',
        }

        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            old_report = output_root / "digests/2026-06-21/ai-topic-radar.md"
            old_report.parent.mkdir(parents=True)
            old_report.write_text("# Old report", encoding="utf-8")

            result = sync_corpus(
                base_url="https://example.com/radar",
                output_root=output_root,
                days=1,
                fetcher=lambda url: payloads[url].encode("utf-8"),
                dry_run=True,
            )

        self.assertEqual(result.upstream_latest_date, "2026-08-05")
        self.assertEqual(result.local_latest_date, "2026-06-21")

    def test_invalid_upstream_json_does_not_replace_local_corpus(self):
        manifest = {
            "generated": "2026-08-05T03:20:50.526Z",
            "dates": [{"date": "2026-08-05", "reports": ["ai-topic-radar"]}],
        }
        payloads = {
            "https://example.com/radar/manifest.json": json.dumps(manifest),
            "https://example.com/radar/digests/search-index.json": '{"topics":[]}',
            "https://example.com/radar/digests/2026-08-05/ai-topic-radar.md": "# New report",
            "https://example.com/radar/digests/2026-08-05/topic-pool.json": "not-json",
        }

        def fetcher(url: str) -> bytes:
            return payloads[url].encode("utf-8")

        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            existing = output_root / "digests/2026-08-05/ai-topic-radar.md"
            existing.parent.mkdir(parents=True)
            existing.write_text("# Last known good report", encoding="utf-8")

            result = sync_corpus(
                base_url="https://example.com/radar",
                output_root=output_root,
                days=1,
                fetcher=fetcher,
            )

            self.assertEqual(len(result.failed), 1)
            self.assertIn("topic-pool.json", result.failed[0])
            self.assertEqual(existing.read_text(encoding="utf-8"), "# Last known good report")


if __name__ == "__main__":
    unittest.main()
