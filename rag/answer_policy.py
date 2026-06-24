"""Deterministic answer policy for grounded RAG responses."""

from __future__ import annotations


def build_answer_policy(plan, citations: list[dict]) -> dict:
    """Build a user-visible answer policy from query plan and citation state."""
    if not citations:
        return {
            "mode": "evidence_insufficient",
            "should_call_llm": False,
            "external_search_required": bool(getattr(plan, "needs_web_search", False)),
            "evidence_boundary": "no_usable_internal_evidence",
            "disclosure": "证据范围：当前 AI Trend Radar 内部语料没有找到足够可用证据。",
            "instruction": "不要生成看似确定的结论；请返回证据不足说明。",
        }

    if getattr(plan, "needs_web_search", False):
        return {
            "mode": "needs_external_evidence",
            "should_call_llm": True,
            "external_search_required": True,
            "evidence_boundary": "internal_corpus_plus_external_needed",
            "disclosure": "证据范围：当前回答只基于 AI Trend Radar 内部语料；该问题仍需要外部证据确认。",
            "instruction": (
                "当前问题仍需要外部证据。只总结内部语料能支持的内容；"
                "不要声称已经完成外部检索；不要编造论文、官方来源、性能数据或实体关系。"
            ),
        }

    if getattr(plan, "answerability_hint", "") == "insufficient-risk":
        return {
            "mode": "evidence_sufficiency_review",
            "should_call_llm": True,
            "external_search_required": False,
            "evidence_boundary": "internal_corpus_sufficiency_review",
            "disclosure": "证据范围：当前回答基于 AI Trend Radar 内部语料，但需要判断证据是否足够支持强结论。",
            "instruction": (
                "当前问题要求判断证据是否足够。请先说明强结论需要哪些证据；"
                "不要把 Product Hunt 热度、GitHub stars、媒体讨论或零散 traction 信号直接等同于商业成功。"
            ),
        }

    return {
        "mode": "internal_grounded",
        "should_call_llm": True,
        "external_search_required": False,
        "evidence_boundary": "internal_corpus_only",
        "disclosure": "证据范围：当前回答基于 AI Trend Radar 内部语料和返回引用。",
        "instruction": (
            "当前问题可先按内部语料回答。请基于引用证据组织结论，"
            "不要把模型记忆或外部事实混入为已检索证据。"
        ),
    }


def mark_external_evidence_used(policy: dict, external_citations: list[dict]) -> dict:
    """Return a policy copy for answers grounded in internal and external evidence."""
    if not external_citations:
        return policy
    updated = dict(policy)
    updated.update(
        {
            "mode": "internal_and_external_grounded",
            "external_search_required": False,
            "evidence_boundary": "internal_corpus_plus_external_evidence",
            "disclosure": "证据范围：当前回答基于 AI Trend Radar 内部语料和已检索到的外部证据。",
            "instruction": (
                "当前问题已包含内部语料和外部证据。请清楚区分两类来源；"
                "只基于引用证据作结论，仍不确定的关系或效果要明确标注。"
            ),
        }
    )
    return updated


def apply_answer_policy(answer: str, policy: dict) -> str:
    """Prepend deterministic evidence-boundary disclosure exactly once."""
    cleaned = (answer or "").strip()
    disclosure = policy.get("disclosure", "").strip()
    if not disclosure:
        return cleaned
    if cleaned.startswith(disclosure) or cleaned.startswith("证据范围："):
        return cleaned
    return f"{disclosure}\n\n{cleaned}"
