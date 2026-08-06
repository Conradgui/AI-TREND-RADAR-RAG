"""Tests for agent tools — creation and basic validation."""

import json
import re

import pytest

from rag.agent.tools import create_tools
from rag.evidence_ledger import EvidenceLedger, activate_evidence_ledger, deactivate_evidence_ledger
from rag.retriever.hybrid import RetrievedChunk


def test_create_tools_returns_six():
    class MockDriver:
        async def execute_query(self, cypher, **params):
            return []

    class MockRetriever:
        async def search(self, query, k=5):
            return []

    tools = create_tools(MockDriver(), MockRetriever())
    assert len(tools) == 6
    names = [t.name for t in tools]
    assert "search" in names
    assert "topic_trend" in names
    assert "entity_info" in names
    assert "daily_overview" in names
    assert "source_coverage" in names
    assert "recommend" in names


def test_date_regex():
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", "2026-05-28")
    assert not re.match(r"^\d{4}-\d{2}-\d{2}$", "2026-5-8")
    assert not re.match(r"^\d{4}-\d{2}-\d{2}$", "not-a-date")


@pytest.mark.asyncio
async def test_search_tool_admits_retrieved_evidence_into_active_ledger():
    class MockDriver:
        async def execute_query(self, cypher, **params):
            return []

    class MockRetriever:
        async def search(self, query, k=5):
            return [
                RetrievedChunk(
                    text="Claude Code Artifacts supports sharing coding work.",
                    source="vector",
                    score=0.9,
                    metadata={
                        "date": "2026-06-21",
                        "source": "Product Hunt",
                        "title": "Claude Code Artifacts",
                        "citation_id": "2026-06-21/topic-pool/0",
                    },
                )
            ]

    search = next(tool for tool in create_tools(MockDriver(), MockRetriever()) if tool.name == "search")
    ledger = EvidenceLedger()
    token = activate_evidence_ledger(ledger)
    try:
        payload = json.loads(await search.ainvoke({"query": "Claude Code"}))
    finally:
        deactivate_evidence_ledger(token)

    assert payload["evidence"][0]["evidence_id"] == "E1"
    assert "[E1]" in payload["result"]
    assert ledger.records[0]["citation_id"] == "2026-06-21/topic-pool/0"
