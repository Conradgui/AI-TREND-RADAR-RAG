"""Vector-only retriever adapter used when graph retrieval is unavailable."""

from __future__ import annotations

from rag.retriever.hybrid import (
    ChannelOutcome,
    HybridRetriever,
    HybridSearchOutcome,
    RetrievedChunk,
    RetrievalFailure,
)
from rag.retriever.vector_store import VectorStore


class VectorOnlyRetriever:
    """Async retriever adapter for ChromaDB-only retrieval."""

    def __init__(self, vector_store: VectorStore, lexical_store=None, rrf_k: int = 60):
        self.vector_store = vector_store
        self.lexical_store = lexical_store
        self.rrf_k = rrf_k

    async def search(self, query: str, k: int = 5, where: dict | None = None) -> list[RetrievedChunk]:
        outcome = await self.search_with_status(query, k=k, where=where)
        if outcome.status in {"error", "timeout"}:
            raise RetrievalFailure(outcome.error_code)
        return outcome.chunks

    async def search_with_status(
        self,
        query: str,
        k: int = 5,
        where: dict | None = None,
        graph_requirement: str = "disabled",
    ) -> HybridSearchOutcome:
        try:
            vector_hits = self.vector_store.search(query, k=k, where=where)
            vector_chunks = self._vector_chunks(vector_hits)
            vector = ChannelOutcome("success" if vector_chunks else "empty", vector_chunks)
        except Exception as exc:
            vector = ChannelOutcome("error", error_code=type(exc).__name__)

        if self.lexical_store is None:
            lexical = ChannelOutcome("disabled")
        else:
            try:
                lexical_hits = self.lexical_store.search(query, k=k, where=where)
                lexical_chunks = [
                    RetrievedChunk(
                        text=hit["text"],
                        source="lexical",
                        score=0.0,
                        metadata={
                            **hit["metadata"],
                            "lexical_match_type": hit.get("match_type", "lexical"),
                            "lexical_score": hit.get("lexical_score", 0.0),
                        },
                    )
                    for hit in lexical_hits
                ]
                lexical = ChannelOutcome("success" if lexical_chunks else "empty", lexical_chunks)
            except Exception as exc:
                lexical = ChannelOutcome("error", error_code=type(exc).__name__)

        channels = {"lexical": lexical, "vector": vector, "graph": ChannelOutcome("disabled")}
        failed = [item for item in (lexical, vector) if item.status in {"error", "timeout"}]
        operational = [item for item in (lexical, vector) if item.status in {"success", "empty"}]
        chunks = HybridRetriever._fuse_rrf(
            vector.chunks,
            lexical.chunks,
            rrf_k=self.rrf_k,
        )[:k]
        if failed and not operational:
            status = "error"
            error_code = "all_channels_failed"
        elif failed:
            status = "degraded"
            error_code = ",".join(item.error_code for item in failed if item.error_code)
        else:
            status = "ready" if chunks else "empty"
            error_code = ""
        return HybridSearchOutcome(status, chunks, channels, error_code)

    @staticmethod
    def _vector_chunks(hits: list[dict]) -> list[RetrievedChunk]:
        chunks = [
            RetrievedChunk(
                text=hit["text"],
                source="vector",
                score=1.0 - (hit["distance"] or 0),
                metadata=hit["metadata"],
            )
            for hit in hits
        ]
        for chunk in chunks:
            chunk.metadata["vector_similarity"] = chunk.score
        return chunks
