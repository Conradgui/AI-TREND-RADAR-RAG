"""Vector-only retriever adapter used when graph retrieval is unavailable."""

from __future__ import annotations

from rag.retriever.hybrid import RetrievedChunk
from rag.retriever.vector_store import VectorStore


class VectorOnlyRetriever:
    """Async retriever adapter for ChromaDB-only retrieval."""

    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store

    async def search(self, query: str, k: int = 5, where: dict | None = None) -> list[RetrievedChunk]:
        hits = self.vector_store.search(query, k=k, where=where)
        return [
            RetrievedChunk(
                text=hit["text"],
                source="vector",
                score=1.0 - (hit["distance"] or 0),
                metadata=hit["metadata"],
            )
            for hit in hits
        ]
