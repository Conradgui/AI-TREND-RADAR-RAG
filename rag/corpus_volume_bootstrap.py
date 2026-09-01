"""Keep the Docker corpus volume and public manifest on one generation."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path


RUNTIME_MANIFEST_NAME = ".runtime-manifest.json"
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
REPORT_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


@dataclass(frozen=True)
class CorpusBootstrapResult:
    source: str
    generated: str


def _read_manifest(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("dates"), list):
        raise RuntimeError(f"invalid corpus manifest: {path}")
    return value


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _validate_reports(manifest: dict, runtime_digests: Path) -> None:
    missing: list[str] = []
    for entry in manifest.get("dates", []):
        date = str(entry.get("date", "")) if isinstance(entry, dict) else ""
        reports = entry.get("reports", []) if isinstance(entry, dict) else []
        if not DATE_PATTERN.fullmatch(date):
            raise RuntimeError(f"invalid corpus date in manifest: {date!r}")
        for report in reports:
            report_name = str(report)
            if not REPORT_PATTERN.fullmatch(report_name):
                raise RuntimeError(f"invalid report name in manifest: {report_name!r}")
            relative = Path(date) / f"{report_name}.md"
            if not (runtime_digests / relative).is_file():
                missing.append(relative.as_posix())
    if missing:
        preview = ", ".join(missing[:5])
        raise RuntimeError(f"corpus manifest references missing reports: {preview}")


def bootstrap_corpus_volume(
    *,
    bundled_root: Path,
    runtime_digests: Path,
    public_manifest: Path,
) -> CorpusBootstrapResult:
    """Select the newest complete corpus and expose one coherent generation."""

    bundled_manifest_path = bundled_root / "manifest.json"
    bundled_manifest = _read_manifest(bundled_manifest_path)
    runtime_manifest_path = runtime_digests / RUNTIME_MANIFEST_NAME
    runtime_manifest = _read_manifest(runtime_manifest_path) if runtime_manifest_path.exists() else None

    bundled_generated = str(bundled_manifest.get("generated", ""))
    runtime_generated = str(runtime_manifest.get("generated", "")) if runtime_manifest else ""
    if runtime_manifest is not None and runtime_generated >= bundled_generated:
        selected = runtime_manifest
        source = "runtime"
    else:
        shutil.copytree(bundled_root / "digests", runtime_digests, dirs_exist_ok=True)
        selected = bundled_manifest
        source = "bundled"

    manifest_content = (json.dumps(selected, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    _write_atomic(runtime_manifest_path, manifest_content)
    _write_atomic(public_manifest, manifest_content)
    _validate_reports(selected, runtime_digests)
    return CorpusBootstrapResult(source=source, generated=str(selected.get("generated", "")))


def main() -> None:
    result = bootstrap_corpus_volume(
        bundled_root=Path(os.getenv("RAG_BUNDLED_CORPUS_ROOT", "/opt/atr-bundled-corpus")),
        runtime_digests=Path(os.getenv("RAG_RUNTIME_DIGESTS_ROOT", "/app/digests")),
        public_manifest=Path(os.getenv("RAG_PUBLIC_MANIFEST", "/app/manifest.json")),
    )
    print(f"[startup] Corpus generation ready from {result.source}: {result.generated}")


if __name__ == "__main__":
    main()
