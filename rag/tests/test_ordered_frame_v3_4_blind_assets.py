"""TDD contract tests for the v3.4 double-annotation Blind assets."""

from __future__ import annotations

from copy import deepcopy
import json

import pytest

from rag.build_ordered_frame_v3_4_blind_assets import (
    REQUIRED_RUNNER_ARTIFACTS,
    REQUIRED_SCORING_ARTIFACTS,
    build_evaluation_freeze_manifest,
    build_prediction_freeze_manifest,
    build_coverage_document,
    compare_independent_annotations,
    validate_adjudication,
    validate_annotation_document,
    validate_gold_coverage,
    validate_query_document,
)


FAMILIES = [
    ("item_navigation", "exact_item", "atr_id"),
    ("trend_discovery", "important_news", "none"),
    ("temporal_relation_exploration", "timeline", "none"),
    ("claim_verification", "verification_verdict", "none"),
    ("evidence_research", "explanation", "none"),
]


def _queries() -> dict:
    return {
        "schema_version": "atr.blind-query/3.4",
        "dataset_id": "fixture",
        "evidence_boundary": "Query only",
        "cases": [
            {
                "case_id": f"case-{index + 1:02d}",
                "query": f"请处理术语{index + 1}。",
                "conversation_context": None,
            }
            for index in range(15)
        ],
    }


