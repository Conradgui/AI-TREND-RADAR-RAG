"""Sync published AI Trend Radar Pages corpus into the local RAG project."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://conradgui.github.io/AI-TREND-RADAR"
PROJECT_ROOT = Path(__file__).parent.parent
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class SyncItem:
    relative_path: str


@dataclass(frozen=True)
class SyncResult:
    downloaded: int
    failed: list[str]
    changed_files: list[str] = field(default_factory=list)
    changed_dates: list[str] = field(default_factory=list)
    synced_dates: list[str] = field(default_factory=list)
    date_fingerprints: dict[str, str] = field(default_factory=dict)
    available_dates: list[str] = field(default_factory=list)
    available_fingerprints: dict[str, str] = field(default_factory=dict)
    upstream_latest_date: str = ""
    local_latest_date: str = ""


def normalize_base_url(base_url: str) -> str:
    """Return base URL without trailing slash."""
    return base_url.rstrip("/")


def build_sync_plan(
    manifest: dict,
    days: int = 30,
    report_types: tuple[str, ...] = ("ai-topic-radar",),
    since_date: str | None = None,
) -> list[SyncItem]:
    """Build a recent recheck plus every date newer than the local corpus."""
    items = [
        SyncItem("manifest.json"),
        SyncItem("digests/search-index.json"),
    ]

    dates = manifest.get("dates") or []
    selected_entries = []
    selected_dates = set()
    for index, entry in enumerate(dates):
        date = str(entry.get("date", "")) if isinstance(entry, dict) else ""
        is_recent = index < days
        is_unseen = bool(
            date and since_date is not None and (not since_date or date > since_date)
        )
        if not (is_recent or is_unseen) or date in selected_dates:
            continue
        selected_entries.append(entry)
        selected_dates.add(date)

    for entry in selected_entries:
        date = entry.get("date")
        reports = entry.get("reports") or []
        if not date:
            continue
        for report_type in report_types:
            if report_type in reports:
                items.append(SyncItem(f"digests/{date}/{report_type}.md"))
        items.append(SyncItem(f"digests/{date}/topic-pool.json"))

    return items


def fetch_url(url: str) -> bytes:
    """Fetch a URL with a small retry budget for transient network failures."""
    req = Request(url, headers={"User-Agent": "ai-trend-radar-rag-sync/1.0"})
    for attempt in range(3):
        try:
            with urlopen(req, timeout=30) as response:
                return response.read()
        except OSError:
            if attempt == 2:
                raise
            time.sleep(0.5 * (2 ** attempt))
    raise RuntimeError("unreachable")


def build_local_manifest(output_root: Path, generated: str = "") -> dict:
    """Describe report files that are actually available under local digests/."""
    digests_root = output_root / "digests"
    dates = []
    if digests_root.exists():
        for date_dir in sorted(digests_root.iterdir(), key=lambda path: path.name, reverse=True):
            if not date_dir.is_dir() or not DATE_PATTERN.fullmatch(date_dir.name):
                continue
            reports = sorted(path.stem for path in date_dir.glob("*.md") if path.is_file())
            if reports:
                dates.append({"date": date_dir.name, "reports": reports})
    return {"generated": generated, "dates": dates}


def validate_sync_payload(relative_path: str, content: bytes) -> None:
    """Reject malformed upstream artifacts before any local file is replaced."""
    text = content.decode("utf-8")
    if relative_path.endswith(".json"):
        parsed = json.loads(text)
        if not isinstance(parsed, (dict, list)):
            raise ValueError("JSON root must be an object or array")
    elif relative_path.endswith(".md") and not text.strip():
        raise ValueError("markdown report is empty")


def write_bytes_atomic(target: Path, content: bytes) -> None:
    """Replace one artifact atomically so readers never observe partial bytes."""
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
        os.replace(temp_name, target)
    finally:
        temp_path = Path(temp_name)
        if temp_path.exists():
            temp_path.unlink()


def build_date_fingerprints(payloads: dict[str, bytes]) -> dict[str, str]:
    """Fingerprint the exact report and topic-pool bytes fetched for each date."""
    grouped: dict[str, list[tuple[str, bytes]]] = {}
    for relative_path, content in payloads.items():
        parts = Path(relative_path).parts
        if len(parts) < 3 or parts[0] != "digests" or not DATE_PATTERN.fullmatch(parts[1]):
            continue
        grouped.setdefault(parts[1], []).append((relative_path, content))

    fingerprints = {}
    for date, artifacts in grouped.items():
        digest = hashlib.sha256()
        for relative_path, content in sorted(artifacts):
            digest.update(relative_path.encode("utf-8"))
            digest.update(b"\0")
            digest.update(content)
            digest.update(b"\0")
        fingerprints[date] = digest.hexdigest()
    return fingerprints


def build_local_date_fingerprints(
    output_root: Path,
    report_types: tuple[str, ...] = ("ai-topic-radar",),
) -> dict[str, str]:
    """Fingerprint every locally available corpus date for first-run indexing."""
    payloads: dict[str, bytes] = {}
    digests_root = output_root / "digests"
    if not digests_root.exists():
        return {}
    for date_dir in digests_root.iterdir():
        if not date_dir.is_dir() or not DATE_PATTERN.fullmatch(date_dir.name):
            continue
        candidates = [date_dir / f"{report_type}.md" for report_type in report_types]
        candidates.append(date_dir / "topic-pool.json")
        for path in candidates:
            if path.is_file():
                payloads[path.relative_to(output_root).as_posix()] = path.read_bytes()
    return build_date_fingerprints(payloads)


def sync_corpus(
    base_url: str = DEFAULT_BASE_URL,
    output_root: Path = PROJECT_ROOT,
    days: int = 30,
    report_types: tuple[str, ...] = ("ai-topic-radar",),
    fetcher: Callable[[str], bytes] = fetch_url,
    dry_run: bool = False,
) -> SyncResult:
    """Sync corpus artifacts from AI Trend Radar Pages."""
    base = normalize_base_url(base_url)
    manifest_url = f"{base}/manifest.json"
    manifest_bytes = fetcher(manifest_url)
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    local_before_sync = build_local_manifest(output_root)
    local_latest_before_sync = (
        local_before_sync["dates"][0]["date"] if local_before_sync["dates"] else ""
    )
    plan = build_sync_plan(
        manifest,
        days=days,
        report_types=report_types,
        since_date=local_latest_before_sync,
    )

    downloaded = 0
    failed: list[str] = []
    cached = {"manifest.json": manifest_bytes}
    payloads: dict[str, bytes] = {}

    # Fetch the complete plan before touching the last known-good local corpus.
    # A network interruption must not leave a half-updated report set.
    for item in plan:
        url = f"{base}/{item.relative_path}"
        try:
            content = cached.get(item.relative_path)
            if content is None:
                content = fetcher(url)
            validate_sync_payload(item.relative_path, content)
            payloads[item.relative_path] = content
            downloaded += 1
        except Exception as exc:
            failed.append(f"{item.relative_path}: {exc}")

    upstream_dates = [
        str(entry.get("date"))
        for entry in manifest.get("dates", [])
        if isinstance(entry, dict) and DATE_PATTERN.fullmatch(str(entry.get("date", "")))
    ]
    upstream_latest_date = max(upstream_dates, default="")
    date_fingerprints = build_date_fingerprints(payloads)
    synced_dates = sorted(date_fingerprints)

    if failed:
        local_manifest = build_local_manifest(output_root)
        local_latest_date = local_manifest["dates"][0]["date"] if local_manifest["dates"] else ""
        available_fingerprints = build_local_date_fingerprints(output_root, report_types)
        return SyncResult(
            downloaded=downloaded,
            failed=failed,
            synced_dates=synced_dates,
            date_fingerprints=date_fingerprints,
            available_dates=sorted(available_fingerprints),
            available_fingerprints=available_fingerprints,
            upstream_latest_date=upstream_latest_date,
            local_latest_date=local_latest_date,
        )

    changed_files = []
    changed_dates = set()
    for item in plan:
        if item.relative_path == "manifest.json":
            continue
        target = output_root / item.relative_path
        current = target.read_bytes() if target.exists() else None
        if current == payloads[item.relative_path]:
            continue
        changed_files.append(item.relative_path)
        parts = Path(item.relative_path).parts
        if len(parts) >= 3 and parts[0] == "digests" and DATE_PATTERN.fullmatch(parts[1]):
            changed_dates.add(parts[1])

    if not dry_run:
        for item in plan:
            if item.relative_path == "manifest.json":
                continue
            if item.relative_path not in changed_files:
                continue
            target = output_root / item.relative_path
            write_bytes_atomic(target, payloads[item.relative_path])
        local_manifest = build_local_manifest(output_root, generated=str(manifest.get("generated", "")))
        manifest_content = (json.dumps(local_manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        manifest_target = output_root / "manifest.json"
        if not manifest_target.exists() or manifest_target.read_bytes() != manifest_content:
            write_bytes_atomic(manifest_target, manifest_content)
            changed_files.append("manifest.json")
    else:
        local_manifest = build_local_manifest(output_root, generated=str(manifest.get("generated", "")))

    local_dates = {entry["date"] for entry in local_manifest.get("dates", [])}
    local_latest_date = max(local_dates, default="")
    available_fingerprints = build_local_date_fingerprints(output_root, report_types)
    # During dry-run, include validated upstream bytes that have not been written yet.
    available_fingerprints.update(date_fingerprints)

    return SyncResult(
        downloaded=downloaded,
        failed=failed,
        changed_files=changed_files,
        changed_dates=sorted(changed_dates),
        synced_dates=synced_dates,
        date_fingerprints=date_fingerprints,
        available_dates=sorted(available_fingerprints),
        available_fingerprints=available_fingerprints,
        upstream_latest_date=upstream_latest_date,
        local_latest_date=local_latest_date,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync AI Trend Radar Pages corpus into this RAG project.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--output-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result = sync_corpus(
        base_url=args.base_url,
        output_root=args.output_root,
        days=args.days,
        dry_run=args.dry_run,
    )
    print(f"[sync] downloaded={result.downloaded} failed={len(result.failed)}")
    print(f"[sync] changed_dates={','.join(result.changed_dates) or '-'}")
    print(f"[sync] upstream_latest={result.upstream_latest_date or '-'} local_latest={result.local_latest_date or '-'}")
    for failure in result.failed:
        print(f"[sync] failed {failure}")
    if result.failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
