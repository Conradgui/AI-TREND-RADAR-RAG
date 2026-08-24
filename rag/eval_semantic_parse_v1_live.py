"""Run the frozen 12-case SemanticParseV1 DeepSeek shadow bakeoff."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

from jsonschema import Draft202012Validator

from rag.route_contract_scoring import score_protected_terms
from rag.route_contract_validation import validate_route_contract_semantics
from rag.semantic_parse_client import DeepSeekSemanticParseClient, prompt_sha256
from rag.semantic_parse_v1 import SCHEMA_PATH, build_route_contract_from_semantic_parse


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _prf(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}


def run(query_path: Path, gold_path: Path, old_predictions_path: Path, client) -> dict:
    query_asset = json.loads(query_path.read_text(encoding="utf-8"))
    gold_asset = json.loads(gold_path.read_text(encoding="utf-8"))
    old_asset = json.loads(old_predictions_path.read_text(encoding="utf-8"))
    gold = {item["case_id"]: item for item in gold_asset["cases"]}
    old = {item["case_id"]: item["prediction"] for item in old_asset["predictions"]}
    route_schema = json.loads((SCHEMA_PATH.parent / "route-contract-v2.schema.json").read_text(encoding="utf-8"))
    route_validator = Draft202012Validator(route_schema)
    rows = []
    protected_tp = protected_fp = protected_fn = 0
    ambiguity_tp = ambiguity_fp = ambiguity_fn = 0

    for case in query_asset["cases"]:
        case_id = case["case_id"]
        expected = gold[case_id]
        started = time.monotonic()
        parse = contract = usage = None
        error = None
        try:
            parse, usage = client.extract(case["query"], case.get("conversation_context"))
            contract = build_route_contract_from_semantic_parse(
                case["query"], case.get("conversation_context"), parse
            ).to_dict()
            route_errors = list(route_validator.iter_errors(contract))
            validate_route_contract_semantics(contract)
            route_valid = not route_errors
        except Exception as exc:
            route_valid = False
            error = f"{type(exc).__name__}: {str(exc)[:500]}"
        latency = round(time.monotonic() - started, 3)

        if contract is None:
            checks = {key: False for key in (
                "route_schema_semantic", "route", "answer_mode", "supporting_routes",
                "web_permission", "protected_terms", "ambiguity", "resolved_references",
            )}
            protected = score_protected_terms([], expected["expected_protected_terms"])
            actual_ambiguity = False
        else:
            protected = score_protected_terms(contract["protected_terms"], expected["expected_protected_terms"])
            actual_ambiguity = bool(contract["ambiguities"])
            checks = {
                "route_schema_semantic": route_valid,
                "route": contract["primary_task_family"] == expected["primary_task_family"],
                "answer_mode": contract["answer_mode"] == expected["answer_mode"],
                "supporting_routes": contract["supporting_task_families"] == expected["supporting_task_families"],
                "web_permission": contract["web_permission"] == expected["web_permission"],
                "protected_terms": protected.f1 == 1.0,
                "ambiguity": actual_ambiguity == expected["ambiguity_expected"],
                "resolved_references": contract["resolved_references"] == expected["expected_resolved_references"],
            }
        protected_tp += protected.true_positive
        protected_fp += protected.false_positive
        protected_fn += protected.false_negative
        ambiguity_tp += int(expected["ambiguity_expected"] and actual_ambiguity)
        ambiguity_fp += int(not expected["ambiguity_expected"] and actual_ambiguity)
        ambiguity_fn += int(expected["ambiguity_expected"] and not actual_ambiguity)
        rows.append({
            "case_id": case_id,
            "latency_seconds": latency,
            "parse": parse,
            "contract": contract,
            "usage": usage,
            "error": error,
            "checks": checks,
            "old_route_correct": old[case_id]["primary_task_family"] == expected["primary_task_family"],
        })

    total = len(rows)
    successful = [row for row in rows if row["error"] is None]
    latencies = sorted(row["latency_seconds"] for row in rows)
    route_correct = sum(row["checks"]["route"] for row in rows)
    old_correct = sum(row["old_route_correct"] for row in rows)
    a_rows = [row for row in rows if gold[row["case_id"]]["primary_task_family"] == "item_navigation"]
    parse_valid = sum(row["error"] is None for row in rows)
    a_correct = sum(row["checks"]["route"] for row in a_rows)
    return {
        "experiment_id": "semantic-parse-v1-diagnostic-calibration-2026-08-13",
        "evidence_boundary": "12-case diagnostic calibration selected from an unsealed dataset; not blind or production evidence.",
        "provider": "deepseek",
        "model": getattr(client, "model", "unknown"),
        "temperature": 0,
        "max_tokens": 2400,
        "timeout_seconds": 45,
        "max_retries": 0,
        "hashes": {
            "queries": _sha256(query_path), "gold": _sha256(gold_path),
            "parse_schema": _sha256(SCHEMA_PATH), "prompt": prompt_sha256(),
        },
        "total": total,
        "parse_schema_semantic_valid": {"correct": parse_valid, "total": total, "rate": round(parse_valid / total, 4)},
        "route": {"correct": route_correct, "total": total, "accuracy": round(route_correct / total, 4)},
        "item_navigation": {
            "correct": a_correct,
            "total": len(a_rows),
            "accuracy": round(a_correct / len(a_rows), 4) if a_rows else None,
        },
        "old_route_baseline": {"correct": old_correct, "total": total, "accuracy": round(old_correct / total, 4), "net_gain_cases": route_correct - old_correct},
        "web_permission_accuracy": round(sum(row["checks"]["web_permission"] for row in rows) / total, 4),
        "protected_term_micro": _prf(protected_tp, protected_fp, protected_fn),
        "ambiguity_detection": _prf(ambiguity_tp, ambiguity_fp, ambiguity_fn),
        "resolved_reference_accuracy": round(sum(row["checks"]["resolved_references"] for row in rows) / total, 4),
        "latency_seconds": {
            "mean": round(sum(latencies) / total, 3),
            "p50": latencies[(total - 1) // 2],
            "p95": latencies[max(0, int(total * 0.95) - 1)],
            "max": max(latencies),
        },
        "reliability": {"success": len(successful), "failure": total - len(successful), "success_rate": round(len(successful) / total, 4)},
        "tokens": {
            "prompt": sum((row["usage"] or {}).get("prompt_tokens", 0) for row in rows),
            "completion": sum((row["usage"] or {}).get("completion_tokens", 0) for row in rows),
            "total": sum((row["usage"] or {}).get("total_tokens", 0) for row in rows),
            "cost_estimate_usd": None,
        },
        "cases": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--old-predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case-id", action="append", default=[])
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"output exists: {args.output}")
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise SystemExit("DEEPSEEK_API_KEY is not configured")
    client = DeepSeekSemanticParseClient(
        api_key=api_key,
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        timeout=45,
    )
    if args.case_id:
        selected = set(args.case_id)
        query_asset = json.loads(args.queries.read_text(encoding="utf-8"))
        query_asset["cases"] = [item for item in query_asset["cases"] if item["case_id"] in selected]
        if len(query_asset["cases"]) != len(selected):
            raise SystemExit("one or more requested canary case IDs are missing")
        canary_path = args.output.with_suffix(".queries.json")
        canary_path.write_text(json.dumps(query_asset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        query_path = canary_path
    else:
        query_path = args.queries
    report = run(query_path, args.gold, args.old_predictions, client)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "route", "item_navigation", "old_route_baseline", "web_permission_accuracy",
        "protected_term_micro", "ambiguity_detection", "latency_seconds", "reliability", "tokens",
    )}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
