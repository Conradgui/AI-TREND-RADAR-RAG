"""Deterministic-first resolver for one production Route Contract."""

from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Callable

from rag.product_query_catalog import find_product_query
from rag.query_signal_extraction import extract_query_signals
from rag.query_understanding_v2 import understand_query_v2
from rag.route_runtime_budget import SEMANTIC_ROUTE_TIMEOUT_SECONDS


class QueryRouteResolver:
    """Resolve high-confidence requests locally and defer only ambiguity.

    The returned envelope matches the existing ordered-frame seam, allowing the
    production chat path to migrate without teaching callers two interfaces.
    """

    def __init__(
        self,
        semantic_fallback: Callable | None = None,
        *,
        fallback_timeout_seconds: float = SEMANTIC_ROUTE_TIMEOUT_SECONDS,
        entity_relation_memory=None,
    ):
        self.semantic_fallback = semantic_fallback
        self.fallback_timeout_seconds = fallback_timeout_seconds
        self.entity_relation_memory = entity_relation_memory

    async def __call__(self, query: str, context: dict) -> tuple[dict, dict]:
        public_context = json.dumps(context or {}, ensure_ascii=False, sort_keys=True)
        contract = understand_query_v2(
            query,
            public_context,
            entity_relation_memory=self.entity_relation_memory,
        ).to_dict()
        signals = extract_query_signals(query, public_context)
        catalog_case = find_product_query(query)

        if catalog_case is not None:
            if (
                contract["primary_task_family"] != catalog_case.task_family
                or contract["answer_mode"] != catalog_case.answer_mode
            ):
                raise RuntimeError(f"product query contract drift: {catalog_case.case_id}")
            return _resolved(contract), _metadata("product_catalog", 0, catalog_case.case_id)

        # A known subject is not a user task by itself.  A semantic model may
        # recognise the entity, but it must not invent whether the user wants
        # news, product updates, comparison, verification, or navigation.
        if (
            signals.has_concrete_subject
            and contract.get("subjects")
            and not signals.intent_signals
            and "request lacks a concrete subject or success criterion"
            in contract.get("ambiguities", [])
        ):
            return {
                "status": "clarification_required",
                "contract": None,
                "reasons": list(contract["ambiguities"]),
            }, _metadata("deterministic_clarification", 0)

        # A missing conversation referent cannot be recovered by semantic
        # classification. Ask for the names instead of spending a model call.
        if any(
            "contextual item reference cannot be resolved" in reason
            for reason in contract.get("ambiguities", [])
        ):
            return {
                "status": "clarification_required",
                "contract": None,
                "reasons": list(contract["ambiguities"]),
            }, _metadata("deterministic_clarification", 0)

        if _is_high_confidence(contract, signals):
            return _resolved(contract), _metadata("deterministic_signals", 0)

        if self.semantic_fallback is not None:
            result = self.semantic_fallback(query, context or {})
            if inspect.isawaitable(result):
                try:
                    result = await asyncio.wait_for(
                        result,
                        timeout=self.fallback_timeout_seconds,
                    )
                except asyncio.TimeoutError:
                    return {
                        "status": "clarification_required",
                        "contract": None,
                        "reasons": ["semantic_route_timeout"],
                    }, _metadata("semantic_fallback_timeout", 1)
            envelope, metadata = result
            return envelope, {
                **dict(metadata or {}),
                "route_source": "semantic_fallback",
                "model_calls": 1,
            }

        return {
            "status": "clarification_required",
            "contract": None,
            "reasons": list(contract.get("ambiguities") or ["low route confidence"]),
        }, _metadata("deterministic_clarification", 0)


def _is_high_confidence(contract: dict, signals=None) -> bool:
    explicit_named_comparison = bool(
        signals is not None
        and signals.comparison_request
        and len(contract.get("protected_terms") or []) >= 2
    )
    unresolved_named_subject = bool(
        signals is not None
        and signals.has_concrete_subject
        and not contract.get("subjects")
        and contract.get("primary_task_family") != "item_navigation"
        and not explicit_named_comparison
    )
    navigation_can_disambiguate = bool(
        contract.get("primary_task_family") == "item_navigation"
        and contract.get("answer_mode") == "item_disambiguation"
        and contract.get("route_confidence", 0) >= 0.5
        and set(contract.get("ambiguities") or [])
        <= {"item locator may match multiple records"}
    )
    return navigation_can_disambiguate or bool(
        contract.get("route_confidence", 0) >= 0.8
        and not contract.get("ambiguities")
        and not unresolved_named_subject
    )


def _resolved(contract: dict) -> dict:
    return {"status": "resolved", "contract": contract, "reasons": []}


def _metadata(route_source: str, model_calls: int, case_id: str | None = None) -> dict:
    return {
        "route_source": route_source,
        "model_calls": model_calls,
        "product_case_id": case_id,
        "attempts": 0 if model_calls == 0 else 1,
    }
