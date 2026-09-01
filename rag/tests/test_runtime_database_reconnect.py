"""Runtime database recovery keeps the existing image, data and vector index."""

from types import SimpleNamespace

import pytest

from rag import server


class FakeNeo4jDriver:
    instances = []

    def __init__(self, *_args, **_kwargs):
        self.connected = False
        self.closed = False
        self.__class__.instances.append(self)

    async def connect(self):
        self.connected = True

    async def close(self):
        self.closed = True

    async def execute_query(self, query, **_kwargs):
        if "SHOW INDEXES" in query:
            return [
                {"name": "entity_search", "state": "ONLINE"},
                {"name": "topic_search", "state": "ONLINE"},
            ]
        if "required_label" in query:
            return [
                {"required_label": "Observation", "node_count": 1},
                {"required_label": "Content", "node_count": 1},
            ]
        return [{"ok": 1}]


@pytest.mark.asyncio
async def test_startup_graph_connection_retries_once_before_degrading(monkeypatch):
    class FlakyDriver(FakeNeo4jDriver):
        def __init__(self):
            super().__init__()
            self.connect_calls = 0

        async def connect(self):
            self.connect_calls += 1
            if self.connect_calls == 1:
                raise OSError("temporary bolt startup lag")
            self.connected = True

    schema_calls = 0

    async def fake_init_schema(_driver):
        nonlocal schema_calls
        schema_calls += 1

    monkeypatch.setattr(server, "init_schema", fake_init_schema)
    driver = FlakyDriver()

    probe = await server._connect_and_verify_graph(
        driver,
        attempts=2,
        retry_delay_seconds=0,
    )

    assert driver.connect_calls == 2
    # An existing healthy graph must not replay all schema DDL on every restart.
    assert schema_calls == 0
    assert (await probe.probe("runtime")).status == "ready"


@pytest.mark.asyncio
async def test_startup_initializes_schema_only_when_required_indexes_are_missing(monkeypatch):
    class MissingIndexDriver(FakeNeo4jDriver):
        indexes_ready = False

        async def execute_query(self, query, **kwargs):
            if "SHOW INDEXES" in query and not self.indexes_ready:
                return []
            return await super().execute_query(query, **kwargs)

    driver = MissingIndexDriver()
    schema_calls = 0

    async def fake_init_schema(_driver):
        nonlocal schema_calls
        schema_calls += 1
        driver.indexes_ready = True

    monkeypatch.setattr(server, "init_schema", fake_init_schema)

    probe = await server._connect_and_verify_graph(driver, attempts=1)

    assert schema_calls == 1
    assert (await probe.probe("runtime")).status == "ready"


@pytest.mark.asyncio
async def test_reconnect_databases_restores_hybrid_runtime_without_rebuilding_index(monkeypatch):
    FakeNeo4jDriver.instances = []
    vector_store = object()
    lexical_store = object()
    answer_composer = object()
    replacement_retriever = object()
    replacement_agent = object()
    state = server.RagState(
        vector_store=vector_store,
        neo4j_driver=None,
        chat_retriever=object(),
        agent=answer_composer,
        answer_composer=answer_composer,
        external_search_registry=None,
        external_deep_fetcher=None,
        lexical_store=lexical_store,
        generation_id="gen-existing",
        retriever_mode="vector-only",
        index_status="vector_ready_graph_unavailable",
    )

    async def fail_if_schema_changes(*_args, **_kwargs):
        raise AssertionError("reconnect must not initialize or mutate the schema")

    def fake_build_runtime(vector, graph, composer, mode, lexical):
        assert vector is vector_store
        assert composer is answer_composer
        assert mode == "hybrid"
        assert lexical is lexical_store
        return replacement_retriever, replacement_agent

    monkeypatch.setattr(server, "Neo4jDriver", FakeNeo4jDriver)
    monkeypatch.setattr(server, "init_schema", fail_if_schema_changes)
    monkeypatch.setattr(
        server,
        "_rebuild_runtime_index",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("reconnect must not rebuild the index")
        ),
    )
    monkeypatch.setattr(server, "_build_retrieval_runtime", fake_build_runtime)
    monkeypatch.setattr(server, "_build_retrieval_gateway", lambda retriever, lexical: "gateway")
    monkeypatch.setattr(server.app, "state", SimpleNamespace(rag=state))

    result = await server.reconnect_databases(api_key="test")
    updated = server.app.state.rag

    assert result == {
        "status": "connected",
        "neo4j_connected": True,
        "retriever_mode": "hybrid",
        "index_generation": "gen-existing",
    }
    assert updated.vector_store is vector_store
    assert updated.generation_id == "gen-existing"
    assert updated.neo4j_driver is FakeNeo4jDriver.instances[0]
    assert updated.chat_retriever is replacement_retriever
    assert updated.agent is replacement_agent
    assert updated.retrieval_gateway == "gateway"
    assert updated.index_status == "ready"


