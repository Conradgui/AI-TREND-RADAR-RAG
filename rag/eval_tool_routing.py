"""Evaluate tool-routing contract compliance in live chat snapshots."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_INPUT = Path("docs/rag-transformation/evals/live-chat-snapshot-2026-06-22.json")
DEFAULT_OUTPUT = Path("docs/rag-transformation/evals/live-tool-routing-rubric-2026-06-22.json")
PLANNED_EXTERNAL_TOOLS = {"web_search", "fetch_url", "compare_internal_and_external"}


def score_tool_routing_rows(rows: list[dict]) -> list[dict]:
    """Score live chat rows against the tool-routing contract."""
    scored = []
    for row in rows:
        failed_checks = _failed_checks(row)
        scored.append({
            "id": row.get("id"),
            "expected_answerability": row.get("expected_answerability"),
            "passed": not failed_checks,
            "failed_checks": failed_checks,
        })
    return scored


def summarize_tool_routing_rows(rows: list[dict]) -> dict:
    """Summarize tool-routing rubric rows."""
    total = len(rows)
    passed = sum(1 for row in rows if row["passed"])
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
    }


def _failed_checks(row: dict) -> list[str]:
    checks = []
    route = (row.get("query_understanding") or {}).get("tool_routing") or {}
    expected_answerability = row.get("expected_answerability")
    steps = route.get("steps") or []
    tools = {step.get("tool") for step in steps}
    states_by_tool = {step.get("tool"): step.get("state") for step in steps}

    if not route:
        return ["missing_tool_routing"]

    if "search_corpus" not in tools:
        checks.append("missing_internal_search_step")

    if route.get("external_tools_available") is not False:
        checks.append("external_tools_should_be_unavailable_in_current_module")

    if expected_answerability == "needs-web":
        if not route.get("external_tools_required"):
            checks.append("missing_external_tools_required_flag")
        if not PLANNED_EXTERNAL_TOOLS.issubset(tools):
            checks.append("missing_planned_external_tools")
        for tool in PLANNED_EXTERNAL_TOOLS.intersection(tools):
            if states_by_tool.get(tool) != "planned_unavailable":
                checks.append(f"{tool}_not_marked_planned_unavailable")
    else:
        external_steps = PLANNED_EXTERNAL_TOOLS.intersection(tools)
        if external_steps:
            checks.append("unexpected_external_steps_for_internal_question")
        if route.get("external_tools_required"):
            checks.append("unexpected_external_tools_required_flag")

    return checks


def main() -> None:
    parser = argparse.ArgumentParser(description="Score live chat snapshots for tool-routing compliance.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    snapshot = json.loads(args.input.read_text(encoding="utf-8"))
    rows = score_tool_routing_rows(snapshot.get("rows", []))
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input": str(args.input),
        "summary": summarize_tool_routing_rows(rows),
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "summary": result["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
