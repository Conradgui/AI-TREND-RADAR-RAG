"""Validate and deterministically project route-neutral Lean Task Atoms."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from jsonschema import Draft202012Validator

from rag.query_understanding_v2 import RouteContractV2, _ROUTE_POLICIES, _supporting_contract


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs/rag-transformation/specs/lean-task-atom-v1.schema.json"
_ATR_ID = re.compile(r"ATR-\d{8}-[A-Z0-9]{6}", re.IGNORECASE)
_RECENT_PERIOD = re.compile(r"(?:近|最近|过去)\s*\d+\s*(?:小时|天|周|个月|月|季度|年)")
_PERCENT = re.compile(r"\d+(?:\.\d+)?\s*%")
_QUOTED = re.compile(r"[“\"]([^”\"]+)[”\"]")
_ACTION_FAMILY = {
    "navigate": "item_navigation", "discover": "trend_discovery",
    "trace": "temporal_relation_exploration", "relate": "temporal_relation_exploration",
    "verify": "claim_verification", "explain": "evidence_research",
    "compare": "evidence_research", "recommend": "evidence_research", "research": "evidence_research",
}
_ACTION_SIGNAL = {
    "navigate": "navigation", "trace": "timeline", "relate": "relation",
    "verify": "verification", "explain": "explanation", "compare": "comparison",
    "recommend": "comparison", "research": "deep_research",
}


class LeanTaskAtomViolation(ValueError):
    pass


def project_lean_task_atoms(query: str, context: str | None, value: dict) -> RouteContractV2:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema).iter_errors(value))
    if errors:
        raise LeanTaskAtomViolation("schema violation: " + "; ".join(error.message for error in errors))

    atoms = [value["main"], *value["supporting"]]
    for atom in atoms:
        if atom["target_span"] not in query:
            raise LeanTaskAtomViolation(f"target span is not literal Query text: {atom['target_span']}")
    for reference in value["references"]:
        if reference["literal_span"] not in query:
            raise LeanTaskAtomViolation("reference span is not literal Query text")
        resolved = reference["resolved_value"]
        if reference["status"] == "resolved_from_context" and (
            not resolved or resolved.casefold() not in (context or "").casefold()
        ):
            raise LeanTaskAtomViolation("resolved reference is not present in public context")

    primary = _ACTION_FAMILY[value["main"]["action"]]
    supporting = []
    for atom in value["supporting"]:
        family = _ACTION_FAMILY[atom["action"]]
        if family != primary and family not in supporting:
            supporting.append(family)
    signals = _intent_signals(query, value)
    ambiguities = list(value["ambiguities"])
    for reference in value["references"]:
        if reference["status"] == "unresolved" and "unresolved reference" not in ambiguities:
            ambiguities.append("unresolved reference")
    protected = _protected_spans(query, value)
    resolved_references = [
        {"reference_type": "item_id", "value": reference["resolved_value"].upper(), "origin": "conversation_context"}
        for reference in value["references"]
        if reference["status"] == "resolved_from_context" and reference["resolved_value"]
    ]
    common = dict(
        schema_version="atr.route/2.0",
        request_id=f"shadow-lean-{uuid.uuid5(uuid.NAMESPACE_URL, query + chr(0) + (context or '')).hex}",
        original_query=query, protected_terms=protected, intent_signals=signals,
        primary_task_family=primary, supporting_task_families=supporting,
        answer_mode=_answer_mode(query, value), route_confidence=min(value["confidence"], 0.55) if ambiguities else value["confidence"],
        ambiguities=ambiguities, resolved_references=resolved_references,
        supporting_contracts=[_supporting_contract(family) for family in supporting],
        subjects=[atom["target_span"] for atom in atoms],
        claims=[atom["target_span"] for atom in atoms if atom["action"] == "verify"],
        web_permission="forbidden" if any(term in query for term in ("不要联网", "禁止联网", "别联网", "无需联网")) else ("explicit" if "联网" in query else "on_demand"),
    )
    if primary == "item_navigation":
        return RouteContractV2(**common)
    rewrite, retrieval, prompt, output, budget = _ROUTE_POLICIES[primary]
    return RouteContractV2(
        **common, rewrite_policy_id=rewrite, retrieval_policy_id=retrieval,
        prompt_contract_id=prompt, answer_builder_contract_id=None,
        output_schema_id=output, budget_profile_id=budget,
    )


def _intent_signals(query: str, value: dict) -> list[str]:
    signals = []
    for atom in (value["main"], *value["supporting"]):
        action = atom["action"]
        signal = _ACTION_SIGNAL.get(action)
        if signal:
            _append(signals, signal)
        if action == "discover":
            _append(signals, "recency")
            if any(term in query for term in ("重要", "最值得")):
                _append(signals, "importance")
            elif any(term in query for term in ("动向", "趋势", "热点", "聚类")):
                _append(signals, "trend")
    if value["main"]["action"] == "verify" and any(term in query for term in ("否定", "关系", "反证")):
        _append(signals, "relation")
    return signals


def _answer_mode(query: str, value: dict) -> str:
    action = value["main"]["action"]
    if action == "navigate":
        return "item_disambiguation" if value["ambiguities"] else "exact_item"
    if action == "discover":
        return "important_news" if "重要" in query else "trend_clusters"
    if action == "trace":
        return "timeline"
    if action == "relate":
        return "relation"
    if action == "verify":
        return "verification_verdict"
    if action in {"research", "recommend"} or query.startswith("深度"):
        return "deep_research"
    if action == "compare":
        return "comparison"
    return "explanation"


def _protected_spans(query: str, value: dict) -> list[str]:
    spans = []
    candidates = []
    candidates.extend(match.group(0) for match in _RECENT_PERIOD.finditer(query))
    for reference in value["references"]:
        candidates.append(reference["literal_span"])
    candidates.extend(atom["target_span"] for atom in (value["main"], *value["supporting"]))
    candidates.extend(match.group(1) for match in _QUOTED.finditer(query))
    candidates.extend(match.group(0) for match in _PERCENT.finditer(query))
    if "是否否定" in query:
        candidates.append("是否否定")
    unique_candidates = {
        candidate for candidate in candidates
        if not any(candidate != other and candidate in other for other in candidates)
    }
    for candidate in sorted(unique_candidates, key=lambda span: query.find(span)):
        if candidate in query and candidate not in spans:
            spans.append(candidate)
    return spans


def _append(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)
