"""Configuration — reads project root .env when python-dotenv is available."""

from __future__ import annotations

import os
from pathlib import Path

from rag.sync_corpus import DEFAULT_BASE_URL as DEFAULT_UPSTREAM_CORPUS_URL

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None

# Load .env from project root (parent of rag/)
_PROJECT_ROOT = Path(__file__).parent.parent
if load_dotenv:
    load_dotenv(_PROJECT_ROOT / ".env")

# LLM — same keys as TypeScript pipeline
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MAX_TOKENS = int(os.getenv("DEEPSEEK_MAX_TOKENS", "1200"))
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "")

# Neo4j
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# Paths
DIGESTS_DIR = str(_PROJECT_ROOT / "digests")
CHROMA_DIR = str(Path(__file__).parent / "data" / "chroma")
INDEX_GENERATIONS_DIR = str(Path(__file__).parent / "data" / "index-generations")

# Server
RAG_HOST = os.getenv("RAG_HOST", "0.0.0.0")
RAG_PORT = int(os.getenv("RAG_PORT", "8001"))
RAG_ENABLE_DEEP_FETCH = os.getenv("RAG_ENABLE_DEEP_FETCH", "false")
RAG_STARTUP_CORPUS_UPDATE_ENABLED = os.getenv(
    "RAG_STARTUP_CORPUS_UPDATE_ENABLED", "false"
)
DEFAULT_CORPUS_UPDATE_INTERVAL_SECONDS = 6 * 60 * 60
RAG_CORPUS_UPDATE_INTERVAL_SECONDS = os.getenv(
    "RAG_CORPUS_UPDATE_INTERVAL_SECONDS",
    str(DEFAULT_CORPUS_UPDATE_INTERVAL_SECONDS),
)
RAG_UPSTREAM_CORPUS_URL = os.getenv(
    "RAG_UPSTREAM_CORPUS_URL", DEFAULT_UPSTREAM_CORPUS_URL
)
RAG_CORPUS_RECHECK_DAYS = os.getenv("RAG_CORPUS_RECHECK_DAYS", "30")

# Optional external search providers
BRAVE_SEARCH_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
EXA_API_KEY = os.getenv("EXA_API_KEY", "")
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")


def get_llm_api_key() -> str:
    """Return the API key for the configured LLM provider."""
    key_map = {
        "anthropic": ANTHROPIC_API_KEY,
        "openai": OPENAI_API_KEY,
        "deepseek": DEEPSEEK_API_KEY,
    }
    return key_map.get(LLM_PROVIDER, ANTHROPIC_API_KEY)


def is_configured() -> bool:
    """Check if at least one LLM API key is configured."""
    return bool(get_llm_api_key())


def get_configured_search_providers(env: dict | None = None) -> set[str]:
    """Return optional external search provider names with configured keys."""
    provider_keys = get_search_provider_api_keys(env)
    return {provider for provider, key in provider_keys.items() if key}


def get_search_provider_api_keys(env: dict | None = None) -> dict[str, str]:
    """Return configured external search provider API keys keyed by provider name."""
    source = env or os.environ
    return {
        "brave": source.get("BRAVE_SEARCH_API_KEY", BRAVE_SEARCH_API_KEY),
        "tavily": source.get("TAVILY_API_KEY", TAVILY_API_KEY),
        "exa": source.get("EXA_API_KEY", EXA_API_KEY),
        "serpapi": source.get("SERPAPI_API_KEY", SERPAPI_API_KEY),
        "github": source.get("GITHUB_TOKEN", GITHUB_TOKEN),
    }


def is_deep_fetch_enabled(env: dict | None = None) -> bool:
    """Return whether live URL deep fetch is explicitly enabled."""
    source = env or os.environ
    value = source.get("RAG_ENABLE_DEEP_FETCH", RAG_ENABLE_DEEP_FETCH)
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def is_startup_corpus_update_enabled(env: dict | None = None) -> bool:
    """Return whether startup may sync and ingest upstream corpus changes.

    The default is frozen so development and evaluation cannot silently change
    their corpus. Managed deployments must opt in explicitly.
    """
    source = os.environ if env is None else env
    value = source.get(
        "RAG_STARTUP_CORPUS_UPDATE_ENABLED",
        RAG_STARTUP_CORPUS_UPDATE_ENABLED if env is None else "false",
    )
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def get_upstream_corpus_url(env: dict | None = None) -> str:
    """Return the configured public corpus endpoint without a trailing slash."""
    source = os.environ if env is None else env
    value = str(source.get("RAG_UPSTREAM_CORPUS_URL", RAG_UPSTREAM_CORPUS_URL) or "").strip()
    return (value or DEFAULT_UPSTREAM_CORPUS_URL).rstrip("/")


def get_corpus_update_interval_seconds(env: dict | None = None) -> int:
    """Return a bounded polling interval for the managed local updater."""
    source = os.environ if env is None else env
    raw = source.get(
        "RAG_CORPUS_UPDATE_INTERVAL_SECONDS",
        RAG_CORPUS_UPDATE_INTERVAL_SECONDS if env is None else str(DEFAULT_CORPUS_UPDATE_INTERVAL_SECONDS),
    )
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        value = DEFAULT_CORPUS_UPDATE_INTERVAL_SECONDS
    return max(60, value)


def get_corpus_recheck_days(env: dict | None = None) -> int:
    """Return the recent revision window used by upstream corpus checks."""
    source = os.environ if env is None else env
    raw = source.get(
        "RAG_CORPUS_RECHECK_DAYS",
        RAG_CORPUS_RECHECK_DAYS if env is None else "30",
    )
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        value = 30
    return max(1, value)
