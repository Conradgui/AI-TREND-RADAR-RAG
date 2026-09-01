"""One-attempt strict adapter for Ordered Semantic Frame v3."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Protocol

from rag.ordered_semantic_frame_v3 import (
    OrderedSemanticFrameViolation,
    SCHEMA_PATH,
    build_ordered_route_envelope_v3,
    validate_ordered_semantic_frame_v3,
)


FUNCTION_NAME = "submit_ordered_semantic_frame_v3"
SYSTEM_PROMPT = """Extract one ordered semantic frame from QUERY and call submit_ordered_semantic_frame_v3 exactly once. Do not answer the Query.

A delivery is an independently routed product task the user explicitly asks the system to perform. Every explicitly requested distinct task family remains a delivery, in the same order as QUERY. Multiple requested sections inside the same task family form one delivery, but choose the output form the user actually requests rather than the most elaborate form. Constraints such as a date range, entity name, source preference, or permission do not create a delivery by themselves. If the requested action is clear but its object is unresolved, keep the delivery and record the unresolved reference. Only emit an empty deliveries array when the requested action itself cannot be identified.

Task families and output forms:
- item_navigation: locate/open records; exact_item or item_disambiguation.
- trend_discovery: recent news, updates, important dynamics, or hot topics; important_news or trend_clusters.
- temporal_relation_exploration: evolution, timeline, relationships, longitudinal or cross-sectional structure; timeline, relation, longitudinal_trend, or cross_sectional_trend.
- claim_verification: judge whether a factual proposition is supported; verification_verdict.
- evidence_research: explain, compare, recommend, or research; explanation, comparison, or deep_research.

Decision boundaries:
- Do not auto-upgrade important_news to trend_clusters. Use important_news for requests asking for recent dynamics, news, updates, or important developments. Use trend_clusters only when QUERY explicitly asks to cluster, group, categorize, or synthesize recurring patterns. The mere word “trend” does not require trend_clusters.
- Every explicitly requested distinct task family remains a delivery. A delivery may provide useful context for another delivery, but that does not erase the user's separately requested action.
- Comparing the same entity across time, versions, or stages is temporal_relation_exploration. Use timeline only when the user asks for ordered discrete events or milestones; use longitudinal_trend for continuous change across a span without fixed comparison points; use cross_sectional_trend when the user asks to compare the same entity at two or more explicit time points, snapshots, versions, or stages. Use relation for non-temporal relationships among entities or events, including relationships among named entities and requests that distinguish cooperation from co-occurrence. Comparing attributes of different entities, products, or approaches is evidence_research comparison.
- Use deep_research only when the user explicitly requests deep, comprehensive, or systematic research. An ordinary impact analysis remains explanation even when it requires evidence.
- Unresolved references do not erase an otherwise explicit delivery. Record the unresolved span and let the downstream envelope request clarification while preserving the requested task.

For item_navigation, use locator_kind atr_id/full_title only when QUERY supplies that observable locator; otherwise use title_fragment or descriptive. The output form must match the locator: atr_id/full_title -> exact_item; title_fragment/descriptive -> item_disambiguation. Other task families use locator_kind none.

web_permission: forbidden only for an explicit denial; explicit only for a direct request to search the web; otherwise on_demand, including “必要时可以联网”. Copy the exact permission phrase into web_evidence_spans when present. Do not duplicate web-permission phrases in protected_spans unless the same text independently contains a content constraint whose loss would change the requested subject or claim.

protected_spans contains only exact content-changing constraints that have no dedicated field, such as numeric thresholds or negative scope constraints. Do not duplicate delivery evidence, subjects, sources, claims, time expressions, or web-permission phrases in protected_spans. unresolved_reference_spans contains only Query references whose antecedent is absent from QUERY and not explicitly mapped in PUBLIC_CONTEXT. A postposed claim after “这个说法” is not unresolved.

claim_spans contains every factual proposition or explicit hypothesis that the user asks the system to verify, assess, or reason from. Copy each claim as exact contiguous QUERY text. Do not put a topic, question instruction, source preference, or model-invented paraphrase in claim_spans. Use an empty array when QUERY contains no proposition.

subject_spans contains the exact named entities, products, records, or events that are objects of the requested task. An earlier subject in the same QUERY may be a later pronoun's antecedent. source_spans contains only exact publisher or organization names explicitly requested as evidence sources, such as the organization in “X 官方材料”. A source-only phrase is not a subject or a pronoun antecedent. Do not duplicate subject_spans, source_spans, claim_spans, or web_evidence_spans in protected_spans unless the same literal independently carries an additional content-changing constraint.

Every evidence or protected span must be copied exactly from QUERY. PUBLIC_CONTEXT is background only. Never output a standalone rewrite, route policy, prompt ID, retrieval plan, budget, answer, or invented ATR ID.

