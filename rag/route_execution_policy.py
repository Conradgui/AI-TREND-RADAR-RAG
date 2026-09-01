"""Route-owned execution budgets and retrieval-channel policy."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RouteExecutionPolicy:
    channels: tuple[str, ...]
    graph_mode: str
    max_composer_calls: int
    allow_web_fallback: bool


_POLICIES = {
    ("item_navigation", "*"): RouteExecutionPolicy(
        channels=("lexical",), graph_mode="disabled",
        max_composer_calls=0, allow_web_fallback=False,
    ),
    ("trend_discovery", "important_news"): RouteExecutionPolicy(
        channels=("structured",), graph_mode="disabled",
        max_composer_calls=0, allow_web_fallback=True,
    ),
    ("trend_discovery", "trend_clusters"): RouteExecutionPolicy(
        channels=("structured", "graph"), graph_mode="candidate_bounded",
        max_composer_calls=1, allow_web_fallback=True,
    ),
    # A bounded list of direct dated reports is answerable from those reports.
    # Graph evidence remains essential for relation and longitudinal routes, but
    # must not turn this deterministic path into a hard dependency.
    ("temporal_relation_exploration", "timeline"): RouteExecutionPolicy(
        channels=("lexical", "vector"), graph_mode="disabled",
        max_composer_calls=1, allow_web_fallback=False,
    ),
    ("temporal_relation_exploration", "*"): RouteExecutionPolicy(
        channels=("lexical", "vector", "graph"), graph_mode="required",
        max_composer_calls=1, allow_web_fallback=False,
    ),
    ("claim_verification", "*"): RouteExecutionPolicy(
        channels=("lexical", "vector"), graph_mode="disabled",
        max_composer_calls=1, allow_web_fallback=True,
    ),
    ("evidence_research", "*"): RouteExecutionPolicy(
        channels=("lexical", "vector"), graph_mode="disabled",
        max_composer_calls=1, allow_web_fallback=True,
    ),
}


def execution_policy_for(task_family: str, answer_mode: str) -> RouteExecutionPolicy:
    """Return the sole execution policy for a resolved route contract."""
    policy = _POLICIES.get((task_family, answer_mode)) or _POLICIES.get((task_family, "*"))
    if policy is None:
        raise ValueError(f"unsupported route execution: {task_family}/{answer_mode}")
    return policy
