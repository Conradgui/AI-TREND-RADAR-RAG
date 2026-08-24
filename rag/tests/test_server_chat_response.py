"""Public request/response-contract tests for the chat endpoint."""

import pytest
import httpx
from pydantic import ValidationError

import rag.server as server
from rag.server import ChatRequest, ChatResponse


def test_chat_request_defaults_to_automatic_web_search_mode():
    request = ChatRequest(message="最近有什么趋势？")

    assert request.web_search_mode == "auto"


def test_chat_request_accepts_explicit_request_scoped_web_search_mode():
    request = ChatRequest(message="请查官网", web_search_mode="always")

    assert request.web_search_mode == "always"


def test_chat_request_rejects_unknown_web_search_mode():
    with pytest.raises(ValidationError):
        ChatRequest(message="最近有什么趋势？", web_search_mode="sometimes")


def test_chat_response_preserves_claim_and_evidence_integrity_fields():
    response = ChatResponse(
        answer="Grounded answer [E1]",
        citations=[{"evidence_id": "E1"}],
        claim_evidence=[{"claim": "Grounded answer", "evidence_ids": ["E1"]}],
        evidence_integrity={"valid": True, "minimum_evidence_markers": 1},
    )

    payload = response.model_dump()

    assert payload["claim_evidence"][0]["evidence_ids"] == ["E1"]
    assert payload["evidence_integrity"]["valid"] is True


def test_chat_response_preserves_claim_verification_contract():
    response = ChatResponse(
        answer="证据不足",
        claim_verification={
            "valid": True,
            "verdict": "insufficient",
            "evidence_ids": ["E1"],
            "missing_criteria": ["财务结果"],
        },
    )

    payload = response.model_dump()

    assert payload["claim_verification"]["verdict"] == "insufficient"


def test_chat_response_exposes_display_contract_without_replacing_canonical_answer():
    response = ChatResponse(
        answer="内部事实 [E1]，外部补充 [E2]。",
        display_answer="🌐 已联网补充（内部语料优先）\n\n内部事实 [I1]，外部补充 [W1 🌐]。",
        citations=[
            {"evidence_id": "E1", "display_label": "I1", "evidence_type": "internal"},
            {"evidence_id": "E2", "display_label": "W1", "evidence_type": "external"},
        ],
        evidence_display_map={"E1": "I1", "E2": "W1"},
        source_summary={"internal_citations": 1, "external_citations": 1},
    )

    payload = response.model_dump()

    assert payload["answer"] == "内部事实 [E1]，外部补充 [E2]。"
    assert "[I1]" in payload["display_answer"]
    assert "[W1 🌐]" in payload["display_answer"]
    assert payload["evidence_display_map"] == {"E1": "I1", "E2": "W1"}
    assert payload["search_references"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/chat", "/chat/stream"])
async def test_chat_endpoints_require_configured_api_key(monkeypatch, path):
    """Public model-consuming endpoints must enforce the configured key."""
    monkeypatch.setattr(server, "API_KEY", "release-secret")

    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(path, json={"message": "最近趋势"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_chat_endpoint_forwards_request_scoped_web_search_mode(monkeypatch):
    captured = {}

    async def fake_build_chat_response(agent, retriever, message, history, **kwargs):
        captured.update(kwargs)
        return {"answer": "ok"}

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
            "/chat",
            json={"message": "请查官网", "web_search_mode": "always"},
        )

    assert response.status_code == 200
    assert captured["web_search_mode"] == "always"


@pytest.mark.asyncio
async def test_chat_endpoint_forwards_the_runtime_gateway(monkeypatch):
    captured = {}
    gateway = object()
    resolver = object()

    async def fake_build_chat_response(agent, retriever, message, history, **kwargs):
        captured.update(kwargs)
        return {"answer": "ok"}

    monkeypatch.setattr(server, "build_chat_response", fake_build_chat_response)
    server.app.state.rag = server.RagState(
        vector_store=object(),
        neo4j_driver=None,
        chat_retriever=object(),
        agent=object(),
        answer_composer=object(),
        external_search_registry=None,
        external_deep_fetcher=None,
        retrieval_gateway=gateway,
        query_contract_resolver=resolver,
        latest_corpus_date="2026-08-21",
    )

    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/chat", json={"message": "最近有什么热门趋势？"})

    assert response.status_code == 200
    assert captured["retrieval_gateway"] is gateway
    assert captured["query_contract_resolver"] is resolver
    assert captured["latest_corpus_date"] == "2026-08-21"


@pytest.mark.asyncio
async def test_web_search_cannot_be_enabled_without_a_configured_provider(monkeypatch):
    monkeypatch.setattr(server, "get_configured_search_providers", lambda: set())
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
        response = await client.post("/config/web-search?enabled=true")

    assert response.status_code == 409
    assert response.json()["detail"].startswith("No web search provider")
    assert server.app.state.rag.external_search_registry is None


@pytest.mark.asyncio
async def test_retriever_mode_swap_rebuilds_agent_tools(monkeypatch):
    old_agent = object()
    rebuilt_agent = object()
    vector_store = object()
    neo4j_driver = object()
    monkeypatch.setattr(server, "create_agent", lambda driver, retriever: rebuilt_agent)
    server.app.state.rag = server.RagState(
        vector_store=vector_store,
        neo4j_driver=neo4j_driver,
        chat_retriever=object(),
        agent=old_agent,
        answer_composer=object(),
        external_search_registry=None,
        external_deep_fetcher=None,
    )

    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/config/retriever-mode?mode=hybrid")

    assert response.status_code == 200
    assert server.app.state.rag.agent is rebuilt_agent
    assert server.app.state.rag.chat_retriever is not None


@pytest.mark.asyncio
async def test_vector_only_mode_uses_direct_composer_instead_of_stale_agent():
    composer = object()
    server.app.state.rag = server.RagState(
        vector_store=object(),
        neo4j_driver=object(),
        chat_retriever=object(),
        agent=object(),
        answer_composer=composer,
        external_search_registry=None,
        external_deep_fetcher=None,
    )

    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/config/retriever-mode?mode=vector-only")

    assert response.status_code == 200
    assert server.app.state.rag.agent is composer
