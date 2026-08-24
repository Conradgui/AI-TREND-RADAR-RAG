"""Deterministic, non-destructive signals extracted from a user Query."""

from __future__ import annotations

import re
from dataclasses import dataclass


_ATR_ID = re.compile(r"\bATR-\d{8}-[A-Z0-9]{6}\b", re.IGNORECASE)
_QUOTED = re.compile(r"[“\"]([^”\"]+)[”\"]")
_SINGLE_QUOTED = re.compile(r"[‘']([^’']+)[’']")
_BOOK_TITLE = re.compile(r"《([^》]+)》")
_CONTEXT_ITEM_ID = re.compile(r"(?:current_item_id|item_id)\s*[=:]\s*(ATR-\d{8}-[A-Z0-9]{6})", re.IGNORECASE)
_LATIN_NAMED_TERM = re.compile(
    r"(?<![A-Za-z0-9])(?:[A-Z][A-Za-z0-9.+-]*|[a-z]+AI)(?:\s+(?:[A-Z][A-Za-z0-9.+-]*|AI|RAG|API)){0,4}(?![A-Za-z0-9])"
)
_ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_CHINESE_DATE = re.compile(r"(?<!\d)\d{1,2}\s*月\s*\d{1,2}\s*日(?!\d)")
_RELATIVE_PERIOD = re.compile(
    r"(?:过去|近|最近)?\s*(?:\d+|一|两|三|半)\s*(?:小时|天|周|个月|月|季度|年)"
)
_QUARTER = re.compile(r"\b\d{4}\s*Q[1-4]\b", re.IGNORECASE)
_MONEY_OR_NUMBER = re.compile(r"(?:\$\s?\d+(?:\.\d+)?\s?[MBK]?|\d+(?:\.\d+)?\s*(?:亿元|万美元|条|个))", re.IGNORECASE)
_CHINESE_COUNT = re.compile(r"(?<![一二三四五六七八九十百千万])([一二三四五六七八九十]+条)(?![一二三四五六七八九十百千万])")

_KNOWN_TERMS = tuple(sorted({
    "Apple Is Getting This Wrong", "Google DeepMind", "ChatGPT Search", "Claude Code", "Product Hunt", "Hacker News",
    "The GTM Co-Founder", "Scaling Laws for Agentic Search", "Economic Research",
    "AI browser agents", "browser-use agents", "small language models", "open-weight models",
    "autonomous agents", "headline-level updates", "enterprise agent", "AI infrastructure",
    "AI robotics", "AI coding", "coding agents", "agent runtime", "tool calling",
    "daily knowledge base", "local daily digest", "internal corpus", "official website",
    "European Union AI Act", "Open AI", "OpenAI", "Anthropic", "Microsoft", "NVIDIA", "CoreWeave",
    "Perplexity", "PromptForge", "Mistral", "Gemini", "Cursor", "Apple", "Google",
    "Meta AI", "DeepSeek", "GraphRAG", "RAGFlow", "LightRAG", "Neo4j", "MCP",
    "GPT-6", "Ona", "Arc", "Hotshot", "xAI", "AI Agent", "Agent", "AI search", "RAG",
    "Amazon", "Sam Altman", "Codex", "Agentic coding", "Graph RAG", "Agentic RAG",
    "普通 RAG", "PMF", "query", "agent workflow", "coding agent", "AI Coding",
    "AI PM", "API", "GitHub",
    "Google DeepMind", "ChatGPT Search", "Claude Code", "Product Hunt", "Hacker News",
    "开放权重模型", "欧盟 AI Act", "AI 基础设施", "AI 搜索", "AI 编码工具", "初级工程师",
    "资深开发者", "免费账户", "个人免费用户", "新增算力", "日报知识库",
    "本地日报", "内部语料", "内部证据", "内部库", "官网资料", "官网", "官方公告",
    "个人免费用户", "免费账户", "新增算力", "几千条日报", "日报知识库",
    "经济研究交流", "企业用户", "专家差距", "新手", "资深开发者", "专家回报递增",
    "生物安全回退机制", "传记电影", "AI 搜索产品",
}, key=len, reverse=True))

