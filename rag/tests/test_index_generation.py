"""Tests for last-known-good vector index generation publishing."""

import json
from pathlib import Path

from rag.index_generation import IndexGenerationStore


def _write_verified_generation(root: Path, generation_id: str, count: int = 3) -> Path:
    path = root / generation_id
    path.mkdir(parents=True)
    (path / "manifest.json").write_text(
        json.dumps({
            "generation_id": generation_id,
            "status": "verified",
            "chunk_count": count,
            "dates": ["2026-08-10"],
            "corpus_revision": "revision-1",
        }),
        encoding="utf-8",
    )
    return path


def test_publish_keeps_previous_generation_for_recovery(tmp_path):
    store = IndexGenerationStore(tmp_path)
    first = _write_verified_generation(tmp_path, "gen-1")
    store.activate(first)
    second = _write_verified_generation(tmp_path, "gen-2")

    store.activate(second)

    pointer = json.loads((tmp_path / "active-generation.json").read_text(encoding="utf-8"))
    assert pointer["active"] == "gen-2"
    assert pointer["previous"] == "gen-1"
    assert first.exists()


def test_resolve_active_falls_back_to_previous_verified_generation(tmp_path):
    store = IndexGenerationStore(tmp_path)
    previous = _write_verified_generation(tmp_path, "gen-good")
    broken = tmp_path / "gen-broken"
    broken.mkdir()
    (tmp_path / "active-generation.json").write_text(
        json.dumps({"active": "gen-broken", "previous": "gen-good"}),
        encoding="utf-8",
    )

    resolved = store.resolve_active()

    assert resolved == previous
    pointer = json.loads((tmp_path / "active-generation.json").read_text(encoding="utf-8"))
    assert pointer["active"] == "gen-good"


def test_resolve_verified_generation_selects_only_the_named_verified_generation(tmp_path):
    store = IndexGenerationStore(tmp_path)
    verified = _write_verified_generation(tmp_path, "gen-evaluation")
    staging = store.create_staging("gen-building")

    assert store.resolve_verified("gen-evaluation") == verified
    assert store.resolve_verified("gen-building") is None
    assert store.resolve_verified("../outside") is None
    assert staging.exists()


def test_restore_active_reverts_pointer_without_deleting_generations(tmp_path):
    store = IndexGenerationStore(tmp_path)
    current = _write_verified_generation(tmp_path, "gen-current")
    next_generation = _write_verified_generation(tmp_path, "gen-next")
    store.activate(current)
    store.activate(next_generation)

    assert store.restore_active("gen-current") == current
    assert store.resolve_active() == current
    assert next_generation.exists()


def test_failed_staging_never_changes_last_known_good_pointer(tmp_path):
    store = IndexGenerationStore(tmp_path)
    current = _write_verified_generation(tmp_path, "gen-current")
    store.activate(current)
    staging = store.create_staging("gen-next")
    (staging / "partial.bin").write_bytes(b"partial")

    store.mark_failed(staging, "build_failed")

    assert store.resolve_active() == current
    failed = json.loads((staging / "manifest.json").read_text(encoding="utf-8"))
    assert failed["status"] == "failed"
    assert failed["error_code"] == "build_failed"


def test_only_verified_generation_can_be_activated(tmp_path):
    store = IndexGenerationStore(tmp_path)
    staging = store.create_staging("gen-unverified")

    try:
        store.activate(staging)
    except ValueError as exc:
        assert "verified" in str(exc)
    else:
        raise AssertionError("unverified generation must not become active")


def test_shadow_generation_records_report_but_cannot_be_activated(tmp_path):
    store = IndexGenerationStore(tmp_path)
    staging = store.create_staging("shadow-next")
    verified = store.write_verified_manifest(
        staging,
        chunk_count=10,
        dates=["2026-08-10"],
        corpus_revision="revision-1",
        lexical_count=10,
    )

    manifest = store.mark_shadow_ready(staging, verified, {"output_record_count": 10})

    assert manifest["status"] == "shadow_ready"
    assert manifest["migration_report"]["output_record_count"] == 10
    try:
        store.activate(staging)
    except ValueError as exc:
        assert "verified" in str(exc)
    else:
        raise AssertionError("shadow generation must never become active implicitly")
