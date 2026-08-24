"""Validation and freezing primitives for the v3.4 contract-completeness Blind.

The public Query shard is intentionally label-free.  Annotation, adjudication,
and coverage remain sealed and are validated before any provider execution.
"""

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
    "temporal_relation_exploration": {
        "timeline", "relation", "longitudinal_trend", "cross_sectional_trend"
    },
    "claim_verification": {"verification_verdict"},
    "evidence_research": {"explanation", "comparison", "deep_research"},
}
LOCATORS = {"atr_id", "full_title", "title_fragment", "descriptive", "none"}
WEB_PERMISSIONS = {"forbidden", "on_demand", "explicit"}
STATUSES = {"resolved", "clarification_required"}
LITERAL_PATHS = {
    "protected_terms", "claims", "temporal_constraint.value",
    "source_constraint.requested_sources",
}
PUBLIC_CASE_KEYS = {"case_id", "query", "conversation_context"}
PUBLIC_DOCUMENT_KEYS = {
    "schema_version", "dataset_id", "evidence_boundary", "cases"
}
ANNOTATION_FIELDS = (
    "expected_status", "expected_deliveries", "expected_web_permission",
    "expected_unresolved_reference_spans", "expected_contract_literals",
)
AGREEMENT_FIELDS = ANNOTATION_FIELDS + ("primary_family",)
REQUIRED_RUNNER_ARTIFACTS = {
    "docs/rag-transformation/specs/ordered-semantic-frame-v3.schema.json",
    "docs/rag-transformation/specs/route-contract-v2.schema.json",
    "rag/config.py",
    "rag/ordered_frame_client_v3.py",
    "rag/ordered_semantic_frame_v3.py",
    "rag/query_understanding_v2.py",
    "rag/route_contract_validation.py",
    "rag/run_ordered_frame_v3_calibration.py",
}
REQUIRED_SCORING_ARTIFACTS = {
    "docs/rag-transformation/specs/route-contract-v2.schema.json",
    "rag/build_ordered_frame_v3_4_blind_assets.py",
    "rag/score_ordered_frame_v3_3_visible.py",
    "rag/score_ordered_frame_v3_4_blind.py",
}


def validate_query_document(document: dict[str, Any]) -> None:
    if set(document) - PUBLIC_DOCUMENT_KEYS:
        raise ValueError("public Query document must not contain coverage or Gold labels")
    if not str(document.get("dataset_id") or "").strip():
        raise ValueError("public Query document requires dataset_id")
    cases = document.get("cases")
    if not isinstance(cases, list) or len(cases) != 15:
        raise ValueError("v3.4 Blind Query document must contain exactly 15 cases")
    ids: list[str] = []
    queries: list[str] = []
    for case in cases:
        if not isinstance(case, dict) or set(case) - PUBLIC_CASE_KEYS:
            raise ValueError("public Query cases must not contain coverage or Gold labels")
        case_id, query = case.get("case_id"), case.get("query")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("case IDs must be non-empty strings")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("queries must be non-empty strings")
        if case.get("conversation_context") is not None and not isinstance(
            case.get("conversation_context"), str
        ):
            raise ValueError("conversation_context must be a string or null")
        ids.append(case_id)
        queries.append(query)
    if len(set(ids)) != 15 or len(set(queries)) != 15:
        raise ValueError("case IDs and queries must be unique")


def validate_annotation_document(
    query_document: dict[str, Any],
    annotation_document: dict[str, Any],
    annotator_id: str,
) -> None:
    validate_query_document(query_document)
    if not annotator_id.strip() or annotation_document.get("annotator_id") != annotator_id:
        raise ValueError("annotation document must declare the expected annotator_id")
    annotations = annotation_document.get("cases")
    query_cases = query_document["cases"]
    if not isinstance(annotations, list) or [row.get("case_id") for row in annotations] != [
        row["case_id"] for row in query_cases
    ]:
        raise ValueError("annotation cases must match Query case order")
    for query_case, annotation in zip(query_cases, annotations, strict=True):
        _validate_annotation_case(query_case, annotation)