_SOURCE_TERMS = ("Product Hunt", "Hacker News", "GitHub", "官网资料", "官网", "官方", "官方公告", "一手来源", "可靠来源", "内部库", "本地日报")
_RECENCY_TERMS = ("今天", "本周", "这周", "最近", "近期", "lately", "刚刚", "过去 72 小时", "过去 48 小时", "48 小时")
_IMPORTANCE_TERMS = ("重要", "热门", "值得看", "值得关注", "大新闻", "大事", "大动态", "影响面", "headline-level", "真正重要")
_TIMELINE_TERMS = ("演变", "变化", "转折", "迁移", "重排", "关键节点", "怎么走到", "转向", "演进顺序", "随日期", "按时间", "经历了", "经历了哪几个阶段", "哪些阶段")
_RELATION_TERMS = ("关系", "格局", "结构", "连接", "依赖", "角色", "供给链", "竞争")
_EXPLANATION_TERMS = ("解释", "为什么", "原因", "讲清楚", "分别扮演什么角色")
_COMPARISON_TERMS = ("比较", "区别", "更适合", "选型", "对比")
_DEEP_RESEARCH_TERMS = ("深挖", "深入研究", "研究一下", "支持证据", "反例", "未知项", "成本和收益", "成本和收益给建议", "接入建议", "风险", "证据和局限", "结合内部语料和官网资料")
_VERIFICATION_TERMS = ("核实", "验证", "是真的吗", "是否属实", "是否说明", "成立不成立", "到底有没有", "对吗", "对不对", "可靠来源支持", "充分证据", "媒体误传", "可核验的结论", "请判断这句话")
_VALUE_JUDGMENT_TERMS = ("值得采用", "更适合", "给建议", "选型", "接入建议", "产品价值", "是否值得")
_NEWS_DISCOVERY_TERMS = ("有什么更新", "有哪些更新", "发生了什么大事", "有啥大动静", "大动静", "哪些新闻", "哪些发布", "几项动态", "重要动态", "热门趋势", "headline-level updates", "What's new", "最近的重要动态")


@dataclass(frozen=True)
class QuerySignals:
    original_query: str
    protected_terms: tuple[str, ...]
    intent_signals: tuple[str, ...]
    locatable_object: bool
    exact_locator: bool
    verification_request: bool
    value_judgment: bool
    news_discovery: bool
    temporal_structure: bool
    relation_structure: bool
    comparison_request: bool
    explanation_request: bool
    deep_research_request: bool
    web_permission: str
    ambiguities: tuple[str, ...]
    resolved_references: tuple[tuple[str, str, str], ...]
    has_concrete_subject: bool


def extract_query_signals(query: str, conversation_context: str | None = None) -> QuerySignals:
    """Extract facts and task clues without selecting the final task route."""
    original = query.strip()
    if not original:
        raise ValueError("query cannot be empty")

    protected_terms = _extract_protected_terms(original)
    navigation_contextual_reference = any(
        term in original for term in ("这条新闻", "这条", "刚点开的", "我说的这条")
    )
    pronoun_requires_context = _pronoun_requires_context(original)
    contextual_reference = navigation_contextual_reference or pronoun_requires_context
    context_item_match = _CONTEXT_ITEM_ID.search(conversation_context or "")
    context_can_resolve = bool(context_item_match and contextual_reference)
    ambiguities = []
    if contextual_reference and not context_can_resolve and not _has_explicit_locator(original):
        ambiguities.append("contextual item reference cannot be resolved without conversation context")
    if "某公司" in original:
        ambiguities.append("claim subject is unspecified")
    resolved_references = ()
    if context_item_match and contextual_reference:
        resolved_references = (("item_id", context_item_match.group(1).upper(), "conversation_context"),)

    locatable_object = _has_explicit_locator(original) or (
        navigation_contextual_reference
        and _contains_any(original, ("原条目", "原记录", "对应记录", "带我回"))
    )
    exact_locator = bool(
        _ATR_ID.search(original)
        or (context_item_match and navigation_contextual_reference)
    ) or bool(
        re.search(r"(?:找到|找)\s+(.+?)\s+这条新闻", original, re.IGNORECASE)
    ) or (
        bool(_QUOTED.search(original) or _SINGLE_QUOTED.search(original) or _BOOK_TITLE.search(original))
        and not _quoted_locator_is_fragment(original)
        and not _contains_any(original, ("标题以", "题目包含", "标题包含"))
    )
    if locatable_object and not exact_locator and not ambiguities:
        ambiguities.append("item locator may match multiple records")

    value_judgment = _contains_any(original, _VALUE_JUDGMENT_TERMS)
    verification_request = _is_verification_request(original, value_judgment)
    temporal_structure = _has_temporal_structure(original)
    news_discovery = _is_news_discovery(original, temporal_structure)
    relation_structure = _has_relation_structure(original)
    comparison_request = _contains_any(original, _COMPARISON_TERMS) or (
        verification_request and "比" in original
    )
    explanation_request = _contains_any(original, _EXPLANATION_TERMS)
    deep_research_request = _contains_any(original, _DEEP_RESEARCH_TERMS) or (
        value_judgment and _contains_any(original, ("成本", "收益", "风险", "替代方案", "建议", "只有", "规模"))
    )

    intent_signals = _collect_intent_signals(
        original=original,
        locatable_object=locatable_object,
        verification_request=verification_request,
        news_discovery=news_discovery,
        temporal_structure=temporal_structure,
        relation_structure=relation_structure,
        comparison_request=comparison_request,
        explanation_request=explanation_request,
        deep_research_request=deep_research_request,
    )
    if _contains_any(original, ("不要联网", "禁止联网", "别联网", "无需联网")):
        web_permission = "forbidden"
    else:
        web_permission = "explicit" if _contains_any(original, ("联网", "官网资料", "官方公告核验")) else "on_demand"
    if _contains_any(original, ("内部证据", "内部库", "本地日报", "随日期")) and web_permission != "explicit":
        web_permission = "forbidden"

    return QuerySignals(
        original_query=original,
        protected_terms=tuple(protected_terms),
        intent_signals=tuple(intent_signals),
        locatable_object=locatable_object,
        exact_locator=exact_locator,
        verification_request=verification_request,
        value_judgment=value_judgment,
        news_discovery=news_discovery,
        temporal_structure=temporal_structure,
        relation_structure=relation_structure,
        comparison_request=comparison_request,
        explanation_request=explanation_request,
        deep_research_request=deep_research_request,
        web_permission=web_permission,
        ambiguities=tuple(ambiguities),
        resolved_references=resolved_references,
        has_concrete_subject=_has_concrete_subject(original),
    )