retrieval_hints is optional and retrieval-only. Use it only when a user names an abstract capability or concept whose common corpus wording may differ across languages. Emit at most six short neutral search phrases; for each abstract capability, include its direct translation and, when useful, a conservative implementation synonym used in technical artifacts. For example, “跨会话上下文” may use “persistent context across sessions” or “session memory”; “代码库知识” may use “codebase context” or “codebase knowledge graph”. Do not invent a product, organization, ATR ID, event, factual claim, or answer. Do not place named subjects in retrieval_hints.
"""

_ATR_ID = re.compile(r"ATR-\d{8}-[A-Z0-9]{6}", re.IGNORECASE)
_FULL_TITLE = re.compile(r"《[^》]+》")
_WEB_FORBIDDEN = ("不要联网", "禁止联网", "无需联网", "不联网")
_WEB_EXPLICIT = ("请联网搜索", "请联网核验", "请联网分析", "请联网看看", "请联网查", "联网搜索")
_CONTENT_NEGATION = re.compile(r"(?:不要|不应|不可|无需|不必)[^，。！？；;]+")


class OrderedFrameModelV3(Protocol):
    model: str

    def complete(
        self, query: str, conversation_context: str | None
    ) -> tuple[dict, dict]: ...


class OrderedFrameExtractionError(ValueError):
    pass


class OrderedFrameClientV3:
    """Accept one model result or fail closed; no semantic correction retry."""

    def __init__(self, model: OrderedFrameModelV3):
        self.model = model

    def extract(
        self, query: str, conversation_context: str | None = None
    ) -> tuple[dict, dict]:
        value, metadata = self.model.complete(query, conversation_context)
        value, sanitation = sanitize_model_frame_v3(query, value, conversation_context)
        try:
            validate_ordered_semantic_frame_v3(query, value)
        except OrderedSemanticFrameViolation as exc:
            raise OrderedFrameExtractionError(
                f"ordered frame failed its single attempt: {exc}"
            ) from exc
        return value, {
            "model": getattr(self.model, "model", "unknown"),
            "attempts": 1,
            **sanitation,
            **metadata,
        }


def sanitize_model_frame_v3(
    query: str,
    value: dict,
    conversation_context: str | None = None,
) -> tuple[dict, dict]:
    """Apply literal-only safety guards, then validate the model's semantic frame."""
    frame = deepcopy(value)
    for field in ("claim_spans", "subject_spans", "source_spans"):
        frame.setdefault(field, [])
    frame["retrieval_hints"] = _sanitize_retrieval_hints(frame.get("retrieval_hints"))
    normalized_locators = []
    observable_locator = (
        "atr_id" if _ATR_ID.search(query)
        else "full_title" if _FULL_TITLE.search(query)
        else None
    )
    if observable_locator:
        for delivery in frame.get("deliveries", []):
            if delivery.get("task_family") != "item_navigation":
                continue
            if (
                delivery.get("locator_kind") != observable_locator
                or delivery.get("requested_output_form") != "exact_item"
            ):
                delivery["locator_kind"] = observable_locator
                delivery["requested_output_form"] = "exact_item"
                normalized_locators.append(observable_locator)

    normalized_permission = None
    permission_literal = _first_literal(query, _WEB_FORBIDDEN)
    permission = "forbidden"
    if permission_literal is None:
        permission_literal = _first_literal(query, _WEB_EXPLICIT)
        permission = "explicit"
    if permission_literal is not None:
        if frame.get("web_permission") != permission or frame.get("web_evidence_spans") != [permission_literal]:
            frame["web_permission"] = permission
            frame["web_evidence_spans"] = [permission_literal]
            normalized_permission = permission

    protected = frame.get("protected_spans")
    if not isinstance(protected, list):
        return frame, {
            "dropped_non_query_protected_spans": [],
            "normalized_observable_locators": normalized_locators,
            "normalized_web_permission": normalized_permission,
        }
    dropped = [span for span in protected if not isinstance(span, str) or span not in query]
    dedicated_spans = [
        span
        for field in ("claim_spans", "subject_spans", "source_spans", "web_evidence_spans")
        for span in frame.get(field, [])
        if isinstance(span, str) and span
    ]
    valid_protected = [
        span for span in protected if isinstance(span, str) and span in query
    ]
    cross_field = [
        span
        for span in valid_protected
        if any(span in dedicated or dedicated in span for dedicated in dedicated_spans)
    ]
    frame["protected_spans"] = [
        span for span in valid_protected if span not in cross_field
    ]
    for match in _CONTENT_NEGATION.finditer(query):
        literal = match.group(0).strip()
        if any(web_literal in literal for web_literal in (*_WEB_FORBIDDEN, *_WEB_EXPLICIT)):
            continue
        if literal and literal not in frame["protected_spans"]:
            frame["protected_spans"].append(literal)
    return frame, {
        "dropped_non_query_protected_spans": dropped,
        "dropped_cross_field_protected_spans": cross_field,
        "normalized_observable_locators": normalized_locators,
        "normalized_web_permission": normalized_permission,
        "retrieval_hint_count": len(frame["retrieval_hints"]),
    }


