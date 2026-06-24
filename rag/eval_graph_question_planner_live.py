"""Live smoke check for graph question planning and graph evidence retrieval."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from rag.graph_question_planning import build_graph_question_plan
from rag.graph_reasoning_service import build_graph_reasoning_citation, build_graph_reasoning_evidence


DEFAULT_OUTPUT = Path("docs/rag-transformation/evals/graph-question-planner-live-2026-06-24.json")
DEFAULT_QUESTION = "RAG 相关主题是否跨多个日期和来源反复出现？"


async def build_live_graph_question_planner_snapshot(question: str) -> dict:
    """Build a live graph planner snapshot from Neo4j."""
    from rag.graphrag.driver import Neo4jDriver

    plan = build_graph_question_plan(question)
    if not plan:
        return {
            "question": question,
            "passed": False,
            "failed_checks": ["missing_graph_question_plan"],
            "graph_question_plan": None,
            "graph_evidence": None,
            "citation": None,
        }

    driver = Neo4jDriver()
    await driver.connect()
    try:
        evidence = await build_graph_reasoning_evidence(driver, plan)
    finally:
        await driver.close()

    citation = build_graph_reasoning_citation(evidence)
    failed_checks = _failed_live_checks(evidence, citation)
    return {
        "question": question,
        "passed": not failed_checks,
        "failed_checks": failed_checks,
        "graph_question_plan": plan.to_dict(),
        "graph_evidence": evidence,
        "citation": citation,
    }


def _failed_live_checks(evidence: dict, citation: dict) -> list[str]:
    failed = []
    if evidence.get("topic_count", 0) < 2:
        failed.append("insufficient_topics")
    if evidence.get("date_count", 0) < 2:
        failed.append("insufficient_dates")
    if evidence.get("source_count", 0) < 1:
        failed.append("insufficient_sources")
    if not evidence.get("sample_paths"):
        failed.append("missing_sample_paths")
    if citation.get("content_type") != "graph_reasoning":
        failed.append("missing_graph_citation")
    return failed


def main() -> None:
    parser = argparse.ArgumentParser(description="Run live graph question planner smoke check.")
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    snapshot = asyncio.run(build_live_graph_question_planner_snapshot(args.question))
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **snapshot,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "passed": result["passed"],
        "failed_checks": result["failed_checks"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
