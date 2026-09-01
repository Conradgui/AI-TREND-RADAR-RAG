"""Tests for config and graphrag modules."""

from rag.config import (
    NEO4J_URI,
    DEFAULT_CORPUS_UPDATE_INTERVAL_SECONDS,
    DEFAULT_UPSTREAM_CORPUS_URL,
    get_corpus_update_interval_seconds,
    get_upstream_corpus_url,
    is_configured,
    is_startup_corpus_update_enabled,
)


def test_neo4j_defaults():
    assert NEO4J_URI == "bolt://localhost:7687"


def test_is_configured_reflects_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    from rag import config
    old = config.ANTHROPIC_API_KEY
    config.ANTHROPIC_API_KEY = "sk-test"
    assert config.is_configured() is True
    config.ANTHROPIC_API_KEY = old


def test_startup_corpus_update_is_frozen_by_default() -> None:
    assert is_startup_corpus_update_enabled({}) is False


def test_startup_corpus_update_requires_explicit_opt_in() -> None:
    assert is_startup_corpus_update_enabled(
        {"RAG_STARTUP_CORPUS_UPDATE_ENABLED": "true"}
    ) is True
    assert is_startup_corpus_update_enabled(
        {"RAG_STARTUP_CORPUS_UPDATE_ENABLED": "false"}
    ) is False


def test_managed_corpus_defaults_are_safe_and_configurable() -> None:
    assert get_upstream_corpus_url({}) == DEFAULT_UPSTREAM_CORPUS_URL
    assert get_upstream_corpus_url(
        {"RAG_UPSTREAM_CORPUS_URL": "https://example.test/corpus/"}
    ) == "https://example.test/corpus"

    assert get_corpus_update_interval_seconds({}) == DEFAULT_CORPUS_UPDATE_INTERVAL_SECONDS
    assert get_corpus_update_interval_seconds(
        {"RAG_CORPUS_UPDATE_INTERVAL_SECONDS": "900"}
    ) == 900
    assert get_corpus_update_interval_seconds(
        {"RAG_CORPUS_UPDATE_INTERVAL_SECONDS": "invalid"}
    ) == DEFAULT_CORPUS_UPDATE_INTERVAL_SECONDS
    assert get_corpus_update_interval_seconds(
        {"RAG_CORPUS_UPDATE_INTERVAL_SECONDS": "1"}
    ) == 60


def test_schema_queries_not_empty():
    from rag.graphrag.schema import SCHEMA_QUERIES
    assert len(SCHEMA_QUERIES) >= 5
    assert any("Topic" in q for q in SCHEMA_QUERIES)


def test_driver_class_exists():
    from rag.graphrag.driver import Neo4jDriver
    d = Neo4jDriver()
    assert d._uri == "bolt://localhost:7687"
