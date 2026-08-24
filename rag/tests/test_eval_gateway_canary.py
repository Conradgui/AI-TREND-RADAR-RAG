from rag.eval_gateway_canary import evaluate_case
from rag.retrieval_gateway import EvidenceBundle


def _bundle(*records, task_family="trend_discovery"):
    return EvidenceBundle(
        status="ready",
        task_family=task_family,
        records=list(records),
        trace={"path": "trend_discovery"},
    )


def test_trend_canary_requires_diverse_unique_evidence_records():
    case = {
        "id": "C01",
        "expected_task_family": "trend_discovery",
        "min_records": 3,
        "min_unique_sources": 2,
    }
    bundle = _bundle(
        {"citation_id": "a", "source": "OpenAI", "title": "A"},
        {"citation_id": "b", "source": "OpenAI", "title": "B"},
        {"citation_id": "c", "source": "Anthropic", "title": "C"},
    )

    result = evaluate_case(case, bundle, baseline_records=[])

    assert result["passed"] is True
    assert result["checks"]["unique_sources"] is True


def test_navigation_canary_requires_target_and_stable_local_url():
    case = {
        "id": "C02",
        "expected_task_family": "item_navigation",
        "expected_citation_id": "occ-apple",
        "requires_local_url": True,
    }
    bundle = _bundle(
        {"citation_id": "occ-apple", "source": "OpenAI", "title": "Apple"},
        task_family="item_navigation",
    )

    result = evaluate_case(case, bundle, baseline_records=[])

    assert result["passed"] is False
    assert result["checks"]["stable_local_url"] is False
