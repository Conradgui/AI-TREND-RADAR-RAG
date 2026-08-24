"""Graph ingestion transaction-boundary tests."""

import pytest

import rag.ingest as ingest
from rag.graphrag.driver import _TransactionDriver


@pytest.mark.asyncio
async def test_each_graph_date_is_ingested_in_one_driver_transaction(monkeypatch):
    transaction_writers = []
    ingested = []
    rollup_refreshes = []

    class FakeDriver:
        async def execute_write_transaction(self, work):
            writer = object()
            transaction_writers.append(writer)
            await work(writer)

    class FakeBuilder:
        def __init__(self, writer):
            self.writer = writer

        async def ingest_date(self, date, topic_pool, reports, *, refresh_rollups=True):
            ingested.append((date, self.writer, topic_pool, reports, refresh_rollups))

        async def refresh_rollups(self):
            rollup_refreshes.append(self.writer)

    async def fake_init_schema(_driver):
        return None

    monkeypatch.setattr(ingest, "select_ingestion_dates", lambda dates: dates)
    monkeypatch.setattr(ingest, "_load_topic_pool", lambda _path: {"candidates": [{"title": "x"}]})
    monkeypatch.setattr(ingest, "_load_reports", lambda _path: {"ai-topic-radar": "report"})
    monkeypatch.setattr(ingest, "load_search_documents", lambda: [])
    monkeypatch.setattr("rag.graphrag.builder.KnowledgeGraphBuilder", FakeBuilder)
    monkeypatch.setattr("rag.graphrag.schema.init_schema", fake_init_schema)

    result = await ingest.ingest_graph_dates(FakeDriver(), ["2026-08-09", "2026-08-10"])

    assert result == ["2026-08-09", "2026-08-10"]
    assert len(transaction_writers) == 2
    assert [row[1] for row in ingested] == transaction_writers
    assert [row[4] for row in ingested] == [False, False]
    assert len(rollup_refreshes) == 1
    assert rollup_refreshes[0] is not transaction_writers[0]


@pytest.mark.asyncio
async def test_transaction_driver_supports_reads_inside_atomic_date_rebuild():
    class Record:
        def data(self):
            return {"content_ids": ["content-1"]}

    class Result:
        def __aiter__(self):
            self._rows = iter([Record()])
            return self

        async def __anext__(self):
            try:
                return next(self._rows)
            except StopIteration as exc:
                raise StopAsyncIteration from exc

    class Transaction:
        async def run(self, cypher, parameters, timeout):
            assert "Observation" in cypher
            assert parameters == {"date": "2026-08-10"}
            return Result()

    rows = await _TransactionDriver(Transaction()).execute_query(
        "MATCH (o:Observation {date: $date}) RETURN collect(o.contentId) AS content_ids",
        date="2026-08-10",
    )

    assert rows == [{"content_ids": ["content-1"]}]
