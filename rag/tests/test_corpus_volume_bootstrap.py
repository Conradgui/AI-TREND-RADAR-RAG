"""Startup contract for the Docker-backed browsable corpus."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rag.corpus_volume_bootstrap import bootstrap_corpus_volume


def _write_manifest(root: Path, generated: str, date: str = "2026-08-22") -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "generated": generated,
                "dates": [{"date": date, "reports": ["ai-topic-radar"]}],
            }
        ),
        encoding="utf-8",
    )


def test_startup_seeds_persistent_volume_from_newer_bundled_corpus(tmp_path: Path) -> None:
    bundled = tmp_path / "bundled"
    runtime_digests = tmp_path / "runtime" / "digests"
    public_manifest = tmp_path / "runtime" / "manifest.json"
    _write_manifest(bundled, "2026-08-24T09:14:45Z")
    report = bundled / "digests/2026-08-22/ai-topic-radar.md"
    report.parent.mkdir(parents=True)
    report.write_text("# 2026-08-22 report", encoding="utf-8")

    result = bootstrap_corpus_volume(
        bundled_root=bundled,
        runtime_digests=runtime_digests,
        public_manifest=public_manifest,
    )

    assert result.source == "bundled"
    assert (runtime_digests / "2026-08-22/ai-topic-radar.md").read_text() == (
        "# 2026-08-22 report"
    )
    assert json.loads(public_manifest.read_text())["generated"] == "2026-08-24T09:14:45Z"
    assert json.loads((runtime_digests / ".runtime-manifest.json").read_text())[
        "generated"
    ] == "2026-08-24T09:14:45Z"


def test_startup_preserves_a_newer_runtime_corpus(tmp_path: Path) -> None:
    bundled = tmp_path / "bundled"
    runtime_digests = tmp_path / "runtime" / "digests"
    public_manifest = tmp_path / "runtime" / "manifest.json"
    _write_manifest(bundled, "2026-08-22T00:00:00Z", date="2026-08-22")
    bundled_report = bundled / "digests/2026-08-22/ai-topic-radar.md"
    bundled_report.parent.mkdir(parents=True)
    bundled_report.write_text("old bundled report", encoding="utf-8")
    _write_manifest(runtime_digests, "2026-08-25T00:00:00Z", date="2026-08-25")
    (runtime_digests / "manifest.json").replace(runtime_digests / ".runtime-manifest.json")
    runtime_report = runtime_digests / "2026-08-25/ai-topic-radar.md"
    runtime_report.parent.mkdir(parents=True)
    runtime_report.write_text("new runtime report", encoding="utf-8")

    result = bootstrap_corpus_volume(
        bundled_root=bundled,
        runtime_digests=runtime_digests,
        public_manifest=public_manifest,
    )

    assert result.source == "runtime"
    assert runtime_report.read_text() == "new runtime report"
    assert not (runtime_digests / "2026-08-22/ai-topic-radar.md").exists()
    assert json.loads(public_manifest.read_text())["generated"] == "2026-08-25T00:00:00Z"


def test_startup_rejects_a_manifest_with_missing_reports(tmp_path: Path) -> None:
    bundled = tmp_path / "bundled"
    _write_manifest(bundled, "2026-08-24T09:14:45Z")
    (bundled / "digests").mkdir()

    with pytest.raises(RuntimeError, match="missing reports: 2026-08-22/ai-topic-radar.md"):
        bootstrap_corpus_volume(
            bundled_root=bundled,
            runtime_digests=tmp_path / "runtime/digests",
            public_manifest=tmp_path / "runtime/manifest.json",
        )
