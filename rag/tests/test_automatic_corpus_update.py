"""Contracts for the single-process automatic corpus updater."""

import asyncio
from types import SimpleNamespace

import pytest

from rag import server


@pytest.mark.asyncio
async def test_automatic_update_uses_configured_source_and_existing_ingestion_path(monkeypatch):
    calls = []

    async def fake_update_corpus(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(status="unchanged")

    async def fake_ingester(_dates):
        raise AssertionError("the updater should pass the server generation callback")

    monkeypatch.setattr(server, "update_corpus", fake_update_corpus)
    monkeypatch.setattr(server, "get_upstream_corpus_url", lambda: "https://example.test/corpus")
    monkeypatch.setattr(server, "get_corpus_recheck_days", lambda: 14)

    await server._run_corpus_update_once()

    assert calls == [{
        "base_url": "https://example.test/corpus",
        "days": 14,
        "ingester": server._rebuild_runtime_index,
    }]


@pytest.mark.asyncio
async def test_automatic_update_loop_rechecks_after_each_completed_run(monkeypatch):
    calls = []
    sleeps = []

    async def fake_run_once():
        calls.append("update")
        return SimpleNamespace(status="unchanged")

    async def stop_after_first_sleep(seconds):
        sleeps.append(seconds)
        raise asyncio.CancelledError()

    monkeypatch.setattr(server, "_run_corpus_update_once", fake_run_once)
    monkeypatch.setattr(server, "get_corpus_update_interval_seconds", lambda: 900)
    monkeypatch.setattr(server.asyncio, "sleep", stop_after_first_sleep)

    with pytest.raises(__import__("asyncio").CancelledError):
        await server._refresh_corpus_in_process()

    assert calls == ["update"]
    assert sleeps == [900]
