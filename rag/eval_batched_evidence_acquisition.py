"""Build or execute a batched external evidence acquisition artifact."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from rag.config import get_configured_search_providers, get_search_provider_api_keys
from rag.evidence_batch_plan import (
    DEFAULT_PRODUCTION_MAX_TOTAL_CALLS,
    build_batched_evidence_acquisition_plan,
    execute_batched_evidence_acquisition_plan,
)
from rag.search_provider_adapters import SearchProviderRegistry


DEFAULT_INPUT = Path("docs/rag-transformation/evals/trend-brief-source-relevance-2026-06-25.json")
DEFAULT_PLAN_OUTPUT = Path("docs/rag-transformation/evals/batched-evidence-acquisition-plan-2026-06-25.json")
DEFAULT_RESULT_OUTPUT = Path("docs/rag-transformation/evals/batched-evidence-acquisition-result-2026-06-25.json")


async def build_batched_evidence_acquisition_artifact(
    *,
    input_path: Path = DEFAULT_INPUT,
    execute: bool = False,
    max_total_calls: int = DEFAULT_PRODUCTION_MAX_TOTAL_CALLS,
    max_results_per_call: int | None = None,
    strategy_mode: str = "production",
) -> dict:
    """Build a planned or executed batch artifact from a source relevance matrix."""
    relevance_matrix = json.loads(input_path.read_text(encoding="utf-8"))
    configured_providers = get_configured_search_providers()
    plan = build_batched_evidence_acquisition_plan(
        relevance_matrix,
        configured_providers=configured_providers,
        max_total_calls=max_total_calls,
        max_results_per_call=max_results_per_call,
        strategy_mode=strategy_mode,
        execute=execute,
    )
    artifact = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "live_batch" if execute else "plan_only",
        "configured_providers": sorted(configured_providers),
        "plan": plan,
    }
    if not execute:
        return artifact

    result = await execute_batched_evidence_acquisition_plan(
        plan,
        SearchProviderRegistry(get_search_provider_api_keys()),
        max_total_calls=max_total_calls,
        max_results_per_call=max_results_per_call,
    )
    return {
        **artifact,
        "result": result,
        "summary": {
            "external_api_calls": result["external_api_calls"],
            "citation_count": result["citation_count"],
            "claim_gap_count": len(result["claim_gap_results"]),
            "gaps_with_citations": [
                row["gap_id"]
                for row in result["claim_gap_results"]
                if row.get("citation_count", 0) > 0
            ],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or execute a batched external evidence artifact.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--strategy-mode", choices=["production", "exploration"], default="production")
    parser.add_argument("--max-total-calls", type=int, default=DEFAULT_PRODUCTION_MAX_TOTAL_CALLS)
    parser.add_argument("--max-results-per-call", type=int, default=None)
    args = parser.parse_args()

    output = args.output or (DEFAULT_RESULT_OUTPUT if args.execute else DEFAULT_PLAN_OUTPUT)
    artifact = asyncio.run(
        build_batched_evidence_acquisition_artifact(
            input_path=args.input,
            execute=args.execute,
            max_total_calls=args.max_total_calls,
            max_results_per_call=args.max_results_per_call,
            strategy_mode=args.strategy_mode,
        )
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = artifact.get("summary") or {
        "planned_calls": artifact["plan"]["budget"]["planned_calls"],
        "claim_gap_count": len(artifact["plan"]["claim_gaps"]),
    }
    print(json.dumps({"output": str(output), **summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
