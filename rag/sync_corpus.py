"""Sync published AI Trend Radar Pages corpus into the local RAG project."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://conradgui.github.io/AI-TREND-RADAR"
PROJECT_ROOT = Path(__file__).parent.parent
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
REPORT_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
MAX_FILE_BYTES = 10 * 1024 * 1024


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


def build_sync_diagnostics(
    result: SyncResult,
    today: date | None = None,
    warning_days: int = 3,
) -> dict:
    """Build a machine-readable sync result with a non-blocking freshness signal."""
    reference_date = today or date.today()
    upstream_age_days: int | None = None
    if result.upstream_latest_date:
        try:
            upstream_date = date.fromisoformat(result.upstream_latest_date)
            upstream_age_days = max(0, (reference_date - upstream_date).days)
        except ValueError:
            pass

    freshness_warning = (
        upstream_age_days is not None and upstream_age_days > warning_days
    )
    freshness = "unknown" if upstream_age_days is None else (
        "stale" if freshness_warning else "fresh"
    )
    return {
        "downloaded": result.downloaded,
        "failed_count": len(result.failed),
        "failed": result.failed,
        "changed_files": result.changed_files,
        "changed_dates": result.changed_dates,
        "upstream_latest_date": result.upstream_latest_date,
        "local_latest_date": result.local_latest_date,
        "upstream_age_days": upstream_age_days,
        "freshness_warning_days": warning_days,
        "freshness_warning": freshness_warning,
        "freshness": freshness,
    }


def normalize_base_url(base_url: str) -> str:
    """Return base URL without trailing slash."""
    return base_url.rstrip("/")


def validate_upstream_manifest(manifest: dict) -> None:
    """Reject malformed paths before they can enter the download plan."""
    if not isinstance(manifest, dict) or not isinstance(manifest.get("dates"), list):
        raise ValueError("manifest must contain a dates array")
    for entry in manifest["dates"]:
        if not isinstance(entry, dict):
            raise ValueError("manifest date entry must be an object")
        date = str(entry.get("date", ""))
        if not DATE_PATTERN.fullmatch(date):
            raise ValueError(f"invalid corpus date: {date}")
        reports = entry.get("reports") or []
        if not isinstance(reports, list) or any(
            not isinstance(report, str) or not REPORT_PATTERN.fullmatch(report)
            for report in reports
        ):
            raise ValueError(f"invalid report list for {date}")


def build_sync_plan(
    manifest: dict,
    days: int = 30,
    report_types: tuple[str, ...] = (
        "ai-topic-radar",
        "ai-weekly",
        "ai-weekly-en",
        "ai-monthly",
        "ai-monthly-en",
    ),
    since_date: str | None = None,
) -> list[SyncItem]:
    """Build a recent recheck plus every date newer than the local corpus."""
    validate_upstream_manifest(manifest)
    items = [
        SyncItem("manifest.json"),
        SyncItem("feed.xml"),
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
        if "ai-topic-radar" in reports and "ai-topic-radar" in report_types:
            items.append(SyncItem(f"digests/{date}/topic-pool.json"))

    return items


def fetch_url(url: str) -> bytes:
    """Fetch a URL with a small retry budget for transient network failures."""
    req = Request(url, headers={"User-Agent": "ai-trend-radar-rag-sync/1.0"})
    for attempt in range(3):
        try:
            with urlopen(req, timeout=30) as response:
                content = response.read(MAX_FILE_BYTES + 1)
                if len(content) > MAX_FILE_BYTES:
                    raise ValueError(f"response exceeds {MAX_FILE_BYTES} bytes")
                return content
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


def validate_sync_payload(
    relative_path: str,
    content: bytes,
    max_file_bytes: int = MAX_FILE_BYTES,
) -> None:
    """Reject malformed upstream artifacts before any local file is replaced."""
    if len(content) > max_file_bytes:
        raise ValueError(f"payload exceeds {max_file_bytes} bytes")
    text = content.decode("utf-8")
    if relative_path.endswith(".json"):
        parsed = json.loads(text)
        if not isinstance(parsed, (dict, list)):
            raise ValueError("JSON root must be an object or array")
    elif relative_path.endswith(".md") and not text.strip():
        raise ValueError("markdown report is empty")
    elif relative_path.endswith(".xml"):
        ET.fromstring(text)


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


def _is_retrieval_artifact(relative_path: str) -> bool:
    return Path(relative_path).name in {"ai-topic-radar.md", "topic-pool.json"}


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


def _local_summary_overrides(output_root: Path, date: str) -> dict[str, str]:
    """Return non-empty local summaries keyed by source URL for one date."""
    pool_path = output_root / "digests" / date / "topic-pool.json"
    try:
        pool = json.loads(pool_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    candidates = pool.get("candidates", []) if isinstance(pool, dict) else []
    return {
        str(candidate["url"]): str(candidate["summary"]).strip()
        for candidate in candidates
        if isinstance(candidate, dict)
        and candidate.get("url")
        and str(candidate.get("summary", "")).strip()
    }


def _preserve_nonempty_local_summaries(
    relative_path: str,
    upstream: bytes,
    overrides: dict[str, str],
) -> bytes:
    """Prevent an empty upstream summary from degrading a richer local artifact."""
    if not overrides:
        return upstream
    if relative_path.endswith("topic-pool.json"):
        pool = json.loads(upstream.decode("utf-8"))
        candidates = pool.get("candidates", []) if isinstance(pool, dict) else []
        changed = False
        for candidate in candidates:
            if not isinstance(candidate, dict) or str(candidate.get("summary", "")).strip():
                continue
            summary = overrides.get(str(candidate.get("url", "")))
            if summary:
                candidate["summary"] = summary
                changed = True
        if changed:
            return (json.dumps(pool, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        return upstream
    if relative_path.endswith("ai-topic-radar.md"):
        changed = False
        lines = upstream.decode("utf-8").splitlines()
        for index, line in enumerate(lines):
            match = re.search(r"\[[^\]]+\]\((https?://[^)]+)\)", line)
            if not match:
                continue
            parts = line.split("|")
            if len(parts) < 6 or parts[4].strip():
                continue
            summary = overrides.get(match.group(1))
            if summary:
                escaped_summary = summary.replace("|", r"\|")
                parts[4] = f" {escaped_summary} "
                lines[index] = "|".join(parts)
                changed = True
        if changed:
            return ("\n".join(lines) + "\n").encode("utf-8")
    return upstream


def sync_corpus(
    base_url: str = DEFAULT_BASE_URL,
    output_root: Path = PROJECT_ROOT,
    days: int = 30,
    report_types: tuple[str, ...] = (
        "ai-topic-radar",
        "ai-weekly",
        "ai-weekly-en",
        "ai-monthly",
        "ai-monthly-en",
    ),
    fetcher: Callable[[str], bytes] = fetch_url,
    dry_run: bool = False,
    source_mode: str = "hosted",
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

    # The upstream project remains authoritative for new reports and all
    # non-summary fields.  A blank summary, however, must not overwrite a
    # source-grounded summary already enriched by this RAG project.
    for relative_path, content in list(payloads.items()):
        parts = Path(relative_path).parts
        if len(parts) < 3 or parts[0] != "digests" or not DATE_PATTERN.fullmatch(parts[1]):
            continue
        payloads[relative_path] = _preserve_nonempty_local_summaries(
            relative_path,
            content,
            _local_summary_overrides(output_root, parts[1]),
        )

    retrieval_payloads = {
        path: content
        for path, content in payloads.items()
        if _is_retrieval_artifact(path)
    }
    date_fingerprints = build_date_fingerprints(retrieval_payloads)
    synced_dates = sorted(date_fingerprints)

    if failed:
        local_manifest = build_local_manifest(output_root)
        local_latest_date = local_manifest["dates"][0]["date"] if local_manifest["dates"] else ""
        available_fingerprints = build_local_date_fingerprints(output_root)
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
        if (
            len(parts) >= 3
            and parts[0] == "digests"
            and DATE_PATTERN.fullmatch(parts[1])
            and _is_retrieval_artifact(item.relative_path)
        ):
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

        from rag.corpus_contract import CONTRACT_FILENAME, write_corpus_contract

        contract_target = output_root / CONTRACT_FILENAME
        contract_before = contract_target.read_bytes() if contract_target.exists() else None
        write_corpus_contract(output_root, source_mode=source_mode)
        if contract_before != contract_target.read_bytes():
            changed_files.append(CONTRACT_FILENAME)
    else:
        local_manifest = build_local_manifest(output_root, generated=str(manifest.get("generated", "")))

    local_dates = {entry["date"] for entry in local_manifest.get("dates", [])}
    local_latest_date = max(local_dates, default="")
    available_fingerprints = build_local_date_fingerprints(output_root)
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
    parser.add_argument("--source-mode", choices=("hosted", "self_managed"), default="hosted")
    parser.add_argument("--result-json", type=Path)
    parser.add_argument("--freshness-warning-days", type=int, default=3)
    args = parser.parse_args()

    result = sync_corpus(
        base_url=args.base_url,
        output_root=args.output_root,
        days=args.days,
        dry_run=args.dry_run,
        source_mode=args.source_mode,
    )
    print(f"[sync] downloaded={result.downloaded} failed={len(result.failed)}")
    print(f"[sync] changed_dates={','.join(result.changed_dates) or '-'}")
    print(f"[sync] upstream_latest={result.upstream_latest_date or '-'} local_latest={result.local_latest_date or '-'}")
    diagnostics = build_sync_diagnostics(
        result,
        warning_days=max(0, args.freshness_warning_days),
    )
    if args.result_json:
        write_bytes_atomic(
            args.result_json,
            (json.dumps(diagnostics, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        )
    if diagnostics["freshness_warning"]:
        print(
            "::warning title=Hosted corpus may be stale::"
            f"Latest upstream date is {result.upstream_latest_date} "
            f"({diagnostics['upstream_age_days']} days old)."
        )
    for failure in result.failed:
        print(f"[sync] failed {failure}")
    if result.failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
