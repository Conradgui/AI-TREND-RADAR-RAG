"""Offline tests for the fixed three-case live canary evaluator."""

from __future__ import annotations

import json
from pathlib import Path

from rag.eval_narrow_query_understanding_v1_live import CASE_IDS, run


ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "docs/rag-transformation/evals/narrow-semantic-decisions-v1-calibration-2026-08-13.json"


class FixtureExtractor:
    model = "fixture"

    def __init__(self):
        cases = json.loads(DATASET.read_text())["cases"]
        self.cases = {case["query"]: case for case in cases}

    def extract(self, query: str, conversation_context: str | None = None):
        case = self.cases[query]
        dimensions = {}
        for name in (
            "item_lookup",
            "recent_update_set",
            "cross_time_or_entity_structure",
            "truth_assessable_claim",
            "explanation_or_comparison",
        ):
            if name in case["present"]:
                state, spans = "present", case["present"][name]
            elif name in case["uncertain"]:
                state, spans = "uncertain", case["uncertain"][name]
            else:
                state, spans = "absent", []
            dimensions[name] = {"state": state, "evidence_spans": spans}
        value = {
            "schema_version": "atr.semantic-decisions/1.0",
            "dimensions": dimensions,
            "protected_spans": case.get("protected_spans", []),
            "item_locator_precision": case.get("item_locator_precision", "none"),
            "unresolved_reference_spans": case["unresolved_reference_spans"],
            "resolved_references": case.get("resolved_references", []),
        }
        return value, {"model": self.model, "attempts": 1}


def test_fixed_canary_scores_full_public_seam_not_raw_model_json() -> None:
    report = run(DATASET, FixtureExtractor())

    assert CASE_IDS == ("NSD-003", "NSD-007", "NSD-009")
    assert report["total"] == 3
    assert "three-case-canary" in report["experiment_id"]
    assert report["complete_projection_correct"] == 3
    assert report["gate"]["passed"] is True
    assert all(row["envelope"]["status"] == row["expected_status"] for row in report["cases"])


def test_visible_calibration_mode_scores_all_twelve_cases() -> None:
    report = run(DATASET, FixtureExtractor(), case_ids=None)

    assert report["total"] == 12
    assert "visible-calibration" in report["experiment_id"]
    assert report["complete_projection_correct"] == 12
    assert report["gate"]["passed"] is True


def test_targeted_mode_scores_only_the_requested_case() -> None:
    report = run(DATASET, FixtureExtractor(), case_ids=("NSD-007",))

    assert report["total"] == 1
    assert [row["case_id"] for row in report["cases"]] == ["NSD-007"]
    assert report["gate"]["passed"] is True


def test_report_is_json_serializable_when_extractor_wraps_a_model_adapter() -> None:
    extractor = FixtureExtractor()
    extractor.model = type("ModelAdapter", (), {"model": "deepseek-v4-flash"})()

    report = run(DATASET, extractor)

    assert report["model"] == "deepseek-v4-flash"
    json.dumps(report, ensure_ascii=False)


def test_complete_projection_gate_includes_protected_terms_and_references() -> None:
    extractor = FixtureExtractor()
    original_extract = extractor.extract

    def degraded_extract(query: str, conversation_context: str | None = None):
        value, diagnostics = original_extract(query, conversation_context)
        if "模型水印" in query:
            value["protected_spans"] = []
        return value, diagnostics

    extractor.extract = degraded_extract

    report = run(DATASET, extractor)
    row = next(row for row in report["cases"] if row["case_id"] == "NSD-003")

    assert row["checks"]["route"] is True
    assert row["checks"]["protected_terms"] is False
    assert report["complete_projection_correct"] == 2
    assert report["gate"]["passed"] is False
