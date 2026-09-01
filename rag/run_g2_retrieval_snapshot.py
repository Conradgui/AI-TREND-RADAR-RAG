"""Collect one immutable internal-only response snapshot for the G2 Gold set."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


RequestFn = Callable[..., dict]
CheckpointFn = Callable[[dict], None]


def _snapshot_document(gold: dict, rows: list[dict]) -> dict:
    return {
        "schema_version": "g2-retrieval-snapshot/1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_schema_version": gold.get("schema_version"),
        "review_status": gold.get("review_status"),
        "corpus_boundary": gold.get("corpus_boundary"),
        "rows": rows,
    }


def collect_snapshot(
    gold: dict,
    request_fn: RequestFn,
    *,
    timeout_seconds: int,
    batch_size: int = 8,
    batch_pause_seconds: float = 61,
    sleep_fn: Callable[[float], None] = time.sleep,
    existing_rows: list[dict] | None = None,
    checkpoint_fn: CheckpointFn | None = None,
) -> dict:
    """Run each pending case once, checkpointing so a rate-limit stop can resume."""
    prior_by_id = {
        str(row.get("case_id") or ""): row
        for row in (existing_rows or [])
        if row.get("response") is not None
    }
    rows = [
        prior_by_id[str(case.get("case_id") or "")]
        for case in gold.get("cases", [])
        if str(case.get("case_id") or "") in prior_by_id
    ]
    completed_ids = set(prior_by_id)
    attempted = 0
    for case in gold.get("cases", []):
        case_id = str(case.get("case_id") or "")
        if case_id in completed_ids:
            continue
        if attempted and batch_size > 0 and attempted % batch_size == 0:
            sleep_fn(batch_pause_seconds)
        query = str(case.get("query") or "")
        row = {"case_id": case_id, "query": query}
        try:
            row["response"] = request_fn(
                query,
                web_search_mode="never",
                timeout_seconds=timeout_seconds,
            )
        except Exception as exc:  # Preserve the failed observation; do not retry silently.
            row["error"] = str(exc)
        rows.append(row)
        attempted += 1
        if checkpoint_fn is not None:
            checkpoint_fn(json.loads(json.dumps(_snapshot_document(gold, rows))))
    return _snapshot_document(gold, rows)


def build_http_requester(base_url: str, api_key: str | None = None) -> RequestFn:
    endpoint = f"{base_url.rstrip('/')}/chat"

    def request(message: str, *, web_search_mode: str, timeout_seconds: int) -> dict:
        payload = json.dumps({
            "message": message,
            "history": [],
            "web_search_mode": web_search_mode,
        }, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["X-API-Key"] = api_key
        req = urllib.request.Request(endpoint, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"service unavailable: {exc.reason}") from exc

    return request


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect the G2 real-corpus retrieval snapshot once.")
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--timeout-seconds", type=int, default=210)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--batch-pause-seconds", type=float, default=61)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse rows with a completed response from an existing checkpoint output.",
    )
    args = parser.parse_args()

    gold = json.loads(args.gold.read_text(encoding="utf-8"))
    if gold.get("review_status") != "human_reviewed":
        raise SystemExit("snapshot collection requires review_status=human_reviewed")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    existing_rows = []
    if args.resume and args.output.exists():
        existing_rows = list(
            json.loads(args.output.read_text(encoding="utf-8")).get("rows") or []
        )

    def checkpoint(snapshot: dict) -> None:
        args.output.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    snapshot = collect_snapshot(
        gold,
        build_http_requester(args.base_url, os.getenv("RAG_API_KEY")),
        timeout_seconds=args.timeout_seconds,
        batch_size=args.batch_size,
        batch_pause_seconds=args.batch_pause_seconds,
        existing_rows=existing_rows,
        checkpoint_fn=checkpoint,
    )
    checkpoint(snapshot)
    failures = sum("error" in row for row in snapshot["rows"])
    print(json.dumps({
        "output": str(args.output),
        "cases": len(snapshot["rows"]),
        "request_failures": failures,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
