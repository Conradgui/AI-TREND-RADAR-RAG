"""Run local-only hybrid structural chat benchmark for golden questions."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from rag.chat_service import build_chat_response
from rag.config import CHROMA_DIR
from rag.eval_golden import DEFAULT_GOLDEN_PATH, load_golden_questions, validate_golden_questions


DEFAULT_OUTPUT = Path("docs/rag-transformation/evals/hybrid-structural-chat-snapshot-2026-06-24-q12.json")


class StructuralMessage:
    type = "ai"

    def __init__(self, content: str):
        self.content = content


class StructuralAgent:
    """Local fake agent that avoids sending retrieved evidence to external LLMs."""

    async def ainvoke(self, payload):
        return {"messages": [StructuralMessage("结构性评测占位回答：仅用于验证检索、引用和策略链路。")]}


async def build_hybrid_structural_chat_snapshot(questions: list[dict], limit: int | None = None) -> dict:
    """Run questions through local hybrid retrieval and chat wiring without external LLM/search."""
    from rag.graphrag.driver import Neo4jDriver
    from rag.retriever.hybrid import HybridRetriever
    from rag.retriever.vector_store import VectorStore

    driver = Neo4jDriver()
    await driver.connect()
    try:
        retriever = HybridRetriever(VectorStore(CHROMA_DIR), driver)
        agent = StructuralAgent()
        rows = []
        selected = questions[:limit] if limit else questions
        for item in selected:
            response = await build_chat_response(
                agent,
                retriever,
                item["question"],
                [],
                external_search_registry=None,
                configured_search_providers=set(),
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
        "mode": "hybrid_structural_local_only",
        "total": len(rows),
        "rows": rows,
        "summary": summarize_hybrid_structural_rows(rows),
    }


def summarize_hybrid_structural_rows(rows: list[dict]) -> dict:
    """Summarize local structural benchmark rows."""
    policy_modes = Counter()
    for row in rows:
        policy_modes.update([row.get("query_understanding", {}).get("answer_policy", {}).get("mode", "unknown")])
    return {
        "total": len(rows),
        "with_citations": sum(1 for row in rows if row["citation_count"] > 0),
        "with_graph_citations": sum(1 for row in rows if _has_graph_citation(row)),
        "with_external_citations": sum(1 for row in rows if _has_external_citation(row)),
        "needs_web_questions": sum(1 for row in rows if row["expected_answerability"] == "needs-web"),
        "evidence_sufficiency_review": sum(
            1
            for row in rows
            if row.get("query_understanding", {}).get("answer_policy", {}).get("mode") == "evidence_sufficiency_review"
        ),
        "answer_policy_modes": dict(sorted(policy_modes.items())),
    }


def _has_graph_citation(row: dict) -> bool:
    return any("/graph-topic/" in citation.get("citation_id", "") for citation in row.get("citations", []))


def _has_external_citation(row: dict) -> bool:
    return any(citation.get("evidence_type") == "external" for citation in row.get("citations", []))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local-only hybrid structural chat benchmark.")
    parser.add_argument("--path", type=Path, default=DEFAULT_GOLDEN_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    questions = load_golden_questions(args.path)
    errors = validate_golden_questions(questions)
    if errors:
        print(json.dumps({"errors": errors}, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    snapshot = asyncio.run(build_hybrid_structural_chat_snapshot(questions, limit=args.limit))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "summary": snapshot["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
