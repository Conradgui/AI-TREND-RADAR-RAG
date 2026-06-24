"""Run live vector-only chat benchmark for golden questions."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from rag.chat_service import build_chat_response
from rag.eval_golden import DEFAULT_GOLDEN_PATH, load_golden_questions, validate_golden_questions


DEFAULT_OUTPUT = Path("docs/rag-transformation/evals/live-chat-snapshot-2026-06-22.json")


async def build_live_chat_snapshot(questions: list[dict], limit: int | None = None) -> dict:
    """Run golden questions through vector-only chat and return snapshot data."""
    from rag.agent.llm import create_direct_llm_agent
    from rag.retriever.vector_only import VectorOnlyRetriever
    from rag.retriever.vector_store import VectorStore

    vector_store = VectorStore()
    retriever = VectorOnlyRetriever(vector_store)
    agent = create_direct_llm_agent()

    rows = []
    selected = questions[:limit] if limit else questions
    for item in selected:
        response = await build_chat_response(agent, retriever, item["question"], [])
        rows.append(
            {
                "id": item["id"],
                "question": item["question"],
                "expected_answerability": item["answerability"],
                "answer": response["answer"],
                "citation_count": len(response["citations"]),
                "citations": response["citations"],
                "query_understanding": response["query_understanding"],
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "vector-only",
        "total": len(rows),
        "rows": rows,
        "summary": summarize_live_chat_snapshot(rows),
    }


def summarize_live_chat_snapshot(rows: list[dict]) -> dict:
    """Summarize live chat benchmark output."""
    return {
        "total": len(rows),
        "with_citations": sum(1 for row in rows if row["citation_count"] > 0),
        "without_citations": sum(1 for row in rows if row["citation_count"] == 0),
        "needs_web_questions": sum(1 for row in rows if row["expected_answerability"] == "needs-web"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run live vector-only chat benchmark.")
    parser.add_argument("--path", type=Path, default=DEFAULT_GOLDEN_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    questions = load_golden_questions(args.path)
    errors = validate_golden_questions(questions)
    if errors:
        print(json.dumps({"errors": errors}, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    snapshot = asyncio.run(build_live_chat_snapshot(questions, limit=args.limit))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "summary": snapshot["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
