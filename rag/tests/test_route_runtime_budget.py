from rag.route_runtime_budget import GLOBAL_CHAT_TIMEOUT_SECONDS, runtime_budget_for


def test_route_runtime_budgets_are_bounded_and_task_specific():
    cases = (
        ({"primary_task_family": "item_navigation", "answer_mode": "exact_item"}, 3, 0),
        ({"primary_task_family": "trend_discovery", "answer_mode": "important_news"}, 20, 0),
        ({"primary_task_family": "trend_discovery", "answer_mode": "trend_clusters"}, 30, 20),
        ({"primary_task_family": "temporal_relation_exploration", "answer_mode": "timeline"}, 60, 40),
        ({"primary_task_family": "claim_verification", "answer_mode": "verification_verdict"}, 45, 35),
        ({"primary_task_family": "evidence_research", "answer_mode": "deep_research"}, 60, 45),
    )

    for contract, total, generation in cases:
        budget = runtime_budget_for(contract)
        assert budget.total_seconds == total
        assert budget.generation_seconds == generation
        assert 0 < budget.retrieval_seconds < budget.total_seconds
        assert budget.total_seconds <= GLOBAL_CHAT_TIMEOUT_SECONDS
