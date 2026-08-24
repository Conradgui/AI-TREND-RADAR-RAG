"""Hybrid retriever combining Neo4j graph search with ChromaDB vector search.
Uses Reciprocal Rank Fusion (RRF) to merge results from both sources."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from rag.retriever.lexical_store import metadata_matches_filter

if TYPE_CHECKING:
    from rag.graphrag.driver import Neo4jDriver
    from rag.retriever.vector_store import VectorStore


@dataclass
class RetrievedChunk:
    text: str
    source: str  # "vector" or "graph"
    score: float
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ChannelOutcome:
    """One retrieval channel result without confusing failure with no matches."""

    status: str
    chunks: list[RetrievedChunk] = field(default_factory=list)
    error_code: str = ""


@dataclass(frozen=True)
class HybridSearchOutcome:
    """Merged retrieval result plus auditable per-channel health."""

    status: str
    chunks: list[RetrievedChunk] = field(default_factory=list)
    channels: dict[str, ChannelOutcome] = field(default_factory=dict)
    error_code: str = ""


class RetrievalFailure(RuntimeError):
    """Raised by the legacy list-only interface when retrieval is unusable."""

    def __init__(self, error_code: str):
        super().__init__(error_code or "retrieval_failed")
        self.error_code = error_code or "retrieval_failed"


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

    def __init__(
        self,
        vector_store: VectorStore,
        neo4j_driver: Neo4jDriver,
        lexical_store=None,
        rrf_k: int = 60,
    ):
        self.vector = vector_store
        self.neo4j = neo4j_driver
        self.lexical = lexical_store
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

    @classmethod
    def _fuse_rrf(
        cls,
        *result_lists: list[RetrievedChunk],
        rrf_k: int,
    ) -> list[RetrievedChunk]:
        """Fuse channel ranks and replace incomparable channel raw scores."""
        fused: dict[str, dict] = {}
        for results in result_lists:
            for rank, chunk in enumerate(results):
                key = cls._dedup_key(chunk)
                if key not in fused:
                    fused[key] = {"chunk": chunk, "score": 0.0}
                else:
                    fused[key]["chunk"].metadata.update(
                        {key: value for key, value in chunk.metadata.items() if value not in (None, "")}
                    )
                fused[key]["score"] += 1.0 / (rrf_k + rank + 1)

        ranked = sorted(fused.values(), key=lambda item: item["score"], reverse=True)
        for item in ranked:
            item["chunk"].score = item["score"]
            if item["chunk"].metadata.get("lexical_match_type") == "exact_title":
                item["chunk"].score += 1.0 / (rrf_k + 1)
            item["chunk"].metadata["fusion_score"] = item["chunk"].score
        ranked.sort(key=lambda item: item["chunk"].score, reverse=True)
        return [item["chunk"] for item in ranked]

    async def search(
        self,
        query: str,
        k: int = 5,
        where: dict | None = None,
        graph_requirement: str = "optional",
    ) -> list[RetrievedChunk]:
        """Backward-compatible list interface that never masks an unusable search."""
        outcome = await self.search_with_status(
            query,
            k=k,
            where=where,
            graph_requirement=graph_requirement,
        )
        if outcome.status in {"error", "timeout", "partial_error"} or (outcome.status == "degraded" and not outcome.chunks):
            raise RetrievalFailure(outcome.error_code)
        return outcome.chunks

    async def search_with_status(
        self,
        query: str,
        k: int = 5,
        where: dict | None = None,
        graph_requirement: str = "optional",
    ) -> HybridSearchOutcome:
        """Hybrid search with channel-level success, empty, error and timeout states."""
        vector = self._vector_search_outcome(query, k, where=where)
        lexical = self._lexical_search_outcome(query, k, where=where)
        graph = (
            ChannelOutcome(status="disabled")
            if graph_requirement == "disabled"
            else await self._graph_search_outcome(query, k, where=where)
        )
        channels = {"lexical": lexical, "vector": vector, "graph": graph}
        lexical_results = lexical.chunks
        vector_results = vector.chunks
        graph_results = graph.chunks

        # Reciprocal Rank Fusion — G-3 修复：用 citation_id 或 title+date+source 作去重 key，
        # 替代原来的全文字符串，使语义近似但文本不完全相同的条目能正确合并
        results = self._fuse_rrf(
            vector_results,
            lexical_results,
            graph_results,
            rrf_k=self.rrf_k,
        )[:k]

        # 应用确定性重排
        results = self._apply_deterministic_reranking(results, query)

        failed = [outcome for outcome in channels.values() if outcome.status in {"error", "timeout"}]
        operational = [outcome for outcome in channels.values() if outcome.status in {"success", "empty"}]
        error_code = ",".join(
            outcome.error_code for outcome in failed if outcome.error_code
        )
        graph_failed = graph.status in {"error", "timeout"}
        if graph_requirement == "required" and graph_failed:
            status = "partial_error"
            error_code = "required_graph_unavailable"
        elif failed and not operational:
            status = "timeout" if all(outcome.status == "timeout" for outcome in failed) else "error"
            error_code = "all_channels_failed"
        elif failed:
            status = "degraded"
        else:
            status = "ready" if results else "empty"
        return HybridSearchOutcome(
            status=status,
            chunks=results,
            channels=channels,
            error_code=error_code,
        )

    def _apply_deterministic_reranking(self, chunks: list[RetrievedChunk], query: str) -> list[RetrievedChunk]:
        """应用确定性重排策略"""
        for chunk in chunks:
            # 计算来源质量分数
            source = chunk.metadata.get("source", "")
            quality_tier = SOURCE_QUALITY_MAP.get(source, "secondary")
            quality_weight = SOURCE_QUALITY_WEIGHTS.get(quality_tier, 0.4)

            # 计算新鲜度分数
            freshness_score = self._calculate_freshness_score(
                chunk.metadata.get("effective_date") or chunk.metadata.get("date", "")
            )

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

    def _vector_search_outcome(self, query: str, k: int, where: dict | None = None) -> ChannelOutcome:
        try:
            hits = self.vector.search(query, k=k, where=where)
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
            return ChannelOutcome(status="success" if chunks else "empty", chunks=chunks)
        except asyncio.TimeoutError:
            return ChannelOutcome(status="timeout", error_code="vector_timeout")
        except Exception as e:
            print(f"[hybrid] vector search failed: {e}")
            return ChannelOutcome(status="error", error_code=type(e).__name__)

    def _lexical_search_outcome(self, query: str, k: int, where: dict | None = None) -> ChannelOutcome:
        if self.lexical is None:
            return ChannelOutcome(status="disabled")
        try:
            hits = self.lexical.search(query, k=k, where=where)
            chunks = [
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
                for hit in hits
            ]
            return ChannelOutcome(status="success" if chunks else "empty", chunks=chunks)
        except asyncio.TimeoutError:
            return ChannelOutcome(status="timeout", error_code="lexical_timeout")
        except Exception as exc:
            return ChannelOutcome(status="error", error_code=type(exc).__name__)

    async def _graph_search_outcome(
        self,
        query: str,
        k: int,
        where: dict | None = None,
    ) -> ChannelOutcome:
        try:
            # 先截断实体候选，再展开到原子 Observation，避免旧 Topic 聚合节点
            # 丢失 ATR 身份、日期和可跳转地址。
            candidate_k = min(k * 3, 30) if where else k
            hits = await self.neo4j.execute_query(
                "CALL db.index.fulltext.queryNodes('entity_search', $query) "
                "YIELD node, score "
                "WITH node, score ORDER BY score DESC LIMIT $k "
                "MATCH (node)-[:MENTIONS]->(o:Observation)-[:INSTANCE_OF]->(t:Topic) "
                "MATCH (o)-[:OBSERVED_ON]->(d:DailyDigest) "
                "RETURN o.id AS occurrenceId, t.name AS topic, "
                "coalesce(o.category, t.category) AS category, o.score AS totalScore, "
                "o.url AS occurrenceUrl, o.localUrl AS localUrl, "
                "o.source AS occurrenceSource, o.summary AS occurrenceSummary, "
                "o.reason AS occurrenceReason, o.evidence AS occurrenceEvidence, d.date AS date, "
                "o.reportDate AS reportDate, o.publicationDate AS publicationDate, "
                "o.publicationDateSource AS publicationDateSource, o.observedAt AS observedAt, "
                "o.sourceUpdatedAt AS sourceUpdatedAt, "
                "o.ingestedAt AS ingestedAt, o.effectiveDate AS effectiveDate, "
                "o.effectiveDateBasis AS effectiveDateBasis, "
                "score AS entityMatchScore "
                "ORDER BY entityMatchScore DESC, totalScore DESC LIMIT $k",
                query=query,
                k=candidate_k,
            )
            chunks = [
                RetrievedChunk(
                    text=_graph_hit_text(h),
                    source="graph",
                    score=float(h.get("totalScore", 0)),
                    metadata=_graph_hit_metadata(h),
                )
                for h in hits
                if metadata_matches_filter(_graph_hit_metadata(h), where)
            ]
            chunks = chunks[:k]
            return ChannelOutcome(status="success" if chunks else "empty", chunks=chunks)
        except asyncio.TimeoutError:
            return ChannelOutcome(status="timeout", error_code="graph_timeout")
        except Exception as e:
            print(f"[hybrid] graph search failed: {e}")
            return ChannelOutcome(status="error", error_code=type(e).__name__)


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
        "content_type": "daily_observation",
        "date": date,
        "report_date": hit.get("reportDate") or date,
        "publication_date": hit.get("publicationDate") or "",
        "publication_date_source": hit.get("publicationDateSource") or "unknown",
        "source_updated_at": hit.get("sourceUpdatedAt") or "",
        "observed_at": hit.get("observedAt") or date,
        "ingested_at": hit.get("ingestedAt") or "",
        "effective_date": hit.get("effectiveDate") or date,
        "effective_date_basis": hit.get("effectiveDateBasis") or "report_date_fallback",
        "source": source,
        "title": title,
        "url": hit.get("occurrenceUrl") or "",
        "local_url": hit.get("localUrl") or "",
        "citation_id": hit.get("occurrenceId") or f"{date}/observation/{str(title).lower().strip()}",
        "occurrence_id": hit.get("occurrenceId") or "",
        "excerpt": evidence_excerpt or hit.get("occurrenceSummary") or "",
        "category": hit.get("category", ""),
        "score": hit.get("totalScore", 0),
    }
