"""Contracts for v3.2 double-annotation blind assets and freeze wiring."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy

import pytest

import rag.score_ordered_frame_v3_layered as layered_scorer
from rag.build_ordered_frame_v3_2_blind_assets import (
    REQUIRED_RUNNER_ARTIFACTS,
    REQUIRED_SCORING_ARTIFACTS,
    build_freeze_manifest,
    build_prediction_freeze_manifest,
    compare_independent_annotations,
    validate_adjudication,
    validate_annotation_document,
    validate_gold_coverage,
    validate_query_document,
)
from rag.ordered_semantic_frame_v3 import build_ordered_route_envelope_v3
from rag.run_ordered_frame_v3_calibration import (
    FreezeViolation,
    run_queries,
    verify_freeze_manifest,
    verify_frozen_queries,
)


FAMILY_DELIVERIES = (
    ["item_navigation", "item_disambiguation", "descriptive"],
    ["trend_discovery", "important_news", "none"],
    ["temporal_relation_exploration", "longitudinal_trend", "none"],
    ["claim_verification", "verification_verdict", "none"],
    ["evidence_research", "explanation", "none"],
)


def _query_document() -> dict:
    cases = []
    for index in range(20):
        permission = "请联网" if index < 4 else "不要联网" if index < 8 else "必要时联网"
        target = "这个对象" if 10 <= index < 14 else f"对象{index + 1}"
        cases.append({
            "case_id": f"v32-blind-{index + 1:02d}",
            "query": f"{permission}核对{target}在2026年8月的任务词{index + 1}，并解释原因。",
            "conversation_context": None,
        })
    return {"schema_version": "atr.blind-query/3.2", "dataset_id": "fixture", "cases": cases}


def _annotation(query_document: dict, annotator: str) -> dict:
    rows = []
    for index, query_case in enumerate(query_document["cases"]):
        query = query_case["query"]
        permission_text = "请联网" if index < 4 else "不要联网" if index < 8 else "必要时联网"
        deliveries = [deepcopy(FAMILY_DELIVERIES[index // 4])]
        if index == 9:
            deliveries[0] = ["temporal_relation_exploration", "timeline", "none"]
        evidence = [[f"任务词{index + 1}"]]
        if index < 6:
            deliveries.append(["evidence_research", "explanation", "none"])
            evidence.append(["解释原因"])
        unresolved = ["这个对象"] if 10 <= index < 14 else []
        rows.append({
            "case_id": query_case["case_id"],
            "expected_status": "clarification_required" if unresolved else "resolved",
            "expected_deliveries": deliveries,
            "expected_delivery_evidence_spans": evidence,
            "expected_protected_terms": ["2026年8月"],
            "expected_critical_terms": {"date": ["2026年8月"], "permission": [permission_text]},
            "expected_unresolved_reference_spans": unresolved,
            "expected_web_permission": "explicit" if index < 4 else "forbidden" if index < 8 else "on_demand",
            "expected_web_evidence_spans": [permission_text],
        })
        assert all(span in query for group in evidence for span in group)
    return {"schema_version": "atr.blind-gold/3.2", "annotator_id": annotator, "cases": rows}


def _coverage() -> dict:
    return {"contrast_pairs": [
        {"kind": "b-c", "case_ids": ["v32-blind-05", "v32-blind-09"]},
        {"kind": "d-e", "case_ids": ["v32-blind-13", "v32-blind-17"]},
        {"kind": "a-e", "case_ids": ["v32-blind-01", "v32-blind-18"]},
        {"kind": "timeline-longitudinal", "case_ids": ["v32-blind-09", "v32-blind-10"]},
        {"kind": "resolved-clarification", "case_ids": ["v32-blind-11", "v32-blind-15"]},
    ]}


def _gold(query_document: dict, left: dict, right: dict) -> dict:
    gold = deepcopy(left)
    gold["annotator_id"] = "adjudicator"
    gold["adjudication_notes"] = []
    return gold


def _write_freeze_inputs(tmp_path):
    queries = _query_document()
    left, right = _annotation(queries, "a"), _annotation(queries, "b")
    gold, coverage = _gold(queries, left, right), _coverage()
    values = {"queries.json": queries, "a.json": left, "b.json": right, "gold.json": gold, "coverage.json": coverage}
    paths = {}
    for name, value in values.items():
        path = tmp_path / name
        path.write_text(json.dumps(value, ensure_ascii=False))
        paths[name] = path
    for relative in REQUIRED_RUNNER_ARTIFACTS | REQUIRED_SCORING_ARTIFACTS:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative)
    return queries, gold, paths


def _runtime() -> dict:
    return {"model": "fixture", "base_url": "https://example.invalid", "temperature": 0, "max_tokens": 900, "timeout_seconds": 20, "thinking": "disabled", "max_retries": 0, "attempts_per_case": 1}


def _write_prediction_freeze(tmp_path, paths):
    manifest = build_prediction_freeze_manifest(
        experiment_id="v3.2-blind",
        query_path=paths["queries.json"],
        runtime=_runtime(),
        runner_artifacts=sorted(REQUIRED_RUNNER_ARTIFACTS),
        root=tmp_path,
    )
    path = tmp_path / "prediction-freeze.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False))
    return manifest, path


def test_public_query_rejects_labels_and_wrong_count() -> None:
    top_level = _query_document()
    top_level["gold_labels"] = []
    with pytest.raises(ValueError, match="must not contain"):
        validate_query_document(top_level)
    document = _query_document()
    document["cases"][0]["family"] = "A"
    with pytest.raises(ValueError, match="must not contain"):
        validate_query_document(document)
    document = _query_document()
    document["cases"].pop()
    with pytest.raises(ValueError, match="20"):
        validate_query_document(document)


def test_annotation_rejects_non_source_span_illegal_delivery_and_status_mismatch() -> None:
    queries = _query_document()
    annotation = _annotation(queries, "a")
    annotation["cases"][0]["expected_protected_terms"] = ["不存在"]
    with pytest.raises(ValueError, match="continuous Query substrings"):
        validate_annotation_document(queries, annotation, "a")
    annotation = _annotation(queries, "a")
    annotation["cases"][8]["expected_deliveries"] = [["trend_discovery", "comparison", "none"]]
    with pytest.raises(ValueError, match="illegal delivery"):
        validate_annotation_document(queries, annotation, "a")
    annotation = _annotation(queries, "a")
    annotation["cases"][10]["expected_status"] = "resolved"
    with pytest.raises(ValueError, match="status and unresolved"):
        validate_annotation_document(queries, annotation, "a")


def test_low_core_agreement_blocks_adjudication() -> None:
    queries = _query_document()
    left, right = _annotation(queries, "a"), _annotation(queries, "b")
    for case in right["cases"][:5]:
        case["expected_web_permission"] = "on_demand"
    assert compare_independent_annotations(queries, left, right)["adjudication_ready"] is False


def test_adjudication_requires_independent_identity_exact_notes_and_consensus() -> None:
    queries = _query_document()
    left, right = _annotation(queries, "a"), _annotation(queries, "b")
    final = _gold(queries, left, right)
    final["annotator_id"] = "a"
    with pytest.raises(ValueError, match="independent"):
        validate_adjudication(queries, left, right, final)
    final = _gold(queries, left, right)
    right["cases"][0]["expected_protected_terms"] = []
    with pytest.raises(ValueError, match="missing or mismatched"):
        validate_adjudication(queries, left, right, final)
    right = _annotation(queries, "b")
    final = _gold(queries, left, right)
    final["cases"][0]["expected_web_permission"] = "on_demand"
    with pytest.raises(ValueError, match="cannot replace annotator consensus"):
        validate_adjudication(queries, left, right, final)


def test_gold_coverage_is_derived_from_labels_not_public_metadata() -> None:
    queries = _query_document()
    left, right = _annotation(queries, "a"), _annotation(queries, "b")
    gold = _gold(queries, left, right)
    validate_gold_coverage(queries, gold, _coverage())
    gold["cases"][0]["expected_deliveries"][0] = deepcopy(FAMILY_DELIVERIES[1])
    with pytest.raises(ValueError, match="four primary"):
        validate_gold_coverage(queries, gold, _coverage())
    gold = _gold(queries, left, right)
    forged = _coverage()
    forged["contrast_pairs"][0]["case_ids"] = ["v32-blind-01", "v32-blind-02"]
    with pytest.raises(ValueError, match="does not match"):
        validate_gold_coverage(queries, gold, forged)
    gold = _gold(queries, left, right)
    gold["cases"][8]["expected_deliveries"].append(
        ["temporal_relation_exploration", "timeline", "none"]
    )
    gold["cases"][8]["expected_delivery_evidence_spans"].append(["任务词9"])
    gold["cases"][9]["expected_deliveries"][0] = [
        "temporal_relation_exploration", "relation", "none"
    ]
    with pytest.raises(ValueError, match="timeline-longitudinal"):
        validate_gold_coverage(queries, gold, _coverage())


def test_freeze_rejects_same_asset_path_and_sealed_runner(tmp_path) -> None:
    _, _, paths = _write_freeze_inputs(tmp_path)
    _, prediction_path = _write_prediction_freeze(tmp_path, paths)
    kwargs = dict(
        experiment_id="x", query_path=paths["queries.json"], annotation_a_path=paths["a.json"],
        annotation_b_path=paths["b.json"], gold_path=paths["gold.json"], coverage_path=paths["coverage.json"],
        prediction_freeze_path=prediction_path,
        runtime=_runtime(), runner_artifacts=sorted(REQUIRED_RUNNER_ARTIFACTS),
        scoring_artifacts=sorted(REQUIRED_SCORING_ARTIFACTS), root=tmp_path,
    )
    with pytest.raises(ValueError, match="distinct paths"):
        build_freeze_manifest(**{**kwargs, "gold_path": paths["a.json"]})
    sealed_runner = tmp_path / "sealed" / "runner.py"
    sealed_runner.parent.mkdir()
    sealed_runner.write_text("sealed")
    with pytest.raises(ValueError, match="sealed"):
        build_freeze_manifest(**{**kwargs, "runner_artifacts": sorted(REQUIRED_RUNNER_ARTIFACTS) + [sealed_runner]})


def test_public_prediction_freeze_excludes_gold_and_binds_sealed_evaluation(tmp_path) -> None:
    _, _, paths = _write_freeze_inputs(tmp_path)
    prediction_manifest = build_prediction_freeze_manifest(
        experiment_id="v3.2-blind",
        query_path=paths["queries.json"],
        runtime=_runtime(),
        runner_artifacts=sorted(REQUIRED_RUNNER_ARTIFACTS),
        root=tmp_path,
    )
    assert "gold_sha256" not in prediction_manifest
    assert "annotation_artifacts" not in prediction_manifest
    assert "scoring_artifacts" not in prediction_manifest

    prediction_path = tmp_path / "prediction-freeze.json"
    prediction_path.write_text(json.dumps(prediction_manifest, ensure_ascii=False))
    evaluation_manifest = build_freeze_manifest(
        experiment_id="v3.2-blind",
        query_path=paths["queries.json"],
        annotation_a_path=paths["a.json"],
        annotation_b_path=paths["b.json"],
        gold_path=paths["gold.json"],
        coverage_path=paths["coverage.json"],
        prediction_freeze_path=prediction_path,
        runtime=_runtime(),
        runner_artifacts=sorted(REQUIRED_RUNNER_ARTIFACTS),
        scoring_artifacts=sorted(REQUIRED_SCORING_ARTIFACTS),
        root=tmp_path,
    )
    assert evaluation_manifest["prediction_freeze_manifest_sha256"] == hashlib.sha256(
        prediction_path.read_bytes()
    ).hexdigest()


def test_builder_manifest_drives_runner_and_perfect_scorer(tmp_path, monkeypatch) -> None:
    queries, gold, paths = _write_freeze_inputs(tmp_path)
    prediction_manifest, prediction_path = _write_prediction_freeze(tmp_path, paths)
    manifest = build_freeze_manifest(
        experiment_id="v3.2-blind", query_path=paths["queries.json"], annotation_a_path=paths["a.json"],
        annotation_b_path=paths["b.json"], gold_path=paths["gold.json"], coverage_path=paths["coverage.json"],
        prediction_freeze_path=prediction_path,
        runtime=_runtime(), runner_artifacts=sorted(REQUIRED_RUNNER_ARTIFACTS),
        scoring_artifacts=sorted(REQUIRED_SCORING_ARTIFACTS), root=tmp_path,
    )
    manifest_path = tmp_path / "evaluation-freeze.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False))
    loaded = verify_freeze_manifest(prediction_path, root=tmp_path, verify_runtime=False)
    verify_frozen_queries(loaded, queries)
    freeze_hash = hashlib.sha256(prediction_path.read_bytes()).hexdigest()
    frames = {}
    for query_case, expected in zip(queries["cases"], gold["cases"], strict=True):
        frame = {
            "schema_version": "atr.ordered-semantic-frame/3.0",
            "deliveries": [
                {"task_family": delivery[0], "requested_output_form": delivery[1], "locator_kind": delivery[2], "evidence_spans": evidence}
                for delivery, evidence in zip(expected["expected_deliveries"], expected["expected_delivery_evidence_spans"], strict=True)
            ],
            "protected_spans": expected["expected_protected_terms"],
            "web_permission": expected["expected_web_permission"],
            "web_evidence_spans": expected["expected_web_evidence_spans"],
            "unresolved_reference_spans": expected["expected_unresolved_reference_spans"],
        }
        frames[query_case["query"]] = frame

    class PerfectExtractor:
        model = "fixture"

        def extract(self, query, conversation_context=None):
            return deepcopy(frames[query]), {"attempts": 1, "model": self.model}

    predictions = run_queries(
        queries,
        PerfectExtractor(),
        experiment_id=prediction_manifest["experiment_id"],
        evidence_boundary=prediction_manifest["evidence_boundary"],
    )
    predictions["freeze_manifest_sha256"] = freeze_hash
    monkeypatch.setattr(layered_scorer, "ROOT", tmp_path)
    evaluation_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    report = layered_scorer.score_layered(queries, gold, predictions, manifest, evaluation_hash)
    assert report["gate"]["passed"] is True
    assert report["metrics"]["critical_term_char_micro_recall"] == 100
    drifted_dependency = tmp_path / "rag/ordered_frame_client_v3.py"
    drifted_dependency.write_text("drift")
    with pytest.raises(FreezeViolation, match="artifact hash drift"):
        verify_freeze_manifest(prediction_path, root=tmp_path, verify_runtime=False)
