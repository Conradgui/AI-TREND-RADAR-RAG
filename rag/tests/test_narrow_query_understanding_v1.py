"""Public-seam tests for real Query -> narrow L1 -> Route Contract v2."""

from __future__ import annotations

import json
from pathlib import Path

from rag.narrow_query_understanding_v1 import understand_narrow_query_v1


ROOT = Path(__file__).resolve().parents[2]
CASES = {
    case["case_id"]: case
    for case in json.loads(
        (ROOT / "docs/rag-transformation/evals/narrow-semantic-decisions-v1-calibration-2026-08-13.json").read_text()
    )["cases"]
}


class SequenceExtractor:
    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def extract(self, query: str, conversation_context: str | None = None):
        outcome = self.outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _l1(case_id: str) -> dict:
    case = CASES[case_id]
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
    return {
        "schema_version": "atr.semantic-decisions/1.0",
        "dimensions": dimensions,
        "protected_spans": case.get("protected_spans", []),
        "item_locator_precision": case.get("item_locator_precision", "none"),
        "unresolved_reference_spans": case["unresolved_reference_spans"],
        "resolved_references": case.get("resolved_references", []),
    }


def test_real_query_reaches_complete_contract_through_one_public_seam() -> None:
    case = CASES["NSD-003"]
    extractor = SequenceExtractor((_l1("NSD-003"), {"attempt": 1}))

    result = understand_narrow_query_v1(case["query"], extractor)

    assert result["status"] == "resolved"
    assert result["contract"]["original_query"] == case["query"]
    assert result["contract"]["primary_task_family"] == "trend_discovery"
    assert result["contract"]["supporting_task_families"] == ["claim_verification"]
    assert result["diagnostics"]["attempt"] == 1
    assert extractor.calls == 1


def test_unresolved_reference_returns_clarification_not_a_default_route() -> None:
    case = CASES["NSD-009"]
    extractor = SequenceExtractor((_l1("NSD-009"), {"attempt": 1}))

    result = understand_narrow_query_v1(case["query"], extractor)

    assert result["status"] == "clarification_required"
    assert result["contract"] is None
    assert result["reasons"]
    assert "l1" not in result


def test_invalid_external_output_fails_closed_without_leaking_a_route() -> None:
    case = CASES["NSD-003"]
    extractor = SequenceExtractor(ValueError("provider returned invalid JSON"))

    result = understand_narrow_query_v1(case["query"], extractor)

    assert result["status"] == "clarification_required"
    assert result["contract"] is None
    assert result["reasons"] == ["semantic extraction unavailable"]
    assert result["diagnostics"]["error_type"] == "ValueError"
    assert "invalid JSON" not in json.dumps(result, ensure_ascii=False)
