"""Run live hybrid Neo4j + Chroma chat benchmark for golden questions."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from rag.chat_service import build_chat_response
from rag.config import CHROMA_DIR
from rag.eval_golden import DEFAULT_GOLDEN_PATH, load_golden_questions, validate_golden_questions
from rag.graphrag.driver import Neo4jDriver
from rag.retriever.hybrid import HybridRetriever
from rag.retriever.vector_store import VectorStore


DEFAULT_OUTPUT = Path("docs/rag-transformation/evals/hybrid-live-chat-snapshot-2026-06-23.json")


async def build_hybrid_live_chat_snapshot(questions: list[dict], limit: int | None = None) -> dict:
    """Run golden questions through hybrid Graph RAG chat and return snapshot data."""
    from rag.agent.llm import create_direct_llm_agent
    from rag.search_provider_adapters import SearchProviderRegistry
    from rag.config import get_search_provider_api_keys

    driver = Neo4jDriver()
    await driver.connect()
    try:
        retriever = HybridRetriever(VectorStore(CHROMA_DIR), driver)
        agent = create_direct_llm_agent()
        registry = SearchProviderRegistry(get_search_provider_api_keys())
        rows = []
        selected = questions[:limit] if limit else questions
        for item in selected:
            response = await build_chat_response(
                agent,
                retriever,
                item["question"],
                [],
                external_search_registry=registry,
            )
            rows.append({
                "id": item["id"],
                "question": item["question"],
                "expected_answerability": item["answerability"],
                "answer": response["answer"],
                "citation_count": len(response["citations"]),
                "citations": response["citations"],
                "query_understanding": response["query_understanding"],
            })
    finally:
        await driver.close()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "hybrid",
        "total": len(rows),
        "rows": rows,
        "summary": {
            "total": len(rows),
            "with_citations": sum(1 for row in rows if row["citation_count"] > 0),
            "with_graph_citations": sum(1 for row in rows if _has_graph_citation(row)),
            "with_external_citations": sum(1 for row in rows if _has_external_citation(row)),
            "needs_web_questions": sum(1 for row in rows if row["expected_answerability"] == "needs-web"),
        },
    }


def _has_graph_citation(row: dict) -> bool:
    return any("/graph-topic/" in citation.get("citation_id", "") for citation in row.get("citations", []))


def _has_external_citation(row: dict) -> bool:
    return any(citation.get("evidence_type") == "external" for citation in row.get("citations", []))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run live hybrid Graph RAG chat benchmark.")
    parser.add_argument("--path", type=Path, default=DEFAULT_GOLDEN_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    questions = load_golden_questions(args.path)
    errors = validate_golden_questions(questions)
    if errors:
        print(json.dumps({"errors": errors}, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    snapshot = asyncio.run(build_hybrid_live_chat_snapshot(questions, limit=args.limit))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "summary": snapshot["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
