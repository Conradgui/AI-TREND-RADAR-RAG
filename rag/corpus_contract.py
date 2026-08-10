"""Build and validate a versioned publication contract for corpus artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path, PurePosixPath


SCHEMA_VERSION = 1
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CONTRACT_FILENAME = "corpus-manifest.json"
SOURCE_MODES = {"hosted", "self_managed"}
REQUIRED_PUBLIC_FILES = {"manifest.json", "feed.xml", "digests/search-index.json"}


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _content_type(path: Path) -> str:
    return {
        ".json": "application/json",
        ".md": "text/markdown",
        ".html": "text/html",
        ".xml": "application/xml",
    }.get(path.suffix.lower(), "application/octet-stream")


def _retrieval_eligible(relative_path: str) -> bool:
    name = PurePosixPath(relative_path).name
    return name in {"ai-topic-radar.md", "topic-pool.json"}


def iter_public_corpus_files(root: Path) -> list[Path]:
    """Return the explicit public corpus allowlist in deterministic order."""
    paths: list[Path] = []
    for name in ("manifest.json", "feed.xml"):
        path = root / name
        if path.is_file():
            paths.append(path)

    search_index = root / "digests" / "search-index.json"
    if search_index.is_file():
        paths.append(search_index)

    digests_root = root / "digests"
    if digests_root.is_dir():
        for date_dir in sorted(digests_root.iterdir()):
            if not date_dir.is_dir() or not DATE_PATTERN.fullmatch(date_dir.name):
                continue
            for path in sorted(date_dir.iterdir()):
                if not path.is_file():
                    continue
                if path.name == "topic-pool.json" or path.suffix.lower() in {".md", ".html"}:
                    paths.append(path)
    return paths


def _manifest_generated_at(root: Path) -> str:
    try:
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    return str(manifest.get("generated") or manifest.get("generated_at") or "")


def _calculate_revision(payload: dict) -> str:
    revision_payload = {
        "schema_version": payload.get("schema_version"),
        "source_mode": payload.get("source_mode"),
        "generated_at": payload.get("generated_at"),
        "files": payload.get("files"),
        "tombstones": payload.get("tombstones"),
    }
    return _sha256(
        json.dumps(
            revision_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def build_corpus_contract(root: Path, source_mode: str) -> dict:
    """Describe the exact public files without including mutable local state."""
    files = []
    for path in iter_public_corpus_files(root):
        content = path.read_bytes()
        if not content:
            raise ValueError(f"public corpus file is empty: {path.relative_to(root)}")
        relative_path = path.relative_to(root).as_posix()
        files.append(
            {
                "path": relative_path,
                "sha256": _sha256(content),
                "size": len(content),
                "content_type": _content_type(path),
                "retrieval_eligible": _retrieval_eligible(relative_path),
            }
        )

    revision_payload = {
        "schema_version": SCHEMA_VERSION,
        "source_mode": source_mode,
        "generated_at": _manifest_generated_at(root),
        "files": files,
        "tombstones": [],
    }
    revision = _calculate_revision(revision_payload)
    return {
        **revision_payload,
        "corpus_revision": revision,
        "complete": True,
    }


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
        os.replace(temporary_name, path)
    finally:
        temporary_path = Path(temporary_name)
        if temporary_path.exists():
            temporary_path.unlink()


def write_corpus_contract(root: Path, source_mode: str) -> dict:
    contract = build_corpus_contract(root, source_mode)
    content = (json.dumps(contract, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    target = root / CONTRACT_FILENAME
    if not target.exists() or target.read_bytes() != content:
        _write_atomic(target, content)
    return contract


def validate_corpus_contract(
    root: Path,
    contract: dict,
    *,
    require_exact: bool = False,
) -> list[str]:
    failures: list[str] = []
    if contract.get("schema_version") != SCHEMA_VERSION:
        failures.append(f"unsupported schema version: {contract.get('schema_version')}")
    if contract.get("complete") is not True:
        failures.append("contract is not marked complete")
    if contract.get("source_mode") not in SOURCE_MODES:
        failures.append(f"invalid source mode: {contract.get('source_mode')}")

    files = contract.get("files")
    if not isinstance(files, list) or not files:
        failures.append("contract contains no public files")
        files = []

    if contract.get("corpus_revision") != _calculate_revision(contract):
        failures.append("corpus revision mismatch")

    seen_paths: set[str] = set()
    retrieval_daily_found = False

    for record in files:
        if not isinstance(record, dict):
            failures.append("file record is not an object")
            continue
        relative_path = str(record.get("path", ""))
        if relative_path in seen_paths:
            failures.append(f"duplicate file path: {relative_path}")
        seen_paths.add(relative_path)
        if (
            relative_path.endswith("/ai-topic-radar.md")
            and record.get("retrieval_eligible") is True
        ):
            retrieval_daily_found = True

        if not isinstance(record.get("size"), int) or record.get("size", 0) <= 0:
            failures.append(f"invalid size: {relative_path}")
        if not isinstance(record.get("content_type"), str) or not record.get("content_type"):
            failures.append(f"invalid content type: {relative_path}")
        if not re.fullmatch(r"[0-9a-f]{64}", str(record.get("sha256", ""))):
            failures.append(f"invalid checksum: {relative_path}")
        if not isinstance(record.get("retrieval_eligible"), bool):
            failures.append(f"invalid retrieval flag: {relative_path}")

        pure_path = PurePosixPath(relative_path)
        if not relative_path or pure_path.is_absolute() or ".." in pure_path.parts:
            failures.append(f"unsafe path: {relative_path}")
            continue
        path = root.joinpath(*pure_path.parts)
        if not path.is_file():
            failures.append(f"missing file: {relative_path}")
            continue
        content = path.read_bytes()
        if len(content) != record.get("size"):
            failures.append(f"size mismatch: {relative_path}")
        if _sha256(content) != record.get("sha256"):
            failures.append(f"checksum mismatch: {relative_path}")

    for required in sorted(REQUIRED_PUBLIC_FILES - seen_paths):
        failures.append(f"missing required public file: {required}")
    if not retrieval_daily_found:
        failures.append("contract contains no retrieval-eligible daily report")
    if require_exact and contract.get("source_mode") in SOURCE_MODES:
        try:
            expected = build_corpus_contract(root, str(contract["source_mode"]))
        except (OSError, ValueError) as exc:
            failures.append(f"cannot rebuild corpus contract: {exc}")
        else:
            if contract != expected:
                failures.append("contract does not exactly match current public corpus")
    return failures


def read_corpus_contract(root: Path) -> dict:
    path = root / CONTRACT_FILENAME
    try:
        contract = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read {CONTRACT_FILENAME}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid {CONTRACT_FILENAME}: {exc}") from exc
    if not isinstance(contract, dict):
        raise ValueError(f"invalid {CONTRACT_FILENAME}: root must be an object")
    return contract


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the auditable corpus publication contract.")
    parser.add_argument("--root", type=Path, default=Path(__file__).parent.parent)
    parser.add_argument("--source-mode", choices=("hosted", "self_managed"))
    parser.add_argument(
        "--check-existing",
        action="store_true",
        help="Validate that corpus-manifest.json exactly matches public corpus files",
    )
    args = parser.parse_args()

    if args.check_existing:
        try:
            contract = read_corpus_contract(args.root)
        except ValueError as exc:
            print(f"[corpus-contract] {exc}")
            raise SystemExit(1) from exc
        failures = validate_corpus_contract(args.root, contract, require_exact=True)
    else:
        if not args.source_mode:
            parser.error("--source-mode is required unless --check-existing is used")
        contract = write_corpus_contract(args.root, args.source_mode)
        failures = validate_corpus_contract(args.root, contract, require_exact=True)
    if failures:
        for failure in failures:
            print(f"[corpus-contract] {failure}")
        raise SystemExit(1)
    print(
        f"[corpus-contract] revision={contract['corpus_revision']} "
        f"files={len(contract['files'])} source_mode={contract['source_mode']}"
    )


if __name__ == "__main__":
    main()
