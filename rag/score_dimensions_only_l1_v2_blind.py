"""Unseal and score predictions only after the prediction file exists."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def score(prediction_path: Path, gold_path: Path) -> dict:
    if not prediction_path.exists():
        raise FileNotFoundError("predictions must exist before blind labels are opened")
    predictions = json.loads(prediction_path.read_text())
    gold = json.loads(gold_path.read_text())
    _validate_gold(gold)
    predicted = {row["case_id"]: row for row in predictions["cases"]}
    expected = {row["case_id"]: row for row in gold["cases"]}
    if set(predicted) != set(expected):
        raise ValueError("prediction and label case IDs differ")

    rows = []
    family_counts: dict[str, list[bool]] = defaultdict(list)
    permission_checks = []
    protected_expected: set[tuple[str, str]] = set()
    protected_predicted: set[tuple[str, str]] = set()
    clarification_tp = clarification_fp = clarification_fn = 0
    for case_id, label in expected.items():
        row = predicted[case_id]
        envelope = row["envelope"]
        contract = envelope.get("contract") or {}
        expected_clarification = label["expected_status"] != "resolved"
        predicted_clarification = envelope["status"] != "resolved"
        clarification_tp += int(expected_clarification and predicted_clarification)
        clarification_fp += int(not expected_clarification and predicted_clarification)
        clarification_fn += int(expected_clarification and not predicted_clarification)

        checks = {
            "status": envelope["status"] == label["expected_status"],
            "primary": contract.get("primary_task_family") == label["expected_primary"],
            "supporting": contract.get("supporting_task_families", []) == label["expected_supporting"],
            "answer_mode": contract.get("answer_mode") == label["expected_answer_mode"],
            "protected_terms": contract.get("protected_terms", []) == label["expected_protected_terms"],
            "references": contract.get("resolved_references", []) == label["expected_references"],
            "web_permission": contract.get("web_permission") == label["expected_web_permission"],
        }
        if expected_clarification:
            for field in ("primary", "supporting", "answer_mode", "protected_terms", "references", "web_permission"):
                checks[field] = contract == {}
        if label["expected_primary"]:
            family_counts[label["expected_primary"]].append(checks["primary"] and checks["status"])
        if not expected_clarification:
            permission_checks.append(checks["web_permission"])
            protected_expected.update(
                (case_id, term) for term in label["expected_protected_terms"]
            )
            protected_predicted.update(
                (case_id, term) for term in contract.get("protected_terms", [])
            )
        rows.append({
            "case_id": case_id,
            "complete_contract_correct": all(checks.values()),
            "checks": checks,
            "latency_seconds": row["latency_seconds"],
        })

    total = len(rows)
    complete = sum(row["complete_contract_correct"] for row in rows)
    per_family = {
        family: {
            "correct": sum(values),
            "total": len(values),
            "accuracy": sum(values) / len(values),
        }
        for family, values in sorted(family_counts.items())
    }
    precision = clarification_tp / (clarification_tp + clarification_fp) if clarification_tp + clarification_fp else 1.0
    recall = clarification_tp / (clarification_tp + clarification_fn) if clarification_tp + clarification_fn else 1.0
    overall = complete / total
    route_values = [value for values in family_counts.values() for value in values]
    route_accuracy = sum(route_values) / len(route_values)
    permission_accuracy = sum(permission_checks) / len(permission_checks) if permission_checks else 1.0
    protected_tp = len(protected_expected & protected_predicted)
    protected_precision = protected_tp / len(protected_predicted) if protected_predicted else 1.0
    protected_recall = protected_tp / len(protected_expected) if protected_expected else 1.0
    protected_f1 = (
        2 * protected_precision * protected_recall / (protected_precision + protected_recall)
        if protected_precision + protected_recall else 0.0
    )
    latencies = [row["latency_seconds"] for row in rows]
    gate_passed = (
        route_accuracy >= 0.85
        and all(item["accuracy"] >= 0.80 for item in per_family.values())
        and permission_accuracy == 1.0
        and protected_f1 >= 0.85
        and precision >= 0.80
        and recall >= 0.80
        and overall >= 0.70
    )
    return {
        "experiment_id": predictions["experiment_id"],
        "evidence_boundary": "Unseen blind score for the frozen candidate; not production approval.",
        "freeze_id": predictions["freeze_id"],
        "total": total,
        "complete_contract_correct": complete,
        "complete_contract_accuracy": overall,
        "primary_route_accuracy": route_accuracy,
        "per_primary_family": per_family,
        "web_permission_accuracy": permission_accuracy,
        "protected_terms": {
            "micro_precision": protected_precision,
            "micro_recall": protected_recall,
            "micro_f1": protected_f1,
            "tp": protected_tp,
            "predicted": len(protected_predicted),
            "expected": len(protected_expected),
        },
        "clarification": {
            "precision": precision,
            "recall": recall,
            "tp": clarification_tp,
            "fp": clarification_fp,
            "fn": clarification_fn,
        },
        "latency": {
            "mean_seconds": sum(latencies) / len(latencies),
            "max_seconds": max(latencies),
        },
        "gate": {
            "passed": gate_passed,
            "requirements": "primary route>=85%; each primary>=80%; web permission=100%; protected-term micro-F1>=85%; clarification precision/recall>=80%; complete projection>=70%",
        },
        "cases": rows,
    }


def _validate_gold(gold: dict) -> None:
    allowed_statuses = {"resolved", "clarification_required"}
    required = {
        "case_id",
        "expected_status",
        "expected_primary",
        "expected_supporting",
        "expected_answer_mode",
        "expected_protected_terms",
        "expected_references",
        "expected_web_permission",
    }
    for case in gold.get("cases", []):
        missing = required - set(case)
        if missing:
            raise ValueError(f"gold case missing fields: {sorted(missing)}")
        if case["expected_status"] not in allowed_statuses:
            raise ValueError(
                f"invalid expected_status: {case['expected_status']}"
            )
        if case["expected_status"] == "clarification_required" and case["expected_primary"] is not None:
            raise ValueError("clarification gold cannot name a primary route")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    report = score(args.predictions, args.gold)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "complete_contract_correct": report["complete_contract_correct"],
        "total": report["total"],
        "gate": report["gate"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
