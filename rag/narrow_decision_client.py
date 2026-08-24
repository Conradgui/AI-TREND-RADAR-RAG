"""Bounded model adapter for dimensions-only L1 v2."""

from __future__ import annotations

import hashlib
import json
from typing import Protocol

from rag.dimensions_only_l1_v2 import (
    DimensionsOnlyViolation,
    assemble_narrow_decisions_v2,
    validate_dimensions_only_v2,
)


FUNCTION_NAME = "submit_semantic_dimensions_v2"
SYSTEM_PROMPT = """Judge five narrow semantic facts in one user Query and call submit_semantic_dimensions_v2 exactly once. Do not answer the Query.

The five independent facts are:
- item_lookup: asks to locate/open one specific record.
- recent_update_set: asks for a recent set of news, updates, dynamics or hot trends.
- cross_time_or_entity_structure: asks for evolution, timeline, relationships or structural patterns.
- truth_assessable_claim: asks whether a factual proposition is supported, contradicted or true.
- explanation_or_comparison: asks to explain, compare, recommend or research.

For every present or uncertain fact, copy one or more exact contiguous evidence_spans from QUERY. Absent facts have no spans. Do not emit route names, A-E labels, answer modes, policies, protected terms, locators, references or answers. PUBLIC_CONTEXT is background only; reference resolution is deliberately outside your responsibility.
"""


class NarrowDecisionModel(Protocol):
    model: str

    def complete(
        self,
        query: str,
        conversation_context: str | None,
        correction: str | None,
    ) -> tuple[dict, dict]: ...


class NarrowDecisionExtractionError(ValueError):
    pass


class NarrowDecisionClient:
    """Validate dimensions, allow one correction, then assemble deterministic facts."""

    def __init__(self, model: NarrowDecisionModel):
        self.model = model

    def extract(
        self, query: str, conversation_context: str | None = None
    ) -> tuple[dict, dict]:
        correction = None
        attempts = []
        for attempt in (1, 2):
            value, metadata = self.model.complete(
                query, conversation_context, correction
            )
            try:
                validate_dimensions_only_v2(query, value)
            except DimensionsOnlyViolation as exc:
                attempts.append({
                    "attempt": attempt,
                    "valid": False,
                    "error_type": type(exc).__name__,
                    "metadata": metadata,
                })
                correction = str(exc)
                continue
            decisions = assemble_narrow_decisions_v2(
                query, value, conversation_context
            )
            attempts.append({"attempt": attempt, "valid": True, "metadata": metadata})
            return decisions, {
                "model": getattr(self.model, "model", "unknown"),
                "attempts": attempt,
                "attempt_details": attempts,
            }
        raise NarrowDecisionExtractionError(
            "narrow semantic extraction failed after two attempts"
        )


class DeepSeekNarrowDecisionModel:
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
        self,
        query: str,
        conversation_context: str | None,
        correction: str | None,
    ) -> tuple[dict, dict]:
        correction_text = (
            "\n\nPREVIOUS_OUTPUT_VALIDATION_ERROR:\n"
            + correction
            + "\nCorrect only that error; call the function once."
            if correction
            else ""
        )
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            max_tokens=600,
            extra_body={"thinking": {"type": "disabled"}},
            tools=[build_strict_tool()],
            tool_choice={"type": "function", "function": {"name": FUNCTION_NAME}},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT + correction_text},
                {
                    "role": "user",
                    "content": f"QUERY:\n{query}\n\nPUBLIC_CONTEXT:\n{conversation_context or '(none)'}",
                },
            ],
        )
        tool_calls = list(response.choices[0].message.tool_calls or [])
        if len(tool_calls) != 1 or tool_calls[0].function.name != FUNCTION_NAME:
            raise NarrowDecisionExtractionError("expected one dimensions-only tool call")
        try:
            value = json.loads(tool_calls[0].function.arguments)
        except json.JSONDecodeError as exc:
            raise NarrowDecisionExtractionError("tool arguments are not valid JSON") from exc
        usage = response.usage
        return value, {
            "model": getattr(response, "model", self.model),
            "finish_reason": response.choices[0].finish_reason,
            "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
            "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
            "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
        }


def build_strict_tool() -> dict:
    judgment = {
        "type": "object",
        "additionalProperties": False,
        "required": ["state", "evidence_spans"],
        "properties": {
            "state": {"type": "string", "enum": ["present", "absent", "uncertain"]},
            "evidence_spans": {"type": "array", "items": {"type": "string"}},
        },
    }
    dimensions = {
        name: judgment
        for name in (
            "item_lookup",
            "recent_update_set",
            "cross_time_or_entity_structure",
            "truth_assessable_claim",
            "explanation_or_comparison",
        )
    }
    return {
        "type": "function",
        "function": {
            "name": FUNCTION_NAME,
            "strict": True,
            "description": "Submit only five route-neutral semantic dimensions.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "required": ["schema_version", "dimensions"],
                "properties": {
                    "schema_version": {
                        "type": "string",
                        "enum": ["atr.semantic-dimensions/2.0"],
                    },
                    "dimensions": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": list(dimensions),
                        "properties": dimensions,
                    },
                },
            },
        },
    }


def prompt_sha256() -> str:
    return hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()


def _strict_beta_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    return normalized if normalized.endswith("/beta") else normalized + "/beta"
