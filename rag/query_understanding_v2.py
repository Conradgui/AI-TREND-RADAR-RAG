"""Shadow-only Query understanding for the Route Contract v2.

This module is intentionally not connected to the production chat or retrieval path.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field

from rag.query_signal_extraction import extract_query_signals
from rag.query_understanding import analyze_query
from rag.task_route_resolution import resolve_task_route
from rag.entity_identity import related_entity_expansions


_ROUTE_POLICIES = {
    "trend_discovery": (
        "atr.rewrite/trend_discovery/1.0",
        "atr.retrieval/trend_discovery/1.0",
        "atr.prompt/trend_discovery/1.0",
        "atr.answer/trend/1.0",
        "atr.budget/standard/1.0",
    ),
    "temporal_relation_exploration": (
        "atr.rewrite/temporal_relation_exploration/1.0",
        "atr.retrieval/temporal_relation_exploration/1.0",
        "atr.prompt/temporal_relation_exploration/1.0",
        "atr.answer/temporal_relation/1.0",
        "atr.budget/graph/1.0",
    ),
    "claim_verification": (
        "atr.rewrite/claim_verification/1.0",
        "atr.retrieval/claim_verification/1.0",
        "atr.prompt/claim_verification/1.0",
        "atr.answer/verification/1.0",
        "atr.budget/verification/1.0",
    ),
    "evidence_research": (
        "atr.rewrite/evidence_research/1.0",
        "atr.retrieval/evidence_research/1.0",
        "atr.prompt/evidence_research/1.0",
        "atr.answer/research/1.0",
        "atr.budget/research/1.0",
    ),
}


@dataclass(frozen=True)
class RouteContractV2:
    schema_version: str
    request_id: str
    original_query: str
    protected_terms: list[str]
    intent_signals: list[str]
    primary_task_family: str
    supporting_task_families: list[str]
    answer_mode: str
    route_confidence: float
    ambiguities: list[str]
    delivery_contracts: list[dict] = field(default_factory=list)
    resolved_references: list[dict] = field(default_factory=list)
    supporting_contracts: list[dict] = field(default_factory=list)
    subjects: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    retrieval_hints: list[str] = field(default_factory=list)
    entity_expansions: list[dict] = field(default_factory=list)
    claims: list[str] = field(default_factory=list)
    temporal_constraint: dict = field(default_factory=lambda: {"mode": "none", "value": None})
    source_constraint: dict = field(
        default_factory=lambda: {"requested_sources": [], "official_first": False}
    )
    web_permission: str = "forbidden"
    rewrite_policy_id: str = "atr.rewrite/item_navigation/1.0"
    retrieval_policy_id: str = "atr.retrieval/item_navigation/1.0"
    prompt_contract_id: str | None = None
    answer_builder_contract_id: str | None = "atr.answer_builder/item_navigation/1.0"
    output_schema_id: str = "atr.answer/navigation/1.0"
    budget_profile_id: str = "atr.budget/deterministic/1.0"

    def __post_init__(self) -> None:
        """Make legacy shadow contracts explicit instead of leaving delivery data absent."""
        if self.delivery_contracts:
            return
        deliveries = [
            {
                "task_family": self.primary_task_family,
                "requested_output_form": self.answer_mode,
                "locator_kind": None if self.primary_task_family == "item_navigation" else "none",
            }
        ]
        deliveries.extend(
            {
                "task_family": family,
                "requested_output_form": None,
                "locator_kind": None if family == "item_navigation" else "none",
            }
            for family in self.supporting_task_families
        )
        object.__setattr__(self, "delivery_contracts", deliveries)

    def to_dict(self) -> dict:
        return asdict(self)


def understand_query_v2(
    original_query: str,
    conversation_context: str | None = None,
    *,
    entity_relation_memory=None,
) -> RouteContractV2:
    """Return a shadow Route Contract without mutating the production QueryPlan."""
    raw_query = original_query
    normalized = raw_query.strip()
    if not normalized:
        raise ValueError("original_query cannot be empty")

    signals = extract_query_signals(normalized, conversation_context)
    decision = resolve_task_route(signals)
    retrieval_facts = analyze_query(
        normalized,
        entity_relation_memory=entity_relation_memory,
    )
    common = dict(
        schema_version="atr.route/2.0",
        request_id=_stable_request_id(raw_query, conversation_context),
        original_query=raw_query,
        protected_terms=list(signals.protected_terms),
        intent_signals=list(signals.intent_signals),
        primary_task_family=decision.primary_task_family,
        supporting_task_families=list(decision.supporting_task_families),
        answer_mode=decision.answer_mode,
        route_confidence=decision.route_confidence,
        ambiguities=list(decision.ambiguities),
        resolved_references=[
            {
                "reference_type": reference_type,
                "value": value,
                "origin": origin,
            }
            for reference_type, value, origin in signals.resolved_references
        ],
        supporting_contracts=[
            _supporting_contract(task_family)
            for task_family in decision.supporting_task_families
        ],
        subjects=list(retrieval_facts.entities),
        topics=list(retrieval_facts.topics),
        entity_expansions=list(retrieval_facts.entity_expansions),
        temporal_constraint=_temporal_constraint_from_plan(retrieval_facts.time_window),
        source_constraint={
            "requested_sources": list(retrieval_facts.sources),
            "official_first": "官方" in normalized,
        },
    )

    if decision.primary_task_family == "item_navigation":
        return RouteContractV2(
            **common,
            web_permission=signals.web_permission if decision.supporting_task_families else "forbidden",
        )

    rewrite, retrieval, prompt, output, budget = _ROUTE_POLICIES[
        decision.primary_task_family
    ]
    return RouteContractV2(
        **common,
        web_permission=signals.web_permission,
        rewrite_policy_id=rewrite,
        retrieval_policy_id=retrieval,
        prompt_contract_id=prompt,
        answer_builder_contract_id=None,
        output_schema_id=output,
        budget_profile_id=budget,
    )


def _stable_request_id(query: str, context: str | None) -> str:
    payload = f"{query}\0{context or ''}"
    return f"shadow-{uuid.uuid5(uuid.NAMESPACE_URL, payload).hex}"


def _temporal_constraint_from_plan(time_window: dict) -> dict:
    """Carry the deterministic analyser's bounded window into the contract."""
    if str((time_window or {}).get("mode") or "") == "absolute_range":
        return {
            key: time_window[key]
            for key in ("mode", "value", "surface", "start", "end")
            if key in time_window
        }
    label = str((time_window or {}).get("label") or "")
    days = (time_window or {}).get("days")
    if label in {"last_7_days", "recent_corpus_first"} and days:
        return {"mode": "relative_window", "value": str(int(days))}
    if label == "not_limited":
        return {"mode": "historical", "value": None}
    return {"mode": "none", "value": None}


