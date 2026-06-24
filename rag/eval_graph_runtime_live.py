"""Run live Neo4j + hybrid retrieval smoke checks."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from rag.citations import retrieve_citations
from rag.config import CHROMA_DIR
from rag.graphrag.driver import Neo4jDriver
from rag.retriever.hybrid import HybridRetriever
from rag.retriever.vector_store import VectorStore


DEFAULT_OUTPUT = Path("docs/rag-transformation/evals/graph-runtime-live-smoke-2026-06-23.json")


async def build_graph_runtime_live_smoke(query: str) -> dict:
    """Verify Neo4j graph data and hybrid retrieval with citation-ready results."""
    driver = Neo4jDriver()
    await driver.connect()
    try:
        node_counts = await driver.execute_query(
            "MATCH (n) RETURN labels(n) AS labels, count(n) AS count ORDER BY count DESC"
        )
        relationship_counts = await driver.execute_query(
            "MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS count ORDER BY count DESC"
        )
        indexes = await driver.execute_query(
            "SHOW INDEXES YIELD name, type, state RETURN name, type, state ORDER BY name"
        )
        retriever = HybridRetriever(VectorStore(CHROMA_DIR), driver)
        citations = await retrieve_citations(retriever, query, k=8)
    finally:
        await driver.close()

    graph_citations = [
        citation for citation in citations
        if "/graph-topic/" in citation.get("citation_id", "")
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "query": query,
        "node_counts": node_counts,
        "relationship_counts": relationship_counts,
        "indexes": indexes,
        "citation_count": len(citations),
        "graph_citation_count": len(graph_citations),
        "first_citations": citations[:8],
        "passed": bool(node_counts and relationship_counts and graph_citations),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run live Graph RAG runtime smoke.")
    parser.add_argument("--query", default="Agentic RAG")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    smoke = asyncio.run(build_graph_runtime_live_smoke(args.query))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(smoke, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "passed": smoke["passed"],
                "node_counts": smoke["node_counts"][:5],
                "relationship_counts": smoke["relationship_counts"][:5],
                "citation_count": smoke["citation_count"],
                "graph_citation_count": smoke["graph_citation_count"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
