"""Score sealed v3 calibration predictions against re-adjudicated Gold."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from jsonschema import Draft202012Validator

from rag.ordered_semantic_frame_v3 import validate_ordered_semantic_frame_v3
from rag.route_contract_validation import validate_route_contract_semantics


ROOT = Path(__file__).resolve().parents[1]
ROUTE_SCHEMA = json.loads(
    (ROOT / "docs/rag-transformation/specs/route-contract-v2.schema.json").read_text()
)


TASK_FAMILIES = (
    "item_navigation",
    "trend_discovery",
    "temporal_relation_exploration",
    "claim_verification",
    "evidence_research",
)


def validate_assets(query_document: dict, gold_document: dict) -> None:
    query_ids = [case["case_id"] for case in query_document["cases"]]
    gold_ids = [case["case_id"] for case in gold_document["cases"]]
    if query_ids != gold_ids or len(set(query_ids)) != len(query_ids):
        raise ValueError("query and gold case IDs must be unique and ordered identically")
    for case in gold_document["cases"]:
        status = case["expected_status"]
        if status not in {"resolved", "clarification_required"}:
            raise ValueError(f"invalid expected_status: {status}")
        deliveries = case["expected_deliveries"]
        if status == "resolved" and not deliveries:
            raise ValueError(f'{case["case_id"]} resolved Gold requires deliveries')


def validate_predictions(query_document: dict, prediction_document: dict) -> None:
    query_cases = query_document["cases"]
    prediction_cases = prediction_document.get("cases", [])
    query_ids = [case["case_id"] for case in query_cases]
    prediction_ids = [case.get("case_id") for case in prediction_cases]
    if prediction_ids != query_ids or len(set(prediction_ids)) != len(prediction_ids):
        raise ValueError("prediction case IDs must be unique and ordered like queries")
    if prediction_document.get("planned") != len(query_cases):
        raise ValueError("prediction planned count does not match queries")
    if prediction_document.get("executed") != len(query_cases):
        raise ValueError("prediction execution is incomplete")
    if prediction_document.get("query_dataset_id") != query_document.get("dataset_id"):
        raise ValueError("prediction query dataset does not match")
    if prediction_document.get("query_sha256") != _canonical_sha256(query_document):
        raise ValueError("prediction query hash does not match")

    for query_case, prediction in zip(query_cases, prediction_cases, strict=True):
        if prediction.get("query") != query_case["query"]:
            raise ValueError(f'{query_case["case_id"]} prediction Query drift')
        if prediction.get("error"):
            raise ValueError(f'{query_case["case_id"]} prediction contains an error')
        frame = prediction.get("frame")
        envelope = prediction.get("envelope") or {}
        validate_ordered_semantic_frame_v3(query_case["query"], frame)
        status = envelope.get("status")
        contract = envelope.get("contract")
        if status == "resolved":
            if not contract:
                raise ValueError(f'{query_case["case_id"]} resolved without a contract')
            Draft202012Validator(ROUTE_SCHEMA).validate(contract)
            validate_route_contract_semantics(contract)
        elif status == "clarification_required":
            if contract is not None:
                raise ValueError(f'{query_case["case_id"]} clarification contains a contract')
        else:
            raise ValueError(f'{query_case["case_id"]} has invalid envelope status')


def score_predictions(
    query_document: dict,
    gold_document: dict,
    prediction_document: dict,
) -> dict:
    validate_assets(query_document, gold_document)
    validate_predictions(query_document, prediction_document)
    predictions = {case["case_id"]: case for case in prediction_document["cases"]}
    rows = []
    primary_by_family = defaultdict(lambda: [0, 0])
    protected_tp = protected_fp = protected_fn = 0
    clarify_tp = clarify_fp = clarify_fn = 0

    for gold in gold_document["cases"]:
        prediction = predictions.get(gold["case_id"])
        envelope = (prediction or {}).get("envelope") or {}
        frame = (prediction or {}).get("frame") or {}
        contract = envelope.get("contract") or {}
        predicted_status = envelope.get("status", "error")
        predicted_deliveries = [
            [
                item.get("task_family"),
                item.get("requested_output_form"),
                item.get("locator_kind"),
            ]
            for item in frame.get("deliveries", [])
        ]
        status_ok = predicted_status == gold["expected_status"]
        delivery_ok = predicted_deliveries == gold["expected_deliveries"]
        predicted_web_permission = (
            contract.get("web_permission")
            if predicted_status == "resolved"
            else frame.get("web_permission")
        )
        web_ok = predicted_web_permission == gold["expected_web_permission"]

        expected_terms = {_norm(term) for term in gold["expected_protected_terms"]}
        protected_source = (
            contract.get("protected_terms", [])
            if predicted_status == "resolved"
            else frame.get("protected_spans", [])
        )
        predicted_terms = {_norm(term) for term in protected_source}
        protected_tp += len(expected_terms & predicted_terms)
        protected_fp += len(predicted_terms - expected_terms)
        protected_fn += len(expected_terms - predicted_terms)
        protected_exact = expected_terms == predicted_terms

        expected_clarify = gold["expected_status"] == "clarification_required"
        predicted_clarify = predicted_status == "clarification_required"
        clarify_tp += int(expected_clarify and predicted_clarify)
        clarify_fp += int(not expected_clarify and predicted_clarify)
        clarify_fn += int(expected_clarify and not predicted_clarify)

        primary_ok = True
        if gold["expected_status"] == "resolved":
            expected_primary = gold["expected_deliveries"][0][0]
            primary_by_family[expected_primary][1] += 1
            primary_ok = contract.get("primary_task_family") == expected_primary
            primary_by_family[expected_primary][0] += int(primary_ok)

        legal = True
        complete = status_ok and delivery_ok and web_ok and protected_exact and legal
        rows.append({
            "case_id": gold["case_id"],
            "checks": {
                "status": status_ok,
                "ordered_deliveries": delivery_ok,
                "primary": primary_ok,
                "web_permission": web_ok,
                "protected_exact": protected_exact,
                "legal": legal,
                "complete_projection": complete,
            },
        })

    resolved_count = sum(
        case["expected_status"] == "resolved" for case in gold_document["cases"]
    )
    primary_correct = sum(values[0] for values in primary_by_family.values())
    primary_accuracy = _pct(primary_correct, resolved_count)
    per_family = {
        family: _pct(*primary_by_family[family])
        for family in TASK_FAMILIES
    }
    protected_precision = _pct(protected_tp, protected_tp + protected_fp)
    protected_recall = _pct(protected_tp, protected_tp + protected_fn)
    protected_f1 = _f1(protected_precision, protected_recall)
    clarification_precision = _pct(clarify_tp, clarify_tp + clarify_fp)
    clarification_recall = _pct(clarify_tp, clarify_tp + clarify_fn)
    ordered_accuracy = _pct(
        sum(row["checks"]["ordered_deliveries"] for row in rows), len(rows)
    )
    complete_accuracy = _pct(
        sum(row["checks"]["complete_projection"] for row in rows), len(rows)
    )
    web_accuracy = _pct(
        sum(row["checks"]["web_permission"] for row in rows),
        len(rows),
    )
    legal_accuracy = _pct(sum(row["checks"]["legal"] for row in rows), len(rows))
    attempts_ok = all(
        (case.get("metadata") or {}).get("attempts") == 1
        for case in prediction_document["cases"]
    ) and len(prediction_document["cases"]) == len(gold_document["cases"])
    latencies = [case["latency_seconds"] for case in prediction_document["cases"]]
    mean_latency = round(sum(latencies) / len(latencies), 3) if latencies else 0
    max_latency = max(latencies, default=0)

    metrics = {
        "ordered_deliveries_accuracy": ordered_accuracy,
        "primary_route_accuracy": primary_accuracy,
        "primary_route_accuracy_by_family": per_family,
        "web_permission_accuracy": web_accuracy,
        "protected_span_micro_precision": protected_precision,
        "protected_span_micro_recall": protected_recall,
        "protected_span_micro_f1": protected_f1,
        "clarification_precision": clarification_precision,
        "clarification_recall": clarification_recall,
        "frame_route_legal_rate": legal_accuracy,
        "complete_projection_accuracy": complete_accuracy,
        "single_attempt_all_cases": attempts_ok,
        "mean_latency_seconds": mean_latency,
        "max_latency_seconds": max_latency,
        "total_tokens": sum(
            int((case.get("metadata") or {}).get("total_tokens", 0) or 0)
            for case in prediction_document["cases"]
        ),
    }
    gate_checks = {
        "ordered_deliveries_at_least_85": ordered_accuracy >= 85,
        "primary_route_at_least_85": primary_accuracy >= 85,
        "every_covered_family_at_least_80": all(
            _pct(*primary_by_family[family]) >= 80
            for family in TASK_FAMILIES
            if primary_by_family[family][1] > 0
        ),
        "web_permission_100": web_accuracy == 100,
        "protected_f1_at_least_85": protected_f1 >= 85,
        "clarification_precision_at_least_80": clarification_precision >= 80,
        "clarification_recall_at_least_80": clarification_recall >= 80,
        "frame_route_legal_100": legal_accuracy == 100,
        "complete_projection_at_least_85": complete_accuracy >= 85,
        "single_attempt_all_cases": attempts_ok,
        "mean_latency_at_most_8": mean_latency <= 8,
        "max_latency_at_most_12": max_latency <= 12,
    }
    return {
        "experiment_id": "ordered-query-frame-v3-visible-calibration-score-2026-08-16",
        "evidence_boundary": "Already-unsealed calibration score; not blind, production, or generalization evidence.",
        "metrics": metrics,
        "gate": {"passed": all(gate_checks.values()), "checks": gate_checks},
        "cases": rows,
    }


def _norm(value: str) -> str:
    return " ".join(value.casefold().split())


def _pct(numerator: int, denominator: int) -> float:
    return round(100 * numerator / denominator, 1) if denominator else 0.0


def _f1(precision: float, recall: float) -> float:
    return round(2 * precision * recall / (precision + recall), 1) if precision + recall else 0.0


def _canonical_sha256(value: dict) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_scoring_artifacts(manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text())
    for artifact in manifest.get("scoring_artifacts", []):
        path = ROOT / artifact["path"]
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != artifact["sha256"]:
            raise ValueError(f"scoring artifact hash drift: {artifact['path']}")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--freeze-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    manifest = verify_scoring_artifacts(args.freeze_manifest)
    predictions = json.loads(args.predictions.read_text())
    expected_freeze_sha256 = hashlib.sha256(args.freeze_manifest.read_bytes()).hexdigest()
    if predictions.get("freeze_manifest_sha256") != expected_freeze_sha256:
        raise ValueError("predictions were not produced by this freeze manifest")
    report = score_predictions(
        json.loads(args.queries.read_text()),
        json.loads(args.gold.read_text()),
        predictions,
    )
    report["experiment_id"] = manifest["experiment_id"] + "-score"
    report["freeze_manifest_sha256"] = expected_freeze_sha256
    report["gate_thresholds"] = manifest["gate_thresholds"]
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"metrics": report["metrics"], "gate": report["gate"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
