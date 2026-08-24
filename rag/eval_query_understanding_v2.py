"""Offline evaluation for the shadow Route Contract v2 understander."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from jsonschema import Draft202012Validator

from rag.query_understanding_v2 import understand_query_v2
from rag.route_contract_scoring import score_protected_terms
from rag.route_contract_validation import validate_route_contract_semantics


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "docs/rag-transformation/evals/route-contract-v2-development-2026-08-13.json"
DEFAULT_SCHEMA = ROOT / "docs/rag-transformation/specs/route-contract-v2.schema.json"
DEFAULT_OUTPUT = ROOT / "docs/rag-transformation/evals/route-contract-v2-shadow-results-2026-08-13.json"


def evaluate(dataset_path: Path, schema_path: Path) -> dict:
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)

    rows = []
    route_counts: Counter[str] = Counter()
    route_correct: Counter[str] = Counter()
    confusion: dict[str, Counter[str]] = defaultdict(Counter)

    for case in dataset["cases"]:
        expected = case["expected"]
        contract = understand_query_v2(case["query"]).to_dict()
        schema_errors = sorted(validator.iter_errors(contract), key=lambda error: list(error.path))
        semantic_error = None
        try:
            validate_route_contract_semantics(contract)
        except ValueError as exc:
            semantic_error = str(exc)

        expected_route = expected["primary_task_family"]
        actual_route = contract["primary_task_family"]
        route_counts[expected_route] += 1
        route_correct[expected_route] += int(expected_route == actual_route)
        confusion[expected_route][actual_route] += 1

        expected_signals = set(expected["intent_signals"])
        actual_signals = set(contract["intent_signals"])
        protected_score = score_protected_terms(
            contract["protected_terms"],
            expected["preserve_tokens"],
        )
        checks = {
            "schema_valid": not schema_errors,
            "semantic_valid": semantic_error is None,
            "route": actual_route == expected_route,
            "answer_mode": contract["answer_mode"] == expected["answer_mode"],
            "supporting_routes": contract["supporting_task_families"] == expected["supporting_task_families"],
            "intent_signals": actual_signals == expected_signals,
            "web_permission": contract["web_permission"] == expected["web_permission"],
            "prompt_contract": contract["prompt_contract_id"] == expected["prompt_contract_id"],
            "answer_builder_contract": contract["answer_builder_contract_id"] == expected["answer_builder_contract_id"],
            "protected_terms": protected_score.f1 == 1.0,
        }
        rows.append(
            {
                "case_id": case["case_id"],
                "query": case["query"],
                "expected_route": expected_route,
                "actual_route": actual_route,
                "checks": checks,
                "passed": all(checks.values()),
                "schema_errors": [error.message for error in schema_errors],
                "semantic_error": semantic_error,
                "protected_term_score": {
                    "true_positive": protected_score.true_positive,
                    "false_positive": protected_score.false_positive,
                    "false_negative": protected_score.false_negative,
                    "precision": round(protected_score.precision, 4),
                    "recall": round(protected_score.recall, 4),
                    "f1": round(protected_score.f1, 4),
                },
            }
        )

    fields = list(rows[0]["checks"])
    field_accuracy = {
        field: round(sum(row["checks"][field] for row in rows) / len(rows), 4)
        for field in fields
    }
    per_route = {
        route: {
            "correct": route_correct[route],
            "total": route_counts[route],
            "route_accuracy": round(route_correct[route] / route_counts[route], 4),
        }
        for route in sorted(route_counts)
    }
    protected_tp = sum(row["protected_term_score"]["true_positive"] for row in rows)
    protected_fp = sum(row["protected_term_score"]["false_positive"] for row in rows)
    protected_fn = sum(row["protected_term_score"]["false_negative"] for row in rows)
    protected_precision = protected_tp / (protected_tp + protected_fp) if protected_tp + protected_fp else 1.0
    protected_recall = protected_tp / (protected_tp + protected_fn) if protected_tp + protected_fn else 1.0
    protected_f1 = (
        2 * protected_precision * protected_recall / (protected_precision + protected_recall)
        if protected_precision + protected_recall
        else 0.0
    )
    return {
        "evaluation_id": "route-contract-v2-shadow-development-2026-08-13",
        "dataset_id": dataset["dataset_id"],
        "evidence_boundary": (
            "Development-set contract matching only; not a blind estimate of production quality. "
            "Entity, topic, temporal and source extraction are not labelled or scored."
        ),
        "total_cases": len(rows),
        "fully_passed": sum(row["passed"] for row in rows),
        "field_accuracy": field_accuracy,
        "protected_term_micro": {
            "true_positive": protected_tp,
            "false_positive": protected_fp,
            "false_negative": protected_fn,
            "precision": round(protected_precision, 4),
            "recall": round(protected_recall, 4),
            "f1": round(protected_f1, 4),
            "policy": "normalized independent-span exact set comparison; extra spans are penalized",
        },
        "per_route": per_route,
        "route_confusion": {expected: dict(actual) for expected, actual in confusion.items()},
        "cases": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    report = evaluate(args.dataset, args.schema)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("total_cases", "fully_passed", "per_route")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
