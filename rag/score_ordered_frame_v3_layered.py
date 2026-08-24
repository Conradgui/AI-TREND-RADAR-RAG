"""Layered evaluator for Ordered Frame v3.1 shadow predictions."""

from __future__ import annotations

import argparse
import json
import hashlib
import unicodedata
from collections import defaultdict
from pathlib import Path

from jsonschema import Draft202012Validator

from rag.ordered_semantic_frame_v3 import (
    build_ordered_route_envelope_v3,
    validate_ordered_semantic_frame_v3,
)
from rag.run_ordered_frame_v3_calibration import _canonical_sha256, _query_dataset_id
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
L2_REPLAY_ARTIFACTS = {
    "docs/rag-transformation/specs/route-contract-v2.schema.json",
    "rag/ordered_semantic_frame_v3.py",
    "rag/query_understanding_v2.py",
    "rag/route_contract_validation.py",
}
LAYERED_SCORING_ARTIFACTS = {
    "docs/rag-transformation/specs/ordered-semantic-frame-v3.schema.json",
    "rag/score_ordered_frame_v3_layered.py",
}


def score_layered(
    query_document: dict,
    gold_document: dict,
    prediction_document: dict,
    freeze_manifest: dict,
    freeze_manifest_sha256: str,
) -> dict:
    _verify_l2_freeze(freeze_manifest, freeze_manifest_sha256, prediction_document)
    _verify_scoring_freeze(freeze_manifest)
    if freeze_manifest.get("query_sha256") != _canonical_sha256(query_document):
        raise ValueError("frozen Query hash mismatch")
    if freeze_manifest.get("gold_sha256") != _canonical_sha256(gold_document):
        raise ValueError("frozen Gold hash mismatch")
    _validate_documents(query_document, gold_document, prediction_document)
    rows = []
    family_counts = defaultdict(lambda: [0, 0])
    output_correct = output_total = locator_correct = locator_total = 0
    protected_counts = [0, 0, 0]
    delivery_evidence_counts = [0, 0, 0]
    web_evidence_counts = [0, 0, 0]
    critical_counts = [0, 0, 0]
    unresolved_counts = [0, 0, 0]
    clarify_tp = clarify_fp = clarify_fn = 0

    for query_case, gold, prediction in zip(
        query_document["cases"], gold_document["cases"], prediction_document["cases"], strict=True
    ):
        query = query_case["query"]
        context = query_case.get("conversation_context")
        frame = prediction["frame"]
        saved_envelope = prediction["envelope"]
        predicted_deliveries = _delivery_triples(frame)
        expected_deliveries = gold["expected_deliveries"]
        delivery_exact = predicted_deliveries == expected_deliveries

        primary_expected = expected_deliveries[0][0] if expected_deliveries else None
        primary_predicted = predicted_deliveries[0][0] if predicted_deliveries else None
        primary_ok = primary_expected == primary_predicted
        if primary_expected:
            family_counts[primary_expected][1] += 1
            family_counts[primary_expected][0] += int(primary_ok)

        width = max(len(expected_deliveries), len(predicted_deliveries))
        output_total += width
        locator_total += width
        for index in range(width):
            expected = expected_deliveries[index] if index < len(expected_deliveries) else None
            predicted = predicted_deliveries[index] if index < len(predicted_deliveries) else None
            output_correct += int(bool(expected and predicted and expected[1] == predicted[1]))
            locator_correct += int(bool(expected and predicted and expected[2] == predicted[2]))

        web_ok = frame["web_permission"] == gold["expected_web_permission"]
        protected = _span_case(query, gold["expected_protected_terms"], frame["protected_spans"])
        expected_delivery_evidence = [
            span
            for group in gold.get("expected_delivery_evidence_spans", [])
            for span in group
        ]
        predicted_delivery_evidence = [
            span for delivery in frame["deliveries"] for span in delivery["evidence_spans"]
        ]
        delivery_evidence = _span_case(
            query, expected_delivery_evidence, predicted_delivery_evidence
        )
        web_evidence = _span_case(
            query,
            gold.get("expected_web_evidence_spans", []),
            frame["web_evidence_spans"],
        )
        expected_critical = [
            span
            for spans in gold.get("expected_critical_terms", {}).values()
            for span in spans
        ]
        predicted_critical = list(dict.fromkeys(
            frame["protected_spans"]
            + predicted_delivery_evidence
            + frame["web_evidence_spans"]
            + frame["unresolved_reference_spans"]
        ))
        critical = _span_case(query, expected_critical, predicted_critical)
        unresolved = _span_case(
            query,
            gold["expected_unresolved_reference_spans"],
            frame["unresolved_reference_spans"],
        )
        _add_counts(protected_counts, protected["counts"])
        _add_counts(delivery_evidence_counts, delivery_evidence["counts"])
        _add_counts(web_evidence_counts, web_evidence["counts"])
        _add_counts(critical_counts, critical["counts"])
        _add_counts(unresolved_counts, unresolved["counts"])

        expected_clarify = gold["expected_status"] == "clarification_required"
        predicted_clarify = saved_envelope.get("status") == "clarification_required"
        clarify_tp += int(expected_clarify and predicted_clarify)
        clarify_fp += int(not expected_clarify and predicted_clarify)
        clarify_fn += int(expected_clarify and not predicted_clarify)
        status_ok = expected_clarify == predicted_clarify

        replay = build_ordered_route_envelope_v3(query, frame, context)
        l3_consistent = _canonical_json(replay) == _canonical_json(saved_envelope)
        l3_legal = _saved_envelope_is_legal(query, saved_envelope)
        product_complete = all((
            delivery_exact,
            web_ok,
            status_ok,
            protected["f1"] >= 80,
            delivery_evidence["f1"] >= 80,
            web_evidence["f1"] >= 80,
            critical["recall"] == 100,
            unresolved["f1"] >= 80,
            l3_legal,
            l3_consistent,
        ))
        rows.append({
            "case_id": gold["case_id"],
            "checks": {
                "delivery_sequence_exact": delivery_exact,
                "primary_task_family": primary_ok,
                "web_permission": web_ok,
                "envelope_status": status_ok,
                "l3_legal": l3_legal,
                "l3_projection_consistent": l3_consistent,
                "product_complete": product_complete,
            },
            "span_scores": {
                "protected": _without_counts(protected),
                "delivery_evidence": _without_counts(delivery_evidence),
                "web_evidence": _without_counts(web_evidence),
                "critical": _without_counts(critical),
                "unresolved": _without_counts(unresolved),
            },
        })

    resolved_primary_total = sum(value[1] for value in family_counts.values())
    latencies = [float(case["latency_seconds"]) for case in prediction_document["cases"]]
    protected_micro = _metrics_from_counts(*protected_counts)
    delivery_evidence_micro = _metrics_from_counts(*delivery_evidence_counts)
    web_evidence_micro = _metrics_from_counts(*web_evidence_counts)
    critical_micro = _metrics_from_counts(*critical_counts)
    unresolved_micro = _metrics_from_counts(*unresolved_counts)
    metrics = {
        "delivery_sequence_exact": _pct(sum(row["checks"]["delivery_sequence_exact"] for row in rows), len(rows)),
        "primary_task_family_accuracy": _pct(sum(value[0] for value in family_counts.values()), resolved_primary_total),
        "primary_task_family_accuracy_by_family": {family: _pct(*family_counts[family]) for family in TASK_FAMILIES},
        "primary_family_sample_count": {family: family_counts[family][1] for family in TASK_FAMILIES},
        "output_form_accuracy": _pct(output_correct, output_total),
        "locator_accuracy": _pct(locator_correct, locator_total),
        "web_permission_accuracy": _pct(sum(row["checks"]["web_permission"] for row in rows), len(rows)),
        "protected_span_char_micro_precision": protected_micro["precision"],
        "protected_span_char_micro_recall": protected_micro["recall"],
        "protected_span_char_micro_f1": protected_micro["f1"],
        "delivery_evidence_char_micro_f1": delivery_evidence_micro["f1"],
        "web_evidence_char_micro_f1": web_evidence_micro["f1"],
        "critical_term_char_micro_recall": critical_micro["recall"],
        "unresolved_span_char_micro_precision": unresolved_micro["precision"],
        "unresolved_span_char_micro_recall": unresolved_micro["recall"],
        "unresolved_span_char_micro_f1": unresolved_micro["f1"],
        "clarification_precision": _binary_precision(clarify_tp, clarify_fp, clarify_fn),
        "clarification_recall": _binary_recall(clarify_tp, clarify_fn),
        "l3_legal_rate": _pct(sum(row["checks"]["l3_legal"] for row in rows), len(rows)),
        "l3_projection_consistency": _pct(sum(row["checks"]["l3_projection_consistent"] for row in rows), len(rows)),
        "product_complete": _pct(sum(row["checks"]["product_complete"] for row in rows), len(rows)),
        "single_attempt_all_cases": len(rows) == len(prediction_document["cases"]) and all((case.get("metadata") or {}).get("attempts") == 1 for case in prediction_document["cases"]),
        "mean_latency_seconds": round(sum(latencies) / len(latencies), 3) if latencies else 0,
        "max_latency_seconds": max(latencies, default=0),
    }
    return {
        "schema_version": "atr.layered-eval/1.0",
        "metrics": metrics,
        "gate": evaluate_gate(metrics),
        "cases": rows,
    }


