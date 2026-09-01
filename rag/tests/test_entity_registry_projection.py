import asyncio
import json

import pytest

from rag.entity_registry_projection import project_entity_registry, project_entity_relation_memory
from rag.entity_relation_memory import EntityRelationMemory


class FakeDriver:
    def __init__(self):
        self.calls = []
        self.committed = []
        self.in_transaction = False

    async def execute_write_transaction(self, work):
        # Database boundary double: publish writes only if the callback succeeds.
        offset = len(self.calls)
        self.in_transaction = True
        try:
            result = await work(self)
            self.committed.extend(self.calls[offset:])
            return result
        finally:
            self.in_transaction = False

    async def execute_write(self, cypher, **params):
        self.calls.append((cypher, params))
        if not self.in_transaction:
            self.committed.append((cypher, params))


def test_projection_is_idempotent_by_using_merge_and_only_verified_relations():
    driver = FakeDriver()
    result = asyncio.run(project_entity_registry(driver))
    assert result["status"] == "projected"
    assert result["entity_count"] >= 17
    assert result["relation_count"] >= 9
    assert all("UNWIND" in cypher for cypher, _ in driver.calls)
    relation_calls = [call for call in driver.calls if "RELATED_TO" in call[0]]
    assert relation_calls
    assert set(item["relation"] for item in relation_calls[0][1]["relations"]) <= {
        "developed_by", "product_of", "owned_by", "distributed_on"
    }


def test_projection_does_not_write_space_x_or_antigravity_relationships():
    driver = FakeDriver()
    asyncio.run(project_entity_registry(driver))
    relation_params = [params for cypher, params in driver.calls if "RELATED_TO" in cypher]
    assert not any(item["source_id"] in {"spacex", "antigravity"}
                   for item in relation_params[0]["relations"])


def test_projection_failure_does_not_leave_partial_committed_writes():
    class FailingDriver(FakeDriver):
        async def execute_write(self, cypher, **params):
            await super().execute_write(cypher, **params)
            if len(self.calls) == 1:
                raise RuntimeError("database unavailable")

    driver = FailingDriver()
    with pytest.raises(RuntimeError, match="database unavailable"):
        asyncio.run(project_entity_registry(driver))
    assert driver.committed == []


def test_projection_commits_the_complete_batch():
    driver = FakeDriver()
    result = asyncio.run(project_entity_registry(driver))
    assert len(driver.committed) == 2


def test_projection_never_updates_existing_entity_properties():
    driver = FakeDriver()
    asyncio.run(project_entity_registry(driver))
    entity_calls = [cypher for cypher, params in driver.calls if "entities" in params]
    assert entity_calls
    assert all("ON CREATE SET" in cypher and "ON MATCH" not in cypher for cypher in entity_calls)


def test_relationships_are_versioned_and_separate_from_corpus_evidence():
    driver = FakeDriver()
    asyncio.run(project_entity_registry(driver))
    relation_calls = [cypher for cypher, params in driver.calls if "relations" in params]
    assert relation_calls
    assert all("registry_version: $registry_version" in cypher for cypher in relation_calls)
    assert all("scope: 'entity_registry'" in cypher for cypher in relation_calls)
    assert all("ON CREATE SET" in cypher for cypher in relation_calls)


def test_verified_learned_relations_are_projected_and_revocations_are_removed(tmp_path):
    memory = EntityRelationMemory(tmp_path / "relations.json")
    candidate = memory.observe(
        "novaflow",
        "google",
        "product_of",
        evidence=[{"url": "https://google.example/novaflow", "supports": True}],
    )
    memory.decide(candidate["candidate_id"], "verified")
    driver = FakeDriver()

    result = asyncio.run(project_entity_relation_memory(driver, memory))

    assert result["relation_count"] == 1
    assert len(driver.committed) == 2
    assert "learned_entity_memory" in driver.committed[0][0]
    assert driver.committed[0][1]["relations"][0]["source_id"] == "novaflow"
    assert "DELETE r" in driver.committed[1][0]


@pytest.mark.parametrize("change", [
    {"version": ""},
    {"duplicate_entity": True},
    {"to": "unknown"},
    {"weight": float("nan")},
    {"weight": 2},
    {"relation": "invented"},
])
def test_invalid_registry_is_rejected_before_any_writes(tmp_path, change):
    payload = {
        "version": "test-v1",
        "entities": [
            {"entity_id": "product", "entity_type": "product", "aliases": ["Product"]},
            {"entity_id": "company", "entity_type": "company", "aliases": ["Company"]},
        ],
        "relations": [{"from": "product", "to": "company", "relation": "product_of",
                       "weight": 0.5, "status": "verified"}],
    }
    if "version" in change:
        payload.update(change)
    elif "duplicate_entity" in change:
        payload["entities"].append(payload["entities"][0])
    else:
        payload["relations"][0].update(change)
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    driver = FakeDriver()
    with pytest.raises(ValueError):
        asyncio.run(project_entity_registry(driver, path))
    assert driver.calls == []