def _annotation(queries: dict, annotator_id: str) -> dict:
    cases = []
    for index, query_case in enumerate(queries["cases"]):
        family, output, locator = FAMILIES[index // 3]
        cases.append(
            {
                "case_id": query_case["case_id"],
                "expected_status": "resolved",
                "expected_deliveries": [[family, output, locator]],
                "expected_web_permission": "on_demand",
                "expected_unresolved_reference_spans": [],
                "expected_contract_literals": [
                    {"path": "protected_terms", "literal": f"术语{index + 1}", "match": "exact"}
                ],
            }
        )
    return {"annotator_id": annotator_id, "cases": cases}


def _gold(queries: dict, left: dict) -> dict:
    gold = deepcopy(left)
    gold["annotator_id"] = "independent-adjudicator"
    gold["adjudication_notes"] = []
    return gold


def test_query_document_requires_exactly_fifteen_query_only_cases() -> None:
    queries = _queries()
    validate_query_document(queries)
    queries["cases"][0]["expected_status"] = "resolved"
    with pytest.raises(ValueError, match="must not contain"):
        validate_query_document(queries)
    queries = _queries()
    queries["cases"].pop()
    with pytest.raises(ValueError, match="15"):
        validate_query_document(queries)


def test_annotation_rejects_noncanonical_delivery_and_clarification_literals() -> None:
    queries = _queries()
    annotation = _annotation(queries, "a")
    annotation["cases"][0]["expected_deliveries"] = [["A", "record", "ATR-123"]]
    with pytest.raises(ValueError, match="illegal delivery"):
        validate_annotation_document(queries, annotation, "a")

    annotation = _annotation(queries, "a")
    annotation["cases"][0].update(
        expected_status="clarification_required",
        expected_unresolved_reference_spans=["术语1"],
    )
    with pytest.raises(ValueError, match="null Contract"):
        validate_annotation_document(queries, annotation, "a")


def test_annotation_requires_literals_to_come_from_query_or_context() -> None:
    queries = _queries()
    queries["cases"][0]["conversation_context"] = "上一轮提到上下文术语。"
    annotation = _annotation(queries, "a")
    annotation["cases"][0]["expected_contract_literals"] = [
        {"path": "claims", "literal": "上下文术语", "match": "exact"}
    ]
    validate_annotation_document(queries, annotation, "a")
    annotation["cases"][0]["expected_contract_literals"][0]["literal"] = "不存在"
    with pytest.raises(ValueError, match="Query or context"):
        validate_annotation_document(queries, annotation, "a")


def test_comparison_and_adjudication_cover_every_disagreement_exactly() -> None:
    queries = _queries()
    left, right = _annotation(queries, "a"), _annotation(queries, "b")
    right["cases"][0]["expected_web_permission"] = "explicit"
    comparison = compare_independent_annotations(queries, left, right)
    assert comparison["adjudication_ready"] is True
    assert comparison["disagreements"] == [
        {"case_id": "case-01", "field": "expected_web_permission"}
    ]

    final = _gold(queries, left)
    with pytest.raises(ValueError, match="missing or mismatched"):
        validate_adjudication(queries, left, right, final)
    final["adjudication_notes"] = [
        {
            "case_id": "case-01",
            "field": "expected_web_permission",
            "selected": "on_demand",
            "rationale": "Query does not explicitly request web access.",
        }
    ]
    validate_adjudication(queries, left, right, final)


def test_coverage_is_derived_from_gold_and_enforces_v34_shape() -> None:
    queries = _queries()
    left = _annotation(queries, "a")
    # Four compounds, four locator kinds, three clarification controls,
    # and sufficient explicit/forbidden permissions.
    left["cases"][0]["expected_deliveries"].append(
        ["evidence_research", "explanation", "none"]
    )
    left["cases"][1]["expected_deliveries"][0][2] = "full_title"
    left["cases"][2]["expected_deliveries"][0] = [
        "item_navigation", "item_disambiguation", "descriptive"
    ]
    for index in (2, 5, 10):
        left["cases"][index].update(
            expected_status="clarification_required",
            expected_unresolved_reference_spans=[f"术语{index + 1}"],
            expected_contract_literals=[],
        )
    left["cases"][5]["expected_deliveries"].append(
        ["item_navigation", "item_disambiguation", "title_fragment"]
    )
    left["cases"][8]["expected_deliveries"].append(
        ["evidence_research", "explanation", "none"]
    )
    left["cases"][11]["expected_deliveries"].append(
        ["evidence_research", "explanation", "none"]
    )
    for index in (3, 6, 9, 12):
        left["cases"][index]["expected_web_permission"] = "explicit"
    for index in (1, 4, 7, 13):
        left["cases"][index]["expected_web_permission"] = "forbidden"

    coverage = build_coverage_document(left)
    validate_gold_coverage(queries, left, coverage)
    assert coverage["primary_family_counts"] == {family: 3 for family, *_ in FAMILIES}
    assert set(coverage["locator_kinds"]) == {
        "atr_id", "full_title", "title_fragment", "descriptive"
    }

    drifted = deepcopy(coverage)
    drifted["clarification_count"] = 2
    with pytest.raises(ValueError, match="does not match Gold"):
        validate_gold_coverage(queries, left, drifted)


def test_public_prediction_freeze_binds_query_runner_and_fifteen_call_budget(tmp_path) -> None:
    query_path = tmp_path / "queries.json"
    query_path.write_text(json.dumps(_queries(), ensure_ascii=False))
    for relative in REQUIRED_RUNNER_ARTIFACTS:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative)
    runtime = {
        "model": "fixture",
        "base_url": "https://example.invalid",
        "temperature": 0,
        "max_tokens": 900,
        "timeout_seconds": 20,
        "thinking": "disabled",
        "max_retries": 0,
        "attempts_per_case": 1,
    }
    manifest = build_prediction_freeze_manifest(
        experiment_id="v3.4-blind",
        query_path=query_path,
        runtime=runtime,
        runner_artifacts=sorted(REQUIRED_RUNNER_ARTIFACTS),
        root=tmp_path,
    )
    assert manifest["runtime_budget"] == {
        "planned_cases": 15,
        "max_provider_calls": 15,
        "attempts_per_case": 1,
        "max_retries": 0,
    }
    assert "gold_sha256" not in manifest
    assert "annotation_artifacts" not in manifest
    assert all("sealed" not in row["path"] for row in manifest["runner_artifacts"])


