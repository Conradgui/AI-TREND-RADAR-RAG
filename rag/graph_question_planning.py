"""Deterministic planner for graph relationship questions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from rag.entity_identity import canonical_entity_ids
from rag.query_understanding import QueryPlan, analyze_query


ENTITY_ALIASES = {
    "rag": ("rag", "graph rag", "agentic rag", "检索增强", "知识增强"),
    "openai": ("openai", "gpt"),
    "ai-agent": ("ai agent", "agentic", "agent", "智能体"),
}

GRAPH_RELATIONSHIP_TERMS = (
    "图谱",
    "关系",
    "关联",
    "跨",
    "多个",
    "来源",
    "日期",
    "反复",
    "多次",
    "出现",
    "趋势",
    "覆盖",
    "共现",
    "历程",
    "演进",
    "变化",
    "时间线",
)


@dataclass(frozen=True)
class GraphQuestionPlan:
    """A compact plan for graph relationship evidence retrieval."""

    original_question: str
    entity_id: str
    entity_label: str
    question_type: str
    required_paths: list[str] = field(default_factory=list)
    answer_mode: str = "graph_relationship_summary"
    routing_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def build_graph_question_plan(
    question: str,
    query_plan: QueryPlan | None = None,
) -> GraphQuestionPlan | None:
    """Compatibility helper returning the first planned entity."""
    plans = build_graph_question_plans(question, query_plan=query_plan)
    return plans[0] if plans else None


def build_graph_question_plans(
    question: str,
    query_plan: QueryPlan | None = None,
) -> list[GraphQuestionPlan]:
    """Return one graph plan per requested entity, preserving user order.

    The singular helper remains the compatibility interface for briefs and
    evaluations. Chat relationship tasks use this plural form so a comparison
    such as ``OpenAI 与 Apple`` cannot silently collapse to the first entity.
    """
    normalized = question.strip()
    if not normalized or not _asks_for_graph_relationships(normalized):
        return []

    query_plan = query_plan or analyze_query(normalized)
    entity_ids = canonical_entity_ids(getattr(query_plan, "entities", []))
    if not entity_ids:
        inferred = _infer_entity_id(normalized, query_plan)
        entity_ids = [inferred] if inferred else []
    if not entity_ids:
        return []

    required_paths = _infer_required_paths(normalized)
    return [
        GraphQuestionPlan(
            original_question=normalized,
            entity_id=entity_id,
            entity_label=_entity_label(entity_id),
            question_type="entity_observation_relationship",
            required_paths=required_paths,
            routing_notes=[
                "Question asks for entity/observation/date/source relationship coverage.",
                "Use graph evidence before answer synthesis.",
            ],
        )
        for entity_id in entity_ids
    ]


def is_graph_relationship_question(question: str, query_plan: QueryPlan | None = None) -> bool:
    """Return whether a question should be handled by graph relationship planning."""
    return build_graph_question_plan(question, query_plan=query_plan) is not None


def _infer_entity_id(question: str, query_plan: QueryPlan) -> str:
    haystack = " ".join([
        question,
        *getattr(query_plan, "topics", []),
        *getattr(query_plan, "entities", []),
        *getattr(query_plan, "sources", []),
    ]).casefold()
    for entity_id, aliases in ENTITY_ALIASES.items():
        if any(alias.casefold() in haystack for alias in aliases):
            return entity_id
    return ""


def _asks_for_graph_relationships(question: str) -> bool:
    lowered = question.casefold()
    return any(term.casefold() in lowered for term in GRAPH_RELATIONSHIP_TERMS)


def _infer_required_paths(question: str) -> list[str]:
    lowered = question.casefold()
    paths = []
    if any(term in lowered for term in ("日期", "跨", "反复", "多次", "出现", "趋势", "覆盖")):
        paths.append("entity_observation_date")
        paths.append("entity_repeated_content")
    if "来源" in lowered:
        paths.append("entity_observation_source")
    if not paths:
        paths = ["entity_observation_date", "entity_observation_source", "entity_repeated_content"]
    return _unique(paths)


def _entity_label(entity_id: str) -> str:
    labels = {
        "rag": "RAG",
        "openai": "OpenAI",
        "ai-agent": "AI Agent",
        "anthropic": "Anthropic",
        "apple": "Apple",
        "google": "Google",
        "google-deepmind": "Google DeepMind",
    }
    return labels.get(entity_id, entity_id)


def _unique(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