@pytest.mark.asyncio
async def test_reconnect_databases_keeps_last_runtime_when_neo4j_is_still_down(monkeypatch):
    class OfflineNeo4jDriver(FakeNeo4jDriver):
        async def connect(self):
            raise OSError("database unavailable")

    state = server.RagState(
        vector_store=object(),
        neo4j_driver=None,
        chat_retriever=object(),
        agent=object(),
        answer_composer=object(),
        external_search_registry=None,
        external_deep_fetcher=None,
        generation_id="gen-last-good",
        retriever_mode="vector-only",
    )
    monkeypatch.setattr(server, "Neo4jDriver", OfflineNeo4jDriver)
    monkeypatch.setattr(server.app, "state", SimpleNamespace(rag=state))

    with pytest.raises(server.HTTPException) as exc_info:
        await server.reconnect_databases(api_key="test")

    assert exc_info.value.status_code == 503
    assert server.app.state.rag is state


def test_system_panel_offers_database_reconnect_without_shell_execution():
    source = server.DASHBOARD_HTML.read_text(encoding="utf-8")
    backend_source = (server.PROJECT_ROOT / "rag/server.py").read_text(encoding="utf-8")

    assert 'id="databaseReconnectBtn"' in source
    assert "function reconnectDatabases" in source
    assert "'/runtime/reconnect-databases'" in source
    assert "docker compose" not in source
    assert "child_process" not in source
    assert "import subprocess" not in backend_source
    assert "os.system(" not in backend_source


@pytest.mark.asyncio
async def test_reconnect_reads_the_latest_runtime_after_acquiring_the_lock(monkeypatch):
    latest_vector = object()
    latest_lexical = object()
    latest_composer = object()
    latest = server.RagState(
        vector_store=latest_vector,
        neo4j_driver=None,
        chat_retriever=object(),
        agent=object(),
        answer_composer=latest_composer,
        external_search_registry=object(),
        external_deep_fetcher=object(),
        lexical_store=latest_lexical,
        generation_id="gen-latest",
        retriever_mode="vector-only",
    )
    monkeypatch.setattr(server, "Neo4jDriver", FakeNeo4jDriver)
    monkeypatch.setattr(server.app, "state", SimpleNamespace(rag=latest))

    def build(vector, _graph, composer, _mode, lexical):
        assert vector is latest_vector
        assert composer is latest_composer
        assert lexical is latest_lexical
        return object(), object()

    monkeypatch.setattr(server, "_build_retrieval_runtime", build)
    monkeypatch.setattr(server, "_build_retrieval_gateway", lambda *_args: object())

    await server.reconnect_databases(api_key="test")

    updated = server.app.state.rag
    assert updated.generation_id == "gen-latest"
    assert updated.external_search_registry is latest.external_search_registry
    assert updated.external_deep_fetcher is latest.external_deep_fetcher