def compare_independent_annotations(
    query_document: dict[str, Any],
    annotation_a: dict[str, Any],
    annotation_b: dict[str, Any],
) -> dict[str, Any]:
    left_id = str(annotation_a.get("annotator_id") or "")
    right_id = str(annotation_b.get("annotator_id") or "")
    if not left_id or not right_id or left_id == right_id:
        raise ValueError("two distinct annotator IDs are required")
    validate_annotation_document(query_document, annotation_a, left_id)
    validate_annotation_document(query_document, annotation_b, right_id)
    agreements: Counter[str] = Counter()
    disagreements: list[dict[str, str]] = []
    for left, right in zip(annotation_a["cases"], annotation_b["cases"], strict=True):
        for field in AGREEMENT_FIELDS:
            if _value(left, field) == _value(right, field):
                agreements[field] += 1
            else:
                disagreements.append({"case_id": left["case_id"], "field": field})
    total = len(query_document["cases"])
    percentages = {
        field: round(agreements[field] * 100 / total, 1) for field in AGREEMENT_FIELDS
    }
    ready = all(
        percentages[field] >= 80
        for field in ("expected_status", "primary_family", "expected_web_permission")
    )
    return {
        "annotators": [left_id, right_id],
        "case_count": total,
        "exact_agreement_pct": percentages,
        "disagreements": disagreements,
        "adjudication_ready": ready,
    }


def validate_adjudication(
    query_document: dict[str, Any],
    annotation_a: dict[str, Any],
    annotation_b: dict[str, Any],
    final_gold: dict[str, Any],
) -> None:
    comparison = compare_independent_annotations(
        query_document, annotation_a, annotation_b
    )
    if not comparison["adjudication_ready"]:
        raise ValueError("annotation agreement gate is below 80 percent")
    adjudicator_id = str(final_gold.get("annotator_id") or "")
    if adjudicator_id in comparison["annotators"]:
        raise ValueError("adjudicator must be independent from both annotators")
    validate_annotation_document(query_document, final_gold, adjudicator_id)
    notes = final_gold.get("adjudication_notes")
    if not isinstance(notes, list):
        raise ValueError("adjudication_notes must be a list")
    note_map: dict[tuple[str, str], dict[str, Any]] = {}
    for note in notes:
        key = (note.get("case_id"), note.get("field"))
        if (
            key in note_map
            or key[1] not in AGREEMENT_FIELDS
            or not str(note.get("rationale") or "").strip()
        ):
            raise ValueError("adjudication notes must be unique, valid, and reasoned")
        note_map[key] = note
    for left, right, final in zip(
        annotation_a["cases"], annotation_b["cases"], final_gold["cases"], strict=True
    ):
        for field in AGREEMENT_FIELDS:
            left_value, right_value, final_value = (
                _value(row, field) for row in (left, right, final)
            )
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
    expected_notes = {
        (row["case_id"], row["field"]) for row in comparison["disagreements"]
    }
    if set(note_map) != expected_notes:
        raise ValueError("adjudication notes must cover exactly all disagreements")


def build_coverage_document(gold: dict[str, Any]) -> dict[str, Any]:
    cases = gold.get("cases") or []
    family_counts = Counter(case["expected_deliveries"][0][0] for case in cases)
    locator_kinds = sorted(
        {
            delivery[2]
            for case in cases
            for delivery in case["expected_deliveries"]
            if delivery[0] == "item_navigation"
        }
    )
    web_counts = Counter(case["expected_web_permission"] for case in cases)
    return {
        "schema_version": "atr.blind-coverage/3.4",
        "primary_family_counts": dict(sorted(family_counts.items())),
        "compound_delivery_count": sum(
            len(case["expected_deliveries"]) > 1 for case in cases
        ),
        "clarification_count": sum(
            case["expected_status"] == "clarification_required" for case in cases
        ),
        "web_permission_counts": dict(sorted(web_counts.items())),
        "locator_kinds": locator_kinds,
    }


