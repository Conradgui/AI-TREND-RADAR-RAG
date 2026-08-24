"""Contract-level scorer for the Ordered Frame v3.3 visible calibration.

This scorer is intentionally separate from the frozen v3.2 Blind scorer.  Raw
Frame spans remain diagnostics; product completion is decided from ordered
deliveries and the final Route Contract fields that downstream modules consume.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from rag.ordered_semantic_frame_v3 import build_ordered_route_envelope_v3
from rag.route_contract_validation import validate_route_contract_semantics
from rag.run_ordered_frame_v3_calibration import _canonical_sha256


ROOT = Path(__file__).resolve().parents[1]
ROUTE_SCHEMA = json.loads(
    (ROOT / "docs/rag-transformation/specs/route-contract-v2.schema.json").read_text()
)


def verify_visible_scoring_freeze(
    manifest_path: Path,
    query_document: dict,
    gold_document: dict,
    prediction_document: dict,
    *,
    root: Path = ROOT,
) -> dict:
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("query_sha256") != _canonical_sha256(query_document):
        raise ValueError("frozen Query hash mismatch")
    if manifest.get("gold_sha256") != _canonical_sha256(gold_document):
        raise ValueError("frozen Gold hash mismatch")
    expected_freeze_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    if prediction_document.get("freeze_manifest_sha256") != expected_freeze_hash:
        raise ValueError("prediction freeze manifest mismatch")
    for artifact in manifest.get("scoring_artifacts", []):
        actual = hashlib.sha256((root / artifact["path"]).read_bytes()).hexdigest()
        if actual != artifact["sha256"]:
            raise ValueError(f"frozen scoring artifact drift: {artifact['path']}")
    return manifest


def score_visible_contract_calibration(
    query_document: dict[str, Any],
    gold_document: dict[str, Any],
    prediction_document: dict[str, Any],
) -> dict[str, Any]:
    """Score visible calibration predictions at their public product seams."""
    _validate_case_alignment(query_document, gold_document, prediction_document)
    rows = []
    for query_case, gold, prediction in zip(
        query_document["cases"],
        gold_document["cases"],
        prediction_document["cases"],
        strict=True,
    ):
        frame = prediction.get("frame") or {}
        envelope = prediction.get("envelope") or {}
        contract = envelope.get("contract")
        expected_deliveries = [tuple(item) for item in gold["expected_deliveries"]]
        actual_deliveries = _delivery_triples(frame)
        delivery_exact = actual_deliveries == expected_deliveries

        expected_status = gold["expected_status"]
        status_shape_ok = (
            envelope.get("status") == expected_status
            and ((expected_status == "clarification_required") == (contract is None))
        )
        contract_legal = _contract_is_legal(contract, expected_status)
        replay_ok = _replay_matches(
            query_case["query"],
            query_case.get("conversation_context"),
            frame,
            envelope,
        )
        main_family_ok, main_output_ok = _main_contract_checks(
            contract, expected_deliveries, expected_status
        )
        supporting_family_ok, supporting_navigation_ok = _supporting_contract_checks(
            contract, expected_deliveries, expected_status
        )
        web_permission_ok = _web_permission(
            frame, contract, expected_status
        ) == gold["expected_web_permission"]
        critical = _score_contract_literals(
            contract, gold.get("expected_contract_literals", []), expected_status
        )
        critical_ok = all(item["matched"] for item in critical)
        no_error = prediction.get("error") is None
        one_attempt = (prediction.get("metadata") or {}).get("attempts") == 1

        checks = {
            "no_prediction_error": no_error,
            "single_attempt": one_attempt,
            "delivery_sequence_exact": delivery_exact,
            "status_and_contract_shape": status_shape_ok,
            "main_task_family_contract": main_family_ok,
            "main_output_contract": main_output_ok,
            "supporting_task_families_contract": supporting_family_ok,
            "supporting_navigation_contract": supporting_navigation_ok,
            "web_permission_contract": web_permission_ok,
            "contract_critical_terms": critical_ok,
            "l3_legal": contract_legal,
            "l3_projection_consistent": replay_ok,
        }
        checks["product_complete"] = all(checks.values())
        scored_checks = [value for key, value in checks.items() if key != "product_complete"]
        rows.append(
            {
                "case_id": gold["case_id"],
                "checks": checks,
                "contract_completion_pct": _pct(sum(scored_checks), len(scored_checks)),
                "contract_literal_checks": critical,
                "diagnostics": {
                    "raw_frame_protected_exact_span": _exact_span_metrics(
                        gold.get("expected_protected_terms", []),
                        frame.get("protected_spans", []),
                    )
                },
            }
        )

    latencies = [float(case.get("latency_seconds") or 0) for case in prediction_document["cases"]]
    metrics = {
        "case_count": len(rows),
        "product_complete_count": sum(row["checks"]["product_complete"] for row in rows),
        "delivery_sequence_exact": _rate(rows, "delivery_sequence_exact"),
        "status_and_contract_shape": _rate(rows, "status_and_contract_shape"),
        "web_permission_contract": _rate(rows, "web_permission_contract"),
        "contract_critical_terms": _rate(rows, "contract_critical_terms"),
        "l3_legal": _rate(rows, "l3_legal"),
        "l3_projection_consistent": _rate(rows, "l3_projection_consistent"),
        "single_attempt_all_cases": all(row["checks"]["single_attempt"] for row in rows),
        "mean_latency_seconds": round(sum(latencies) / len(latencies), 3) if latencies else 0,
        "max_latency_seconds": max(latencies, default=0),
    }
    checks = {
        "all_cases_product_complete": metrics["product_complete_count"] == len(rows),
        "delivery_sequence_100": metrics["delivery_sequence_exact"] == 100.0,
        "status_and_contract_shape_100": metrics["status_and_contract_shape"] == 100.0,
        "web_permission_100": metrics["web_permission_contract"] == 100.0,
        "contract_critical_terms_100": metrics["contract_critical_terms"] == 100.0,
        "l3_legal_100": metrics["l3_legal"] == 100.0,
        "l3_projection_consistent_100": metrics["l3_projection_consistent"] == 100.0,
        "single_attempt_all_cases": metrics["single_attempt_all_cases"],
        "mean_latency_at_most_8": metrics["mean_latency_seconds"] <= 8,
        "max_latency_at_most_12": metrics["max_latency_seconds"] <= 12,
    }
    return {
        "schema_version": "atr.visible-contract-eval/3.3",
        "metrics": metrics,
        "gate": {"passed": bool(rows) and all(checks.values()), "checks": checks},
        "cases": rows,
    }


def _validate_case_alignment(query_document: dict, gold_document: dict, predictions: dict) -> None:
    query_ids = [row.get("case_id") for row in query_document.get("cases", [])]
    gold_ids = [row.get("case_id") for row in gold_document.get("cases", [])]
    prediction_ids = [row.get("case_id") for row in predictions.get("cases", [])]
    if not query_ids or len(query_ids) != len(set(query_ids)):
        raise ValueError("Query case IDs must be non-empty and unique")
    if gold_ids != query_ids:
        raise ValueError("Gold case IDs must match Query order")
    if prediction_ids != query_ids:
        raise ValueError("prediction case IDs must match Query order")
    if predictions.get("planned") != len(query_ids) or predictions.get("executed") != len(query_ids):
        raise ValueError("visible calibration must execute every planned case")


def _delivery_triples(frame: dict) -> list[tuple[str, str, str]]:
    return [
        (
            row.get("task_family"),
            row.get("requested_output_form"),
            row.get("locator_kind"),
        )
        for row in frame.get("deliveries", [])
    ]


def _main_contract_checks(contract: dict | None, expected: list[tuple], status: str) -> tuple[bool, bool]:
    if status == "clarification_required":
        return contract is None, contract is None
    if not contract or not expected:
        return False, False
    family, output, _ = expected[0]
    return contract.get("primary_task_family") == family, contract.get("answer_mode") == output


def _supporting_contract_checks(contract: dict | None, expected: list[tuple], status: str) -> tuple[bool, bool]:
    if status == "clarification_required":
        return contract is None, contract is None
    if not contract:
        return False, False
    expected_supporting = expected[1:]
    family_ok = contract.get("supporting_task_families") == [row[0] for row in expected_supporting]
    actual_contracts = contract.get("supporting_contracts", [])
    if len(actual_contracts) != len(expected_supporting):
        return family_ok, False
    navigation_ok = True
    for expected_delivery, actual in zip(expected_supporting, actual_contracts, strict=True):
        family, output, locator = expected_delivery
        if family != "item_navigation":
            continue
        navigation_ok &= (
            actual.get("task_family") == family
            and actual.get("requested_output_form") == output
            and actual.get("locator_kind") == locator
        )
    return family_ok, bool(navigation_ok)


def _web_permission(frame: dict, contract: dict | None, status: str) -> str | None:
    if status == "clarification_required":
        return frame.get("web_permission")
    return contract.get("web_permission") if contract else None


def _contract_is_legal(contract: dict | None, status: str) -> bool:
    if status == "clarification_required":
        return contract is None
    if not isinstance(contract, dict):
        return False
    try:
        Draft202012Validator(ROUTE_SCHEMA).validate(contract)
        validate_route_contract_semantics(contract)
    except Exception:
        return False
    return True


def _replay_matches(query: str, context: str | None, frame: dict, envelope: dict) -> bool:
    try:
        replay = build_ordered_route_envelope_v3(query, frame, context)
    except Exception:
        return False
    return _canonical(replay) == _canonical(envelope)


def _score_contract_literals(
    contract: dict | None, expectations: list[dict[str, str]], status: str
) -> list[dict[str, Any]]:
    if status == "clarification_required":
        return [dict(expectation, matched=False) for expectation in expectations]
    result = []
    for expectation in expectations:
        path = expectation["path"]
        literal = expectation["literal"]
        mode = expectation.get("match", "exact")
        values = _contract_values_at_path(contract or {}, path)
        matched = (
            literal in values
            if mode == "exact"
            else any(literal in value for value in values)
        )
        result.append({**expectation, "observed_values": sorted(values), "matched": matched})
    return result


def _contract_values_at_path(contract: dict, path: str) -> set[str]:
    if path == "protected_terms":
        return {str(value) for value in contract.get("protected_terms", [])}
    if path == "claims":
        return {str(value) for value in contract.get("claims", [])}
    if path == "resolved_references.value":
        return {str(row.get("value")) for row in contract.get("resolved_references", [])}
    if path == "temporal_constraint.value":
        value = (contract.get("temporal_constraint") or {}).get("value")
        return {str(value)} if value else set()
    if path == "source_constraint.requested_sources":
        return {
            str(value)
            for value in (contract.get("source_constraint") or {}).get("requested_sources", [])
        }
    raise ValueError(f"unsupported contract literal path: {path}")


def _exact_span_metrics(expected: list[str], actual: list[str]) -> dict[str, float]:
    expected_set, actual_set = set(expected), set(actual)
    matched = len(expected_set & actual_set)
    precision = _pct(matched, len(actual_set))
    recall = _pct(matched, len(expected_set))
    f1 = round(2 * precision * recall / (precision + recall), 1) if precision + recall else 100.0
    return {"precision": precision, "recall": recall, "f1": f1}


def _rate(rows: list[dict], check: str) -> float:
    return _pct(sum(row["checks"][check] for row in rows), len(rows))


def _pct(numerator: int, denominator: int) -> float:
    return round(numerator * 100 / denominator, 1) if denominator else 100.0


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


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
    query_document = json.loads(args.queries.read_text())
    gold_document = json.loads(args.gold.read_text())
    prediction_document = json.loads(args.predictions.read_text())
    verify_visible_scoring_freeze(
        args.freeze_manifest, query_document, gold_document, prediction_document
    )
    report = score_visible_contract_calibration(query_document, gold_document, prediction_document)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report["gate"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