def _extract_protected_terms(query: str) -> list[str]:
    candidates: list[tuple[int, str]] = []
    for pattern in (_ATR_ID, _QUOTED, _SINGLE_QUOTED, _BOOK_TITLE, _ISO_DATE, _CHINESE_DATE, _RELATIVE_PERIOD, _QUARTER, _MONEY_OR_NUMBER, _CHINESE_COUNT):
        for match in pattern.finditer(query):
            value = match.group(1) if pattern in (_QUOTED, _SINGLE_QUOTED, _BOOK_TITLE, _CHINESE_COUNT) else match.group(0)
            candidates.append((match.start(), _clean_token(value)))

    for match in _LATIN_NAMED_TERM.finditer(query):
        candidates.append((match.start(), _clean_token(match.group(0))))

    title_match = re.search(r"(?:找到|找)\s+(.+?)\s+这条新闻", query, re.IGNORECASE)
    if title_match:
        candidates.append((title_match.start(1), _clean_token(title_match.group(1))))

    for phrase in (
        "Agent 战略", "竞争关系", "同一条", "热度", "随日期", "商业化路径",
        "产品价值", "官方", "联网", "不要联网", "禁止联网", "别联网", "无需联网",
        "按时间", "争议", "一手来源",
        "降低了安全标准", "召回率", "一定", "可能", "收购", "这条新闻",
    ):
        start = query.casefold().find(phrase.casefold())
        if start >= 0:
            candidates.append((start, query[start:start + len(phrase)]))

    for term in _KNOWN_TERMS:
        start = query.casefold().find(term.casefold())
        if start >= 0:
            candidates.append((start, query[start:start + len(term)]))

    for term in ("今天", "本周", "这周", "最近", "lately", "过去一年", "这一年", "半年"):
        start = query.casefold().find(term.casefold())
        if start >= 0:
            candidates.append((start, query[start:start + len(term)]))

    result = []
    seen = set()
    for _, value in sorted(candidates, key=lambda item: (item[0], -len(item[1]))):
        normalized = value.casefold()
        if not value or normalized in seen:
            continue
        if any(normalized in existing.casefold() and normalized != existing.casefold() for existing in result):
            continue
        seen.add(normalized)
        result.append(value)
    return result


def _has_explicit_locator(query: str) -> bool:
    if _ATR_ID.search(query):
        return True
    quoted = bool(_QUOTED.search(query) or _SINGLE_QUOTED.search(query) or _BOOK_TITLE.search(query))
    item_object = _contains_any(query, ("原条目", "原记录", "对应记录", "原始条目", "那篇原文", "这条"))
    date_source_fragment = bool(
        (_ISO_DATE.search(query) or _CHINESE_DATE.search(query))
        and _contains_any(query, _SOURCE_TERMS + ("OpenAI", "Open AI"))
        and _contains_any(query, ("标题", "题目", "那篇", "来源", "条目", "内容", "那一条"))
    )
    unquoted_title = bool(re.search(r"(?:找到|找)\s+.+?\s+这条新闻", query, re.IGNORECASE))
    return (quoted and item_object) or date_source_fragment or unquoted_title


