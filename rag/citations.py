"""Citation helpers for grounding chat answers in retrieval metadata."""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from datetime import date


REQUIRED_CITATION_FIELDS = ("date", "source", "title", "citation_id")


@dataclass(frozen=True)
class RetrievalOutcome:
    status: str
    citations: list[dict]
    error_code: str = ""
    elapsed_ms: float = 0.0


def _chunk_metadata(chunk) -> dict:
    if isinstance(chunk, dict):
        return chunk.get("metadata") or {}
    return getattr(chunk, "metadata", {}) or {}


def _chunk_text(chunk) -> str:
    if isinstance(chunk, dict):
        return chunk.get("text") or ""
    return getattr(chunk, "text", "") or ""


def _clean_excerpt(text: str, limit: int) -> str:
    excerpt = str(text).strip()
    return excerpt[:limit]


def _semantic_citation_key(metadata: dict) -> str:
    raw = "|".join(str(metadata.get(field, "")) for field in ("title", "source", "url"))
    return re.sub(r"\s+", " ", raw.casefold()).strip()


def build_citations(chunks: list, max_citations: int = 15, excerpt_chars: int = 240) -> list[dict]:
    """Build citations from retrieved chunks without asking the LLM to invent them."""
    citations = []
    seen = set()
    seen_semantic = set()
    source_counts = {}  # 用于多样性检查

    for chunk in chunks:
        metadata = _chunk_metadata(chunk)
        if not all(metadata.get(field) for field in REQUIRED_CITATION_FIELDS):
            continue

        citation_id = str(metadata["citation_id"])
        semantic_key = _semantic_citation_key(metadata)
        if citation_id in seen or semantic_key in seen_semantic:
            continue
        seen.add(citation_id)
        seen_semantic.add(semantic_key)

        # 多样性检查：限制单一来源的引用数量
        source = metadata.get("source", "unknown")
        if source_counts.get(source, 0) >= 2:  # 每个来源最多2个引用
            continue

        excerpt = metadata.get("evidence") or _chunk_text(chunk)
        citation = {
            "evidence_type": "internal",
            "date": metadata["date"],
            "source": metadata["source"],
            "title": metadata["title"],
            "citation_id": citation_id,
            "excerpt": _clean_excerpt(excerpt, excerpt_chars),
        }

        for optional_field in ("url", "score", "category", "entities"):
            value = metadata.get(optional_field)
            if value not in (None, ""):
                citation[optional_field] = value

        citations.append(citation)
        source_counts[source] = source_counts.get(source, 0) + 1

        if len(citations) >= max_citations:
            break

    return citations


async def retrieve_citations(
    retriever,
    question: str,
    k: int = 10,
    where: dict | None = None,
    *,
    prefer_recent: bool = False,
    latest_date: str | None = None,
) -> list[dict]:
    """Backward-compatible citation-only retrieval interface."""
    outcome = await retrieve_citations_with_status(
        retriever,
        question,
        k=k,
        where=where,
        prefer_recent=prefer_recent,
        latest_date=latest_date,
    )
    return outcome.citations


async def retrieve_citations_with_status(
    retriever,
    question: str,
    k: int = 10,
    where: dict | None = None,
    *,
    prefer_recent: bool = False,
    latest_date: str | None = None,
) -> RetrievalOutcome:
    """Retrieve citations without confusing empty results with system failure.

    The retriever's order remains the relevance proxy. Recent questions inspect a
    wider bounded pool, then blend that rank with document age before admitting
    at most ``k`` citation-ready records.
    """
    started_at = time.perf_counter()
    try:
        candidate_k = min(max(k * 3, k), 30) if prefer_recent else k
        chunks = await retriever.search(question, k=candidate_k, where=where)
    except asyncio.TimeoutError:
        return RetrievalOutcome(
            status="timeout",
            citations=[],
            error_code="timeout",
            elapsed_ms=(time.perf_counter() - started_at) * 1000,
        )
    except Exception as exc:
        return RetrievalOutcome(
            status="error",
            citations=[],
            error_code=type(exc).__name__,
            elapsed_ms=(time.perf_counter() - started_at) * 1000,
        )
    if prefer_recent:
        chunks = _rerank_recent_chunks(chunks, latest_date)
    citations = build_citations(chunks, max_citations=k)
    return RetrievalOutcome(
        status="ready" if citations else "empty",
        citations=citations,
        elapsed_ms=(time.perf_counter() - started_at) * 1000,
    )


def _rerank_recent_chunks(chunks: list, latest_date: str | None) -> list:
    """Blend original retrieval rank with age for explicitly recent questions."""
    if len(chunks) < 2:
        return chunks

    dated_chunks = []
    for chunk in chunks:
        value = _chunk_metadata(chunk).get("date")
        try:
            parsed = date.fromisoformat(str(value))
        except (TypeError, ValueError):
            parsed = None
        dated_chunks.append(parsed)

    try:
        newest = date.fromisoformat(latest_date) if latest_date else None
    except ValueError:
        newest = None
    newest = newest or max((value for value in dated_chunks if value), default=None)
    if newest is None:
        return chunks

    pool_size = len(chunks)
    scored = []
    for index, (chunk, chunk_date) in enumerate(zip(chunks, dated_chunks)):
        relevance = 1.0 - (index / pool_size)
        if chunk_date is None:
            freshness = 0.0
        else:
            age_days = max(0, (newest - chunk_date).days)
            freshness = max(0.0, 1.0 - (age_days / 14.0))
        score = 0.45 * relevance + 0.55 * freshness
        scored.append((score, index, chunk))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in scored]


def evidence_insufficient_answer(question: str) -> str:
    """Return a conservative answer when no usable retrieval evidence exists."""
    return (
        "我在当前 AI Trend Radar RAG 知识库中没有找到足够可靠的证据来回答这个问题。\n\n"
        f"问题：{question}\n\n"
        "为了避免编造结论，我建议先补充语料、扩大检索范围，或在后续启用明确标注为外部来源的联网搜索。"
    )
