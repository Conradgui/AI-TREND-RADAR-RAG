"""Run one live chat smoke with external search and URL deep fetch enabled."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from rag.config import get_search_provider_api_keys
from rag.runtime_tools import select_external_deep_fetcher


DEFAULT_OUTPUT = Path("docs/rag-transformation/evals/deep-fetch-live-smoke-2026-06-23.json")
DEFAULT_QUESTION = (
    "比如最近 Google 出了一个 OKF，它与之前提出的 ALM Wiki 知识框架有什么关系？"
    "既然是 Google 提出来的，它整体的核心思想是什么？在提升用户偏好效率方面表现如何？"
)


async def build_deep_fetch_live_smoke(question: str) -> dict:
    """Run one vector-only chat response with external search and live deep fetch."""
    from rag.agent.llm import create_direct_llm_agent
    from rag.chat_service import build_chat_response
    from rag.retriever.vector_only import VectorOnlyRetriever
    from rag.retriever.vector_store import VectorStore
    from rag.search_provider_adapters import SearchProviderRegistry

    vector_store = VectorStore()
    retriever = VectorOnlyRetriever(vector_store)
    agent = create_direct_llm_agent()
    registry = SearchProviderRegistry(get_search_provider_api_keys())
    response = await build_chat_response(
        agent,
        retriever,
        question,
        [],
        external_search_registry=registry,
        external_deep_fetcher=select_external_deep_fetcher(True),
    )
    citations = response["citations"]
    deep_fetch = response["query_understanding"].get("deep_fetch", {})
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "question": question,
        "answer": response["answer"],
        "citation_count": len(citations),
        "internal_citation_count": sum(1 for citation in citations if citation.get("evidence_type", "internal") == "internal"),
        "external_citation_count": sum(1 for citation in citations if citation.get("evidence_type") == "external"),
        "deep_fetch": deep_fetch,
        "query_understanding": response["query_understanding"],
        "citations": citations,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one live external-evidence chat smoke with URL deep fetch.")
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    smoke = asyncio.run(build_deep_fetch_live_smoke(args.question))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(smoke, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "citation_count": smoke["citation_count"],
                "internal_citation_count": smoke["internal_citation_count"],
                "external_citation_count": smoke["external_citation_count"],
                "answer_policy_mode": smoke["query_understanding"]["answer_policy"]["mode"],
                "external_search_attempted": smoke["query_understanding"]["external_search"].get("attempted"),
                "deep_fetch_attempted": smoke["deep_fetch"].get("attempted"),
                "deep_fetch_selected_count": smoke["deep_fetch"].get("selected_count"),
                "deep_fetch_success_count": smoke["deep_fetch"].get("success_count"),
                "deep_fetch_failure_count": smoke["deep_fetch"].get("failure_count"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