def test_prediction_freeze_rejects_query_file_inside_sealed_storage(tmp_path) -> None:
    sealed = tmp_path / "sealed"
    sealed.mkdir()
    query_path = sealed / "queries.json"
    query_path.write_text(json.dumps(_queries(), ensure_ascii=False))
    for relative in REQUIRED_RUNNER_ARTIFACTS:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative)
    with pytest.raises(ValueError, match="public and outside sealed"):
        build_prediction_freeze_manifest(
            experiment_id="v3.4-blind",
            query_path=query_path,
            runtime={},
            runner_artifacts=sorted(REQUIRED_RUNNER_ARTIFACTS),
            root=tmp_path,
        )


def test_evaluation_freeze_binds_double_annotations_gold_coverage_and_public_freeze(tmp_path) -> None:
    queries = _queries()
    left = _annotation(queries, "a")
    left["cases"][0]["expected_deliveries"].append(
        ["evidence_research", "explanation", "none"]
    )
    left["cases"][1]["expected_deliveries"][0][2] = "full_title"
    left["cases"][2]["expected_deliveries"][0] = [
        "item_navigation", "item_disambiguation", "descriptive"
    ]
    for index in (2, 5, 10):
        left["cases"][index].update(
            expected_status="clarification_required",
            expected_unresolved_reference_spans=[f"术语{index + 1}"],
            expected_contract_literals=[],
        )
    left["cases"][5]["expected_deliveries"].append(
        ["item_navigation", "item_disambiguation", "title_fragment"]
    )
    left["cases"][8]["expected_deliveries"].append(
        ["evidence_research", "explanation", "none"]
    )
    left["cases"][11]["expected_deliveries"].append(
        ["evidence_research", "explanation", "none"]
    )
    for index in (3, 6, 9, 12):
        left["cases"][index]["expected_web_permission"] = "explicit"
    for index in (1, 4, 7, 13):
        left["cases"][index]["expected_web_permission"] = "forbidden"
    right = deepcopy(left)
    right["annotator_id"] = "b"
    gold = _gold(queries, left)
    coverage = build_coverage_document(gold)

    values = {
        "queries.json": queries,
        "sealed/a.json": left,
        "sealed/b.json": right,
        "sealed/gold.json": gold,
        "sealed/coverage.json": coverage,
    }
    paths = {}
    for name, value in values.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False))
        paths[name] = path
    for relative in REQUIRED_RUNNER_ARTIFACTS | REQUIRED_SCORING_ARTIFACTS:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative)
    runtime = {
        "model": "fixture", "base_url": "https://example.invalid",
        "temperature": 0, "max_tokens": 900, "timeout_seconds": 20,
        "thinking": "disabled", "max_retries": 0, "attempts_per_case": 1,
    }
    prediction = build_prediction_freeze_manifest(
        experiment_id="v3.4-blind", query_path=paths["queries.json"],
        runtime=runtime, runner_artifacts=sorted(REQUIRED_RUNNER_ARTIFACTS), root=tmp_path,
    )
    prediction_path = tmp_path / "prediction-freeze.json"
    prediction_path.write_text(json.dumps(prediction, ensure_ascii=False))
    manifest = build_evaluation_freeze_manifest(
        experiment_id="v3.4-blind",
        query_path=paths["queries.json"],
        annotation_a_path=paths["sealed/a.json"],
        annotation_b_path=paths["sealed/b.json"],
        gold_path=paths["sealed/gold.json"],
        coverage_path=paths["sealed/coverage.json"],
        prediction_freeze_path=prediction_path,
        runtime=runtime,
        runner_artifacts=sorted(REQUIRED_RUNNER_ARTIFACTS),
        scoring_artifacts=sorted(REQUIRED_SCORING_ARTIFACTS),
        root=tmp_path,
    )
    assert manifest["runtime_budget"]["max_provider_calls"] == 15
    assert len(manifest["annotation_artifacts"]) == 4
    assert manifest["prediction_freeze_manifest_sha256"]
