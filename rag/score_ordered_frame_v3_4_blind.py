"""Final-contract scorer for the v3.4 unseen Ordered Query Frame Blind."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from rag.run_ordered_frame_v3_calibration import _canonical_sha256
from rag.score_ordered_frame_v3_3_visible import (
    _contract_is_legal,
    _contract_values_at_path,
    _pct,
    _replay_matches,
)


ROOT = Path(__file__).resolve().parents[1]


def verify_blind_scoring_freeze(
    evaluation_manifest_path: Path,
    prediction_freeze_path: Path,
    query_document: dict[str, Any],
    gold_document: dict[str, Any],
    prediction_document: dict[str, Any],
    *,
    root: Path = ROOT,
) -> dict[str, Any]:
    """Fail closed if labels, scorer, public freeze, or case order drifted."""
    manifest = json.loads(evaluation_manifest_path.read_text())
    if manifest.get("query_sha256") != _canonical_sha256(query_document):
        raise ValueError("frozen Query hash mismatch")
    if manifest.get("gold_sha256") != _canonical_sha256(gold_document):
        raise ValueError("frozen Gold hash mismatch")
    prediction_freeze_hash = hashlib.sha256(prediction_freeze_path.read_bytes()).hexdigest()
    if manifest.get("prediction_freeze_manifest_sha256") != prediction_freeze_hash:
        raise ValueError("evaluation freeze does not bind the public prediction freeze")
    if prediction_document.get("freeze_manifest_sha256") != prediction_freeze_hash:
        raise ValueError("predictions do not bind the public prediction freeze")
    query_order = [case.get("case_id") for case in query_document.get("cases", [])]
    if manifest.get("case_order") != query_order:
        raise ValueError("frozen case order mismatch")
    for artifact in manifest.get("scoring_artifacts", []):
        path = root / artifact["path"]
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != artifact["sha256"]:
            raise ValueError(f"frozen scoring artifact drift: {artifact['path']}")
    return manifest


def score_blind_contract_v3_4(
    query_document: dict[str, Any],
    gold_document: dict[str, Any],
    prediction_document: dict[str, Any],
) -> dict[str, Any]:
    """Score only observable semantic and final Route Contract product seams."""
    _validate_alignment(query_document, gold_document, prediction_document)
    rows: list[dict[str, Any]] = []
    for query_case, gold, prediction in zip(
        query_document["cases"],
        gold_document["cases"],
        prediction_document["cases"],
        strict=True,
    ):
        frame = prediction.get("frame") or {}
        envelope = prediction.get("envelope") or {}
        contract = envelope.get("contract")
        expected_status = gold["expected_status"]
        expected_deliveries = [tuple(item) for item in gold["expected_deliveries"]]
        frame_deliveries = _frame_delivery_triples(frame)
        final_deliveries = _contract_delivery_triples(contract)
        is_clarification = expected_status == "clarification_required"

        status_shape = (
            envelope.get("status") == expected_status
            and (is_clarification == (contract is None))
        )
        final_delivery_exact = (
            contract is None if is_clarification else final_deliveries == expected_deliveries
        )
        clarification_delivery_exact = (
            frame_deliveries == expected_deliveries if is_clarification else True
        )
        unresolved_exact = frame.get("unresolved_reference_spans", []) == gold.get(
            "expected_unresolved_reference_spans", []
        )
        web_permission = (
            frame.get("web_permission")
            if is_clarification
            else contract.get("web_permission") if contract else None
        )
        literal_checks = _score_literals(
            contract, gold.get("expected_contract_literals", []), is_clarification
        )
        checks = {
            "no_prediction_error": prediction.get("error") is None,
            "single_attempt": (prediction.get("metadata") or {}).get("attempts") == 1,
            "status_and_contract_shape": status_shape,
            "final_delivery_contract_exact": final_delivery_exact,
            "clarification_delivery_exact": clarification_delivery_exact,
            "unresolved_references_exact": unresolved_exact,
            "web_permission_contract": web_permission == gold["expected_web_permission"],
            "contract_literals": all(item["matched"] for item in literal_checks),
            "l3_legal": _contract_is_legal(contract, expected_status),
            "l3_projection_consistent": _replay_matches(
                query_case["query"],
                query_case.get("conversation_context"),
                frame,
                envelope,
            ),
        }
        checks["product_complete"] = all(checks.values())
        scored = [value for key, value in checks.items() if key != "product_complete"]
        rows.append(
            {
                "case_id": gold["case_id"],
                "checks": checks,
                "contract_completion_pct": _pct(sum(scored), len(scored)),
                "contract_literal_checks": literal_checks,
                "diagnostics": {
                    "ordered_frame_delivery_exact": frame_deliveries == expected_deliveries,
                    "observed_frame_deliveries": [list(item) for item in frame_deliveries],
                    "observed_final_deliveries": [list(item) for item in final_deliveries],
                },
            }
        )

    latencies = [
        float(case.get("latency_seconds") or 0) for case in prediction_document["cases"]
    ]
    metrics = {
        "case_count": len(rows),
        "product_complete_count": sum(
            row["checks"]["product_complete"] for row in rows
        ),
        "status_and_contract_shape": _rate(rows, "status_and_contract_shape"),
        "final_delivery_contract_exact": _rate(rows, "final_delivery_contract_exact"),
        "clarification_delivery_exact": _rate(rows, "clarification_delivery_exact"),
        "unresolved_references_exact": _rate(rows, "unresolved_references_exact"),
        "web_permission_contract": _rate(rows, "web_permission_contract"),
        "contract_literals": _rate(rows, "contract_literals"),
        "l3_legal": _rate(rows, "l3_legal"),
        "l3_projection_consistent": _rate(rows, "l3_projection_consistent"),
        "single_attempt_all_cases": all(
            row["checks"]["single_attempt"] for row in rows
        ),
        "mean_latency_seconds": round(sum(latencies) / len(latencies), 3)
        if latencies
        else 0,
        "max_latency_seconds": max(latencies, default=0),
    }
    required_complete = max(len(rows) - 2, 1)
    gate_checks = {
        "product_complete_at_least_n_minus_2": metrics["product_complete_count"]
        >= required_complete,
        "status_shape_100": metrics["status_and_contract_shape"] == 100.0,
        "final_delivery_100": metrics["final_delivery_contract_exact"] == 100.0,
        "clarification_delivery_100": metrics["clarification_delivery_exact"] == 100.0,
        "unresolved_references_100": metrics["unresolved_references_exact"] == 100.0,
        "web_permission_100": metrics["web_permission_contract"] == 100.0,
        "contract_literals_100": metrics["contract_literals"] == 100.0,
        "l3_legal_100": metrics["l3_legal"] == 100.0,
        "l3_projection_consistent_100": metrics["l3_projection_consistent"] == 100.0,
        "single_attempt_all_cases": metrics["single_attempt_all_cases"],
        "mean_latency_at_most_8": metrics["mean_latency_seconds"] <= 8,
        "max_latency_at_most_12": metrics["max_latency_seconds"] <= 12,
    }
    return {
        "schema_version": "atr.blind-contract-eval/3.4",
        "metrics": metrics,
        "gate": {"passed": bool(rows) and all(gate_checks.values()), "checks": gate_checks},
        "cases": rows,
    }


def _validate_alignment(query: dict, gold: dict, predictions: dict) -> None:
    query_ids = [row.get("case_id") for row in query.get("cases", [])]
    gold_ids = [row.get("case_id") for row in gold.get("cases", [])]
    prediction_ids = [row.get("case_id") for row in predictions.get("cases", [])]
    if not query_ids or len(query_ids) != len(set(query_ids)):
        raise ValueError("Query case IDs must be non-empty and unique")
    if gold_ids != query_ids or prediction_ids != query_ids:
        raise ValueError("Gold and prediction cases must match Query order")
    if predictions.get("planned") != len(query_ids) or predictions.get("executed") != len(query_ids):
        raise ValueError("Blind must execute every planned case")


def _frame_delivery_triples(frame: dict) -> list[tuple[str, str, str]]:
    return [
        (
            row.get("task_family"),
            row.get("requested_output_form"),
            row.get("locator_kind"),
        )
        for row in frame.get("deliveries", [])
    ]


def _contract_delivery_triples(contract: dict | None) -> list[tuple[str, str, str]]:
    if not contract:
        return []
    return [
        (
            row.get("task_family"),
            row.get("requested_output_form"),
            row.get("locator_kind"),
        )
        for row in contract.get("delivery_contracts", [])
    ]


def _score_literals(
    contract: dict | None,
    expectations: list[dict[str, str]],
    is_clarification: bool,
) -> list[dict[str, Any]]:
    if is_clarification:
        return [] if not expectations else [
            {**expectation, "observed_values": [], "matched": False}
            for expectation in expectations
        ]
    result = []
    for expectation in expectations:
        values = _contract_values_at_path(contract or {}, expectation["path"])
        literal = expectation["literal"]
        matched = (
            literal in values
            if expectation.get("match", "exact") == "exact"
            else any(literal in value for value in values)
        )
        result.append(
            {**expectation, "observed_values": sorted(values), "matched": matched}
        )
    return result


def _rate(rows: list[dict[str, Any]], check: str) -> float:
    return _pct(sum(row["checks"][check] for row in rows), len(rows))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--evaluation-freeze", type=Path, required=True)
    parser.add_argument("--prediction-freeze", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    query_document = json.loads(args.queries.read_text())
    gold_document = json.loads(args.gold.read_text())
    prediction_document = json.loads(args.predictions.read_text())
    verify_blind_scoring_freeze(
        args.evaluation_freeze,
        args.prediction_freeze,
        query_document,
        gold_document,
        prediction_document,
    )
    report = score_blind_contract_v3_4(
        query_document, gold_document, prediction_document
    )
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report["gate"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
