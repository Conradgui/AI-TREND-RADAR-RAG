"""Forward local maintenance commands to the running single-writer server."""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class LocalServiceError(RuntimeError):
    """The local service is running but rejected a maintenance request."""


def _base_url() -> str:
    explicit = os.getenv("RAG_LOCAL_SERVER_URL", "").strip()
    if explicit:
        return explicit.rstrip("/")
    return f"http://127.0.0.1:{os.getenv('RAG_PORT', '8001')}"


def request_local_service(
    path: str,
    *,
    payload: dict | None = None,
    opener=urlopen,
) -> dict | None:
    """Return server JSON, or ``None`` only when no local server is listening.

    Once the health probe succeeds, any maintenance failure is raised instead
    of silently falling back to a second writer.
    """
    base_url = _base_url()
    health_request = Request(f"{base_url}/health", method="GET")
    try:
        with opener(health_request, timeout=0.75) as response:
            response.read()
    except HTTPError as exc:
        raise LocalServiceError(f"Local RAG service health probe failed: HTTP {exc.code}") from exc
    except URLError:
        return None

    headers = {"Content-Type": "application/json"}
    api_key = os.getenv("RAG_API_KEY", "").strip()
    if api_key:
        headers["X-API-Key"] = api_key
    body = json.dumps(payload or {}).encode("utf-8")
    request = Request(f"{base_url}{path}", data=body, headers=headers, method="POST")
    try:
        with opener(request, timeout=900) as response:
            decoded = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise LocalServiceError(f"Local RAG service rejected maintenance request: HTTP {exc.code}") from exc
    except URLError as exc:
        raise LocalServiceError("Local RAG service disconnected during maintenance request") from exc
    if not isinstance(decoded, dict):
        raise LocalServiceError("Local RAG service returned an invalid maintenance response")
    return decoded
