"""Deterministic query-understanding helpers for retrieval planning."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


RECENT_RAG_TERMS = [
    "RAG",
    "retrieval",
    "vector database",
    "knowledge graph",
    "Graph RAG",
    "Agentic RAG",
    "evaluation",
]

CLAUDE_TERMS = [
    "Claude",
    "Anthropic",
    "Claude Code",
    "Artifacts",
    "plugins",
    "developer tools",
]

GITHUB_TERMS = [
    "GitHub",
    "GitHub Trending",
    "GitHub Search",
    "repository",
    "open source",
]

PRODUCT_HUNT_TERMS = [
    "Product Hunt",
    "launch",
    "AI product",
    "heat signal",
]

OPENAI_TERMS = [
    "OpenAI",
    "GPT",
    "agent",
    "developer",
    "model",
]

AI_AGENT_TERMS = [
    "AI Agent",
    "agentic",
    "智能体",
    "workflow",
    "tool use",
]

AI_CODING_TERMS = [
    "AI coding",
    "developer tools",
    "coding assistant",
    "Claude Code",
    "GitHub",
]

GOOGLE_KNOWLEDGE_TERMS = [
    "Google",
    "OKF",
    "ALM Wiki",
    "knowledge framework",
    "user preference",
]


@dataclass(frozen=True)
class QueryPlan:
    """A compact retrieval plan inferred from a user question."""

    original_question: str
    intent: str
    retrieval_query: str
    top_k: int = 5
    topics: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    time_window: dict = field(default_factory=dict)
    answerability_hint: str = "internal-first"
    needs_web_search: bool = False
    routing_notes: list[str] = field(default_factory=list)
    task_mode: str = "general"  # 任务模式：general, explain, compare, timeline, brief_followup, source_check

    def to_dict(self) -> dict:
        return asdict(self)


def analyze_query(question: str) -> QueryPlan:
    """Infer a small, deterministic retrieval plan from a natural-language question."""
    normalized = question.strip()
    lowered = normalized.lower()

    intent = "general_search"
    topics: list[str] = []
    entities: list[str] = []
    sources: list[str] = []
    terms: list[str] = []
    notes: list[str] = []
    top_k = 10
    answerability_hint = "internal-first"
    needs_web_search = False
    time_window = _infer_time_window(normalized, lowered)

    if _contains_any(lowered, ["rag", "graph rag", "agentic rag"]):
        topics.append("RAG")
        terms.extend(RECENT_RAG_TERMS)

    if _contains_any(lowered, ["ai agent", "agentic", "智能体"]):
        topics.append("AI Agent")
        terms.extend(AI_AGENT_TERMS)

    if _contains_any(lowered, ["ai 编码", "编码工具", "开发者工具", "coding tool", "developer tool"]):
        topics.append("AI Coding Tools")
        terms.extend(AI_CODING_TERMS)

    if _contains_any(lowered, ["claude", "anthropic"]):
        entities.append("Claude")
        entities.append("Anthropic")
        terms.extend(CLAUDE_TERMS)
        if _contains_any(normalized, ["上线", "新功能", "插件", "动态", "更新"]):
            intent = "product_update"
            top_k = 8

    if _contains_any(lowered, ["github"]):
        sources.append("GitHub")
        terms.extend(GITHUB_TERMS)
        intent = "source_specific_discovery"
        top_k = 8

    if _contains_any(lowered, ["product hunt"]):
        sources.append("Product Hunt")
        terms.extend(PRODUCT_HUNT_TERMS)
        intent = "source_specific_discovery"
        top_k = max(top_k, 8)

    if _contains_any(lowered, ["openai"]):
        entities.append("OpenAI")
        terms.extend(OPENAI_TERMS)
        if intent == "general_search":
            intent = "recent_trend"
        top_k = max(top_k, 8)

    if _contains_any(lowered, ["google", "okf", "alm wiki"]):
        entities.append("Google")
        topics.extend(["OKF", "ALM Wiki"])
        terms.extend(GOOGLE_KNOWLEDGE_TERMS)
        intent = "technical_comparison"
        top_k = 10
        answerability_hint = "needs-web"
        needs_web_search = True
        notes.append("This comparison likely needs primary external sources after internal corpus search.")

    if _contains_any(normalized, ["发展演进", "演进路线", "论文", "文章", "资料"]):
        intent = "learning_map"
        top_k = max(top_k, 10)
        answerability_hint = "needs-web"
        needs_web_search = True
        notes.append("A complete learning map needs external papers or primary references.")

    # 识别用户明确要求联网搜索的意图
    if _contains_any(normalized, ["联网搜索", "搜索最新", "搜索外部", "web search", "search online"]):
        intent = "web_search_request"
        top_k = max(top_k, 15)
        answerability_hint = "needs-web"
        needs_web_search = True
        notes.append("User explicitly requested web search.")

    if _contains_any(normalized, ["足够证据", "证据说明", "明确商业成功", "商业成功"]):
        intent = "evidence_sufficiency"
        top_k = max(top_k, 8)
        answerability_hint = "insufficient-risk"
        notes.append("Question asks whether evidence is sufficient; answer should avoid inferring proof from weak signals.")

    if intent == "general_search" and _contains_any(normalized, ["最近", "新动向", "趋势", "值得关注"]):
        intent = "recent_trend"
        top_k = max(top_k, 8)

    if time_window.get("label") == "last_7_days":
        top_k = max(top_k, 8)
        notes.append("Question contains a one-week time constraint; retrieval should prefer recent dated corpus.")
    elif time_window.get("label") == "recent_corpus_first":
        notes.append("Question asks for recent information; retrieval should prefer the freshest local corpus.")

    retrieval_query = _build_retrieval_query(normalized, terms)

    # 检测任务模式
    task_mode = _detect_task_mode(normalized, lowered, intent)

    return QueryPlan(
        original_question=normalized,
        intent=intent,
        retrieval_query=retrieval_query,
        top_k=top_k,
        topics=_unique(topics),
        entities=_unique(entities),
        sources=_unique(sources),
        time_window=time_window,
        answerability_hint=answerability_hint,
        needs_web_search=needs_web_search,
        routing_notes=notes,
        task_mode=task_mode,
    )


def _detect_task_mode(question: str, lowered: str, intent: str) -> str:
    """检测任务模式"""
    # explain: 解释复杂话题
    if _contains_any(lowered, ["解释", "什么是", "如何理解", "帮我理解", "说明"]):
        return "explain"

    # compare: 对比多个项目
    if _contains_any(lowered, ["对比", "比较", "区别", "差异", "vs", "versus"]):
        return "compare"

    # timeline: 追踪演进（排除"趋势"在一般查询中的使用）
    if _contains_any(lowered, ["演进", "发展", "历程", "历史", "变化"]):
        return "timeline"
    # "趋势"只在明确要求演进时触发timeline
    if _contains_any(lowered, ["趋势"]) and _contains_any(lowered, ["演进", "发展", "历程"]):
        return "timeline"

    # brief_followup: 深入Brief话题
    if _contains_any(lowered, ["brief", "简报", "详细", "深入", "展开"]):
        return "brief_followup"

    # source_check: 验证来源
    if _contains_any(lowered, ["验证", "来源", "出处", "真实性", "可靠性"]):
        return "source_check"

    # 根据intent推断
    if intent == "technical_comparison":
        return "compare"
    if intent == "learning_map":
        return "timeline"
    if intent == "evidence_sufficiency":
        return "source_check"

    return "general"


def _infer_time_window(question: str, lowered: str) -> dict:
    if _contains_any(question, ["过去一周", "近一周", "最近一周", "7天", "七天"]):
        return {"label": "last_7_days", "days": 7, "requires_date_filter": True}
    if _contains_any(question, ["最近", "新动向", "动态", "更新"]):
        return {"label": "recent_corpus_first", "days": 14, "requires_date_filter": False}
    if _contains_any(question, ["发展演进", "演进路线", "演进历程", "论文", "文章", "资料"]) or "history" in lowered:
        return {"label": "not_limited", "days": None, "requires_date_filter": False}
    return {"label": "unspecified", "days": None, "requires_date_filter": False}


def _build_retrieval_query(question: str, terms: list[str]) -> str:
    pieces = [question]
    for term in terms:
        if term.lower() not in question.lower():
            pieces.append(term)
    return " ".join(_unique(pieces))


def _contains_any(text: str, needles: list[str]) -> bool:
    return any(needle.lower() in text.lower() for needle in needles)


def _unique(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result
