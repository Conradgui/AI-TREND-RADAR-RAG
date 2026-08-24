"""Validate and freeze the six-case Ordered Frame v3.3 visible calibration."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from rag.ordered_frame_client_v3 import build_strict_tool_v3, prompt_sha256_v3
from rag.run_ordered_frame_v3_calibration import _canonical_sha256
from rag import config


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DOCUMENT_KEYS = {"schema_version", "dataset_id", "evidence_boundary", "cases"}
PUBLIC_CASE_KEYS = {"case_id", "query", "conversation_context"}
STATUSES = {"resolved", "clarification_required"}
WEB_PERMISSIONS = {"forbidden", "on_demand", "explicit"}
CONTRACT_LITERAL_PATHS = {
    "protected_terms",
    "claims",
    "resolved_references.value",
    "temporal_constraint.value",
    "source_constraint.requested_sources",
}
REQUIRED_RUNNER_ARTIFACTS = {
    "docs/rag-transformation/specs/ordered-semantic-frame-v3.schema.json",
    "docs/rag-transformation/specs/route-contract-v2.schema.json",
    "rag/config.py",
    "rag/ordered_frame_client_v3.py",
    "rag/ordered_semantic_frame_v3.py",
    "rag/query_understanding_v2.py",
    "rag/query_signal_extraction.py",
    "rag/route_contract_validation.py",
    "rag/run_ordered_frame_v3_calibration.py",
    "rag/task_route_resolution.py",
}
REQUIRED_SCORING_ARTIFACTS = {
    "docs/rag-transformation/specs/route-contract-v2.schema.json",
    "rag/ordered_semantic_frame_v3.py",
    "rag/route_contract_validation.py",
    "rag/score_ordered_frame_v3_3_visible.py",
}


def validate_visible_queries(document: dict[str, Any]) -> None:
    if set(document) - PUBLIC_DOCUMENT_KEYS:
        raise ValueError("visible Query document contains non-public labels")
    if not isinstance(document.get("dataset_id"), str) or not document["dataset_id"].strip():
        raise ValueError("visible Query requires dataset_id")
    cases = document.get("cases")
    if not isinstance(cases, list) or len(cases) != 6:
        raise ValueError("visible calibration requires exactly six cases")
    ids, queries = [], []
    for case in cases:
        if set(case) - PUBLIC_CASE_KEYS:
            raise ValueError("visible Query case contains non-public labels")
        ids.append(case.get("case_id"))
        queries.append(case.get("query"))
        if case.get("conversation_context") is not None and not isinstance(
            case.get("conversation_context"), str
        ):
            raise ValueError("conversation_context must be a string or null")
    if any(not isinstance(value, str) or not value.strip() for value in ids) or len(set(ids)) != 6:
        raise ValueError("visible case IDs must be non-empty and unique")
    if any(not isinstance(value, str) or not value.strip() for value in queries) or len(set(queries)) != 6:
        raise ValueError("visible queries must be non-empty and unique")


def validate_visible_gold(query_document: dict[str, Any], gold_document: dict[str, Any]) -> None:
    validate_visible_queries(query_document)
    if gold_document.get("dataset_id") != query_document["dataset_id"]:
        raise ValueError("Gold dataset_id must match Query")
    cases = gold_document.get("cases")
    expected_ids = [row["case_id"] for row in query_document["cases"]]
    if not isinstance(cases, list) or [row.get("case_id") for row in cases] != expected_ids:
        raise ValueError("Gold cases must match visible Query order")
    for row in cases:
        if row.get("expected_status") not in STATUSES:
            raise ValueError("invalid expected_status")
        deliveries = row.get("expected_deliveries")
        if not isinstance(deliveries, list) or not deliveries:
            raise ValueError("each visible Gold case requires ordered deliveries")
        if row.get("expected_web_permission") not in WEB_PERMISSIONS:
            raise ValueError("invalid expected_web_permission")
        literals = row.get("expected_contract_literals")
        if not isinstance(literals, list):
            raise ValueError("expected_contract_literals must be a list")
        for item in literals:
            if (
                not isinstance(item, dict)
                or item.get("path") not in CONTRACT_LITERAL_PATHS
                or not isinstance(item.get("literal"), str)
                or not item["literal"]
                or item.get("match", "exact") not in {"exact", "substring"}
            ):
                raise ValueError("invalid expected_contract_literals entry")


def build_visible_freeze_manifest(
    *,
    experiment_id: str,
    query_path: str | Path,
    gold_path: str | Path,
    runtime: dict[str, Any],
    runner_artifacts: list[str | Path],
    scoring_artifacts: list[str | Path],
    root: str | Path,
    require_project_artifacts: bool = True,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    query_file = _resolve(root_path, query_path)
    gold_file = _resolve(root_path, gold_path)
    query = json.loads(query_file.read_text())
    gold = json.loads(gold_file.read_text())
    validate_visible_gold(query, gold)
    runner = [_resolve(root_path, path) for path in runner_artifacts]
    scoring = [_resolve(root_path, path) for path in scoring_artifacts]
    if any("sealed" in {part.lower() for part in path.parts} for path in [query_file, gold_file, *runner, *scoring]):
        raise ValueError("visible calibration must not depend on sealed storage")
    runner_names = {_relative(root_path, path) for path in runner}
    scoring_names = {_relative(root_path, path) for path in scoring}
    if require_project_artifacts and not REQUIRED_RUNNER_ARTIFACTS <= runner_names:
        raise ValueError("visible freeze lacks required Runner dependencies")
    if require_project_artifacts and not REQUIRED_SCORING_ARTIFACTS <= scoring_names:
        raise ValueError("visible freeze lacks required scoring dependencies")
    return {
        "schema_version": "atr.visible-calibration-freeze/3.3",
        "experiment_id": experiment_id,
        "evidence_boundary": "Visible calibration only; it cannot support a Blind or generalization claim.",
        "case_order": [row["case_id"] for row in query["cases"]],
        "query_path": _relative(root_path, query_file),
        "query_sha256": _canonical_sha256(query),
        "gold_path": _relative(root_path, gold_file),
        "gold_sha256": _canonical_sha256(gold),
        "prompt_sha256": prompt_sha256_v3(),
        "provider_schema_sha256": _canonical_sha256(build_strict_tool_v3()["function"]["parameters"]),
        "runtime": runtime,
        "runner_artifacts": _records(root_path, runner),
        "scoring_artifacts": _records(root_path, scoring),
        "runtime_budget": {
            "planned_cases": 6,
            "max_provider_calls": 6,
            "attempts_per_case": 1,
            "max_retries": 0,
        },
        "stop_conditions": [
            "artifact_hash_drift",
            "provider_or_network_error",
            "more_than_one_attempt_for_any_case",
            "invalid_or_incomplete_prediction",
        ],
    }


def _resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def _relative(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError(f"artifact is outside freeze root: {path}") from exc


def _records(root: Path, paths: list[Path]) -> list[dict[str, str]]:
    return [
        {"path": _relative(root, path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        for path in paths
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    manifest = build_visible_freeze_manifest(
        experiment_id="ordered-query-frame-v3-3-visible-calibration-2026-08-21",
        query_path=args.queries,
        gold_path=args.gold,
        runtime={
            "model": config.DEEPSEEK_MODEL,
            "base_url": config.DEEPSEEK_BASE_URL.rstrip("/"),
            "temperature": 0,
            "max_tokens": 900,
            "timeout_seconds": 20,
            "thinking": "disabled",
            "max_retries": 0,
            "attempts_per_case": 1,
        },
        runner_artifacts=sorted(REQUIRED_RUNNER_ARTIFACTS),
        scoring_artifacts=sorted(REQUIRED_SCORING_ARTIFACTS),
        root=ROOT,
    )
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"cases": len(manifest["case_order"]), "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
