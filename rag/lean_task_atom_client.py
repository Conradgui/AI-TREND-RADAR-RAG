"""DeepSeek strict fallback for route-neutral Lean Task Atoms."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from jsonschema import Draft202012Validator

from rag.lean_task_atom_v1 import SCHEMA_PATH, LeanTaskAtomViolation


FUNCTION_NAME = "submit_lean_task_atoms"
REQUIRED_MODEL = "deepseek-v4-flash"
SYSTEM_PROMPT = """Parse one user Query into task atoms and call submit_lean_task_atoms exactly once. Do not answer the Query.
main/supporting atoms contain action, exact target_span copied from QUERY, and success_criterion.
Actions: navigate, discover, trace, relate, verify, explain, compare, recommend, research.
Exactly one main. supporting is only a separate user-requested result, never an evidence-gathering step.
For pronouns or left/right references, copy literal_span and resolve an ATR ID only when PUBLIC_CONTEXT proves it.
For an unresolved reference, use status=unresolved and resolved_value="". For other statuses, resolved_value must be non-empty.
Never emit route labels, answer modes, policies, subjects, constraints, or final answers.
All target_span and reference literal_span values must be exact contiguous QUERY substrings.
"""


class LeanTaskAtomCallError(LeanTaskAtomViolation):
    def __init__(self, message: str, *, diagnostics: dict[str, Any] | None = None):
        super().__init__(message)
        self.diagnostics = diagnostics or {}


def strict_beta_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    return normalized if normalized.endswith("/beta") else normalized + "/beta"


def build_strict_tool() -> dict:
    atom = {
        "type": "object",
        "additionalProperties": False,
        "required": ["action", "target_span", "success_criterion"],
        "properties": {
            "action": {
                "type": "string",
                "enum": ["navigate", "discover", "trace", "relate", "verify", "explain", "compare", "recommend", "research"],
            },
            "target_span": {"type": "string"},
            "success_criterion": {"type": "string"},
        },
    }
    reference = {
        "type": "object",
        "additionalProperties": False,
        "required": ["literal_span", "status", "resolved_value"],
        "properties": {
            "literal_span": {"type": "string"},
            "status": {
                "type": "string",
                "enum": ["resolved_in_query", "resolved_from_context", "unresolved"],
            },
            "resolved_value": {"type": "string"},
        },
    }
    parameters = {
        "type": "object",
        "additionalProperties": False,
        "required": ["main", "supporting", "references", "confidence", "ambiguities"],
        "properties": {
            "main": atom,
            "supporting": {"type": "array", "items": atom},
            "references": {"type": "array", "items": reference},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "ambiguities": {"type": "array", "items": {"type": "string"}},
        },
    }
    return {
        "type": "function",
        "function": {
            "name": FUNCTION_NAME,
            "strict": True,
            "description": "Submit the route-neutral task atoms parsed from the Query.",
            "parameters": parameters,
        },
    }


def validate_reference_statuses(references: list[dict]) -> None:
    for reference in references:
        status = reference["status"]
        resolved = reference["resolved_value"]
        if status == "unresolved" and resolved != "":
            raise LeanTaskAtomCallError("unresolved reference must use an empty resolved_value")
        if status != "unresolved" and not resolved:
            raise LeanTaskAtomCallError(f"{status} reference resolved_value must be non-empty")


class LeanTaskAtomClient:
    request_mode = "deepseek_beta_strict_function_non_thinking"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = 45.0,
        sdk_client=None,
    ):
        if model != REQUIRED_MODEL:
            raise LeanTaskAtomCallError(
                f"strict canary requires model={REQUIRED_MODEL}; got {model or '(missing)'}"
            )
        if sdk_client is None:
            from openai import OpenAI

            sdk_client = OpenAI(
                api_key=api_key,
                base_url=strict_beta_url(base_url),
                timeout=timeout,
                max_retries=0,
            )
        self.client = sdk_client
        self.model = model

    def extract(self, query: str, context: str | None = None) -> tuple[dict, dict]:
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            max_tokens=800,
            extra_body={"thinking": {"type": "disabled"}},
            tools=[build_strict_tool()],
            tool_choice={"type": "function", "function": {"name": FUNCTION_NAME}},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"QUERY:\n{query}\n\nPUBLIC_CONTEXT:\n{context or '(none)'}"},
            ],
        )
        choice = response.choices[0]
        tool_calls = list(choice.message.tool_calls or [])
        diagnostics = _diagnostics(response, tool_calls)
        if len(tool_calls) != 1:
            raise LeanTaskAtomCallError("expected exactly one strict tool call", diagnostics=diagnostics)
        call = tool_calls[0].function
        if call.name != FUNCTION_NAME:
            raise LeanTaskAtomCallError("unexpected tool function name", diagnostics=diagnostics)
        diagnostics["raw_arguments"] = call.arguments
        try:
            value = json.loads(call.arguments)
        except json.JSONDecodeError as exc:
            raise LeanTaskAtomCallError("tool arguments are not valid JSON", diagnostics=diagnostics) from exc

        errors = list(Draft202012Validator(json.loads(SCHEMA_PATH.read_text())).iter_errors(value))
        if errors:
            raise LeanTaskAtomCallError(
                "schema violation: " + "; ".join(error.message for error in errors),
                diagnostics=diagnostics,
            )
        validate_reference_statuses(value["references"])
        _validate_query_and_context_references(query, context, value)
        return value, diagnostics


def _diagnostics(response, tool_calls: list) -> dict:
    usage = response.usage
    return {
        "model": getattr(response, "model", None),
        "finish_reason": response.choices[0].finish_reason,
        "tool_call_count": len(tool_calls),
        "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
        "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
        "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
        "raw_arguments": None,
        "cost_estimate_usd": None,
    }


def _validate_query_and_context_references(query: str, context: str | None, value: dict) -> None:
    for reference in value["references"]:
        if reference["literal_span"] not in query:
            raise LeanTaskAtomCallError("reference span is not literal Query text")
        resolved = reference["resolved_value"]
        if reference["status"] == "resolved_from_context":
            if not re.fullmatch(r"ATR-\d{8}-[A-Z0-9]{6}", resolved, re.I):
                raise LeanTaskAtomCallError("context reference must resolve to a bare ATR ID")
            if resolved.casefold() not in (context or "").casefold():
                raise LeanTaskAtomCallError("resolved ATR ID is absent from public context")


def prompt_sha256() -> str:
    return hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()
