"""Deterministically score frozen Route Contract v2 predictions against sealed Gold."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from jsonschema import Draft202012Validator

from rag.route_contract_scoring import score_protected_terms
from rag.route_contract_validation import validate_route_contract_semantics


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = ROOT / "docs/rag-transformation/specs/route-contract-v2.schema.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _set_counts(actual: list[str], expected: list[str]) -> tuple[int, int, int]:
    actual_set = {" ".join(item.casefold().split()) for item in actual}
    expected_set = {" ".join(item.casefold().split()) for item in expected}
    return (
        len(actual_set & expected_set),
        len(actual_set - expected_set),
        len(expected_set - actual_set),
    )


def _prf(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def evaluate_predictions(prediction_path: Path, gold_path: Path, schema_path: Path) -> dict:
    predictions_file = json.loads(prediction_path.read_text(encoding="utf-8"))
    gold_file = json.loads(gold_path.read_text(encoding="utf-8"))
    if predictions_file["query_dataset_id"] != gold_file["dataset_id"]:
        raise ValueError("prediction and Gold dataset IDs do not match")

    predictions = {item["case_id"]: item for item in predictions_file["predictions"]}
    gold = {item["case_id"]: item for item in gold_file["cases"]}
    if set(predictions) != set(gold):
        raise ValueError("prediction and Gold case IDs do not match")

    validator = Draft202012Validator(json.loads(schema_path.read_text(encoding="utf-8")))
    route_total: Counter[str] = Counter()
    route_correct: Counter[str] = Counter()
    confusion: dict[str, Counter[str]] = defaultdict(Counter)
    intent_tp = intent_fp = intent_fn = 0
    protected_tp = protected_fp = protected_fn = 0
    ambiguity_tp = ambiguity_fp = ambiguity_fn = 0
    pair_checks: dict[str, list[bool]] = defaultdict(list)
    rows = []

    for case_id, expected in gold.items():
        prediction_row = predictions[case_id]
        contract = prediction_row["prediction"]
        if prediction_row["query"] != expected["original_query"]:
            raise ValueError(f"query text differs for {case_id}")

        schema_errors = list(validator.iter_errors(contract))
        semantic_error = None
        try:
            validate_route_contract_semantics(contract)
        except ValueError as exc:
            semantic_error = str(exc)

        expected_route = expected["primary_task_family"]
        actual_route = contract["primary_task_family"]
        route_total[expected_route] += 1
        route_correct[expected_route] += int(actual_route == expected_route)
        confusion[expected_route][actual_route] += 1

        intent_counts = _set_counts(contract["intent_signals"], expected["intent_signals"])
        intent_tp += intent_counts[0]
        intent_fp += intent_counts[1]
        intent_fn += intent_counts[2]
        protected = score_protected_terms(
            contract["protected_terms"], expected["expected_protected_terms"]
        )
        protected_tp += protected.true_positive
        protected_fp += protected.false_positive
        protected_fn += protected.false_negative

        expected_ambiguity = bool(expected.get("ambiguity_expected", False))
        actual_ambiguity = bool(contract["ambiguities"])
        ambiguity_tp += int(expected_ambiguity and actual_ambiguity)
        ambiguity_fp += int(not expected_ambiguity and actual_ambiguity)
        ambiguity_fn += int(expected_ambiguity and not actual_ambiguity)

        expected_references = expected.get("expected_resolved_references", [])
        checks = {
            "schema_valid": not schema_errors,
            "semantic_valid": semantic_error is None,
            "route": actual_route == expected_route,
            "answer_mode": contract["answer_mode"] == expected["answer_mode"],
            "supporting_routes": contract["supporting_task_families"] == expected["supporting_task_families"],
            "intent_signals": intent_counts[1:] == (0, 0),
            "web_permission": contract["web_permission"] == expected["web_permission"],
            "protected_terms": protected.f1 == 1.0,
            "ambiguity": actual_ambiguity == expected_ambiguity,
            "resolved_references": contract.get("resolved_references", []) == expected_references,
        }
        full_projection = all(checks.values())
        pair_id = expected.get("minimal_pair_id")
        if pair_id:
            pair_checks[pair_id].append(checks["route"] and checks["answer_mode"])
        rows.append(
            {
                "case_id": case_id,
                "expected_route": expected_route,
                "actual_route": actual_route,
                "checks": checks,
                "full_projection_exact": full_projection,
                "schema_errors": [error.message for error in schema_errors],
                "semantic_error": semantic_error,
            }
        )

    total = len(rows)
    complete_pairs = [all(values) for values in pair_checks.values()]
    permission_rows = [
        row for row in rows
        if gold[row["case_id"]]["web_permission"] in {"forbidden", "explicit"}
    ]
    return {
        "score_id": f"{predictions_file['prediction_id']}-score",
        "dataset_id": gold_file["dataset_id"],
        "prediction_id": predictions_file["prediction_id"],
        "protocol": "Predictions were frozen before sealed Gold was read by the scoring process.",
        "hashes": {
            "prediction_file_sha256": _sha256(prediction_path),
            "sealed_gold_file_sha256": _sha256(gold_path),
            "schema_file_sha256": _sha256(schema_path),
        },
        "total": total,
        "route_accuracy": {
            "overall": {
                "correct": sum(row["checks"]["route"] for row in rows),
                "total": total,
                "accuracy": round(sum(row["checks"]["route"] for row in rows) / total, 4),
            },
            "per_route": {
                route: {
                    "correct": route_correct[route],
                    "total": route_total[route],
                    "accuracy": round(route_correct[route] / route_total[route], 4),
                }
                for route in sorted(route_total)
            },
            "confusion": {route: dict(values) for route, values in confusion.items()},
        },
        "intent_signal_micro": _prf(intent_tp, intent_fp, intent_fn),
        "protected_term_micro": _prf(protected_tp, protected_fp, protected_fn),
        "ambiguity_detection": _prf(ambiguity_tp, ambiguity_fp, ambiguity_fn),
        "permission_critical_accuracy": {
            "correct": sum(row["checks"]["web_permission"] for row in permission_rows),
            "total": len(permission_rows),
            "accuracy": round(
                sum(row["checks"]["web_permission"] for row in permission_rows) / len(permission_rows), 4
            ) if permission_rows else 1.0,
        },
        "minimal_pairs": {
            "pair_count": len(complete_pairs),
            "all_cases_route_correct": round(sum(complete_pairs) / len(complete_pairs), 4)
            if complete_pairs else 1.0,
        },
        "full_projection_exact": {
            "correct": sum(row["full_projection_exact"] for row in rows),
            "total": total,
            "accuracy": round(sum(row["full_projection_exact"] for row in rows) / total, 4),
        },
        "cases": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"score already exists and will not be overwritten: {args.output}")
    report = evaluate_predictions(args.predictions, args.gold, args.schema)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("route_accuracy", "full_projection_exact")}, indent=2))


if __name__ == "__main__":
    main()
