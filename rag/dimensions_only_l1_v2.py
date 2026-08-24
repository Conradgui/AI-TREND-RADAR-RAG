"""Validate model-only dimensions and assemble the existing narrow L1 contract."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from rag.narrow_semantic_decisions_v1 import validate_narrow_decisions
from rag.query_facts_v1 import extract_query_facts_v1


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs/rag-transformation/specs/dimensions-only-l1-v2.schema.json"


class DimensionsOnlyViolation(ValueError):
    pass


def validate_dimensions_only_v2(query: str, value: dict) -> None:
    errors = sorted(
        Draft202012Validator(json.loads(SCHEMA_PATH.read_text())).iter_errors(value),
        key=lambda error: tuple(str(part) for part in error.path),
    )
    if errors:
        raise DimensionsOnlyViolation(
            "schema violation: " + "; ".join(error.message for error in errors)
        )
    for name, judgment in value["dimensions"].items():
        spans = judgment["evidence_spans"]
        if judgment["state"] in {"present", "uncertain"} and not spans:
            raise DimensionsOnlyViolation(f"{name} requires evidence spans")
        if judgment["state"] == "absent" and spans:
            raise DimensionsOnlyViolation(f"absent {name} cannot carry evidence")
        for span in spans:
            if span not in query:
                raise DimensionsOnlyViolation(
                    f"evidence span is not literal Query text: {span}"
                )


def assemble_narrow_decisions_v2(
    query: str,
    model_value: dict,
    conversation_context: str | None = None,
) -> dict:
    """Merge semantic judgments with deterministic Query Facts."""
    validate_dimensions_only_v2(query, model_value)
    facts = extract_query_facts_v1(
        query, model_value["dimensions"], conversation_context
    )
    result = {
        "schema_version": "atr.semantic-decisions/1.0",
        "dimensions": model_value["dimensions"],
        "protected_spans": list(facts.protected_spans),
        "item_locator_precision": facts.item_locator_precision,
        "unresolved_reference_spans": list(facts.unresolved_reference_spans),
        "resolved_references": [
            {"literal_span": literal, "item_id": item_id}
            for literal, item_id in facts.resolved_references
        ],
    }
    validate_narrow_decisions(query, result, conversation_context)
    return result
