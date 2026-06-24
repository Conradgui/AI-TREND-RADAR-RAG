"""Evaluate search-provider routing for golden questions without network calls."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from rag.config import get_configured_search_providers
from rag.eval_golden import DEFAULT_GOLDEN_PATH, load_golden_questions, validate_golden_questions
from rag.query_understanding import analyze_query
from rag.search_provider_routing import build_search_provider_route
from rag.tool_routing import infer_search_task_type


DEFAULT_OUTPUT = Path("docs/rag-transformation/evals/search-provider-routing-2026-06-22.json")


def build_search_provider_routing_snapshot(
    questions: list[dict],
    configured_providers: set[str] | None = None,
) -> dict:
    """Build provider-routing snapshot for golden questions without external calls."""
    providers = configured_providers if configured_providers is not None else get_configured_search_providers()
    rows = []
    for item in questions:
        plan = analyze_query(item["question"])
        task_type = infer_search_task_type(plan)
        route = build_search_provider_route(
            {
                "query": plan.retrieval_query,
                "task_type": task_type,
            },
            configured_providers=providers,
        )
        rows.append(
            {
                "id": item["id"],
                "question": item["question"],
                "expected_answerability": item["answerability"],
                "needs_web_search": plan.needs_web_search,
                "search_task_type": task_type,
                "provider_route": route,
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "configured_providers": sorted(providers),
        "total": len(rows),
        "rows": rows,
        "summary": summarize_search_provider_routing(rows),
    }


def summarize_search_provider_routing(rows: list[dict]) -> dict:
    """Summarize provider-routing rows."""
    needs_web = [row for row in rows if row["needs_web_search"]]
    with_primary = [row for row in needs_web if row["provider_route"]["primary_provider"]]
    return {
        "total": len(rows),
        "needs_web": len(needs_web),
        "needs_web_with_configured_primary": len(with_primary),
        "needs_web_without_configured_primary": len(needs_web) - len(with_primary),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate search provider routing for golden questions.")
    parser.add_argument("--path", type=Path, default=DEFAULT_GOLDEN_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    questions = load_golden_questions(args.path)
    errors = validate_golden_questions(questions)
    if errors:
        print(json.dumps({"errors": errors}, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    snapshot = build_search_provider_routing_snapshot(questions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "summary": snapshot["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
