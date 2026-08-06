"""Behavior tests for the progressive chat event interface."""

import asyncio

import pytest

from rag.chat_stream import encode_stream_event, iter_chat_events


@pytest.mark.asyncio
async def test_stream_emits_progress_then_validated_answer_citations_and_done():
    async def build_response(progress_callback):
        await progress_callback("understanding", {"task_mode": "general"})
        await progress_callback("retrieving", {"top_k": 10})
        await progress_callback("evidence_ready", {"admitted_count": 3})
        await progress_callback("generating", {"execution_path": "direct_composer"})
        return {
            "answer": "第一段答案。[E1]\n\n第二段答案。[E2]",
            "display_answer": "第一段答案。[I1]\n\n第二段答案。[W1 🌐]",
            "citations": [
                {"evidence_id": "E1", "display_label": "I1"},
                {"evidence_id": "E2", "display_label": "W1"},
            ],
            "evidence_display_map": {"E1": "I1", "E2": "W1"},
            "search_references": [{"url": "https://example.com/read", "source_role": "discovery_only"}],
            "source_summary": {"internal_citations": 1, "external_citations": 1},
            "claim_evidence": [],
            "evidence_integrity": {"valid": True},
            "query_understanding": {"task_mode": "general"},
            "tool_trace": {"timings": {"total_ms": 123.0}},
        }

    events = [event async for event in iter_chat_events(build_response, timeout_seconds=1)]

    assert [event["event"] for event in events] == [
        "accepted",
        "understanding",
        "retrieving",
        "evidence_ready",
        "generating",
        "source_groups",
        "answer_chunk",
        "answer_chunk",
        "citations",
        "done",
    ]
    assert "".join(
        event["data"]["content"]
        for event in events
        if event["event"] == "answer_chunk"
    ) == "第一段答案。[I1]\n\n第二段答案。[W1 🌐]"
    source_groups = next(event for event in events if event["event"] == "source_groups")
    assert source_groups["data"]["evidence_display_map"] == {"E1": "I1", "E2": "W1"}
    assert source_groups["data"]["search_references"][0]["source_role"] == "discovery_only"
    assert events[-1]["data"]["evidence_integrity"]["valid"] is True


@pytest.mark.asyncio
async def test_stream_reports_timeout_and_cancels_unfinished_work():
    cancelled = asyncio.Event()

    async def build_response(progress_callback):
        await progress_callback("understanding", {"task_mode": "general"})
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.set()

    events = [event async for event in iter_chat_events(build_response, timeout_seconds=0.01)]

    assert [event["event"] for event in events] == ["accepted", "understanding", "error"]
    assert events[-1]["data"]["code"] == "request_timeout"
    assert cancelled.is_set()


def test_stream_event_encoding_is_one_json_object_per_line():
    encoded = encode_stream_event({"event": "accepted", "data": {"message": "已接收"}})

    assert encoded.endswith("\n")
    assert encoded.count("\n") == 1
    assert '"event":"accepted"' in encoded
