"""Route execution policy behavior at its public seam."""

from __future__ import annotations

import pytest

from rag.route_execution_policy import execution_policy_for


@pytest.mark.parametrize(
    ("family", "mode", "channels", "graph_mode", "composer_calls"),
    [
        ("item_navigation", "exact_item", ("lexical",), "disabled", 0),
        ("trend_discovery", "important_news", ("structured",), "disabled", 0),
        ("trend_discovery", "trend_clusters", ("structured", "graph"), "candidate_bounded", 1),
        ("temporal_relation_exploration", "timeline", ("lexical", "vector"), "disabled", 1),
        ("claim_verification", "verification_verdict", ("lexical", "vector"), "disabled", 1),
        ("evidence_research", "comparison", ("lexical", "vector"), "disabled", 1),
    ],
)
def test_each_route_has_an_explicit_bounded_execution_policy(
    family: str,
    mode: str,
    channels: tuple[str, ...],
    graph_mode: str,
    composer_calls: int,
) -> None:
    policy = execution_policy_for(family, mode)

    assert policy.channels == channels
    assert policy.graph_mode == graph_mode
    assert policy.max_composer_calls == composer_calls


def test_unknown_route_fails_closed() -> None:
    with pytest.raises(ValueError, match="unsupported route execution"):
        execution_policy_for("unknown", "unknown")