def _verify_l2_freeze(manifest: dict, manifest_sha256: str, prediction_document: dict) -> None:
    prediction_freeze = manifest.get("prediction_freeze_manifest_sha256", manifest_sha256)
    if prediction_document.get("freeze_manifest_sha256") != prediction_freeze:
        raise ValueError("prediction freeze manifest mismatch")
    artifacts = {item["path"]: item["sha256"] for item in manifest.get("runner_artifacts", [])}
    missing = sorted(L2_REPLAY_ARTIFACTS - artifacts.keys())
    if missing:
        raise ValueError("freeze manifest lacks L2 replay artifacts: " + ", ".join(missing))
    for relative_path in L2_REPLAY_ARTIFACTS:
        actual = hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest()
        if actual != artifacts[relative_path]:
            raise ValueError(f"frozen L2 artifact drift: {relative_path}")


def _verify_scoring_freeze(manifest: dict) -> None:
    artifacts = {item["path"]: item["sha256"] for item in manifest.get("scoring_artifacts", [])}
    missing = sorted(LAYERED_SCORING_ARTIFACTS - artifacts.keys())
    if missing:
        raise ValueError("freeze manifest lacks layered scoring artifacts: " + ", ".join(missing))
    for relative_path in LAYERED_SCORING_ARTIFACTS:
        actual = hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest()
        if actual != artifacts[relative_path]:
            raise ValueError(f"frozen scoring artifact drift: {relative_path}")


