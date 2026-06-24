"""Readiness evaluation for search provider adapters without network calls."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from rag.search_provider_adapters import SearchProviderRegistry, SearchRequest
from rag.search_provider_routing import PROVIDER_PROFILES


DEFAULT_OUTPUT = Path("docs/rag-transformation/evals/search-provider-adapters-2026-06-22.json")


async def build_search_provider_adapter_readiness() -> dict:
    """Check adapter registry behavior without calling external providers."""
    registry = SearchProviderRegistry(configured_provider_keys={})
    rows = []
    for provider in PROVIDER_PROFILES:
        request = SearchRequest(
            query="adapter readiness check",
            task_type="broad_serp",
            provider=provider,
        )
        result = await registry.search(request)
        rows.append({
            "provider": provider,
            "available": result["available"],
            "errors": result["errors"],
        })

    failed_checks = []
    for row in rows:
        if row["available"]:
            failed_checks.append(f"{row['provider']}_should_not_be_available_without_key")
        if "missing_api_key" not in row["errors"]:
            failed_checks.append(f"{row['provider']}_missing_expected_error")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "passed": not failed_checks,
        "failed_checks": failed_checks,
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Check search provider adapter readiness.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    result = asyncio.run(build_search_provider_adapter_readiness())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "passed": result["passed"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