def _supporting_contract(
    task_family: str,
    *,
    requested_output_form: str | None = None,
    locator_kind: str | None = None,
) -> dict:
    if task_family == "item_navigation":
        if requested_output_form not in {"exact_item", "item_disambiguation"}:
            raise ValueError("supporting item_navigation requires an output form")
        if locator_kind not in {"atr_id", "full_title", "title_fragment", "descriptive"}:
            raise ValueError("supporting item_navigation requires a locator kind")
        ambiguous = locator_kind in {"title_fragment", "descriptive"}
        expected_output = "item_disambiguation" if ambiguous else "exact_item"
        if requested_output_form != expected_output:
            raise ValueError("supporting item_navigation output conflicts with locator")
        return {
            "task_family": task_family,
            "rewrite_policy_id": "atr.rewrite/item_navigation/1.0",
            "retrieval_policy_id": "atr.retrieval/item_navigation/1.0",
            "prompt_contract_id": None,
            "answer_builder_contract_id": "atr.answer_builder/item_navigation/1.0",
            "requested_output_form": requested_output_form,
            "locator_kind": locator_kind,
            "route_confidence": 0.65 if ambiguous else 1.0,
            "ambiguities": ["item locator may match multiple records"] if ambiguous else [],
            "output_schema_id": "atr.answer/navigation/1.0",
            "budget_profile_id": "atr.budget/deterministic/1.0",
        }
    rewrite, retrieval, prompt, output, budget = _ROUTE_POLICIES[task_family]
    return {
        "task_family": task_family,
        "rewrite_policy_id": rewrite,
        "retrieval_policy_id": retrieval,
        "prompt_contract_id": prompt,
        "answer_builder_contract_id": None,
        "output_schema_id": output,
        "budget_profile_id": budget,
    }
