"""Hybrid retriever combining Neo4j graph search with ChromaDB vector search.
Uses Reciprocal Rank Fusion (RRF) to merge results from both sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
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


# 来源质量权重
SOURCE_QUALITY_WEIGHTS = {
    "official": 1.0,      # 官方文档、公告
    "primary": 0.8,       # 论文、仓库
    "high-signal": 0.6,   # 技术博客、分析
    "secondary": 0.4,     # 新闻、社交媒体
    "weak": 0.2,          # 未验证、低质量
}

# 来源质量映射
SOURCE_QUALITY_MAP = {
    "GitHub": "primary",
    "arxiv": "primary",
    "HuggingFace": "primary",
    "Product Hunt": "secondary",
    "Hacker News": "secondary",
    "Dev.to": "high-signal",
    "InfoQ": "high-signal",
    "掘金": "high-signal",
    "36氪": "secondary",
    "开源中国": "high-signal",
    "Lobsters": "high-signal",
}


class HybridRetriever:
    """Combines Neo4j graph traversal with ChromaDB vector similarity using RRF."""

    def __init__(self, vector_store: VectorStore, neo4j_driver: Neo4jDriver, rrf_k: int = 60):
        self.vector = vector_store
        self.neo4j = neo4j_driver
        self.rrf_k = rrf_k

    @staticmethod
    def _dedup_key(chunk: RetrievedChunk) -> str:
        """G-3 修复：生成 RRF 去重 key。
        优先使用 citation_id（结构化唯一标识），若缺失则回退到 title+date+source 组合。
        不再使用全文字符串作 key，避免语义近似但文本微调的条目无法合并。
        """
        meta = chunk.metadata
        citation_id = meta.get("citation_id")
        if citation_id:
            return str(citation_id).strip().lower()
        # 回退：title + date + source 组合
        title = str(meta.get("title", "")).strip().lower()
        date = str(meta.get("date", "")).strip()
        source = str(meta.get("source", "")).strip().lower()
        return f"{title}|{date}|{source}"

    async def search(self, query: str, k: int = 5, where: dict | None = None) -> list[RetrievedChunk]:
        """Hybrid search: vector + graph, merge via Reciprocal Rank Fusion."""
        vector_results = self._safe_vector_search(query, k, where=where)
        graph_results = await self._safe_graph_search(query, k)

        # Reciprocal Rank Fusion — G-3 修复：用 citation_id 或 title+date+source 作去重 key，
        # 替代原来的全文字符串，使语义近似但文本不完全相同的条目能正确合并
        fused: dict[str, dict] = {}
        for rank, r in enumerate(vector_results):
            key = self._dedup_key(r)
            if key not in fused:
                fused[key] = {"chunk": r, "score": 0.0}
            fused[key]["score"] += 1.0 / (self.rrf_k + rank + 1)

        for rank, r in enumerate(graph_results):
            key = self._dedup_key(r)
            if key not in fused:
                fused[key] = {"chunk": r, "score": 0.0}
            fused[key]["score"] += 1.0 / (self.rrf_k + rank + 1)

        ranked = sorted(fused.values(), key=lambda x: x["score"], reverse=True)
        results = [item["chunk"] for item in ranked[:k]]

        # 应用确定性重排
        results = self._apply_deterministic_reranking(results, query)

        return results

    def _apply_deterministic_reranking(self, chunks: list[RetrievedChunk], query: str) -> list[RetrievedChunk]:
        """应用确定性重排策略"""
        for chunk in chunks:
            # 计算来源质量分数
            source = chunk.metadata.get("source", "")
            quality_tier = SOURCE_QUALITY_MAP.get(source, "secondary")
            quality_weight = SOURCE_QUALITY_WEIGHTS.get(quality_tier, 0.4)

            # 计算新鲜度分数
            freshness_score = self._calculate_freshness_score(chunk.metadata.get("date", ""))

            # 计算相关性分数（基于文本匹配）
            relevance_score = self._calculate_relevance_score(chunk.text, query)

            # 综合评分：RRF分数 * 来源质量 * 新鲜度 * 相关性
            chunk.score = chunk.score * quality_weight * freshness_score * relevance_score

        # 重新排序
        chunks.sort(key=lambda x: x.score, reverse=True)
        return chunks

    def _calculate_freshness_score(self, date_str: str) -> float:
        """计算新鲜度分数"""
        if not date_str:
            return 0.5  # 无日期信息，中等分数

        try:
            doc_date = datetime.strptime(date_str, "%Y-%m-%d")
            days_old = (datetime.now() - doc_date).days

            # 7天内：1.0，30天内：0.8，90天内：0.6，更老：0.4
            if days_old <= 7:
                return 1.0
            elif days_old <= 30:
                return 0.8
            elif days_old <= 90:
                return 0.6
            else:
                return 0.4
        except ValueError:
            return 0.5

    def _calculate_relevance_score(self, text: str, query: str) -> float:
        """计算相关性分数（简单的关键词匹配）"""
        if not query or not text:
            return 0.5

        # 提取查询关键词
        query_words = set(query.lower().split())
        text_words = set(text.lower().split())

        # 计算匹配比例
        if not query_words:
            return 0.5

        matches = query_words.intersection(text_words)
        return len(matches) / len(query_words)

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
            # 修复 G-1：在全文索引后立即截断节点数量，避免 MATCH 展开导致中间结果爆炸
            # 1. 全文索引返回节点 → 2. 按 score 排序并 LIMIT 截断 → 3. 再展开路径 → 4. 最终 LIMIT
            hits = await self.neo4j.execute_query(
                "CALL db.index.fulltext.queryNodes('entity_search', $query) "
                "YIELD node, score "
                # 步骤 1-2：先按相关性分数截断全文索引节点，限制后续展开的基数
                "WITH node, score ORDER BY score DESC LIMIT $k "
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
