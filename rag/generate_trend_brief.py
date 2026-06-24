"""Generate a local-only Markdown trend brief."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from pathlib import Path

from rag.answer_policy import build_answer_policy, mark_external_evidence_used
from rag.citations import retrieve_citations
from rag.graph_question_planning import build_graph_question_plan
from rag.graph_reasoning_service import build_graph_reasoning_citation, build_graph_reasoning_evidence
from rag.query_understanding import analyze_query
from rag.retrieval_planning import build_metadata_filter, load_latest_corpus_date
from rag.search_provider_adapters import SearchProviderRegistry, SearchRequest
from rag.search_provider_routing import build_search_provider_route
from rag.source_review import build_source_review, classify_artifact_quality_status
from rag.source_relevance import inspect_trend_brief_source_relevance
from rag.tool_routing import infer_search_task_type
from rag.trend_brief import build_trend_brief_markdown, inspect_trend_brief_artifact, save_trend_brief, select_brief_citations


def build_generation_summary(
    *,
    output: str,
    topic: str,
    citation_count: int,
    external_citation_count: int = 0,
    evidence_type_counts: dict | None = None,
    has_graph_summary: bool,
    mode: str = "local-only",
    policy_mode: str,
    source_review: dict | None = None,
    artifact_consistency: dict | None = None,
    source_relevance: dict | None = None,
    external_search_trace: dict | None = None,
) -> dict:
    """Build the machine-readable CLI result summary."""
    source_review = source_review or {}
    return {
        "output": output,
        "topic": topic,
        "citation_count": citation_count,
        "external_citation_count": external_citation_count,
        "evidence_type_counts": evidence_type_counts or {},
        "has_graph_summary": has_graph_summary,
        "mode": mode,
        "policy_mode": policy_mode,
        "source_review_status": source_review.get("status", "unknown"),
        "artifact_quality_status": classify_artifact_quality_status(source_review),
        "artifact_consistency": artifact_consistency or {"consistent": False, "issues": ["not_checked"]},
        "source_relevance": source_relevance or {"relevance_status": "not_checked"},
        "external_search": external_search_trace or {"attempted": False, "citations": []},
    }


def build_trend_brief_external_search_requests(
    *,
    topic: str,
    plan,
    mode: str,
    configured_providers: set[str],
    max_external_citations: int = 3,
) -> list[SearchRequest]:
    """Build provider-routed external search requests for live trend briefs."""
    if mode != "live-external":
        return []

    task_type = infer_search_task_type(plan)
    route = build_search_provider_route(
        {"query": getattr(plan, "retrieval_query", topic), "task_type": task_type},
        configured_providers=configured_providers,
    )
    max_providers = route.get("budget_policy", {}).get("max_external_providers", 2)
    query = _build_trend_brief_external_query(topic, plan, task_type)
    return [
        SearchRequest(
            query=query,
            task_type=task_type,
            provider=provider,
            max_results=max_external_citations,
        )
        for provider in route.get("available_provider_chain", [])[:max_providers]
    ]


async def generate_trend_brief(
    *,
    topic: str,
    output_path: Path | None = None,
    max_internal_citations: int = 8,
    max_external_citations: int = 3,
    mode: str = "local-only",
) -> dict:
    """Generate and save a deterministic trend brief from local RAG evidence."""
    from rag.config import CHROMA_DIR, get_configured_search_providers, get_search_provider_api_keys
    from rag.graphrag.driver import Neo4jDriver
    from rag.retriever.hybrid import HybridRetriever
    from rag.retriever.vector_store import VectorStore

    question = f"最近 {topic} 领域有什么值得关注的新动向？"
    plan = analyze_query(question)
    latest_corpus_date = load_latest_corpus_date()
    where = build_metadata_filter(plan, latest_corpus_date)

    driver = Neo4jDriver()
    await driver.connect()
    try:
        retriever = HybridRetriever(VectorStore(CHROMA_DIR), driver)
        citations = await retrieve_citations(
            retriever,
            plan.retrieval_query,
            k=max_internal_citations,
            where=where,
        )
        if not citations and where:
            citations = await retrieve_citations(
                retriever,
                plan.retrieval_query,
                k=max_internal_citations,
                where=None,
            )

        graph_evidence = await _build_graph_evidence(driver, topic, plan)
        graph_citation = _graph_citation(graph_evidence)
        configured_providers = get_configured_search_providers()
        external_search_requests = build_trend_brief_external_search_requests(
            topic=topic,
            plan=plan,
            mode=mode,
            configured_providers=configured_providers,
            max_external_citations=max_external_citations,
        )
        external_search = await _search_external_evidence_for_brief(
            SearchProviderRegistry(get_search_provider_api_keys()),
            external_search_requests,
        )
        external_citations = external_search.get("citations", [])
        citations_for_policy = select_brief_citations(
            citations + ([graph_citation] if graph_citation else []) + external_citations,
            topic=topic,
        )
        answer_policy = build_answer_policy(plan, citations_for_policy)
        if external_citations:
            answer_policy = mark_external_evidence_used(answer_policy, external_citations)
        source_review = build_source_review(citations_for_policy)

        markdown = build_trend_brief_markdown(
            topic=topic,
            citations=citations_for_policy,
            graph_evidence=graph_evidence,
            source_review=source_review,
            answer_policy=answer_policy,
            latest_corpus_date=latest_corpus_date,
            mode=mode,
        )
        artifact_consistency = inspect_trend_brief_artifact(markdown)
        source_relevance = inspect_trend_brief_source_relevance(markdown, topic=topic)
        output = save_trend_brief(markdown, topic=topic, output_path=output_path)
    finally:
        await driver.close()

    return build_generation_summary(
        output=str(output),
        topic=topic,
        citation_count=len(citations_for_policy),
        external_citation_count=sum(
            1 for citation in citations_for_policy
            if citation.get("evidence_type") == "external"
        ),
        evidence_type_counts=dict(sorted(Counter(
            citation.get("evidence_type", "unknown")
            for citation in citations_for_policy
        ).items())),
        has_graph_summary=bool(graph_evidence),
        mode=mode,
        policy_mode=answer_policy.get("mode", "unknown"),
        source_review=source_review,
        artifact_consistency=artifact_consistency,
        source_relevance=source_relevance,
        external_search_trace=external_search,
    )


async def _build_graph_evidence(driver, topic: str, plan) -> dict | None:
    graph_question = f"请分析 {topic} 是否跨多个日期和来源反复出现，并给出图谱关系覆盖。"
    graph_plan = build_graph_question_plan(graph_question, query_plan=plan)
    if not graph_plan:
        return None
    try:
        return await build_graph_reasoning_evidence(driver, graph_plan)
    except Exception:
        return None


def _graph_citation(graph_evidence: dict | None) -> dict | None:
    if not graph_evidence:
        return None
    citation = build_graph_reasoning_citation(graph_evidence)
    citation["evidence_type"] = "graph"
    return citation


async def _search_external_evidence_for_brief(registry, requests: list[SearchRequest]) -> dict:
    if not requests:
        return {"attempted": False, "citations": []}

    attempts = []
    citations = []
    for request in requests:
        result = await registry.search(request)
        request_citations = result.get("citations", [])
        attempts.append({
            "provider": request.provider,
            "available": result.get("available", False),
            "citation_count": len(request_citations),
            "errors": result.get("errors", []),
        })
        citations.extend(request_citations)

    return {
        "attempted": True,
        "provider": next((attempt["provider"] for attempt in attempts if attempt["citation_count"]), None),
        "attempts": attempts,
        "citations": citations,
        "citation_count": len(citations),
    }


def _build_trend_brief_external_query(topic: str, plan, task_type: str) -> str:
    topics = list(getattr(plan, "topics", []) or [])
    entities = list(getattr(plan, "entities", []) or [])
    terms = [topic, *topics, *entities]
    if task_type == "research_paper":
        terms.extend(["survey", "benchmark", "retrieval augmented generation"])
    elif task_type == "github_repo":
        terms.extend(["AI", "trending repositories"])
    else:
        terms.extend(["latest updates", "primary sources", "retrieval augmented generation"])
    if topic.strip().casefold() == "rag":
        terms.extend(["arxiv", "benchmark", "evaluation", "graph rag", "agentic rag"])
    return _join_unique_terms(terms)


def _join_unique_terms(terms: list[str]) -> str:
    seen = set()
    result = []
    for term in terms:
        cleaned = str(term or "").strip()
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return " ".join(result)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a local-only AI trend brief.")
    parser.add_argument("--topic", default="RAG")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--max-internal-citations", type=int, default=8)
    parser.add_argument("--max-external-citations", type=int, default=3)
    parser.add_argument("--mode", choices=["local-only", "live-external"], default="local-only")
    args = parser.parse_args()

    summary = asyncio.run(
        generate_trend_brief(
            topic=args.topic,
            output_path=args.output,
            max_internal_citations=args.max_internal_citations,
            max_external_citations=args.max_external_citations,
            mode=args.mode,
        )
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
