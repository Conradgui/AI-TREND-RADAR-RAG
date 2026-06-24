"""Runtime tool selection helpers without web framework dependencies."""

from __future__ import annotations

from rag.url_fetch import fetch_url


def select_external_deep_fetcher(enabled: bool):
    """Return the live deep-fetch function only when explicitly enabled."""
    return fetch_url if enabled else None
