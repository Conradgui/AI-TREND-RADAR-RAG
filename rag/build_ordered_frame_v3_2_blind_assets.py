"""Offline validation and freezing for the v3.2 double-annotation blind."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from rag.ordered_frame_client_v3 import build_strict_tool_v3, prompt_sha256_v3
from rag.run_ordered_frame_v3_calibration import _canonical_sha256


TASK_FAMILIES = {
    "item_navigation": {"exact_item", "item_disambiguation"},
    "trend_discovery": {"important_news", "trend_clusters"},
    "temporal_relation_exploration": {"timeline", "relation", "longitudinal_trend", "cross_sectional_trend"},
    "claim_verification": {"verification_verdict"},
    "evidence_research": {"explanation", "comparison", "deep_research"},
}
FAMILY_CODES = dict(zip(TASK_FAMILIES, "ABCDE", strict=True))
LOCATORS = {"atr_id", "full_title", "title_fragment", "descriptive", "none"}
WEB_PERMISSIONS = {"forbidden", "on_demand", "explicit"}
STATUSES = {"resolved", "clarification_required"}
CRITICAL_KINDS = {"date", "amount", "atr_id", "source", "negation", "permission", "other"}
PUBLIC_CASE_KEYS = {"case_id", "query", "conversation_context"}
PUBLIC_DOCUMENT_KEYS = {"schema_version", "dataset_id", "shard_id", "evidence_boundary", "cases"}
GOLD_FIELDS = (
    "expected_status", "expected_deliveries", "expected_delivery_evidence_spans",
    "expected_protected_terms", "expected_critical_terms", "expected_web_permission",
    "expected_web_evidence_spans", "expected_unresolved_reference_spans",
)
AGREEMENT_FIELDS = GOLD_FIELDS + ("primary_family",)
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
    "docs/rag-transformation/specs/ordered-semantic-frame-v3.schema.json",
    "rag/score_ordered_frame_v3_layered.py",
}
REQUIRED_CONTRAST_KINDS = {"b-c", "d-e", "a-e", "timeline-longitudinal", "resolved-clarification"}


def validate_query_document(document: dict[str, Any]) -> None:
    if set(document) - PUBLIC_DOCUMENT_KEYS:
        raise ValueError("public Query document must not contain coverage or Gold labels")
    identifiers = [document.get("dataset_id"), document.get("shard_id")]
    if sum(isinstance(value, str) and bool(value.strip()) for value in identifiers) != 1:
        raise ValueError("public Query document requires exactly one dataset_id or shard_id")
    cases = document.get("cases")
    if not isinstance(cases, list) or len(cases) != 20:
        raise ValueError("blind Query document must contain exactly 20 cases")
    ids, queries = [], []
    for case in cases:
        if set(case) - PUBLIC_CASE_KEYS:
            raise ValueError("public Query cases must not contain coverage or Gold labels")
        ids.append(case.get("case_id"))
        queries.append(case.get("query"))
        context = case.get("conversation_context")
        if context is not None and not isinstance(context, str):
            raise ValueError("conversation_context must be a string or null")
    if any(not isinstance(value, str) or not value for value in ids) or len(set(ids)) != 20:
        raise ValueError("case IDs must be non-empty and unique")
    if any(not isinstance(value, str) or not value.strip() for value in queries) or len(set(queries)) != 20:
        raise ValueError("blind queries must be non-empty and unique")


def validate_annotation_document(query_document: dict[str, Any], annotation_document: dict[str, Any], annotator_id: str) -> None:
    validate_query_document(query_document)
    if not annotator_id.strip() or annotation_document.get("annotator_id") != annotator_id:
        raise ValueError("annotation document must declare the expected annotator_id")
    query_cases, annotations = query_document["cases"], annotation_document.get("cases")
    if not isinstance(annotations, list) or [row.get("case_id") for row in annotations] != [row["case_id"] for row in query_cases]:
        raise ValueError("annotation cases must match Query case order")
    for query_case, annotation in zip(query_cases, annotations, strict=True):
        _validate_annotation_case(query_case["query"], annotation)


def compare_independent_annotations(query_document: dict[str, Any], annotation_a: dict[str, Any], annotation_b: dict[str, Any]) -> dict[str, Any]:
    left_id, right_id = str(annotation_a.get("annotator_id") or ""), str(annotation_b.get("annotator_id") or "")
    if not left_id or not right_id or left_id == right_id:
        raise ValueError("two distinct annotator IDs are required")
    validate_annotation_document(query_document, annotation_a, left_id)
    validate_annotation_document(query_document, annotation_b, right_id)
    agreements: Counter[str] = Counter()
    disagreements = []
    for left, right in zip(annotation_a["cases"], annotation_b["cases"], strict=True):
        for field in AGREEMENT_FIELDS:
            if _value(left, field) == _value(right, field):
                agreements[field] += 1
            else:
                disagreements.append({"case_id": left["case_id"], "field": field})
    total = len(query_document["cases"])
    percentages = {field: round(agreements[field] * 100 / total, 1) for field in AGREEMENT_FIELDS}
    ready = all(percentages[field] >= 80 for field in ("expected_status", "primary_family", "expected_web_permission"))
    return {"annotators": [left_id, right_id], "case_count": total, "exact_agreement_pct": percentages, "disagreements": disagreements, "adjudication_ready": ready}


def validate_adjudication(query_document: dict[str, Any], annotation_a: dict[str, Any], annotation_b: dict[str, Any], final_gold: dict[str, Any]) -> None:
    comparison = compare_independent_annotations(query_document, annotation_a, annotation_b)
    if not comparison["adjudication_ready"]:
        raise ValueError("annotation agreement gate is below 80 percent")
    adjudicator_id = str(final_gold.get("annotator_id") or "")
    if adjudicator_id in comparison["annotators"]:
        raise ValueError("adjudicator must be independent from both annotators")
    validate_annotation_document(query_document, final_gold, adjudicator_id)
    notes = final_gold.get("adjudication_notes")
    if not isinstance(notes, list):
        raise ValueError("adjudication_notes must be a list")
    note_map = {}
    for note in notes:
        key = (note.get("case_id"), note.get("field"))
        if key in note_map or key[1] not in AGREEMENT_FIELDS or not str(note.get("rationale") or "").strip():
            raise ValueError("adjudication notes must be unique, valid, and include rationale")
        note_map[key] = note
    for left, right, final in zip(annotation_a["cases"], annotation_b["cases"], final_gold["cases"], strict=True):
        for field in AGREEMENT_FIELDS:
            left_value, right_value, final_value = (_value(row, field) for row in (left, right, final))
            key = (final["case_id"], field)
            if left_value == right_value:
                if final_value != left_value:
                    raise ValueError(f"adjudication cannot replace annotator consensus: {key}")
                if key in note_map:
                    raise ValueError(f"consensus field must not have a disagreement note: {key}")
            else:
                note = note_map.get(key)
                if note is None or note.get("selected") != final_value:
                    raise ValueError(f"missing or mismatched adjudication note: {key}")
    actual_disagreements = {(row["case_id"], row["field"]) for row in comparison["disagreements"]}
    if set(note_map) != actual_disagreements:
        raise ValueError("adjudication notes must cover exactly the annotation disagreements")


def validate_gold_coverage(query_document: dict[str, Any], final_gold: dict[str, Any], coverage_document: dict[str, Any]) -> None:
    validate_query_document(query_document)
    validate_annotation_document(query_document, final_gold, str(final_gold.get("annotator_id") or ""))
    family_counts = Counter(FAMILY_CODES[case["expected_deliveries"][0][0]] for case in final_gold["cases"])
    if family_counts != Counter({family: 4 for family in "ABCDE"}):
        raise ValueError("adjudicated Gold must contain exactly four primary cases for each A-E family")
    if sum(len(case["expected_deliveries"]) > 1 for case in final_gold["cases"]) < 6:
        raise ValueError("adjudicated Gold requires at least six compound deliveries")
    status_counts = Counter(case["expected_status"] for case in final_gold["cases"])
    if status_counts["clarification_required"] < 4 or status_counts["resolved"] < 4:
        raise ValueError("adjudicated Gold requires clarification and resolved controls")
    web_counts = Counter(case["expected_web_permission"] for case in final_gold["cases"])
    if web_counts["explicit"] < 4 or web_counts["forbidden"] < 4:
        raise ValueError("adjudicated Gold requires at least four explicit and four forbidden cases")
    valid_ids = {case["case_id"] for case in query_document["cases"]}
    gold_by_id = {case["case_id"]: case for case in final_gold["cases"]}
    pairs = coverage_document.get("contrast_pairs")
    if not isinstance(pairs, list):
        raise ValueError("sealed coverage requires contrast_pairs")
    kinds = set()
    used_pairs = set()
    for pair in pairs:
        kind, case_ids = pair.get("kind"), pair.get("case_ids")
        if kind not in REQUIRED_CONTRAST_KINDS or not isinstance(case_ids, list) or len(case_ids) != 2 or len(set(case_ids)) != 2 or not set(case_ids) <= valid_ids:
            raise ValueError("invalid sealed contrast pair")
        key = tuple(sorted(case_ids))
        if key in used_pairs:
            raise ValueError("duplicate sealed contrast pair")
        kinds.add(kind)
        used_pairs.add(key)
        if not _contrast_matches(kind, *(gold_by_id[case_id] for case_id in case_ids)):
            raise ValueError(f"sealed contrast pair does not match adjudicated Gold: {kind}")
    if not REQUIRED_CONTRAST_KINDS <= kinds:
        raise ValueError("sealed coverage lacks required contrast kinds")


def build_prediction_freeze_manifest(*, experiment_id: str, query_path: str | Path, runtime: dict[str, Any], runner_artifacts: list[str | Path], root: str | Path) -> dict[str, Any]:
    root_path = Path(root).resolve()
    query_file = _resolve_artifact(root_path, query_path)
    query = _read_json(query_file)
    validate_query_document(query)
    runner = [_resolve_artifact(root_path, path) for path in runner_artifacts]
    runner_names = {_relative(root_path, path) for path in runner}
    if not REQUIRED_RUNNER_ARTIFACTS <= runner_names:
        raise ValueError("prediction freeze lacks required Runner dependencies")
    if any("sealed" in {part.lower() for part in path.parts} for path in runner):
        raise ValueError("runner artifacts must not reference sealed storage")
    provider_schema = build_strict_tool_v3()["function"]["parameters"]
    return {
        "schema_version": "atr.prediction-freeze/1.0",
        "experiment_id": experiment_id,
        "evidence_boundary": "Query-only execution; Runner cannot read annotations, Gold, sealed coverage, or scores.",
        "case_order": [case["case_id"] for case in query["cases"]],
        "query_sha256": _canonical_sha256(query),
        "prompt_sha256": prompt_sha256_v3(),
        "provider_schema_sha256": _canonical_sha256(provider_schema),
        "runtime": runtime,
        "runner_artifacts": _records(root_path, runner),
        "runtime_budget": {"planned_cases": 20, "max_provider_calls": 20, "attempts_per_case": 1, "max_retries": 0},
        "stop_conditions": ["artifact_hash_drift", "provider_or_network_error", "more_than_one_attempt_for_any_case", "invalid_or_incomplete_prediction"],
    }


def build_freeze_manifest(*, experiment_id: str, query_path: str | Path, annotation_a_path: str | Path, annotation_b_path: str | Path, gold_path: str | Path, coverage_path: str | Path, prediction_freeze_path: str | Path, runtime: dict[str, Any], runner_artifacts: list[str | Path], scoring_artifacts: list[str | Path], root: str | Path) -> dict[str, Any]:
    root_path = Path(root).resolve()
    asset_paths = [Path(path).resolve() for path in (query_path, annotation_a_path, annotation_b_path, gold_path, coverage_path)]
    prediction_path = Path(prediction_freeze_path).resolve()
    if len(set([*asset_paths, prediction_path])) != len(asset_paths) + 1:
        raise ValueError("Query, annotations, Gold, coverage, and prediction freeze must use distinct paths")
    if "sealed" in {part.lower() for part in prediction_path.parts}:
        raise ValueError("prediction freeze must be outside sealed storage")
    query, left, right, gold, coverage = (_read_json(path) for path in asset_paths)
    validate_adjudication(query, left, right, gold)
    validate_gold_coverage(query, gold, coverage)
    runner = [_resolve_artifact(root_path, path) for path in runner_artifacts]
    scoring = [_resolve_artifact(root_path, path) for path in scoring_artifacts]
    runner_names = {_relative(root_path, path) for path in runner}
    scoring_names = {_relative(root_path, path) for path in scoring}
    if not REQUIRED_RUNNER_ARTIFACTS <= runner_names or not REQUIRED_SCORING_ARTIFACTS <= scoring_names:
        raise ValueError("freeze manifest lacks required Runner or Scorer dependencies")
    if any("sealed" in {part.lower() for part in path.parts} for path in runner):
        raise ValueError("runner artifacts must not reference sealed labels or Gold")
    if set(runner) & set(asset_paths[1:]):
        raise ValueError("runner artifacts must not include annotations, Gold, or sealed coverage")

    expected_prediction = build_prediction_freeze_manifest(
        experiment_id=experiment_id,
        query_path=asset_paths[0],
        runtime=runtime,
        runner_artifacts=runner,
        root=root_path,
    )
    if _read_json(prediction_path) != expected_prediction:
        raise ValueError("prediction freeze does not match Query, Runner, Prompt, Schema, or runtime")
    return {
        "schema_version": "atr.eval-freeze/1.3",
        "experiment_id": experiment_id,
        "evidence_boundary": "Unseen double-annotation blind for Ordered Query Frame v3.2; not retrieval, GraphRAG, answer-quality, production, or release evidence.",
        "case_order": [case["case_id"] for case in query["cases"]],
        "query_sha256": _canonical_sha256(query),
        "gold_sha256": _canonical_sha256(gold),
        "prompt_sha256": expected_prediction["prompt_sha256"],
        "provider_schema_sha256": expected_prediction["provider_schema_sha256"],
        "runtime": runtime,
        "prediction_freeze_manifest_sha256": _file_sha256(prediction_path),
        "annotation_artifacts": _records(root_path, asset_paths[1:]),
        "runner_artifacts": _records(root_path, runner),
        "scoring_artifacts": _records(root_path, scoring),
        "runtime_budget": {"planned_cases": 20, "max_provider_calls": 20, "attempts_per_case": 1, "max_retries": 0},
        "stop_conditions": ["artifact_hash_drift", "annotation_agreement_gate_failure", "runner_reads_sealed_labels", "provider_or_network_error", "more_than_one_attempt_for_any_case", "invalid_or_incomplete_prediction"],
    }


def _validate_annotation_case(query: str, annotation: dict[str, Any]) -> None:
    missing = [field for field in GOLD_FIELDS if field not in annotation]
    if missing:
        raise ValueError("annotation case lacks fields: " + ", ".join(missing))
    status, unresolved = annotation["expected_status"], annotation["expected_unresolved_reference_spans"]
    if status not in STATUSES or (status == "clarification_required") != bool(unresolved):
        raise ValueError("status and unresolved references must agree")
    if annotation["expected_web_permission"] not in WEB_PERMISSIONS:
        raise ValueError("invalid web permission")
    deliveries, evidence_groups = annotation["expected_deliveries"], annotation["expected_delivery_evidence_spans"]
    if not isinstance(deliveries, list) or not deliveries or not isinstance(evidence_groups, list) or len(evidence_groups) != len(deliveries):
        raise ValueError("deliveries and delivery evidence must be non-empty and aligned")
    for delivery, spans in zip(deliveries, evidence_groups, strict=True):
        if not isinstance(delivery, list) or len(delivery) != 3:
            raise ValueError("each delivery must be a triple")
        family, output, locator = delivery
        if family not in TASK_FAMILIES or output not in TASK_FAMILIES[family] or locator not in LOCATORS:
            raise ValueError("illegal delivery triple")
        if (family == "item_navigation" and locator == "none") or (family != "item_navigation" and locator != "none"):
            raise ValueError("illegal delivery locator")
        _validate_spans(query, spans, "delivery evidence")
    for field in ("expected_protected_terms", "expected_web_evidence_spans", "expected_unresolved_reference_spans"):
        _validate_spans(query, annotation[field], field)
    web_spans = annotation["expected_web_evidence_spans"]
    if annotation["expected_web_permission"] in {"explicit", "forbidden"} and not web_spans:
        raise ValueError("explicit or forbidden web permission requires source evidence")
    critical = annotation["expected_critical_terms"]
    if not isinstance(critical, dict) or set(critical) - CRITICAL_KINDS:
        raise ValueError("invalid critical term kinds")
    for kind, spans in critical.items():
        _validate_spans(query, spans, f"critical terms: {kind}")


def _validate_spans(query: str, spans: Any, label: str) -> None:
    if not isinstance(spans, list) or len(spans) != len(set(spans)) or any(not isinstance(span, str) or not span or span not in query for span in spans):
        raise ValueError(f"{label} must contain unique continuous Query substrings")


def _value(annotation: dict[str, Any], field: str) -> Any:
    return annotation["expected_deliveries"][0][0] if field == "primary_family" else annotation[field]


def _contrast_matches(kind: str, left: dict[str, Any], right: dict[str, Any]) -> bool:
    families = {left["expected_deliveries"][0][0], right["expected_deliveries"][0][0]}
    statuses = {left["expected_status"], right["expected_status"]}
    if kind == "b-c":
        return families == {"trend_discovery", "temporal_relation_exploration"}
    if kind == "d-e":
        return families == {"claim_verification", "evidence_research"}
    if kind == "a-e":
        return families == {"item_navigation", "evidence_research"}
    if kind == "timeline-longitudinal":
        temporal_outputs = [
            {
                delivery[1]
                for delivery in case["expected_deliveries"]
                if delivery[0] == "temporal_relation_exploration"
            }
            for case in (left, right)
        ]
        return {frozenset(outputs) for outputs in temporal_outputs} == {
            frozenset({"timeline"}),
            frozenset({"longitudinal_trend"}),
        }
    if kind == "resolved-clarification":
        return statuses == {"resolved", "clarification_required"}
    return False


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _resolve_artifact(root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    return resolved


def _relative(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError("freeze artifacts must be inside the project root") from exc


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _records(root: Path, items: list[Path]) -> list[dict[str, str]]:
    return [
        {"path": _relative(root, path), "sha256": _file_sha256(path)}
        for path in items
    ]
