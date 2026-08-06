"""Agent tool definitions — 6 tools organized by user intent."""

from __future__ import annotations

import json
import re

from langchain_core.tools import tool

from rag.citations import build_citations
from rag.evidence_ledger import admit_active_evidence
from rag.graphrag.driver import Neo4jDriver
from rag.retriever.hybrid import HybridRetriever


# ---------------------------------------------------------------------------
# G-2 helpers: Lucene query escaping for fulltext index calls
# ---------------------------------------------------------------------------

_LUCENE_SPECIAL = re.compile(r'([+\-!(){}\[\]^"~*?:\\/]|&&|\|\|)')


def _escape_lucene(query: str) -> str:
    """Escape Lucene special characters so the search term is treated as literal text."""
    return _LUCENE_SPECIAL.sub(r'\\\1', query)


# ---------------------------------------------------------------------------
# A-1 helpers: structured tool responses so the Agent can distinguish
# "no results" (empty) from "system error" (error)
# ---------------------------------------------------------------------------

def _ok(result: str, evidence: list[dict] | None = None) -> str:
    """Successful tool call with data."""
    payload = {"status": "success", "result": result}
    if evidence:
        payload["evidence"] = evidence
    return json.dumps(payload, ensure_ascii=False)


def _empty(message: str) -> str:
    """Tool ran correctly but found no matching data."""
    return json.dumps({"status": "empty", "message": message}, ensure_ascii=False)


