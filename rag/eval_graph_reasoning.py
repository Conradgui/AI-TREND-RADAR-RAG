"""Deterministic multi-hop graph reasoning checks for Neo4j graph data."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_SEED = Path("docs/rag-transformation/evals/graph-reasoning-seed-2026-06-24.json")
DEFAULT_OUTPUT = Path("docs/rag-transformation/evals/graph-reasoning-matrix-2026-06-24.json")


def load_graph_reasoning_seed(path: Path) -> list[dict]:
    """Load graph reasoning seed rows."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("questions"), list):
        return data["questions"]
    if isinstance(data, list):
        return data
    return []


def score_graph_reasoning_rows(observations: list[dict], seeds: list[dict]) -> list[dict]:
    """Score graph observations against seed thresholds."""
    observations_by_id = {row.get("id"): row for row in observations}
    scored = []
    for seed in seeds:
        observation = observations_by_id.get(seed.get("id"))
        if not observation:
            scored.append(_missing_observation(seed))
            continue
        failed_checks = _failed_checks(observation, seed)
        scored.append({
            "id": seed.get("id"),
            "entity_id": seed.get("entity_id"),
            "question": seed.get("question", ""),
            "passed": not failed_checks,
            "failed_checks": failed_checks,
            "content_count": observation.get("content_count", 0),
            "repeated_content_count": observation.get("repeated_content_count", 0),
            "date_count": observation.get("date_count", 0),
            "source_count": observation.get("source_count", 0),
            "sample_paths": observation.get("sample_paths", []),
            "needs_conrad_review": bool(seed.get("needs_conrad_review", True)),
        })
    return scored


def summarize_graph_reasoning_rows(rows: list[dict]) -> dict:
    """Summarize graph reasoning score rows."""
    failures = Counter()
    for row in rows:
        failures.update(row.get("failed_checks", []))
    total = len(rows)
    passed = sum(1 for row in rows if row.get("passed"))
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "failure_counts": dict(failures),
    }


async def build_graph_reasoning_observations(seeds: list[dict]) -> list[dict]:
    """Build graph observations from live Neo4j relationships."""
    from rag.graphrag.driver import Neo4jDriver

    driver = Neo4jDriver()
    await driver.connect()
    try:
        observations = []
        for seed in seeds:
            observations.append(await _observe_seed(driver, seed))
    finally:
        await driver.close()
    return observations


async def _observe_seed(driver: Neo4jDriver, seed: dict) -> dict:
    from rag.graph_question_planning import GraphQuestionPlan
    from rag.graph_reasoning_service import build_graph_reasoning_evidence

    entity_id = seed.get("entity_id", "")
    plan = GraphQuestionPlan(
        original_question=seed.get("question", ""), entity_id=entity_id,
        entity_label=seed.get("entity_label") or entity_id,
        question_type="observation_relationship", required_paths=seed.get("required_paths", []),
    )
    return {"id": seed.get("id"), **await build_graph_reasoning_evidence(driver, plan)}


def _failed_checks(observation: dict, seed: dict) -> list[str]:
    failed = []
    if observation.get("content_count", 0) < seed.get("min_contents", 0):
        failed.append("insufficient_contents")
    if observation.get("repeated_content_count", 0) < seed.get("min_repeated_contents", 0):
        failed.append("insufficient_repeated_contents")
    if observation.get("date_count", 0) < seed.get("min_dates", 0):
        failed.append("insufficient_dates")
    if observation.get("source_count", 0) < seed.get("min_sources", 0):
        failed.append("insufficient_sources")

    required_paths = set(seed.get("required_paths") or [])
    if "entity_observation_date" in required_paths and observation.get("date_count", 0) <= 0:
        failed.append("missing_entity_observation_date_path")
    if "entity_observation_source" in required_paths and observation.get("source_count", 0) <= 0:
        failed.append("missing_entity_observation_source_path")
    if "entity_repeated_content" in required_paths and observation.get("repeated_content_count", 0) <= 0:
        failed.append("missing_entity_repeated_content_path")
    return sorted(set(failed))


def _missing_observation(seed: dict) -> dict:
    return {
        "id": seed.get("id"),
        "entity_id": seed.get("entity_id"),
        "question": seed.get("question", ""),
        "passed": False,
        "failed_checks": ["missing_observation"],
        "content_count": 0,
        "repeated_content_count": 0,
        "date_count": 0,
        "source_count": 0,
        "sample_paths": [],
        "needs_conrad_review": bool(seed.get("needs_conrad_review", True)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Score live Neo4j graph reasoning seed checks.")
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    seeds = load_graph_reasoning_seed(args.seed)
    observations = asyncio.run(build_graph_reasoning_observations(seeds))
    scored = score_graph_reasoning_rows(observations, seeds)
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": str(args.seed),
        "summary": summarize_graph_reasoning_rows(scored),
        "rows": scored,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "summary": result["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
