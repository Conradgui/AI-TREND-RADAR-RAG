"""Tests for serial staging build and atomic runtime publication."""

import asyncio
import json

import pytest

from rag.index_coordinator import IndexBuildCoordinator, VectorBuildResult
from rag.index_generation import IndexGenerationStore


def _seed_current(store: IndexGenerationStore):
    staging = store.create_staging("gen-current")
    store.write_verified_manifest(
        staging,
        chunk_count=2,
        dates=["2026-08-09"],
        corpus_revision="revision-old",
    )
    current = store.promote(staging)
    store.activate(current)
    return current


@pytest.mark.asyncio
async def test_failed_build_preserves_last_known_good(tmp_path):
    store = IndexGenerationStore(tmp_path)
    current = _seed_current(store)
    coordinator = IndexBuildCoordinator(store)

    async def fail(_path):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await coordinator.build_and_publish("gen-next", build=fail, prepare_runtime=lambda *_: None, publish_runtime=lambda _: None)

    assert store.resolve_active() == current
    failed = json.loads((tmp_path / "gen-next.staging" / "manifest.json").read_text(encoding="utf-8"))
    assert failed["status"] == "failed"


@pytest.mark.asyncio
async def test_runtime_is_prepared_before_pointer_and_state_are_published(tmp_path):
    store = IndexGenerationStore(tmp_path)
    _seed_current(store)
    coordinator = IndexBuildCoordinator(store)
    events = []

    async def build(path):
        events.append(("build", store.resolve_active().name))
        return VectorBuildResult(4, ["2026-08-10"], "revision-new")

    async def prepare(path, manifest):
        events.append(("prepare", store.resolve_active().name, path.name))
        return {"path": path, "manifest": manifest}

    def publish(runtime):
        events.append(("publish", store.resolve_active().name, runtime["path"].name))

    result = await coordinator.build_and_publish(
        "gen-next",
        build=build,
        prepare_runtime=prepare,
        publish_runtime=publish,
    )

    assert result.generation_path.name == "gen-next"
    assert events == [
        ("build", "gen-current"),
        ("prepare", "gen-current", "gen-next"),
        ("publish", "gen-next", "gen-next"),
    ]


@pytest.mark.asyncio
async def test_concurrent_builds_are_serialized(tmp_path):
    store = IndexGenerationStore(tmp_path)
    coordinator = IndexBuildCoordinator(store)
    active_builds = 0
    max_active_builds = 0

    async def run(generation_id):
        async def build(_path):
            nonlocal active_builds, max_active_builds
            active_builds += 1
            max_active_builds = max(max_active_builds, active_builds)
            await asyncio.sleep(0.01)
            active_builds -= 1
            return VectorBuildResult(1, ["2026-08-10"], generation_id)

        return await coordinator.build_and_publish(
            generation_id,
            build=build,
            prepare_runtime=lambda path, manifest: asyncio.sleep(0, result=(path, manifest)),
            publish_runtime=lambda _: None,
        )

    await asyncio.gather(run("gen-a"), run("gen-b"))

    assert max_active_builds == 1


@pytest.mark.asyncio
async def test_failed_runtime_publication_restores_previous_pointer(tmp_path):
    store = IndexGenerationStore(tmp_path)
    current = _seed_current(store)
    coordinator = IndexBuildCoordinator(store)

    async def build(_path):
        return VectorBuildResult(4, ["2026-08-10"], "revision-new")

    def fail_publish(_runtime):
        raise RuntimeError("publish failed")

    with pytest.raises(RuntimeError, match="publish failed"):
        await coordinator.build_and_publish(
            "gen-next",
            build=build,
            prepare_runtime=lambda path, _manifest: path,
            publish_runtime=fail_publish,
        )

    assert store.resolve_active() == current


@pytest.mark.asyncio
async def test_incomplete_atomic_migration_is_rejected_before_publication(tmp_path):
    store = IndexGenerationStore(tmp_path)
    current = _seed_current(store)
    coordinator = IndexBuildCoordinator(store)
    prepared = False

    async def build(_path):
        return VectorBuildResult(
            3,
            ["2026-08-10"],
            "revision-new",
            lexical_count=2,
            migration_report={
                "target_document_count": 3,
                "output_record_count": 3,
                "atr_id_coverage": 1.0,
            },
        )

    def prepare(*_args):
        nonlocal prepared
        prepared = True

    with pytest.raises(RuntimeError, match="publication gate"):
        await coordinator.build_and_publish(
            "gen-incomplete",
            build=build,
            prepare_runtime=prepare,
            publish_runtime=lambda _: None,
        )

    assert prepared is False
    assert store.resolve_active() == current