def _is_verification_request(query: str, value_judgment: bool) -> bool:
    if value_judgment:
        return False
    if _contains_any(query, _VERIFICATION_TERMS):
        return True
    fact_predicates = ("已经", "已向", "已停止", "收购", "发布", "开放", "覆盖", "生效", "提供")
    interrogative = _contains_any(query, ("是否", "有没有", "对吗", "是真的吗", "Did ", "did "))
    return interrogative and _contains_any(query, fact_predicates)


def _collect_intent_signals(**facts: object) -> list[str]:
    query = str(facts["original"])
    signals = []
    if facts["locatable_object"]:
        signals.append("navigation")
    if _has_recent_window(query):
        signals.append("recency")
    if _contains_any(query, _IMPORTANCE_TERMS):
        signals.append("importance")
    if facts["temporal_structure"]:
        signals.append("timeline")
    if facts["relation_structure"]:
        signals.append("relation")
    if _contains_any(query, ("趋势", "路线", "格局", "迁移", "战略", "热度")):
        signals.append("trend")
    elif "领域" in query and _contains_any(query, ("值得关注", "值得看")):
        signals.append("trend")
    if facts["verification_request"]:
        signals.append("verification")
    if facts["explanation_request"]:
        signals.append("explanation")
    if facts["comparison_request"]:
        signals.append("comparison")
    if facts["deep_research_request"]:
        signals.append("deep_research")
    if _contains_any(query, _SOURCE_TERMS):
        signals.append("source_specific")
    if "联网" in query and not _contains_any(query, ("不要联网", "禁止联网", "别联网", "无需联网")):
        signals.append("web_requested")
    return list(dict.fromkeys(signals))


def _contains_any(value: str, terms: tuple[str, ...]) -> bool:
    folded = value.casefold()
    return any(term.casefold() in folded for term in terms)


def _clean_token(value: str) -> str:
    return " ".join(value.strip().rstrip(".…").split())


def _has_recent_window(query: str) -> bool:
    if _contains_any(query, _RECENCY_TERMS + ("这周", "本周")):
        return True
    match = _RELATIVE_PERIOD.search(query)
    if not match:
        return False
    value = match.group(0).replace(" ", "")
    return any(unit in value for unit in ("小时", "天", "周"))


def _has_temporal_structure(query: str) -> bool:
    if _contains_any(query, ("别给我一年时间线", "不要一年时间线")):
        return False
    has_change = _contains_any(query, _TIMELINE_TERMS) or bool(
        re.search(r"从.+?(?:到|至).+?(?:变化|演变|争议|现在|近期)", query)
    )
    has_time_range = bool(_RELATIVE_PERIOD.search(query) or _QUARTER.search(query)) or _contains_any(
        query, ("这一年", "到现在", "半年", "两个季度")
    )
    has_structural_target = _contains_any(query, ("路线", "格局", "关系", "关注点", "结构", "关键节点", "演进顺序"))
    long_horizon_trend = has_time_range and _contains_any(query, ("月", "季度", "年")) and _contains_any(
        query, ("形成", "趋势", "路线", "格局", "转向")
    )
    return has_change or (has_time_range and has_structural_target) or long_horizon_trend


def _has_relation_structure(query: str) -> bool:
    if not _contains_any(query, _RELATION_TERMS):
        return False
    if _contains_any(query, ("更适合什么场景", "选型比较", "产品价值", "API 策略")):
        return False
    return True


def _is_news_discovery(query: str, temporal_structure: bool) -> bool:
    if temporal_structure:
        return False
    if _contains_any(query, _NEWS_DISCOVERY_TERMS):
        return True
    return _has_recent_window(query) and _contains_any(
        query,
        _IMPORTANCE_TERMS + ("更新", "动态", "发布", "新闻", "大事", "大动作", "值得看的"),
    )


def _quoted_locator_is_fragment(query: str) -> bool:
    for pattern in (_QUOTED, _SINGLE_QUOTED, _BOOK_TITLE):
        match = pattern.search(query)
        if match and match.group(1).rstrip().endswith(("...", "…")):
            return True
    return False


def _has_concrete_subject(query: str) -> bool:
    if any(pattern.search(query) for pattern in (_ATR_ID, _QUOTED, _SINGLE_QUOTED, _BOOK_TITLE)):
        return True
    if _LATIN_NAMED_TERM.search(query):
        return True
    folded = query.casefold()
    return any(term.casefold() in folded for term in _KNOWN_TERMS)


def _pronoun_requires_context(query: str) -> bool:
    """Return whether any `它` needs a reference outside the current Query."""
    positions = [match.start() for match in re.finditer("它", query)]
    if not positions:
        return False

    comparison_reference = re.search(
        r"(?:比较|对比).*(?:它\s*(?:和|与|跟)|(?:和|与|跟)\s*它)",
        query,
    )
    if comparison_reference:
        return True

    return any(not _has_concrete_subject(query[:position]) for position in positions)
