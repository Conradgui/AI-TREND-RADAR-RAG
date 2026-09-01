"""Active Neo4j readiness behavior through one probe interface."""

from __future__ import annotations

import pytest

from rag.graph_readiness import GraphReadinessProbe


class ScriptedDriver:
    def __init__(self, *, indexes=None, fail=False):
        self.indexes = indexes or [
            {"name": "entity_search", "state": "ONLINE"},
            {"name": "topic_search", "state": "ONLINE"},
        ]
        self.fail = fail
        self.queries = []

    async def execute_query(self, query: str, **_params):
        self.queries.append(query)
        if self.fail:
            raise OSError("bolt unavailable")
        if "SHOW INDEXES" in query:
            return self.indexes
        if "required_label" in query:
            return [
                {"required_label": "Observation", "node_count": 2},
                {"required_label": "Content", "node_count": 2},
            ]
        return [{"ok": 1}]


@pytest.mark.asyncio
async def test_runtime_probe_is_cached_and_can_be_forced() -> None:
    driver = ScriptedDriver()
    probe = GraphReadinessProbe(driver, ttl_seconds=30)

    first = await probe.probe("runtime")
    cached = await probe.probe("runtime")
    forced = await probe.probe("runtime", force=True)

    assert first.status == cached.status == forced.status == "ready"
    assert cached.cached is True
    assert len(driver.queries) == 2


@pytest.mark.asyncio
async def test_startup_probe_requires_key_indexes_online() -> None:
    driver = ScriptedDriver(indexes=[{"name": "entity_search", "state": "POPULATING"}])

    result = await GraphReadinessProbe(driver).probe("startup")

    assert result.status == "degraded"
    assert result.error_code == "graph_indexes_not_ready"
    assert set(result.details["missing_or_offline_indexes"]) == {"entity_search", "topic_search"}


@pytest.mark.asyncio
async def test_failed_minimal_query_marks_graph_unavailable() -> None:
    result = await GraphReadinessProbe(ScriptedDriver(fail=True)).probe("runtime")

    assert result.status == "unavailable"
    assert result.error_code == "graph_connectivity_failed"


@pytest.mark.asyncio
async def test_startup_probe_reports_missing_core_graph_labels() -> None:
    class MissingContentDriver(ScriptedDriver):
        async def execute_query(self, query: str, **params):
            if "required_label" in query:
                return [
                    {"required_label": "Observation", "node_count": 1},
                    {"required_label": "Content", "node_count": 0},
                ]
            return await super().execute_query(query, **params)

    result = await GraphReadinessProbe(MissingContentDriver()).probe("startup")

    assert result.status == "degraded"
    assert result.error_code == "graph_core_labels_empty"
    assert result.details["empty_labels"] == ["Content"]
