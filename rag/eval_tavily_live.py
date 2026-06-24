"""Minimal Tavily live smoke test."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from rag.config import TAVILY_API_KEY
from rag.search_provider_adapters import SearchProviderRegistry, build_tavily_request_for_task


DEFAULT_OUTPUT = Path("docs/rag-transformation/evals/tavily-live-smoke-2026-06-22.json")


async def build_tavily_live_smoke(query: str) -> dict:
    """Run one low-cost Tavily search and return sanitized smoke output."""
    registry = SearchProviderRegistry(configured_provider_keys={"tavily": TAVILY_API_KEY})
    request = build_tavily_request_for_task(
        query=query,
        task_type="official_source_lookup",
        entities=["Google"],
        max_results=1,
    )
    result = await registry.search(request)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "query": query,
        "provider": result["provider"],
        "available": result["available"],
        "citation_count": len(result["citations"]),
        "raw_results_count": result["raw_results_count"],
        "errors": result["errors"],
        "usage": result.get("usage", {}),
        "citations": result["citations"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one Tavily live smoke test.")
    parser.add_argument("--query", default="AI Trend Radar RAG official source")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    smoke = asyncio.run(build_tavily_live_smoke(args.query))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(smoke, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "available": smoke["available"],
                "citation_count": smoke["citation_count"],
                "raw_results_count": smoke["raw_results_count"],
                "errors": smoke["errors"],
                "usage": smoke["usage"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
