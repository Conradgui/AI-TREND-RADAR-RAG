"""Application-level invariants for the Route Contract v2 shadow contract."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from jsonschema import Draft202012Validator


class RouteContractViolation(ValueError):
    """Raised when a contract is schema-shaped but violates product semantics."""


class RouteContractReunderstandingRequired(RouteContractViolation):
    """Raised when a legacy contract cannot safely drive retrieval."""


_ROUTE_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs/rag-transformation/specs/route-contract-v2.schema.json"
)
_ROUTE_VALIDATOR = Draft202012Validator(
    json.loads(_ROUTE_SCHEMA_PATH.read_text(encoding="utf-8"))
)


_SUPPORTING_POLICIES = {
    route: {
        "rewrite_policy_id": f"atr.rewrite/{route}/1.0",
        "retrieval_policy_id": f"atr.retrieval/{route}/1.0",
        "prompt_contract_id": f"atr.prompt/{route}/1.0",
        "output_schema_id": output,
        "budget_profile_id": budget,
    }
    for route, output, budget in (
        ("trend_discovery", "atr.answer/trend/1.0", "atr.budget/standard/1.0"),
        (
            "temporal_relation_exploration",
            "atr.answer/temporal_relation/1.0",
            "atr.budget/graph/1.0",
        ),
        (
            "claim_verification",
            "atr.answer/verification/1.0",
            "atr.budget/verification/1.0",
        ),
        ("evidence_research", "atr.answer/research/1.0", "atr.budget/research/1.0"),
    )
}
_SUPPORTING_POLICIES["item_navigation"] = {
    "rewrite_policy_id": "atr.rewrite/item_navigation/1.0",
    "retrieval_policy_id": "atr.retrieval/item_navigation/1.0",
    "prompt_contract_id": None,
    "answer_builder_contract_id": "atr.answer_builder/item_navigation/1.0",
    "output_schema_id": "atr.answer/navigation/1.0",
    "budget_profile_id": "atr.budget/deterministic/1.0",
}
for _policy in _SUPPORTING_POLICIES.values():
    _policy.setdefault("answer_builder_contract_id", None)


def validate_route_contract_semantics(contract: dict) -> None:
    """Validate cross-field invariants that JSON Schema cannot express cleanly."""
    primary = contract["primary_task_family"]
    supporting = contract["supporting_task_families"]
    if primary in supporting:
        raise RouteContractViolation("primary_task_family cannot also be supporting")

    delivery_contracts = contract.get("delivery_contracts", [])
    if delivery_contracts:
        delivery_routes = [item["task_family"] for item in delivery_contracts]
        if delivery_routes != [primary, *supporting]:
            raise RouteContractViolation(
                "delivery contracts must match primary and supporting task families in order"
            )
        if delivery_contracts[0]["requested_output_form"] != contract["answer_mode"]:
            raise RouteContractViolation(
                "primary delivery contract output must match answer_mode"
            )
        for item in delivery_contracts:
            is_navigation = item["task_family"] == "item_navigation"
            locator = item["locator_kind"]
            if locator is not None and is_navigation == (locator == "none"):
                raise RouteContractViolation(
                    "delivery contract locator must match task family"
                )

    supporting_contracts = contract.get("supporting_contracts", [])
    contracted_routes = [item["task_family"] for item in supporting_contracts]
    if contracted_routes != supporting:
        raise RouteContractViolation(
            "supporting contracts must match supporting task families in order"
        )
    for item in supporting_contracts:
        expected = _SUPPORTING_POLICIES.get(item["task_family"])
        if expected is None or any(item[key] != value for key, value in expected.items()):
            raise RouteContractViolation(
                "supporting contract policy IDs must match the supporting task family"
            )
        if item["task_family"] == "item_navigation":
            locator = item.get("locator_kind")
            ambiguous = locator in {"title_fragment", "descriptive"}
            if item.get("requested_output_form") != (
                "item_disambiguation" if ambiguous else "exact_item"
            ):
                raise RouteContractViolation(
                    "supporting item navigation output must match locator kind"
                )
            if ambiguous != bool(item.get("ambiguities")):
                raise RouteContractViolation(
                    "supporting item navigation ambiguity must match locator kind"
                )
            if ambiguous == (item.get("route_confidence", 1) >= 1):
                raise RouteContractViolation(
                    "supporting item navigation confidence must match locator kind"
                )

    original_query = _normalized(contract["original_query"])
    missing = [
        term
        for term in contract["protected_terms"]
        if _normalized(term) not in original_query
    ]
    if missing:
        raise RouteContractViolation(
            "protected terms are missing from original_query: " + ", ".join(missing)
        )

    if contract["answer_mode"] == "item_disambiguation":
        if not contract["ambiguities"] or contract["route_confidence"] >= 1:
            raise RouteContractViolation(
                "item disambiguation requires an explicit ambiguity and confidence below 1"
            )


def validate_route_contract_for_retrieval(contract: dict) -> None:
    """Validate invariants that must hold before any retrieval adapter is called."""
    try:
        errors = sorted(
            _ROUTE_VALIDATOR.iter_errors(contract),
            key=lambda item: [str(part) for part in item.absolute_path],
        )
        if errors:
            path = ".".join(str(part) for part in errors[0].absolute_path) or "$"
            raise RouteContractViolation(
                f"route contract schema violation at {path}: {errors[0].message}"
            )
        validate_route_contract_semantics(contract)
    except RouteContractReunderstandingRequired:
        raise
    except (KeyError, TypeError, RouteContractViolation) as exc:
        raise RouteContractReunderstandingRequired(str(exc)) from exc

    temporal = contract.get("temporal_constraint") or {}
    if temporal.get("mode") != "absolute_range":
        return
    start = temporal.get("start")
    end = temporal.get("end")
    if not start or not end:
        raise RouteContractReunderstandingRequired(
            "absolute_range requires machine-readable start and end boundaries"
        )
    try:
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
    except (TypeError, ValueError) as exc:
        raise RouteContractReunderstandingRequired(
            "absolute_range boundaries must be ISO dates"
        ) from exc
    if start_date > end_date:
        raise RouteContractReunderstandingRequired(
            "absolute_range starts after it ends"
        )


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())
