"""One deep interface for sync → incremental ingestion → consistency status."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable

from rag.sync_corpus import (
    DEFAULT_BASE_URL,
    PROJECT_ROOT,
    SyncResult,
    build_local_date_fingerprints,
    sync_corpus,
)


DEFAULT_STATE_PATH = PROJECT_ROOT / "rag" / "data" / "corpus-update-state.json"


@dataclass(frozen=True)
class UpdateResult:
    status: str
    checked_at: str
    # Compatibility note: this is deliberately the time of a successful
    # *upstream* synchronization.  It must not be overwritten just because
    # the bundled local corpus was indexed while the upstream was unavailable.
    last_success_at: str
    local_indexed_at: str
    upstream_latest_date: str
    local_latest_date: str
    changed_dates: list[str] = field(default_factory=list)
    ingested_dates: list[str] = field(default_factory=list)
    indexed_fingerprints: dict[str, str] = field(default_factory=dict)
    consistency: dict = field(default_factory=dict)
    error: str = ""
    dry_run: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def load_update_state(state_path: Path = DEFAULT_STATE_PATH) -> dict:
    """Load the latest update status without making startup depend on it."""
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def summarize_update_state(state: dict) -> dict:
    """Return the small, user-facing subset of the durable update ledger."""
    return {
        "status": state.get("status", ""),
        "checked_at": state.get("checked_at", ""),
        "last_success_at": state.get("last_success_at", ""),
        "local_indexed_at": state.get("local_indexed_at", ""),
        "upstream_latest_date": state.get("upstream_latest_date", ""),
        "local_latest_date": state.get("local_latest_date", ""),
        "changed_date_count": len(state.get("changed_dates", [])),
        "ingested_date_count": len(state.get("ingested_dates", [])),
        "error": state.get("error", ""),
    }


def _write_update_state(result: UpdateResult, state_path: Path) -> None:
    """Atomically replace the small local status file."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n"
    descriptor, temp_name = tempfile.mkstemp(prefix="corpus-update-", suffix=".json", dir=state_path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.replace(temp_name, state_path)
    finally:
        temp_path = Path(temp_name)
        if temp_path.exists():
            temp_path.unlink()


async def update_corpus(
    *,
    base_url: str = DEFAULT_BASE_URL,
    output_root: Path = PROJECT_ROOT,
    days: int = 30,
    dry_run: bool = False,
    state_path: Path = DEFAULT_STATE_PATH,
    syncer: Callable[..., SyncResult] = sync_corpus,
    ingester: Callable[[list[str]], Awaitable[tuple[int, dict]]] | None = None,
) -> UpdateResult:
    """Update the local corpus through one caller-facing interface.

    Callers only decide source, window and dry-run mode. Network validation,
    changed-date detection, database ingestion, consistency reporting and
    durable status remain inside this module.
    """
    checked_at = datetime.now(timezone.utc).isoformat()
    previous = load_update_state(state_path)
    previous_fingerprints = previous.get("indexed_fingerprints", {})
    if not isinstance(previous_fingerprints, dict):
        previous_fingerprints = {}

    indexed_fingerprints = dict(previous_fingerprints)
    checkpointed_dates: list[str] = []
    previous_local_indexed_at = str(previous.get("local_indexed_at", ""))
    local_fingerprints = build_local_date_fingerprints(output_root)
    bootstrap_dates = sorted(
        (
            date
            for date, fingerprint in local_fingerprints.items()
            if indexed_fingerprints.get(date) != fingerprint
        ),
        reverse=True,
    )

    def checkpoint(
        date: str,
        fingerprints: dict[str, str],
        status: str,
        changed_dates: list[str],
        upstream_latest_date: str = "",
        local_latest_date: str = "",
    ) -> None:
        """Persist each successful date so an interrupted first run can resume."""
        if date not in checkpointed_dates:
            checkpointed_dates.append(date)
        fingerprint = fingerprints.get(date)
        if fingerprint:
            indexed_fingerprints[date] = fingerprint
        _write_update_state(
            UpdateResult(
                status=status,
                checked_at=checked_at,
                last_success_at=str(previous.get("last_success_at", "")),
                local_indexed_at=checked_at,
                upstream_latest_date=upstream_latest_date,
                local_latest_date=local_latest_date,
                changed_dates=changed_dates,
                ingested_dates=checkpointed_dates,
                indexed_fingerprints=indexed_fingerprints,
            ),
            state_path,
        )

    async def ingest_dates(
        dates: list[str],
        fingerprints: dict[str, str],
        status: str,
        upstream_latest_date: str = "",
        local_latest_date: str = "",
    ) -> tuple[bool, dict, str]:
        """Ingest one ordered batch and keep its checkpoint independent of sync."""
        if not dates:
            return True, {}, ""
        if ingester is None:
            from rag.ingest import run_ingestion

            try:
                _, consistency = await run_ingestion(
                    dates,
                    on_date_ingested=lambda date: checkpoint(
                        date,
                        fingerprints,
                        status,
                        dates,
                        upstream_latest_date,
                        local_latest_date,
                    ),
                )
            except Exception as exc:
                return False, {}, str(exc)
        else:
            try:
                _, consistency = await ingester(dates)
                for date in dates:
                    checkpoint(
                        date,
                        fingerprints,
                        status,
                        dates,
                        upstream_latest_date,
                        local_latest_date,
                    )
            except Exception as exc:
                return False, {}, str(exc)

        if consistency and not consistency.get("is_consistent", False):
            return False, consistency, "Neo4j and ChromaDB date coverage is inconsistent"
        return True, consistency, ""

    if dry_run:
        # Keep dry runs side-effect free; they are for remote sync planning,
        # not for bootstrapping the local database.
        bootstrap_dates = []

    if not dry_run:
        _write_update_state(
            UpdateResult(
                status="bootstrapping" if bootstrap_dates else "syncing",
                checked_at=checked_at,
                last_success_at=str(previous.get("last_success_at", "")),
                local_indexed_at=previous_local_indexed_at,
                upstream_latest_date=str(previous.get("upstream_latest_date", "")),
                local_latest_date=str(previous.get("local_latest_date", "")),
                changed_dates=bootstrap_dates,
                indexed_fingerprints=indexed_fingerprints,
            ),
            state_path,
        )

    if bootstrap_dates:
        # A fresh clone already contains public, auditable reports. Index them
        # before touching the network so an upstream outage cannot leave a new
        # user with an empty Agent.
        if not dry_run:
            bootstrap_ok, bootstrap_consistency, bootstrap_error = await ingest_dates(
                bootstrap_dates,
                local_fingerprints,
                "bootstrapping",
                local_latest_date=max(local_fingerprints, default=""),
            )
            if not bootstrap_ok:
                result = UpdateResult(
                    status="failed",
                    checked_at=checked_at,
                    last_success_at=str(previous.get("last_success_at", "")),
                    local_indexed_at=checked_at if checkpointed_dates else previous_local_indexed_at,
                    upstream_latest_date=str(previous.get("upstream_latest_date", "")),
                    local_latest_date=max(local_fingerprints, default=""),
                    changed_dates=bootstrap_dates,
                    ingested_dates=checkpointed_dates,
                    indexed_fingerprints=indexed_fingerprints,
                    consistency=bootstrap_consistency,
                    error=f"Local corpus bootstrap failed: {bootstrap_error}",
                )
                _write_update_state(result, state_path)
                return result

    try:
        sync_result = syncer(
            base_url=base_url,
            output_root=output_root,
            days=days,
            dry_run=dry_run,
        )
    except Exception as exc:
        sync_result = SyncResult(downloaded=0, failed=[str(exc)])

    if sync_result.failed:
        # A previously indexed corpus is still useful even when this check for
        # fresh upstream reports fails.  The UI must distinguish that degraded
        # freshness from an actually unusable first start.
        local_corpus_available = bool(indexed_fingerprints)
        result = UpdateResult(
            status="degraded" if local_corpus_available else "failed",
            checked_at=checked_at,
            last_success_at=str(previous.get("last_success_at", "")),
            local_indexed_at=checked_at if checkpointed_dates else previous_local_indexed_at,
            upstream_latest_date=sync_result.upstream_latest_date,
            local_latest_date=sync_result.local_latest_date or max(local_fingerprints, default=""),
            changed_dates=bootstrap_dates,
            ingested_dates=checkpointed_dates,
            indexed_fingerprints=indexed_fingerprints,
            error="; ".join(sync_result.failed),
            dry_run=dry_run,
        )
        if not dry_run:
            _write_update_state(result, state_path)
        return result

    candidate_dates = sync_result.available_dates or sync_result.synced_dates
    candidate_fingerprints = (
        sync_result.available_fingerprints or sync_result.date_fingerprints
    )
    dates_to_ingest = set(sync_result.changed_dates)
    for date in candidate_dates:
        fingerprint = candidate_fingerprints.get(date)
        if fingerprint and indexed_fingerprints.get(date) != fingerprint:
            dates_to_ingest.add(date)
    # On a fresh install, make the most recent reports queryable first. The
    # full corpus is still indexed, but current-trend questions do not wait
    # behind months of historical data.
    dates_to_ingest = sorted(dates_to_ingest, reverse=True)

    if dry_run:
        return UpdateResult(
            status="dry_run",
            checked_at=checked_at,
            last_success_at=str(previous.get("last_success_at", "")),
            local_indexed_at=previous_local_indexed_at,
            upstream_latest_date=sync_result.upstream_latest_date,
            local_latest_date=sync_result.local_latest_date,
            changed_dates=dates_to_ingest,
            indexed_fingerprints=previous_fingerprints,
            dry_run=True,
        )

    if not dates_to_ingest:
        result = UpdateResult(
            status="unchanged",
            checked_at=checked_at,
            last_success_at=checked_at,
            local_indexed_at=previous_local_indexed_at,
            upstream_latest_date=sync_result.upstream_latest_date,
            local_latest_date=sync_result.local_latest_date,
            indexed_fingerprints=indexed_fingerprints,
        )
        _write_update_state(result, state_path)
        return result

    update_ok, consistency, error = await ingest_dates(
        dates_to_ingest,
        candidate_fingerprints,
        "syncing",
        sync_result.upstream_latest_date,
        sync_result.local_latest_date,
    )
    status = "updated" if update_ok else "failed"

    result = UpdateResult(
        status=status,
        checked_at=checked_at,
        last_success_at=checked_at if status == "updated" else str(previous.get("last_success_at", "")),
        local_indexed_at=checked_at if status == "updated" else previous_local_indexed_at,
        upstream_latest_date=sync_result.upstream_latest_date,
        local_latest_date=sync_result.local_latest_date,
        changed_dates=dates_to_ingest,
        ingested_dates=checkpointed_dates,
        indexed_fingerprints=indexed_fingerprints,
        consistency=consistency,
        error=error,
    )
    _write_update_state(result, state_path)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync and incrementally ingest AI Trend Radar corpus.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--output-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--state-path", type=Path, default=DEFAULT_STATE_PATH)
    args = parser.parse_args()

    result = asyncio.run(
        update_corpus(
            base_url=args.base_url,
            output_root=args.output_root,
            days=args.days,
            dry_run=args.dry_run,
            state_path=args.state_path,
        )
    )
    print(json.dumps(summarize_update_state(result.to_dict()), ensure_ascii=False, indent=2))
    if result.status == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
