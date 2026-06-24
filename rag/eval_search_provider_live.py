"""Run low-volume live smoke checks for configured search providers."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from rag.config import get_search_provider_api_keys
from rag.search_provider_adapters import SearchProviderRegistry, SearchRequest


DEFAULT_OUTPUT = Path("docs/rag-transformation/evals/search-provider-live-smoke-2026-06-23.json")

SMOKE_REQUESTS = [
    SearchRequest(
        query="Claude latest product update Anthropic",
        task_type="recent_web",
        provider="brave",
        max_results=1,
    ),
    SearchRequest(
        query="retrieval augmented generation survey graph rag agentic rag",
        task_type="research_paper",
        provider="exa",
        max_results=1,
    ),
    SearchRequest(
        query="agentic rag AI",
        task_type="github_repo",
        provider="github",
        max_results=1,
    ),
]


async def build_search_provider_live_smoke() -> dict:
    """Run one request per configured provider and return sanitized evidence."""
    registry = SearchProviderRegistry(get_search_provider_api_keys())
    rows = []
    for request in SMOKE_REQUESTS:
        result = await registry.search(request)
        rows.append({
            "provider": request.provider,
            "task_type": request.task_type,
            "available": result.get("available", False),
            "citation_count": len(result.get("citations", [])),
            "raw_results_count": result.get("raw_results_count", 0),
            "errors": result.get("errors", []),
            "usage": result.get("usage", {}),
            "citations": result.get("citations", []),
        })
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rows": rows,
        "summary": {
            "provider_count": len(rows),
            "available_count": sum(1 for row in rows if row["available"]),
            "providers_with_citations": [
                row["provider"] for row in rows if row["citation_count"] > 0
            ],
            "providers_with_errors": [
                row["provider"] for row in rows if row["errors"]
            ],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run low-volume live search provider smoke checks.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    smoke = asyncio.run(build_search_provider_live_smoke())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(smoke, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), **smoke["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
