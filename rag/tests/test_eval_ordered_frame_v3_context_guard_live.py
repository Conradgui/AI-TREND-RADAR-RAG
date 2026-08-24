"""Offline contract test for the one-case context-pollution canary."""

from rag.eval_ordered_frame_v3_context_guard_live import run_context_guard_canary
from rag.ordered_frame_client_v3 import OrderedFrameClientV3


class ContextPollutingModel:
    model = "fixture"

    def complete(self, query: str, conversation_context: str | None):
        return {
            "schema_version": "atr.ordered-semantic-frame/3.0",
            "deliveries": [{
                "task_family": "item_navigation",
                "evidence_spans": ["标题包含“端侧推理框架”"],
                "requested_output_form": "item_disambiguation",
                "locator_kind": "title_fragment",
            }],
            "protected_spans": ["端侧推理框架", "左侧列表中上周新增的是融资新闻"],
            "web_permission": "on_demand",
            "web_evidence_spans": [],
            "unresolved_reference_spans": [],
        }, {"total_tokens": 10}


class ClarifyingModel(ContextPollutingModel):
    def complete(self, query: str, conversation_context: str | None):
        frame, metadata = super().complete(query, conversation_context)
        frame["protected_spans"] = ["端侧推理框架"]
        frame["unresolved_reference_spans"] = ["匹配项"]
        return frame, metadata


def test_context_guard_canary_accepts_route_and_audits_only_optional_pollution() -> None:
    report = run_context_guard_canary(
        OrderedFrameClientV3(ContextPollutingModel())
    )

    assert report["gate"]["passed"] is True
    assert report["case"]["metadata"]["dropped_non_query_protected_spans"] == [
        "左侧列表中上周新增的是融资新闻"
    ]


def test_context_guard_canary_preserves_clarification_diagnostics() -> None:
    report = run_context_guard_canary(OrderedFrameClientV3(ClarifyingModel()))

    assert report["gate"]["passed"] is False
    assert report["case"]["frame"] is not None
    assert report["case"]["envelope"]["status"] == "clarification_required"
    assert report["case"]["error"] is None
