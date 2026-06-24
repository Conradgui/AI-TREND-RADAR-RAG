"""Sync published AI Trend Radar Pages corpus into the local RAG project."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://conradgui.github.io/AI-TREND-RADAR"
PROJECT_ROOT = Path(__file__).parent.parent


@dataclass(frozen=True)
class SyncItem:
    relative_path: str


@dataclass(frozen=True)
class SyncResult:
    downloaded: int
    failed: list[str]


def normalize_base_url(base_url: str) -> str:
    """Return base URL without trailing slash."""
    return base_url.rstrip("/")


def build_sync_plan(
    manifest: dict,
    days: int = 30,
    report_types: tuple[str, ...] = ("ai-topic-radar",),
) -> list[SyncItem]:
    """Build the list of public corpus artifacts to sync."""
    items = [
        SyncItem("manifest.json"),
        SyncItem("digests/search-index.json"),
    ]

    dates = manifest.get("dates") or []
    for entry in dates[:days]:
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
    """Fetch a URL using only Python standard library."""
    req = Request(url, headers={"User-Agent": "ai-trend-radar-rag-sync/1.0"})
    with urlopen(req, timeout=30) as response:
        return response.read()


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
    plan = build_sync_plan(manifest, days=days, report_types=report_types)

    downloaded = 0
    failed: list[str] = []
    cached = {"manifest.json": manifest_bytes}

    for item in plan:
        url = f"{base}/{item.relative_path}"
        try:
            content = cached.get(item.relative_path)
            if content is None:
                content = fetcher(url)
            if not dry_run:
                target = output_root / item.relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
            downloaded += 1
        except Exception as exc:
            failed.append(f"{item.relative_path}: {exc}")

    return SyncResult(downloaded=downloaded, failed=failed)


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
    for failure in result.failed:
        print(f"[sync] failed {failure}")


if __name__ == "__main__":
    main()