def _sanitize_retrieval_hints(value: object) -> list[str]:
    """Keep untrusted model paraphrases bounded and evidence-neutral."""
    if not isinstance(value, list):
        return []
    hints: list[str] = []
    for raw in value:
        hint = " ".join(str(raw or "").split())
        if len(hint) < 2 or len(hint) > 160 or _ATR_ID.search(hint):
            continue
        if hint not in hints:
            hints.append(hint)
        if len(hints) == 6:
            break
    return hints


def _first_literal(query: str, candidates: tuple[str, ...]) -> str | None:
    matches = [(query.find(candidate), candidate) for candidate in candidates if candidate in query]
    return min(matches)[1] if matches else None


def understand_ordered_query_v3(
    query: str,
    extractor: OrderedFrameClientV3,
    conversation_context: str | None = None,
) -> tuple[dict, dict]:
    frame, metadata = extractor.extract(query, conversation_context)
    envelope = build_ordered_route_envelope_v3(query, frame, conversation_context)
    return envelope, {**metadata, "frame": frame}


class DeepSeekOrderedFrameModelV3:
    request_mode = "deepseek_beta_strict_function_non_thinking"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = 20.0,
        sdk_client=None,
    ):
        if sdk_client is None:
            from openai import OpenAI

            sdk_client = OpenAI(
                api_key=api_key,
                base_url=_strict_beta_url(base_url),
                timeout=timeout,
                max_retries=0,
            )
        self.client = sdk_client
        self.model = model

    def complete(
        self, query: str, conversation_context: str | None
    ) -> tuple[dict, dict]:
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            max_tokens=900,
            extra_body={"thinking": {"type": "disabled"}},
            tools=[build_strict_tool_v3()],
            tool_choice={"type": "function", "function": {"name": FUNCTION_NAME}},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"QUERY:\n{query}\n\nPUBLIC_CONTEXT:\n{conversation_context or '(none)'}",
                },
            ],
        )
        tool_calls = list(response.choices[0].message.tool_calls or [])
        if len(tool_calls) != 1 or tool_calls[0].function.name != FUNCTION_NAME:
            raise OrderedFrameExtractionError("expected one ordered-frame tool call")
        try:
            value = json.loads(tool_calls[0].function.arguments)
        except json.JSONDecodeError as exc:
            raise OrderedFrameExtractionError("tool arguments are not valid JSON") from exc
        usage = response.usage
        return value, {
            "finish_reason": response.choices[0].finish_reason,
            "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
            "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
            "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
        }


def build_strict_tool_v3() -> dict:
    parameters = json.loads(SCHEMA_PATH.read_text())
    for metadata_key in ("$schema", "$id", "title"):
        parameters.pop(metadata_key, None)
    parameters.pop("allOf", None)
    parameters["properties"]["schema_version"] = {
        "type": "string",
        "enum": ["atr.ordered-semantic-frame/3.0"],
    }
    parameters["properties"]["web_permission"] = {
        "type": "string",
        "enum": ["forbidden", "on_demand", "explicit"],
    }
    parameters["properties"]["deliveries"]["items"] = {
        "anyOf": _provider_delivery_variants()
    }
    for field in ("claim_spans", "subject_spans", "retrieval_hints", "source_spans"):
        if field not in parameters["required"]:
            parameters["required"].append(field)
    return {
        "type": "function",
        "function": {
            "name": FUNCTION_NAME,
            "strict": True,
            "description": "Submit only the ordered semantic frame for the Query.",
            "parameters": parameters,
        },
    }


def _provider_delivery_variants() -> list[dict]:
    variants = []
    for family, outputs, locators in (
        ("item_navigation", ["exact_item"], ["atr_id", "full_title"]),
        (
            "item_navigation",
            ["item_disambiguation"],
            ["title_fragment", "descriptive"],
        ),
        ("trend_discovery", ["important_news", "trend_clusters"], ["none"]),
        (
            "temporal_relation_exploration",
            ["timeline", "relation", "longitudinal_trend", "cross_sectional_trend"],
            ["none"],
        ),
        ("claim_verification", ["verification_verdict"], ["none"]),
        ("evidence_research", ["explanation", "comparison", "deep_research"], ["none"]),
    ):
        variants.append({
            "type": "object",
            "additionalProperties": False,
            "required": [
                "task_family",
                "evidence_spans",
                "requested_output_form",
                "locator_kind",
            ],
            "properties": {
                "task_family": {"type": "string", "enum": [family]},
                "evidence_spans": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"type": "string"},
                },
                "requested_output_form": {"type": "string", "enum": outputs},
                "locator_kind": {"type": "string", "enum": locators},
            },
        })
    return variants


def prompt_sha256_v3() -> str:
    return hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()


def _strict_beta_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    return normalized if normalized.endswith("/beta") else normalized + "/beta"
