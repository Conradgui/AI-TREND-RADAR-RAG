"""Serialize vector generation builds and publish only verified runtimes."""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable

from rag.index_generation import IndexGenerationStore


@dataclass(frozen=True)
class VectorBuildResult:
    chunk_count: int
    dates: list[str]
    corpus_revision: str
    embedding_id: str = "chroma-default"
    lexical_count: int = 0
    migration_report: dict = field(default_factory=dict)

    def assert_publishable(self) -> None:
        """Reject partial atomic-corpus generations before pointer publication."""
        if not self.migration_report:
            return
        target = int(self.migration_report.get("target_document_count") or 0)
        output = int(self.migration_report.get("output_record_count") or 0)
        atr_coverage = float(self.migration_report.get("atr_id_coverage") or 0.0)
        if (
            target <= 0
            or self.chunk_count != target
            or output != target
            or self.lexical_count != target
            or atr_coverage < 1.0
        ):
            raise RuntimeError("atomic corpus publication gate failed")


@dataclass(frozen=True)
class BuildPublishResult:
    generation_path: Path
    manifest: dict


class IndexBuildCoordinator:
    """One-writer coordinator for staging, verification and active publication."""

    def __init__(self, store: IndexGenerationStore):
        self.store = store
        self._lock = asyncio.Lock()
        self.status = "idle"
        self.last_error_code = ""

    @property
    def updating(self) -> bool:
        return self._lock.locked()

    async def build_and_publish(
        self,
        generation_id: str,
        *,
        build: Callable[[Path], Awaitable[VectorBuildResult]],
        prepare_runtime: Callable[[Path, dict], object],
        publish_runtime: Callable[[object], object],
    ) -> BuildPublishResult:
        async with self._lock:
            self.status = "building"
            self.last_error_code = ""
            staging_path = self.store.create_staging(generation_id)
            failure_path = staging_path
            try:
                build_result = await build(staging_path)
                build_result.assert_publishable()
                manifest = self.store.write_verified_manifest(
                    staging_path,
                    chunk_count=build_result.chunk_count,
                    dates=build_result.dates,
                    corpus_revision=build_result.corpus_revision,
                    embedding_id=build_result.embedding_id,
                    lexical_count=build_result.lexical_count,
                )
                self.status = "preparing"
                generation_path = self.store.promote(staging_path)
                failure_path = generation_path
                runtime = prepare_runtime(generation_path, manifest)
                if inspect.isawaitable(runtime):
                    runtime = await runtime

                self.status = "publishing"
                self.store.activate(generation_path)
                published = publish_runtime(runtime)
                if inspect.isawaitable(published):
                    await published
                self.status = "ready"
                return BuildPublishResult(generation_path=generation_path, manifest=manifest)
            except Exception as exc:
                error_code = type(exc).__name__
                self.status = "failed"
                self.last_error_code = error_code
                if failure_path.exists():
                    self.store.mark_failed(failure_path, error_code)
                # Activation precedes the in-memory swap. If that swap fails,
                # heal the pointer to the previous verified generation now.
                self.store.resolve_active()
                raise