def _error(message: str, error_type: str = "") -> str:
    """Tool hit an exception — Agent should retry or surface to user."""
    payload: dict = {"status": "error", "message": message}
    if error_type:
        payload["error_type"] = error_type
    return json.dumps(payload, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Tool factory
# ---------------------------------------------------------------------------

# A-4 修复：搜索结果格式化常量
_SEARCH_TEXT_LIMIT = 500  # 文本摘要截断上限（字符数）


def _format_search_result(index: int, result, evidence_id: str = "") -> str:
    """格式化单条搜索结果，优先使用结构化元数据，附带文本摘要。

    A-4 修复：不再硬截断 200 字符，而是：
    1. 优先展示 title / category / score 等结构化字段
    2. 文本摘要上限提升到 500 字符，在句号处断句避免截断
    """
    meta = result.metadata
    date = meta.get("date", "")
    source = meta.get("source", result.source)
    content_type = meta.get("content_type", "")

    # 结构化头部：利用元数据字段构建信息密度更高的摘要
    header_parts = [f"[{date}/{source}]"]
    if evidence_id:
        header_parts.append(f"[{evidence_id}]")
    if meta.get("title"):
        header_parts.append(f"**{meta['title']}**")
    if meta.get("category"):
        header_parts.append(f"[{meta['category']}]")
    if meta.get("score") is not None:
        header_parts.append(f"({meta['score']}分)")
    if meta.get("action"):
        header_parts.append(f"→ {meta['action']}")

    header = " ".join(header_parts)

    # 文本摘要：动态截断，在句号处断句，避免截断到 500 字符上限
    text = result.text
    if len(text) <= _SEARCH_TEXT_LIMIT:
        excerpt = text
    else:
        truncated = text[:_SEARCH_TEXT_LIMIT]
        # 尝试在最后一个句号处断句，让摘要更自然
        last_period = max(truncated.rfind("。"), truncated.rfind(". "), truncated.rfind("\n"))
        if last_period > _SEARCH_TEXT_LIMIT // 3:
            excerpt = truncated[:last_period + 1]
        else:
            excerpt = truncated + "..."

    return f"{index}. {header}\n   {excerpt}"


def create_tools(neo4j_driver: Neo4jDriver, hybrid_retriever: HybridRetriever) -> list:
    """Create 6 agent tools bound to the given drivers."""

    @tool
    async def search(query: str) -> str:
        """搜索所有日报和选题数据。适用于查找话题、项目、技术、产品等任何内容。
        输入: 自然语言搜索查询。"""
        try:
            results = await hybrid_retriever.search(query, k=5)
            if not results:
                # Cold start check
                try:
                    count = hybrid_retriever.vector.count()
                    if count == 0:
                        return _empty(
                            "知识库为空，无法搜索。请先运行 `python -m rag.ingest` 导入数据。\n"
                            "或者试试 daily_overview 工具查看某天的选题（需要 Neo4j 连接）。"
                        )
                except Exception:
                    pass
                return _empty(
                    f"没有找到与 '{query}' 相关的内容。\n"
                    "建议：换一个关键词，或使用 topic_trend / recommend 工具。"
                )
            # search 是初版唯一的证据工具：把原始检索元数据写入请求级账本，
            # 并把账本编号回显给 Agent，供最终答案使用 [E#] 标记。
            evidence = admit_active_evidence(build_citations(results, max_citations=len(results)))
            evidence_by_citation_id = {
                str(item.get("citation_id", "")): item.get("evidence_id", "")
                for item in evidence
            }
            lines = [
                _format_search_result(
                    i,
                    result,
                    evidence_by_citation_id.get(str(result.metadata.get("citation_id", "")), ""),
                )
                for i, result in enumerate(results, 1)
            ]
            return _ok("搜索结果：\n" + "\n".join(lines), evidence=evidence)
        except Exception as e:
            return _error(f"搜索失败: {e}", type(e).__name__)

    @tool
    async def topic_trend(topic: str, days: int = 30) -> str:
        """分析某个话题在不同日期的热度变化趋势。
        输入: 话题名称，可选天数（默认 30 天）。"""
        try:
            # G-2 修复：使用 topic_search 全文索引替代 toLower(t.name) CONTAINS
            # 全文索引原生支持大小写不敏感匹配，且能命中索引
            results = await neo4j_driver.execute_query(
                "CALL db.index.fulltext.queryNodes('topic_search', $topic) "
                "YIELD node AS t, score AS ftScore "
                "WITH t, ftScore ORDER BY ftScore DESC "
                "MATCH (t)-[r:APPEARED_ON]->(d:DailyDigest) "
                "WHERE d.date >= date() - duration({days: $days}) "
                "RETURN t.name AS name, d.date AS date, r.score AS score, r.action AS action "
                "ORDER BY d.date",
                topic=_escape_lucene(topic),
                days=days,
            )
            if not results:
                return _empty(f"话题 '{topic}' 在最近 {days} 天没有出现。")
            scores = [(r["date"], r["score"]) for r in results]
            direction = (
                "上升 ↑"
                if len(scores) > 1 and scores[-1][1] > scores[0][1]
                else "平稳 →"
                if len(scores) > 1
                else "新出现"
            )
            lines = [f"- {r['date']}: {r['score']}分 ({r['action']})" for r in results]
            return _ok(f"**{results[0]['name']}** 趋势（{len(results)} 天，{direction}）：\n" + "\n".join(lines))
        except Exception as e:
            return _error(f"趋势分析失败: {e}", type(e).__name__)

    @tool
    async def entity_info(entity: str) -> str:
        """查询某个实体（公司/项目/人物/产品）的详细信息和关系网络。
        输入: 实体名称。"""
        try:
            # G-2 修复：使用已有的 entity_search 全文索引替代 toLower(e.name) CONTAINS
            results = await neo4j_driver.execute_query(
                "CALL db.index.fulltext.queryNodes('entity_search', $entity) "
                "YIELD node AS e, score AS ftScore "
                "WITH e, ftScore ORDER BY ftScore DESC LIMIT 1 "
                "OPTIONAL MATCH (e)-[:MENTIONS]->(t:Topic) "
                "OPTIONAL MATCH (e2:Entity)-[:MENTIONS]->(t) WHERE e2 <> e "
                "RETURN e.name AS name, e.type AS type, "
                "collect(DISTINCT t.name)[..5] AS topics, "
                "collect(DISTINCT e2.name)[..5] AS related_entities",
                entity=_escape_lucene(entity),
            )
            if not results:
                return _empty(f"没有找到实体 '{entity}'。")
            r = results[0]
            return _ok(
                f"**{r['name']}**（类型: {r['type']}）\n"
                f"- 相关话题: {', '.join(r['topics']) or '无'}\n"
                f"- 关联实体: {', '.join(r['related_entities']) or '无'}"
            )
        except Exception as e:
            return _error(f"实体查询失败: {e}", type(e).__name__)

    @tool
    async def daily_overview(date: str) -> str:
        """获取某一天的选题概览，包括热门话题和分数。
        输入: 日期（YYYY-MM-DD 格式）。"""
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
            return _error("日期格式错误，请使用 YYYY-MM-DD 格式。", "ValidationError")
        try:
            results = await neo4j_driver.execute_query(
                "MATCH (t:Topic)-[r:APPEARED_ON]->(d:DailyDigest {date: $date}) "
                "RETURN t.name AS topic, t.category AS category, r.score AS score, r.action AS action "
                "ORDER BY r.score DESC LIMIT 10",
                date=date,
            )
            if not results:
                return _empty(f"{date} 没有选题数据。")
            lines = [
                f"- **{r['topic']}** | {r['score']}分 ({r['action']}) | {r['category']}" for r in results
            ]
            return _ok(f"**{date}** 选题概览（Top {len(results)}）：\n" + "\n".join(lines))
        except Exception as e:
            return _error(f"日期查询失败: {e}", type(e).__name__)

    @tool
    async def source_coverage(topic: str) -> str:
        """对比某个话题在不同数据源中的覆盖情况。
        输入: 话题名称。"""
        try:
            # G-2 修复：使用 topic_search 全文索引替代 toLower(t.name) CONTAINS
            results = await neo4j_driver.execute_query(
                "CALL db.index.fulltext.queryNodes('topic_search', $topic) "
                "YIELD node AS t, score AS ftScore "
                "WITH t, ftScore ORDER BY ftScore DESC LIMIT 1 "
                "MATCH (t)-[:DISCOVERED_VIA]->(s:Source) "
                "RETURN t.name AS name, collect(s.name) AS sources, t.totalScore AS score",
                topic=_escape_lucene(topic),
            )
            if not results:
                return _empty(f"话题 '{topic}' 没有数据源覆盖信息。")
            r = results[0]
            return _ok(f"**{r['name']}** 被以下数据源覆盖：{', '.join(r['sources'])}（总分: {r['score']}）")
        except Exception as e:
            return _error(f"跨源查询失败: {e}", type(e).__name__)

    @tool
    async def recommend(category: str = "") -> str:
        """推荐值得深挖的选题，基于评分和趋势。
        输入: 可选分类过滤（如'模型与技术突破'、'AI 产品与用户入口'）。"""
        try:
            if category:
                results = await neo4j_driver.execute_query(
                    "MATCH (t:Topic) "
                    "WHERE t.category CONTAINS $cat "
                    "AND t.lastSeen >= date() - duration({days: 14}) "
                    "AND COALESCE(t.mentionCount, 0) > 0 "
                    "WITH t, t.totalScore * 0.7 + COALESCE(t.mentionCount, 0) * 3 * 0.3 AS weightedScore "
                    "RETURN t.name AS topic, t.category AS category, "
                    "t.totalScore AS score, t.mentionCount AS mentions "
                    "ORDER BY weightedScore DESC LIMIT 5",
                    cat=category,
                )
            else:
                results = await neo4j_driver.execute_query(
                    "MATCH (t:Topic) "
                    "WHERE t.lastSeen >= date() - duration({days: 14}) "
                    "AND COALESCE(t.mentionCount, 0) > 0 "
                    "WITH t, t.totalScore * 0.7 + COALESCE(t.mentionCount, 0) * 3 * 0.3 AS weightedScore "
                    "RETURN t.name AS topic, t.category AS category, "
                    "t.totalScore AS score, t.mentionCount AS mentions "
                    "ORDER BY weightedScore DESC LIMIT 5"
                )
            if not results:
                return _empty("暂无推荐选题。")
            lines = [
                f"- **{r['topic']}** | {r['score']}分 | 出现{r['mentions']}次 | {r['category']}"
                for r in results
            ]
            return _ok("推荐选题：\n" + "\n".join(lines))
        except Exception as e:
            return _error(f"推荐失败: {e}", type(e).__name__)

    return [search, topic_trend, entity_info, daily_overview, source_coverage, recommend]
