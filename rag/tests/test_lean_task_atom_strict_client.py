"""Request-contract tests for the DeepSeek strict Lean Task Atom client."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from rag.lean_task_atom_client import LeanTaskAtomCallError, LeanTaskAtomClient


def _response(*, arguments: dict | None, finish_reason: str = "tool_calls"):
    function = None if arguments is None else SimpleNamespace(
        name="submit_lean_task_atoms", arguments=json.dumps(arguments, ensure_ascii=False)
    )
    tool_calls = [] if function is None else [SimpleNamespace(function=function)]
    return SimpleNamespace(
        choices=[SimpleNamespace(
            finish_reason=finish_reason,
            message=SimpleNamespace(tool_calls=tool_calls, content=None),
        )],
        usage=SimpleNamespace(prompt_tokens=20, completion_tokens=12, total_tokens=32),
    )


class _Completions:
    def __init__(self, response):
        self.response = response
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return self.response


class _OpenAI:
    def __init__(self, response):
        self.chat = SimpleNamespace(completions=_Completions(response))


def _value() -> dict:
    return {
        "main": {"action": "discover", "target_span": "模型水印", "success_criterion": "汇总重要动态"},
        "supporting": [], "references": [], "confidence": 0.9, "ambiguities": [],
    }


def test_extract_uses_non_thinking_forced_strict_function_call() -> None:
    sdk = _OpenAI(_response(arguments=_value()))
    client = LeanTaskAtomClient(
        api_key="not-used", base_url="https://api.deepseek.com", model="deepseek-v4-flash",
        sdk_client=sdk,
    )

    value, usage = client.extract("汇总模型水印的重要动态")

    assert value == _value()
    kwargs = sdk.chat.completions.kwargs
    assert kwargs["extra_body"] == {"thinking": {"type": "disabled"}}
    assert kwargs["tools"][0]["function"]["strict"] is True
    assert kwargs["tool_choice"] == {
        "type": "function", "function": {"name": "submit_lean_task_atoms"},
    }
    assert "response_format" not in kwargs
    assert usage["raw_arguments"] == json.dumps(_value(), ensure_ascii=False)
    assert usage["completion_tokens"] == 12


def test_extract_preserves_diagnostics_when_tool_call_is_missing() -> None:
    sdk = _OpenAI(_response(arguments=None, finish_reason="stop"))
    client = LeanTaskAtomClient(
        api_key="not-used", base_url="https://api.deepseek.com", model="deepseek-v4-flash",
        sdk_client=sdk,
    )

    with pytest.raises(LeanTaskAtomCallError) as caught:
        client.extract("比较两个条目")

    assert caught.value.diagnostics["finish_reason"] == "stop"
    assert caught.value.diagnostics["tool_call_count"] == 0
    assert caught.value.diagnostics["total_tokens"] == 32


def test_client_refuses_any_model_except_frozen_flash_model() -> None:
    with pytest.raises(LeanTaskAtomCallError, match="requires model=deepseek-v4-flash"):
        LeanTaskAtomClient(
            api_key="not-used", base_url="https://api.deepseek.com",
            model="deepseek-chat", sdk_client=_OpenAI(_response(arguments=_value())),
        )
