"""Citation helpers for grounding chat answers in retrieval metadata."""

from __future__ import annotations

import re


REQUIRED_CITATION_FIELDS = ("date", "source", "title", "citation_id")


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

        for optional_field in ("url", "score", "category"):
            value = metadata.get(optional_field)
            if value not in (None, ""):
                citation[optional_field] = value

        citations.append(citation)
        source_counts[source] = source_counts.get(source, 0) + 1

        if len(citations) >= max_citations:
            break

    return citations


async def retrieve_citations(retriever, question: str, k: int = 10, where: dict | None = None) -> list[dict]:
    """Retrieve citation candidates from the corpus retriever."""
    try:
        chunks = await retriever.search(question, k=k, where=where)
    except Exception:
        return []
    return build_citations(chunks, max_citations=k)


def evidence_insufficient_answer(question: str) -> str:
    """Return a conservative answer when no usable retrieval evidence exists."""
    return (
        "我在当前 AI Trend Radar RAG 知识库中没有找到足够可靠的证据来回答这个问题。\n\n"
        f"问题：{question}\n\n"
        "为了避免编造结论，我建议先补充语料、扩大检索范围，或在后续启用明确标注为外部来源的联网搜索。"
    )