def evaluate_gate(metrics: dict) -> dict:
    family_checks = {
        family: accuracy >= 80
        for family, accuracy in metrics["primary_task_family_accuracy_by_family"].items()
        if metrics["primary_family_sample_count"].get(family, 0) >= 3
    }
    checks = {
        "delivery_sequence_at_least_85": metrics["delivery_sequence_exact"] >= 85,
        "primary_task_family_at_least_85": metrics["primary_task_family_accuracy"] >= 85,
        "eligible_primary_families_at_least_80": all(family_checks.values()),
        "output_form_at_least_85": metrics["output_form_accuracy"] >= 85,
        "web_permission_100": metrics["web_permission_accuracy"] == 100,
        "protected_char_f1_at_least_85": metrics["protected_span_char_micro_f1"] >= 85,
        "delivery_evidence_char_f1_at_least_85": metrics["delivery_evidence_char_micro_f1"] >= 85,
        "web_evidence_char_f1_at_least_85": metrics["web_evidence_char_micro_f1"] >= 85,
        "critical_term_recall_100": metrics["critical_term_char_micro_recall"] == 100,
        "unresolved_char_precision_at_least_80": metrics["unresolved_span_char_micro_precision"] >= 80,
        "unresolved_char_recall_at_least_80": metrics["unresolved_span_char_micro_recall"] >= 80,
        "clarification_precision_at_least_80": metrics["clarification_precision"] >= 80,
        "clarification_recall_at_least_80": metrics["clarification_recall"] >= 80,
        "l3_legal_100": metrics["l3_legal_rate"] == 100,
        "l3_projection_consistency_100": metrics["l3_projection_consistency"] == 100,
        "product_complete_at_least_80": metrics["product_complete"] >= 80,
        "single_attempt_all_cases": metrics["single_attempt_all_cases"] is True,
        "mean_latency_at_most_8": metrics["mean_latency_seconds"] <= 8,
        "max_latency_at_most_12": metrics["max_latency_seconds"] <= 12,
    }
    return {"passed": all(checks.values()), "checks": checks, "eligible_family_checks": family_checks}


def _validate_documents(query_document: dict, gold_document: dict, prediction_document: dict) -> None:
    query_ids = [case["case_id"] for case in query_document["cases"]]
    gold_ids = [case["case_id"] for case in gold_document["cases"]]
    prediction_ids = [case["case_id"] for case in prediction_document["cases"]]
    if not (query_ids == gold_ids == prediction_ids) or len(set(query_ids)) != len(query_ids):
        raise ValueError("query, Gold, and prediction case IDs must be unique and ordered identically")
    if prediction_document.get("planned") != len(query_ids) or prediction_document.get("executed") != len(query_ids):
        raise ValueError("prediction execution is incomplete")
    if prediction_document.get("query_dataset_id") != _query_dataset_id(query_document):
        raise ValueError("prediction dataset mismatch")
    if prediction_document.get("query_sha256") != _canonical_sha256(query_document):
        raise ValueError("prediction Query hash mismatch")
    for query_case, gold, prediction in zip(query_document["cases"], gold_document["cases"], prediction_document["cases"], strict=True):
        if prediction.get("error") or prediction.get("query") != query_case["query"]:
            raise ValueError(f'{query_case["case_id"]} prediction is invalid or drifted')
        validate_ordered_semantic_frame_v3(query_case["query"], prediction["frame"])
        if gold["expected_status"] not in {"resolved", "clarification_required"}:
            raise ValueError(f'{gold["case_id"]} has invalid expected status')
        if not gold["expected_deliveries"]:
            raise ValueError(f'{gold["case_id"]} layered Gold must preserve explicit deliveries')
        evidence_groups = gold.get("expected_delivery_evidence_spans")
        if not isinstance(evidence_groups, list) or len(evidence_groups) != len(gold["expected_deliveries"]):
            raise ValueError(f'{gold["case_id"]} delivery evidence must align with deliveries')
        _span_positions(query_case["query"], gold["expected_protected_terms"])
        for spans in evidence_groups:
            _span_positions(query_case["query"], spans)
        _span_positions(query_case["query"], gold.get("expected_web_evidence_spans", []))
        for spans in gold.get("expected_critical_terms", {}).values():
            _span_positions(query_case["query"], spans)
        _span_positions(query_case["query"], gold["expected_unresolved_reference_spans"])


