"""Readiness probes must stay cheap while background maintenance is active."""

from types import SimpleNamespace

import pytest

from rag import consistency, server


@pytest.mark.asyncio
async def test_health_probe_does_not_run_cross_store_consistency(monkeypatch):
    async def fail_if_called(*_args, **_kwargs):
        raise AssertionError("deep consistency must not run in the readiness probe")

    monkeypatch.setattr(consistency, "check_consistency", fail_if_called)
    rag = SimpleNamespace(
        neo4j_driver=object(),
        vector_store=SimpleNamespace(count=lambda: 42),
        retriever_mode="vector-only",
        generation_id="gen-test",
        index_status="graph_maintenance",
        external_deep_fetcher=None,
    )

    result = await server.health(rag)

    assert result["status"] == "ok"
    assert result["index_status"] == "graph_maintenance"
    assert "data_consistency" not in result


@pytest.mark.asyncio
async def test_dashboard_reports_frozen_runtime_instead_of_stale_syncing(monkeypatch):
    monkeypatch.setattr(server, "is_startup_corpus_update_enabled", lambda: False)
    monkeypatch.setattr(server, "load_update_state", lambda: {"status": "syncing"})
    monkeypatch.setattr(server, "get_configured_search_providers", lambda: set())
    monkeypatch.setattr(server, "get_search_provider_api_keys", lambda: {})
    rag = SimpleNamespace(
        neo4j_driver=object(),
        vector_store=SimpleNamespace(count=lambda: 42),
        retriever_mode="hybrid",
        generation_id="gen-frozen",
        index_status="ready",
        external_deep_fetcher=None,
        external_search_registry=None,
    )

    result = await server.dashboard_status(rag)

    assert result["corpus_mode"] == "frozen"
    assert result["corpus_update"]["status"] == "frozen"
