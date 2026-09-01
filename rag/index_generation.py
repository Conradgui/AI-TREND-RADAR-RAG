"""Atomic last-known-good vector index generation metadata."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


class IndexGenerationStore:
    """Own generation manifests and the small atomic active pointer.

    This module intentionally does not delete generations. Retention cleanup is
    a separate, explicit operation so a failed build cannot erase recovery data.
    """

    POINTER_NAME = "active-generation.json"
    MANIFEST_NAME = "manifest.json"

    def __init__(self, root: Path | str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.pointer_path = self.root / self.POINTER_NAME

    def create_staging(self, generation_id: str) -> Path:
        safe_id = self._validate_generation_id(generation_id)
        path = self.root / f"{safe_id}.staging"
        path.mkdir(parents=False, exist_ok=False)
        self._write_json(
            path / self.MANIFEST_NAME,
            {
                "generation_id": safe_id,
                "status": "building",
                "created_at": self._now(),
            },
        )
        return path

    def write_verified_manifest(
        self,
        path: Path,
        *,
        chunk_count: int,
        dates: list[str],
        corpus_revision: str,
        embedding_id: str = "chroma-default",
        lexical_count: int = 0,
    ) -> dict:
        generation_id = self._generation_id_from_path(path)
        manifest = {
            "generation_id": generation_id,
            "status": "verified",
            "created_at": self._now(),
            "verified_at": self._now(),
            "chunk_count": int(chunk_count),
            "dates": sorted(set(dates), reverse=True),
            "corpus_revision": str(corpus_revision),
            "embedding_id": str(embedding_id),
            "lexical_count": int(lexical_count),
        }
        if manifest["chunk_count"] <= 0:
            raise ValueError("verified generation must contain at least one chunk")
        self._write_json(path / self.MANIFEST_NAME, manifest)
        return manifest

    def mark_failed(self, path: Path, error_code: str) -> None:
        generation_id = self._generation_id_from_path(path)
        self._write_json(
            path / self.MANIFEST_NAME,
            {
                "generation_id": generation_id,
                "status": "failed",
                "failed_at": self._now(),
                "error_code": str(error_code),
            },
        )

    def mark_shadow_ready(self, path: Path, manifest: dict, migration_report: dict) -> dict:
        """Persist a reviewed-but-never-activatable shadow generation."""
        generation_id = self._generation_id_from_path(path)
        payload = {
            **manifest,
            "generation_id": generation_id,
            "status": "shadow_ready",
            "shadow_ready_at": self._now(),
            "migration_report": migration_report,
        }
        self._write_json(path / self.MANIFEST_NAME, payload)
        return payload

    def promote(self, staging_path: Path) -> Path:
        manifest = self._read_manifest(staging_path)
        if manifest.get("status") != "verified":
            raise ValueError("only a verified staging generation can be promoted")
        generation_id = self._validate_generation_id(str(manifest.get("generation_id", "")))
        destination = self.root / generation_id
        if destination.exists():
            raise FileExistsError(f"generation already exists: {generation_id}")
        os.replace(staging_path, destination)
        return destination

    def activate(self, path: Path) -> None:
        manifest = self._read_manifest(path)
        if manifest.get("status") != "verified":
            raise ValueError("only a verified generation can become active")
        generation_id = self._validate_generation_id(str(manifest.get("generation_id", "")))
        if path.resolve() != (self.root / generation_id).resolve():
            raise ValueError("generation must be promoted before activation")
        current = self._read_pointer()
        old_active = str(current.get("active", ""))
        pointer = {
            "active": generation_id,
            "previous": old_active if old_active != generation_id else str(current.get("previous", "")),
            "updated_at": self._now(),
        }
        self._write_json(self.pointer_path, pointer)

    def resolve_active(self) -> Path | None:
        pointer = self._read_pointer()
        for key in ("active", "previous"):
            generation_id = str(pointer.get(key, ""))
            if not generation_id:
                continue
            try:
                candidate = self.root / self._validate_generation_id(generation_id)
            except ValueError:
                continue
            if self._is_verified(candidate):
                if key == "previous":
                    self._write_json(
                        self.pointer_path,
                        {
                            "active": generation_id,
                            "previous": "",
                            "recovered_at": self._now(),
                        },
                    )
                return candidate
        return None

    def resolve_verified(self, generation_id: str) -> Path | None:
        """Resolve one explicitly named verified generation without changing pointers."""
        try:
            candidate = self.root / self._validate_generation_id(str(generation_id or ""))
        except ValueError:
            return None
        return candidate if self._is_verified(candidate) else None

    def restore_active(self, generation_id: str | None) -> Path | None:
        """Restore the last-known-good pointer after a downstream stage fails.

        The legacy index is represented by an empty pointer.  This only changes
        the small pointer file; generation directories and data are retained for
        diagnosis and recovery.
        """
        normalized = str(generation_id or "").strip()
        if not normalized or normalized == "legacy":
            self._write_json(
                self.pointer_path,
                {"active": "", "previous": "", "recovered_at": self._now()},
            )
            return None
        candidate = self.resolve_verified(normalized)
        if candidate is None:
            raise ValueError("cannot restore an unverified generation")
        self._write_json(
            self.pointer_path,
            {
                "active": normalized,
                "previous": "",
                "recovered_at": self._now(),
            },
        )
        return candidate

    def _is_verified(self, path: Path) -> bool:
        try:
            manifest = self._read_manifest(path)
        except (OSError, ValueError, json.JSONDecodeError):
            return False
        return manifest.get("status") == "verified" and int(manifest.get("chunk_count", 0)) > 0

    def _read_pointer(self) -> dict:
        try:
            payload = json.loads(self.pointer_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _read_manifest(self, path: Path) -> dict:
        self._assert_within_root(path)
        payload = json.loads((path / self.MANIFEST_NAME).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("generation manifest must be an object")
        return payload

    def _generation_id_from_path(self, path: Path) -> str:
        self._assert_within_root(path)
        name = path.name
        if name.endswith(".staging"):
            name = name.removesuffix(".staging")
        return self._validate_generation_id(name)

    def _assert_within_root(self, path: Path) -> None:
        resolved = path.resolve()
        if resolved.parent != self.root:
            raise ValueError("generation path must be a direct child of generation root")

    @staticmethod
    def _validate_generation_id(value: str) -> str:
        if not value or value in {".", ".."} or "/" in value or "\\" in value:
            raise ValueError("invalid generation id")
        return value

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _write_json(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            os.replace(temporary_name, path)
        finally:
            temporary_path = Path(temporary_name)
            if temporary_path.exists():
                temporary_path.unlink()
