"""Per-route latency budgets for the public chat orchestration path."""

from __future__ import annotations

from dataclasses import dataclass


SEMANTIC_ROUTE_TIMEOUT_SECONDS = 8.0
GLOBAL_CHAT_TIMEOUT_SECONDS = 70.0


@dataclass(frozen=True)
class RouteRuntimeBudget:
    total_seconds: float
    retrieval_seconds: float
    generation_seconds: float


def runtime_budget_for(route_contract: dict | None) -> RouteRuntimeBudget:
    if not route_contract:
        return RouteRuntimeBudget(total_seconds=60.0, retrieval_seconds=15.0, generation_seconds=45.0)
    family = str(route_contract.get("primary_task_family") or "")
    mode = str(route_contract.get("answer_mode") or "")
    if family == "item_navigation":
        return RouteRuntimeBudget(total_seconds=3.0, retrieval_seconds=2.0, generation_seconds=0.0)
    if family == "trend_discovery" and mode == "important_news":
        return RouteRuntimeBudget(total_seconds=20.0, retrieval_seconds=8.0, generation_seconds=0.0)
    if family == "trend_discovery":
        return RouteRuntimeBudget(total_seconds=30.0, retrieval_seconds=10.0, generation_seconds=20.0)
    if family == "temporal_relation_exploration":
        return RouteRuntimeBudget(total_seconds=60.0, retrieval_seconds=20.0, generation_seconds=40.0)
    if family == "claim_verification":
        return RouteRuntimeBudget(total_seconds=45.0, retrieval_seconds=10.0, generation_seconds=35.0)
    if family == "evidence_research":
        return RouteRuntimeBudget(total_seconds=60.0, retrieval_seconds=15.0, generation_seconds=45.0)
    return RouteRuntimeBudget(total_seconds=60.0, retrieval_seconds=15.0, generation_seconds=45.0)
