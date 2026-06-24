"""Hybrid retriever combining Neo4j graph search with ChromaDB vector search.
Uses Reciprocal Rank Fusion (RRF) to merge results from both sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rag.graphrag.driver import Neo4jDriver
    from rag.retriever.vector_store import VectorStore


@dataclass
class RetrievedChunk:
    text: str
    source: str  # "vector" or "graph"
    score: float
    metadata: dict = field(default_factory=dict)


class HybridRetriever:
    """Combines Neo4j graph traversal with ChromaDB vector similarity using RRF."""

    def __init__(self, vector_store: VectorStore, neo4j_driver: Neo4jDriver, rrf_k: int = 60):
        self.vector = vector_store
        self.neo4j = neo4j_driver
        self.rrf_k = rrf_k

    async def search(self, query: str, k: int = 5, where: dict | None = None) -> list[RetrievedChunk]:
        """Hybrid search: vector + graph, merge via Reciprocal Rank Fusion."""
        vector_results = self._safe_vector_search(query, k, where=where)
        graph_results = await self._safe_graph_search(query, k)

        # Reciprocal Rank Fusion — use full text as key to avoid hash collisions
        fused: dict[str, dict] = {}
        for rank, r in enumerate(vector_results):
            key = r.text
            if key not in fused:
                fused[key] = {"chunk": r, "score": 0.0}
            fused[key]["score"] += 1.0 / (self.rrf_k + rank + 1)

        for rank, r in enumerate(graph_results):
            key = r.text
            if key not in fused:
                fused[key] = {"chunk": r, "score": 0.0}
            fused[key]["score"] += 1.0 / (self.rrf_k + rank + 1)

        ranked = sorted(fused.values(), key=lambda x: x["score"], reverse=True)
        return [item["chunk"] for item in ranked[:k]]

    def _safe_vector_search(self, query: str, k: int, where: dict | None = None) -> list[RetrievedChunk]:
        try:
            hits = self.vector.search(query, k=k, where=where)
            return [
                RetrievedChunk(
                    text=hit["text"],
                    source="vector",
                    score=1.0 - (hit["distance"] or 0),
                    metadata=hit["metadata"],
                )
                for hit in hits
            ]
        except Exception as e:
            print(f"[hybrid] vector search failed: {e}")
            return []

    async def _safe_graph_search(self, query: str, k: int) -> list[RetrievedChunk]:
        try:
            hits = await self.neo4j.execute_query(
                "CALL db.index.fulltext.queryNodes('entity_search', $query) "
                "YIELD node, score "
                "MATCH (node)-[:MENTIONS]->(t:Topic)-[r:APPEARED_ON]->(d:DailyDigest) "
                "RETURN t.name AS topic, t.category AS category, t.totalScore AS totalScore, "
                "t.url AS topicUrl, t.source AS topicSource, t.summary AS topicSummary, "
                "r.url AS occurrenceUrl, r.source AS occurrenceSource, r.summary AS occurrenceSummary, "
                "r.reason AS occurrenceReason, r.evidence AS occurrenceEvidence, d.date AS date "
                "ORDER BY score DESC LIMIT $k",
                query=query,
                k=k,
            )
            return [
                RetrievedChunk(
                    text=_graph_hit_text(h),
                    source="graph",
                    score=float(h.get("totalScore", 0)),
                    metadata=_graph_hit_metadata(h),
                )
                for h in hits
            ]
        except Exception as e:
            print(f"[hybrid] graph search failed: {e}")
            return []


def _graph_hit_text(hit: dict) -> str:
    evidence = hit.get("occurrenceEvidence") or []
    if isinstance(evidence, list):
        evidence_text = "；".join(str(item) for item in evidence)
    else:
        evidence_text = str(evidence or "")
    pieces = [
        f"话题: {hit.get('topic', '')}",
        f"分类: {hit.get('category', '')}",
        f"分数: {hit.get('totalScore', '')}",
        f"摘要: {hit.get('occurrenceSummary') or hit.get('topicSummary') or ''}",
        f"推荐理由: {hit.get('occurrenceReason', '')}",
        f"证据: {evidence_text}",
    ]
    return " | ".join(piece for piece in pieces if piece.strip(" |"))


def _graph_hit_metadata(hit: dict) -> dict:
    date = hit.get("date", "")
    title = hit.get("topic", "")
    source = hit.get("occurrenceSource") or hit.get("topicSource") or "graph"
    evidence = hit.get("occurrenceEvidence") or []
    if isinstance(evidence, list):
        evidence_excerpt = "；".join(str(item) for item in evidence)
    else:
        evidence_excerpt = str(evidence or "")
    return {
        "content_type": "graph_topic",
        "date": date,
        "source": source,
        "title": title,
        "url": hit.get("occurrenceUrl") or hit.get("topicUrl") or "",
        "citation_id": f"{date}/graph-topic/{str(title).lower().strip()}",
        "excerpt": evidence_excerpt or hit.get("occurrenceSummary") or hit.get("topicSummary") or "",
        "category": hit.get("category", ""),
        "score": hit.get("totalScore", 0),
    }