def _delivery_triples(frame: dict) -> list[list[str]]:
    return [[item["task_family"], item["requested_output_form"], item["locator_kind"]] for item in frame["deliveries"]]


def _saved_envelope_is_legal(query: str, envelope: dict) -> bool:
    status = envelope.get("status")
    contract = envelope.get("contract")
    if status == "clarification_required":
        return contract is None and bool(envelope.get("reasons"))
    if status != "resolved" or not contract or contract.get("original_query") != query:
        return False
    try:
        Draft202012Validator(ROUTE_SCHEMA).validate(contract)
        validate_route_contract_semantics(contract)
    except Exception:
        return False
    return True


def _span_case(query: str, expected: list[str], predicted: list[str]) -> dict:
    gold_positions = _span_positions(query, expected)
    predicted_positions = _span_positions(query, predicted)
    tp = len(gold_positions & predicted_positions)
    fp = len(predicted_positions - gold_positions)
    fn = len(gold_positions - predicted_positions)
    result = _metrics_from_counts(tp, fp, fn)
    result["counts"] = [tp, fp, fn]
    return result


def _span_positions(query: str, spans: list[str]) -> set[int]:
    positions: set[int] = set()
    for span in spans:
        if not isinstance(span, str) or not span:
            raise ValueError("span must be a non-empty literal string")
        start = 0
        found = False
        while True:
            index = query.find(span, start)
            if index < 0:
                break
            found = True
            positions.update(
                offset
                for offset in range(index, index + len(span))
                if _is_scored_character(query[offset])
            )
            start = index + len(span)
        if not found:
            raise ValueError(f"span is not literal Query text: {span}")
    return positions


def _is_scored_character(character: str) -> bool:
    return not character.isspace() and not unicodedata.category(character).startswith("P")


def _metrics_from_counts(tp: int, fp: int, fn: int) -> dict:
    if tp == fp == fn == 0:
        return {"precision": 100.0, "recall": 100.0, "f1": 100.0}
    precision = 100 * tp / (tp + fp) if tp + fp else 0.0
    recall = 100 * tp / (tp + fn) if tp + fn else 100.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": round(precision, 1), "recall": round(recall, 1), "f1": round(f1, 1)}


def _binary_precision(tp: int, fp: int, fn: int) -> float:
    if tp == fp == fn == 0:
        return 100.0
    return _pct(tp, tp + fp)


def _binary_recall(tp: int, fn: int) -> float:
    return _pct(tp, tp + fn) if tp + fn else 100.0


def _pct(numerator: int, denominator: int) -> float:
    return round(100 * numerator / denominator, 1) if denominator else 100.0


def _add_counts(total: list[int], values: list[int]) -> None:
    for index, value in enumerate(values):
        total[index] += value


def _without_counts(value: dict) -> dict:
    return {key: item for key, item in value.items() if key != "counts"}


def _canonical_json(value: dict) -> str:
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
    freeze_manifest = json.loads(args.freeze_manifest.read_text())
    freeze_manifest_sha256 = hashlib.sha256(args.freeze_manifest.read_bytes()).hexdigest()
    report = score_layered(
        query_document,
        gold_document,
        prediction_document,
        freeze_manifest,
        freeze_manifest_sha256,
    )
    report.update({
        "experiment_id": freeze_manifest["experiment_id"],
        "evidence_boundary": "Sealed blind evaluation; predictions were generated from Query-only input before Gold was unsealed to the scorer.",
        "freeze_manifest_sha256": freeze_manifest_sha256,
        "prediction_freeze_manifest_sha256": freeze_manifest.get(
            "prediction_freeze_manifest_sha256", freeze_manifest_sha256
        ),
        "query_sha256": freeze_manifest["query_sha256"],
        "gold_sha256": freeze_manifest["gold_sha256"],
    })
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"gate_passed": report["gate"]["passed"], "metrics": report["metrics"]}, ensure_ascii=False, indent=2))
    if not report["gate"]["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
