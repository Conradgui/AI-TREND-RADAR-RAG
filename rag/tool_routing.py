"""Deterministic tool-routing contract for AI Trend Radar RAG."""

from __future__ import annotations

from rag.search_provider_routing import build_search_provider_route


def build_tool_route(
    plan,
    answer_policy: dict,
    citations: list[dict],
    configured_search_providers: set[str] | None = None,
) -> dict:
    """Build a serializable tool-routing trace without executing external tools."""
    if not citations:
        external_required = bool(answer_policy.get("external_search_required"))
        provider_route = build_search_provider_route(
            {
                "query": getattr(plan, "retrieval_query", getattr(plan, "original_question", "")),
                "task_type": infer_search_task_type(plan),
            },
            configured_providers=configured_search_providers or set(),
        ) if external_required else {}
        return {
            "status": "external_fallback_planned" if external_required else "evidence_insufficient",
            "external_tools_required": external_required,
            "external_tools_available": bool(provider_route.get("available_provider_chain")),
            "provider_route": provider_route,
            "max_tool_calls": 2 if external_required else 1,
            "steps": [
                _step(
                    "search_corpus",
                    "executed",
                    "Internal corpus search returned no usable citation-ready evidence.",
                ),
                *(
                    [_step("web_search", "planned", "External search may recover an internal evidence gap.")]
                    if external_required else []
                ),
            ],
            "fallback": "停止生成确定性结论；建议补充语料、调整检索词，或在后续启用带外部来源标注的 web_search。",
        }

    if answer_policy.get("external_search_required"):
        provider_route = build_search_provider_route(
            {
                "query": getattr(plan, "retrieval_query", getattr(plan, "original_question", "")),
                "task_type": infer_search_task_type(plan),
            },
            configured_providers=configured_search_providers or set(),
        )
        return {
            "status": "external_required_not_available",
            "external_tools_required": True,
            "external_tools_available": False,
            "max_tool_calls": 4,
            "provider_route": provider_route,
            "steps": [
                _step("search_corpus", "executed", "Internal AI Trend Radar corpus searched first."),
                _step("web_search", "planned_unavailable", "External discovery is required but not implemented in this module."),
                _step("fetch_url", "planned_unavailable", "Specific external source fetching is required after web_search."),
                _step(
                    "compare_internal_and_external",
                    "planned_unavailable",
                    "External findings must be compared with internal corpus before final claims.",
                ),
            ],
            "fallback": "只回答内部语料可支持的部分，并明确提示仍需要外部证据确认。",
        }

    return {
        "status": "internal_only_ready",
        "external_tools_required": False,
        "external_tools_available": False,
        "max_tool_calls": 1,
        "steps": [
            _step("search_corpus", "executed", "Internal AI Trend Radar corpus searched and citation-ready evidence found.")
        ],
        "fallback": "如内部证据不足，应返回证据不足，而不是自动编造外部事实。",
    }


def format_tool_route_for_prompt(route: dict) -> str:
    """Format routing trace for the LLM system prompt."""
    lines = [
        "工具路由:",
        f"- 路由状态: {route.get('status', '')}",
        f"- 外部工具状态: available={route.get('external_tools_available', False)}",
        f"- 最大工具调用数: {route.get('max_tool_calls', 0)}",
        f"- 降级策略: {route.get('fallback', '')}",
        "- 工具步骤:",
    ]
    for step in route.get("steps", []):
        lines.append(f"  - {step.get('tool', '')}: {step.get('state', '')} | {step.get('reason', '')}")
    return "\n".join(lines)


def _step(tool: str, state: str, reason: str) -> dict:
    return {
        "tool": tool,
        "state": state,
        "reason": reason,
    }


def infer_search_task_type(plan) -> str:
    intent = getattr(plan, "intent", "")
    task_mode = getattr(plan, "task_mode", "")
    question = str(getattr(plan, "original_question", "")).casefold()
    sources = set(getattr(plan, "sources", []) or [])
    topics = set(getattr(plan, "topics", []) or [])
    entities = set(getattr(plan, "entities", []) or [])

    if "GitHub" in sources:
        return "github_repo"
    if intent == "learning_map":
        return "research_paper"
    if entities and (task_mode == "source_check" or any(term in question for term in ("官方", "官网", "primary source"))):
        return "official_source_lookup"
    if "OKF" in topics or "ALM Wiki" in topics or "Google" in entities:
        return "official_source_lookup"
    if intent in {"recent_trend", "product_update"}:
        return "recent_web"
    return "broad_serp"
