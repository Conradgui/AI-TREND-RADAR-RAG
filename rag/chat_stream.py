"""Transport-neutral progressive events for one grounded chat request."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable


ProgressCallback = Callable[[str, dict], Awaitable[None]]
ResponseBuilder = Callable[[ProgressCallback], Awaitable[dict]]
TimeoutCallback = Callable[[], Awaitable[None]]


def encode_stream_event(event: dict) -> str:
    """Encode one event as compact NDJSON for incremental browser parsing."""
    return json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"


def _answer_chunks(answer: str, max_chars: int = 800) -> list[str]:
    """Split a validated answer at paragraph seams while preserving exact text."""
    if not answer:
        return []

    paragraphs = answer.split("\n\n")
    chunks: list[str] = []
    for index, paragraph in enumerate(paragraphs):
        suffix = "\n\n" if index < len(paragraphs) - 1 else ""
        text = paragraph + suffix
        while len(text) > max_chars:
            chunks.append(text[:max_chars])
            text = text[max_chars:]
        if text:
            chunks.append(text)
    return chunks


async def iter_chat_events(
    build_response: ResponseBuilder,
    *,
    timeout_seconds: float,
    on_timeout: TimeoutCallback | None = None,
) -> AsyncIterator[dict]:
    """Run one request and expose truthful progress through a small event interface.

    The answer is emitted only after ``build_response`` has completed its evidence
    validation.  Progress events may arrive earlier, but they contain execution
    facts rather than model chain-of-thought.
    """
    queue: asyncio.Queue[dict] = asyncio.Queue()

    async def report(event: str, data: dict) -> None:
        await queue.put({"event": event, "data": data})

    async def run() -> dict:
        return await asyncio.wait_for(
            build_response(report),
            timeout=timeout_seconds,
        )

    task = asyncio.create_task(run())
    yield {
        "event": "accepted",
        "data": {"message": "问题已接收，准备分析"},
    }

    try:
        while not task.done() or not queue.empty():
            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.05)
            except asyncio.TimeoutError:
                continue
            yield event

        response = await task
        yield {
            "event": "source_groups",
            "data": {
                "citations": response.get("citations", []),
                "search_references": response.get("search_references", []),
                "source_summary": response.get("source_summary", {}),
                "evidence_display_map": response.get("evidence_display_map", {}),
            },
        }
        display_answer = response.get("display_answer") or response.get("answer", "")
        for chunk in _answer_chunks(display_answer):
            yield {"event": "answer_chunk", "data": {"content": chunk}}

        yield {
            "event": "citations",
            "data": {
                "citations": response.get("citations", []),
                "claim_evidence": response.get("claim_evidence", []),
            },
        }
        yield {
            "event": "done",
            "data": {
                "evidence_integrity": response.get("evidence_integrity", {}),
                "query_understanding": response.get("query_understanding", {}),
                "tool_trace": response.get("tool_trace", {}),
            },
        }
    except asyncio.TimeoutError:
        if on_timeout is not None:
            await on_timeout()
        yield {
            "event": "error",
            "data": {
                "code": "request_timeout",
                "message": "请求处理超时，请简化问题或稍后重试。",
                "retryable": True,
            },
        }
    except asyncio.CancelledError:
        task.cancel()
        raise
    except Exception:
        yield {
            "event": "error",
            "data": {
                "code": "stream_failed",
                "message": "回答生成失败，请稍后重试。",
                "retryable": True,
            },
        }
    finally:
        if not task.done():
            task.cancel()
        try:
            await task
        except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
            pass
