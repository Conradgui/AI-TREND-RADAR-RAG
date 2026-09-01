"""Public request/response-contract tests for the chat endpoint."""

import pytest
import httpx
import re
from dataclasses import replace
from pydantic import ValidationError

import rag.server as server
from rag.graph_readiness import GraphReadiness
from rag.server import ChatRequest, ChatResponse
from rag.query_route_resolver import QueryRouteResolver
from rag.query_understanding import analyze_query
from rag.retrieval_gateway import EvidenceBundle


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
async def test_health_actively_probes_graph_instead_of_trusting_driver_presence():
    class Vector:
        def count(self):
            return 12

    class Probe:
        def __init__(self):
            self.calls = 0

        async def probe(self, level="runtime", **_kwargs):
            self.calls += 1
            return GraphReadiness(
                status="unavailable",
                level=level,
                checked_at=1.0,
                latency_ms=2.0,
                error_code="graph_connectivity_failed",
            )

    probe = Probe()
    server.app.state.rag = server.RagState(
        vector_store=Vector(),
        neo4j_driver=object(),
        chat_retriever=object(),
        agent=object(),
        answer_composer=object(),
        external_search_registry=None,
        external_deep_fetcher=None,
        graph_readiness_probe=probe,
    )

    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["graph_readiness"]["status"] == "unavailable"
    assert probe.calls == 1


@pytest.mark.asyncio
async def test_dashboard_status_actively_probes_graph_instead_of_trusting_driver_presence(monkeypatch):
    class Probe:
        async def probe(self, level="runtime", **_kwargs):
            return GraphReadiness(
                status="unavailable",
                level=level,
                checked_at=1.0,
                latency_ms=2.0,
                error_code="graph_connectivity_failed",
            )

    monkeypatch.setattr(server, "get_configured_search_providers", lambda: set())
    monkeypatch.setattr(server, "get_search_provider_api_keys", lambda: {})
    server.app.state.rag = server.RagState(
        vector_store=None,
        neo4j_driver=object(),
        chat_retriever=object(),
        agent=object(),
        answer_composer=object(),
        external_search_registry=None,
        external_deep_fetcher=None,
        graph_readiness_probe=Probe(),
    )

    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/dashboard/status")

    assert response.status_code == 200
    assert response.json()["neo4j_connected"] is False
    assert response.json()["graph_readiness"]["status"] == "unavailable"


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
async def test_public_chat_seam_preserves_a_to_e_execution_paths(monkeypatch):
    class Message:
        type = "ai"

        def __init__(self, content):
            self.content = content

    class Composer:
        async def ainvoke(self, payload, config=None):
            evidence_ids = list(dict.fromkeys(
                re.findall(r"\[(E\d+)\]", payload["messages"][0]["content"])
            ))
            return {"messages": [Message("有据回答。" + " ".join(
                f"[{evidence_id}]" for evidence_id in evidence_ids
            ))]}

    class NoReact:
        async def ainvoke(self, *_args, **_kwargs):
            raise AssertionError("resolved A-E routes must not enter ReAct")

    class Gateway:
        async def retrieve(self, request):
            contract = request.route_contract
            family = contract["primary_task_family"]
            mode = contract["answer_mode"]
            plan = analyze_query(request.question)
            if mode == "important_news":
                plan = replace(plan, intent="important_news", entities=["Claude"])
            elif mode == "trend_clusters":
                plan = replace(plan, intent="recent_trend")
            elif family == "temporal_relation_exploration":
                plan = replace(plan, graph_requirement="required")
            base = {
                "evidence_type": "internal",
                "date": "2026-08-21",
                "source": "Official",
                "title": "Primary evidence",
                "citation_id": "ATR-20260821-ONE001",
                "occurrence_id": "ATR-20260821-ONE001",
                "local_url": "#2026-08-21/ai-topic-radar/item/ATR-20260821-ONE001",
                "excerpt": "Primary evidence for the product-path test.",
            }
            records = [base]
            if family == "temporal_relation_exploration":
                records.append({
                    "evidence_type": "graph",
                    "content_type": "graph_reasoning",
                    "date": "2026-08-21",
                    "source": "Neo4j Graph",
                    "title": "Graph evidence",
                    "citation_id": "graph-reasoning/openai",
                    "excerpt": "Cross-date graph evidence.",
                })
            return EvidenceBundle(
                status="ready",
                task_family=family,
                records=records,
                analysis=plan,
                query_plan=plan.to_dict(),
                trace={"path": "public_chat_gate", "answer_mode": mode},
            )

    monkeypatch.setattr(server, "API_KEY", None)
    server.app.state.rag = server.RagState(
        vector_store=object(),
        neo4j_driver=None,
        chat_retriever=object(),
        agent=NoReact(),
        answer_composer=Composer(),
        external_search_registry=None,
        external_deep_fetcher=None,
        retrieval_gateway=Gateway(),
        query_contract_resolver=QueryRouteResolver(),
        latest_corpus_date="2026-08-21",
    )
    cases = (
        ("打开 ATR-20260805-99E550", "item_navigation", "deterministic_navigation", 0),
        ("Claude 最近有什么动态？", "trend_discovery", "deterministic_important_news", 0),
        ("最近有什么热门趋势？", "trend_discovery", "direct_composer", 1),
        ("OpenAI 的 Agent 战略过去三个月是如何演变的？", "temporal_relation_exploration", "direct_composer", 1),
        ("OpenAI 是否已经发布 GPT-6？", "claim_verification", "direct_composer", 1),
        ("用内部证据解释 Graph RAG 和 Agentic RAG 的区别", "evidence_research", "direct_composer", 1),
    )

    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        for index, (question, family, path, model_turns) in enumerate(cases, 1):
            response = await client.post(
                "/chat",
                json={"message": question},
                headers={"x-forwarded-for": f"198.51.100.{index}"},
            )
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["query_understanding"]["task_family"] == family
            assert body["tool_trace"]["execution_path"] == path
            assert body["tool_trace"]["execution_counts"]["model_turns"] == model_turns


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
