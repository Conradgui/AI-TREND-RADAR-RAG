"""Tests for syncing published AI Trend Radar Pages corpus."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from rag.sync_corpus import (
    SyncResult,
    build_sync_diagnostics,
    build_sync_plan,
    fetch_url,
    normalize_base_url,
    sync_corpus,
    validate_sync_payload,
)


class SyncCorpusTests(unittest.TestCase):
    def test_sync_corpus_persists_runtime_manifest_when_configured(self):
        manifest = {
            "generated": "2026-08-25T10:00:00Z",
            "dates": [{"date": "2026-08-25", "reports": ["ai-topic-radar"]}],
        }
        payloads = {
            "https://example.com/radar/manifest.json": json.dumps(manifest),
            "https://example.com/radar/feed.xml": "<rss><channel /></rss>",
            "https://example.com/radar/digests/2026-08-25/ai-topic-radar.md": "# Report",
            "https://example.com/radar/digests/2026-08-25/topic-pool.json": '{"candidates":[]}',
        }

        def fetcher(url: str) -> bytes:
            return payloads[url].encode("utf-8")

        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            runtime_manifest = output_root / "digests/.runtime-manifest.json"
            with patch.dict(
                os.environ,
                {"RAG_RUNTIME_CORPUS_MANIFEST": str(runtime_manifest)},
            ):
                sync_corpus(
                    base_url="https://example.com/radar",
                    output_root=output_root,
                    days=1,
                    fetcher=fetcher,
                )

            self.assertEqual(
                json.loads(runtime_manifest.read_text(encoding="utf-8"))["generated"],
                "2026-08-25T10:00:00Z",
            )

    def test_sync_diagnostics_marks_stale_upstream_without_failing_the_sync(self):
        result = SyncResult(
            downloaded=4,
            failed=[],
            upstream_latest_date="2026-08-05",
            local_latest_date="2026-08-05",
        )

        diagnostics = build_sync_diagnostics(
            result,
            today=date(2026, 8, 10),
            warning_days=3,
        )

        self.assertEqual(diagnostics["freshness"], "stale")
        self.assertEqual(diagnostics["upstream_age_days"], 5)
        self.assertTrue(diagnostics["freshness_warning"])
        self.assertEqual(diagnostics["failed_count"], 0)

    @patch("rag.sync_corpus.time.sleep")
    @patch("rag.sync_corpus.urlopen")
    def test_fetch_url_retries_transient_network_failures(self, mock_urlopen, _sleep):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b"ok"
        mock_urlopen.side_effect = [OSError("temporary TLS failure"), response]

        self.assertEqual(fetch_url("https://example.com/report"), b"ok")
        self.assertEqual(mock_urlopen.call_count, 2)

    @patch("rag.sync_corpus.MAX_FILE_BYTES", 4)
    @patch("rag.sync_corpus.urlopen")
    def test_fetch_url_stops_reading_after_the_size_limit(self, mock_urlopen):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b"12345"
        mock_urlopen.return_value = response

        with self.assertRaisesRegex(ValueError, "response exceeds 4 bytes"):
            fetch_url("https://example.com/oversized")

        response.__enter__.return_value.read.assert_called_once_with(5)

    def test_normalize_base_url_removes_trailing_slash(self):
        self.assertEqual(
            normalize_base_url("https://example.com/project/"),
            "https://example.com/project",
        )

    def test_build_sync_plan_keeps_search_projection_local(self):
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
                "feed.xml",
                "digests/2026-06-21/ai-topic-radar.md",
                "digests/2026-06-21/topic-pool.json",
            ],
        )

    def test_build_sync_plan_downloads_rollups_for_browsing_without_extra_topic_pool(self):
        manifest = {
            "dates": [
                {
                    "date": "2026-08-09",
                    "reports": ["ai-topic-radar", "ai-weekly", "ai-monthly-en"],
                }
            ]
        }

        plan = build_sync_plan(manifest, days=1)

        self.assertEqual(
            [item.relative_path for item in plan],
            [
                "manifest.json",
                "feed.xml",
                "digests/2026-08-09/ai-topic-radar.md",
                "digests/2026-08-09/ai-weekly.md",
                "digests/2026-08-09/ai-monthly-en.md",
                "digests/2026-08-09/topic-pool.json",
            ],
        )

    def test_build_sync_plan_rejects_manifest_path_traversal(self):
        manifest = {
            "dates": [
                {"date": "../../outside", "reports": ["ai-topic-radar"]},
            ]
        }

        with self.assertRaisesRegex(ValueError, "invalid corpus date"):
            build_sync_plan(manifest, days=1)

    def test_validate_sync_payload_rejects_oversized_files(self):
        with self.assertRaisesRegex(ValueError, "payload exceeds 4 bytes"):
            validate_sync_payload("digests/search-index.json", b"12345", max_file_bytes=4)

    def test_sync_corpus_writes_files_from_fetcher(self):
        manifest = {
            "generated": "2026-06-21T05:07:03.937Z",
            "dates": [{"date": "2026-06-21", "reports": ["ai-topic-radar"]}],
        }
        payloads = {
            "https://example.com/radar/manifest.json": json.dumps(manifest),
            "https://example.com/radar/feed.xml": "<rss><channel /></rss>",
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
            self.assertEqual(
                (Path(tmp) / "feed.xml").read_text(encoding="utf-8"),
                "<rss><channel /></rss>",
            )
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
            "https://example.com/radar/feed.xml": "<rss><channel /></rss>",
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
            "https://example.com/radar/feed.xml": "<rss><channel /></rss>",
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
            "https://example.com/radar/feed.xml": "<rss><channel /></rss>",
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
            "https://example.com/radar/feed.xml": "<rss><channel /></rss>",
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
            "https://example.com/radar/feed.xml": "<rss><channel /></rss>",
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
            "https://example.com/radar/feed.xml": "<rss><channel /></rss>",
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

    def test_sync_does_not_replace_a_nonempty_local_summary_with_an_empty_upstream_summary(self):
        date = "2026-08-05"
        article_url = "https://openai.com/index/example/"
        manifest = {
            "generated": "2026-08-05T03:20:50.526Z",
            "dates": [{"date": date, "reports": ["ai-topic-radar"]}],
        }
        remote_markdown = (
            "| 分数 | 动作 | 题目 | 摘要 | 分类 |\n"
            "| ---: | --- | --- | --- | --- |\n"
            f"| 98 | 深挖 | [Updated title]({article_url}) |  | 分类 |\n"
        )
        remote_pool = {
            "candidates": [{"title": "Updated title", "url": article_url, "summary": ""}],
        }
        payloads = {
            "https://example.com/radar/manifest.json": json.dumps(manifest),
            "https://example.com/radar/feed.xml": "<rss><channel /></rss>",
            "https://example.com/radar/digests/search-index.json": '{"topics":[]}',
            f"https://example.com/radar/digests/{date}/ai-topic-radar.md": remote_markdown,
            f"https://example.com/radar/digests/{date}/topic-pool.json": json.dumps(remote_pool),
        }

        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            date_root = output_root / "digests" / date
            date_root.mkdir(parents=True)
            (date_root / "ai-topic-radar.md").write_text(
                remote_markdown.replace(" |  | 分类 |", " | Existing official summary. | 分类 |"),
                encoding="utf-8",
            )
            (date_root / "topic-pool.json").write_text(
                json.dumps({
                    "candidates": [
                        {"title": "Old title", "url": article_url, "summary": "Existing official summary."}
                    ]
                }),
                encoding="utf-8",
            )

            sync_corpus(
                base_url="https://example.com/radar",
                output_root=output_root,
                days=1,
                fetcher=lambda url: payloads[url].encode("utf-8"),
            )

            saved_pool = json.loads((date_root / "topic-pool.json").read_text(encoding="utf-8"))
            saved_markdown = (date_root / "ai-topic-radar.md").read_text(encoding="utf-8")

        self.assertEqual(saved_pool["candidates"][0]["title"], "Updated title")
        self.assertEqual(saved_pool["candidates"][0]["summary"], "Existing official summary.")
        self.assertIn("[Updated title]", saved_markdown)
        self.assertIn("| Existing official summary. | 分类 |", saved_markdown)

    def test_rollup_only_change_does_not_mark_daily_retrieval_for_reingestion(self):
        date_value = "2026-08-10"
        manifest = {
            "generated": "2026-08-10T00:17:00Z",
            "dates": [
                {
                    "date": date_value,
                    "reports": ["ai-topic-radar", "ai-weekly"],
                }
            ],
        }
        payloads = {
            "https://example.com/radar/manifest.json": json.dumps(manifest),
            "https://example.com/radar/feed.xml": "<rss><channel /></rss>",
            "https://example.com/radar/digests/search-index.json": '{"topics":[]}',
            f"https://example.com/radar/digests/{date_value}/ai-topic-radar.md": "# Daily",
            f"https://example.com/radar/digests/{date_value}/ai-weekly.md": "# Updated weekly",
            f"https://example.com/radar/digests/{date_value}/topic-pool.json": '{"candidates":[]}',
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dated = root / "digests" / date_value
            dated.mkdir(parents=True)
            (dated / "ai-topic-radar.md").write_text("# Daily", encoding="utf-8")
            (dated / "ai-weekly.md").write_text("# Old weekly", encoding="utf-8")
            (dated / "topic-pool.json").write_text(
                '{"candidates":[]}', encoding="utf-8"
            )

            result = sync_corpus(
                base_url="https://example.com/radar",
                output_root=root,
                days=1,
                fetcher=lambda url: payloads[url].encode("utf-8"),
                dry_run=True,
            )

        self.assertIn(f"digests/{date_value}/ai-weekly.md", result.changed_files)
        self.assertEqual(result.changed_dates, [])


if __name__ == "__main__":
    unittest.main()