def validate_gold_coverage(
    query_document: dict[str, Any],
    final_gold: dict[str, Any],
    coverage_document: dict[str, Any],
) -> None:
    validate_annotation_document(
        query_document, final_gold, str(final_gold.get("annotator_id") or "")
    )
    if coverage_document != build_coverage_document(final_gold):
        raise ValueError("sealed coverage does not match Gold")
    expected_families = {family: 3 for family in TASK_FAMILIES}
    if coverage_document["primary_family_counts"] != expected_families:
        raise ValueError("Gold must contain exactly three primary cases per A-E family")
    if coverage_document["compound_delivery_count"] < 4:
        raise ValueError("Gold requires at least four compound deliveries")
    if coverage_document["clarification_count"] < 3:
        raise ValueError("Gold requires at least three clarification controls")
    web = coverage_document["web_permission_counts"]
    if web.get("explicit", 0) < 4 or web.get("forbidden", 0) < 3:
        raise ValueError("Gold lacks explicit and forbidden web controls")
    if not {"atr_id", "full_title", "title_fragment", "descriptive"} <= set(
        coverage_document["locator_kinds"]
    ):
        raise ValueError("Gold lacks all four item locator kinds")


def build_prediction_freeze_manifest(
    *,
    experiment_id: str,
    query_path: str | Path,
    runtime: dict[str, Any],
    runner_artifacts: list[str | Path],
    root: str | Path,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    query_file = _resolve_artifact(root_path, query_path)
    if "sealed" in {part.lower() for part in query_file.parts}:
        raise ValueError("prediction Query file must be public and outside sealed storage")
    query_document = json.loads(query_file.read_text())
    validate_query_document(query_document)
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
        "evidence_boundary": (
            "Query-only execution; Runner cannot read annotations, Gold, sealed "
            "coverage, or scores."
        ),
        "case_order": [case["case_id"] for case in query_document["cases"]],
        "query_sha256": _canonical_sha256(query_document),
        "prompt_sha256": prompt_sha256_v3(),
        "provider_schema_sha256": _canonical_sha256(provider_schema),
        "runtime": runtime,
        "runner_artifacts": _records(root_path, runner),
        "runtime_budget": {
            "planned_cases": 15,
            "max_provider_calls": 15,
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


def build_evaluation_freeze_manifest(
    *,
    experiment_id: str,
    query_path: str | Path,
    annotation_a_path: str | Path,
    annotation_b_path: str | Path,
    gold_path: str | Path,
    coverage_path: str | Path,
    prediction_freeze_path: str | Path,
    runtime: dict[str, Any],
    runner_artifacts: list[str | Path],
    scoring_artifacts: list[str | Path],
    root: str | Path,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    asset_paths = [
        _resolve_artifact(root_path, path)
        for path in (
            query_path, annotation_a_path, annotation_b_path, gold_path, coverage_path
        )
    ]
    if len(set(asset_paths)) != len(asset_paths):
        raise ValueError("Query, annotations, Gold, and coverage require distinct paths")
    prediction_path = _resolve_artifact(root_path, prediction_freeze_path)
    if "sealed" in {part.lower() for part in prediction_path.parts}:
        raise ValueError("prediction freeze must remain outside sealed storage")
    query, left, right, gold, coverage = (
        json.loads(path.read_text()) for path in asset_paths
    )
    validate_adjudication(query, left, right, gold)
    validate_gold_coverage(query, gold, coverage)
    runner = [_resolve_artifact(root_path, path) for path in runner_artifacts]
    scoring = [_resolve_artifact(root_path, path) for path in scoring_artifacts]
    if not REQUIRED_RUNNER_ARTIFACTS <= {_relative(root_path, path) for path in runner}:
        raise ValueError("evaluation freeze lacks required Runner dependencies")
    if not REQUIRED_SCORING_ARTIFACTS <= {_relative(root_path, path) for path in scoring}:
        raise ValueError("evaluation freeze lacks required Scorer dependencies")
    if any("sealed" in {part.lower() for part in path.parts} for path in runner):
        raise ValueError("runner artifacts must not reference sealed labels")
    expected_prediction = build_prediction_freeze_manifest(
        experiment_id=experiment_id,
        query_path=asset_paths[0],
        runtime=runtime,
        runner_artifacts=runner,
        root=root_path,
    )
    if json.loads(prediction_path.read_text()) != expected_prediction:
        raise ValueError("prediction freeze does not match Query, Runner, Prompt, or runtime")
    return {
        "schema_version": "atr.eval-freeze/1.4",
        "experiment_id": experiment_id,
        "evidence_boundary": (
            "Unseen double-annotation Blind for Ordered Query Frame v3.4; not "
            "retrieval, GraphRAG, answer-quality, production, or release evidence."
        ),
        "case_order": [case["case_id"] for case in query["cases"]],
        "query_sha256": _canonical_sha256(query),
        "gold_sha256": _canonical_sha256(gold),
        "prompt_sha256": expected_prediction["prompt_sha256"],
        "provider_schema_sha256": expected_prediction["provider_schema_sha256"],
        "runtime": runtime,
        "prediction_freeze_manifest_sha256": hashlib.sha256(
            prediction_path.read_bytes()
        ).hexdigest(),
        "annotation_artifacts": _records(root_path, asset_paths[1:]),
        "runner_artifacts": _records(root_path, runner),
        "scoring_artifacts": _records(root_path, scoring),
        "runtime_budget": expected_prediction["runtime_budget"],
        "stop_conditions": [
            "artifact_hash_drift",
            "annotation_agreement_gate_failure",
            "runner_reads_sealed_labels",
            "provider_or_network_error",
            "more_than_one_attempt_for_any_case",
            "invalid_or_incomplete_prediction",
        ],
    }


def _validate_annotation_case(query_case: dict[str, Any], annotation: dict[str, Any]) -> None:
    missing = [field for field in ANNOTATION_FIELDS if field not in annotation]
    if missing:
        raise ValueError("annotation case lacks fields: " + ", ".join(missing))
    status = annotation["expected_status"]
    unresolved = annotation["expected_unresolved_reference_spans"]
    if status not in STATUSES or (status == "clarification_required") != bool(unresolved):
        raise ValueError("status and unresolved references must agree")
    if annotation["expected_web_permission"] not in WEB_PERMISSIONS:
        raise ValueError("invalid web permission")
    deliveries = annotation["expected_deliveries"]
    if not isinstance(deliveries, list) or not deliveries:
        raise ValueError("expected_deliveries must be non-empty")
    for delivery in deliveries:
        if not isinstance(delivery, list) or len(delivery) != 3:
            raise ValueError("each delivery must be a triple")
        family, output, locator = delivery
        if family not in TASK_FAMILIES or output not in TASK_FAMILIES[family] or locator not in LOCATORS:
            raise ValueError("illegal delivery triple")
        if (family == "item_navigation") != (locator != "none"):
            raise ValueError("illegal delivery locator")
    source_text = query_case["query"] + "\n" + (query_case.get("conversation_context") or "")
    _validate_source_spans(source_text, unresolved, "unresolved references")
    literals = annotation["expected_contract_literals"]
    if status == "clarification_required" and literals:
        raise ValueError("clarification with a null Contract cannot require contract literals")
    if not isinstance(literals, list):
        raise ValueError("expected_contract_literals must be a list")
    for expectation in literals:
        if set(expectation) != {"path", "literal", "match"}:
            raise ValueError("contract literal requires path, literal, and match")
        if expectation["path"] not in LITERAL_PATHS or expectation["match"] not in {"exact", "substring"}:
            raise ValueError("invalid contract literal expectation")
        literal = expectation["literal"]
        if not isinstance(literal, str) or not literal or literal not in source_text:
            raise ValueError("contract literals must originate in Query or context")


def _validate_source_spans(source_text: str, spans: Any, label: str) -> None:
    if (
        not isinstance(spans, list)
        or len(spans) != len(set(spans))
        or any(not isinstance(span, str) or not span or span not in source_text for span in spans)
    ):
        raise ValueError(f"{label} must be unique source substrings")


def _value(annotation: dict[str, Any], field: str) -> Any:
    if field == "primary_family":
        return annotation["expected_deliveries"][0][0]
    return annotation[field]


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


def _records(root: Path, items: list[Path]) -> list[dict[str, str]]:
    return [
        {
            "path": _relative(root, path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in items
    ]
