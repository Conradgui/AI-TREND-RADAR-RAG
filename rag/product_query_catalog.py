"""Product-owned query examples shared by routing and regression tests.

The catalog is intentionally small.  It defines high-value user entry points,
not an exhaustive dictionary of every phrase a user may type.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProductQueryCase:
    case_id: str
    question: str
    task_family: str
    answer_mode: str
    surface: str = "common"


PRODUCT_QUERY_CASES = (
    ProductQueryCase("HOME-01", "最近有什么热门趋势？", "trend_discovery", "trend_clusters", "home"),
    ProductQueryCase("HOME-02", "推荐值得深挖的选题", "evidence_research", "deep_research", "home"),
    ProductQueryCase("HOME-03", "Claude 最近有什么动态？", "trend_discovery", "important_news", "home"),
    ProductQueryCase("A-01", "打开 ATR-20260805-99E550", "item_navigation", "exact_item"),
    ProductQueryCase("A-02", "找到 Apple Is Getting This Wrong 这条新闻", "item_navigation", "exact_item"),
    ProductQueryCase("B-01", "OpenAI 最近有哪些重要动态？", "trend_discovery", "important_news"),
    ProductQueryCase("B-02", "过去 7 天 AI Agent 领域什么最值得关注？", "trend_discovery", "important_news"),
    ProductQueryCase("B-03", "过去一周 GitHub 热榜上有什么值得关注的选题？", "trend_discovery", "important_news"),
    ProductQueryCase("C-01", "OpenAI 的 Agent 战略过去三个月是如何演变的？", "temporal_relation_exploration", "timeline"),
    ProductQueryCase("C-02", "OpenAI 和 Anthropic 最近的竞争关系发生了什么变化？", "temporal_relation_exploration", "relation"),
    ProductQueryCase("D-01", "OpenAI 是否已经发布 GPT-6？", "claim_verification", "verification_verdict"),
    ProductQueryCase("D-02", "请验证：GraphRAG 一定比普通 RAG 的召回率更高", "claim_verification", "verification_verdict"),
    ProductQueryCase("E-01", "用内部证据解释 Graph RAG 和 Agentic RAG 的区别", "evidence_research", "comparison"),
    ProductQueryCase("E-02", "比较 Codex 与 Claude Code 面向企业用户的产品价值", "evidence_research", "comparison"),
    ProductQueryCase("E-03", "深挖 AI 搜索产品的商业化路径，并给出证据和局限", "evidence_research", "deep_research"),
)

HOME_SUGGESTED_QUESTIONS = tuple(
    case.question for case in PRODUCT_QUERY_CASES if case.surface == "home"
)


def find_product_query(question: str) -> ProductQueryCase | None:
    """Return an exact product entry after presentation-only normalization."""
    normalized = _normalize(question)
    return next(
        (case for case in PRODUCT_QUERY_CASES if _normalize(case.question) == normalized),
        None,
    )


def _normalize(value: str) -> str:
    return "".join(value.casefold().split()).rstrip("？?!！。.")
