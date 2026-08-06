"""Public HTTP contract tests for progressive chat."""

import json

import httpx
import pytest

import rag.server as server


@pytest.mark.asyncio
async def test_chat_stream_exposes_ordered_ndjson_without_breaking_chat_contract(monkeypatch):
    captured = {}

    async def fake_build_chat_response(
        agent,
        retriever,
        message,
        history,
        **kwargs,
    ):
        captured.update(kwargs)
        progress = kwargs["progress_callback"]
        await progress("understanding", {"task_mode": "general"})
        await progress("retrieving", {"top_k": 10})
        await progress("evidence_ready", {"admitted_count": 1})
        await progress("generating", {"execution_path": "direct_composer"})
        return {
            "answer": "已校验回答。[E1]",
            "display_answer": "📚 仅内部语料\n\n已校验回答。[I1]",
            "citations": [{"evidence_id": "E1", "display_label": "I1"}],
            "evidence_display_map": {"E1": "I1"},
            "source_summary": {"internal_citations": 1, "external_citations": 0},
            "claim_evidence": [],
            "evidence_integrity": {"valid": True},
            "query_understanding": {"task_mode": "general"},
            "tool_trace": {"timings": {"total_ms": 10}},
        }

    monkeypatch.setattr(server, "build_chat_response", fake_build_chat_response)
    server.app.state.rag = server.RagState(
        vector_store=object(),
        neo4j_driver=None,
        chat_retriever=object(),
        agent=object(),
        answer_composer=object(),
        external_search_registry=None,
        external_deep_fetcher=None,
    )

    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/chat/stream",
            json={"message": "最近趋势", "history": [], "web_search_mode": "always"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    assert captured["web_search_mode"] == "always"
    events = [json.loads(line) for line in response.text.splitlines()]
    assert [item["event"] for item in events] == [
        "accepted",
        "understanding",
        "retrieving",
        "evidence_ready",
        "generating",
        "source_groups",
        "answer_chunk",
        "answer_chunk",
        "citations",
        "done",
    ]
