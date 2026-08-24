import pytest

from rag.migrate_observation_graph import (
    apply_observation_graph_migration,
    validate_observation_graph,
)


def test_invariants_accept_complete_observation_projection():
    assert validate_observation_graph({
        "observations": 4, "content_eligible": 4, "source_eligible": 4,
        "category_eligible": 4, "observes": 4, "from_links": 4,
        "about": 4, "published_in": 4, "previous_links": 2,
        "expected_previous_links": 2, "orphan_contents": 0,
    }) == []


def test_invariants_reject_partial_projection():
    failures = validate_observation_graph({
        "observations": 4, "content_eligible": 4, "source_eligible": 4,
        "category_eligible": 4, "observes": 3, "from_links": 4,
        "about": 4, "published_in": 4, "previous_links": 1,
        "expected_previous_links": 2, "orphan_contents": 1,
    })
    assert failures == ["observes_mismatch", "previous_chain_mismatch", "orphan_content"]


@pytest.mark.asyncio
async def test_apply_uses_one_transaction_and_returns_validated_stats(monkeypatch):
    class Driver:
        async def execute_write(self, *_args, **_kwargs):
            return None

        async def execute_write_transaction(self, work):
            return await work(TransactionDriver())

    class TransactionDriver:
        async def execute_write(self, *_args, **_kwargs):
            return None

        async def execute_query(self, cypher, **_kwargs):
            if "expected_previous_links" in cypher:
                return [{"expected_previous_links": 1}]
            if "RETURN count(r) AS previous_links" in cypher:
                return [{"previous_links": 1}]
            if "orphan_contents" in cypher:
                return [{"orphan_contents": 0}]
            if "content_ids" in cypher:
                return [{"content_ids": ["c1"]}]
            return [{
                "observations": 2, "content_eligible": 2, "source_eligible": 2,
                "category_eligible": 2, "observes": 2, "from_links": 2,
                "about": 2, "published_in": 2,
            }]

    monkeypatch.setattr("rag.migrate_observation_graph.init_schema", lambda _driver: _async_none())
    result = await apply_observation_graph_migration(Driver())
    assert result["valid"] is True


async def _async_none():
    return None
