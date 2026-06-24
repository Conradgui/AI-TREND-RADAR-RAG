"""Tests for syncing published AI Trend Radar Pages corpus."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rag.sync_corpus import (
    build_sync_plan,
    normalize_base_url,
    sync_corpus,
)


class SyncCorpusTests(unittest.TestCase):
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
            self.assertEqual((Path(tmp) / "manifest.json").read_text(encoding="utf-8"), json.dumps(manifest))
            self.assertEqual(
                (Path(tmp) / "digests/2026-06-21/ai-topic-radar.md").read_text(encoding="utf-8"),
                "# Report",
            )


if __name__ == "__main__":
    unittest.main()
