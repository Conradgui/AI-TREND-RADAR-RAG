import json
from urllib.error import HTTPError, URLError

import pytest

from rag.runtime_admin_client import LocalServiceError, request_local_service


class _Response:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_returns_none_when_local_service_is_not_running():
    def unavailable(_request, timeout):
        assert timeout == 0.75
        raise URLError("connection refused")

    assert request_local_service("/ingest", opener=unavailable) is None


def test_forwards_post_to_running_service_with_api_key(monkeypatch):
    calls = []

    def opener(request, timeout):
        calls.append((request, timeout))
        if request.full_url.endswith("/health"):
            return _Response({"status": "ok"})
        return _Response({"status": "ok", "dates_ingested": 2})

    monkeypatch.setenv("RAG_API_KEY", "secret")
    result = request_local_service(
        "/ingest",
        payload={"dates": ["2026-08-10"]},
        opener=opener,
    )

    assert result == {"status": "ok", "dates_ingested": 2}
    request, timeout = calls[-1]
    assert timeout == 900
    assert request.method == "POST"
    assert request.headers["X-api-key"] == "secret"
    assert json.loads(request.data) == {"dates": ["2026-08-10"]}


def test_running_service_http_error_does_not_fall_back_to_direct_write():
    calls = 0

    def opener(request, timeout):
        nonlocal calls
        assert timeout in {0.75, 900}
        calls += 1
        if calls == 1:
            return _Response({"status": "ok"})
        raise HTTPError(request.full_url, 409, "Conflict", {}, None)

    with pytest.raises(LocalServiceError, match="HTTP 409"):
        request_local_service("/ingest", opener=opener)


def test_health_http_error_is_a_running_service_not_an_offline_fallback():
    def opener(request, timeout):
        raise HTTPError(request.full_url, 503, "Unavailable", {}, None)

    with pytest.raises(LocalServiceError, match="health probe failed: HTTP 503"):
        request_local_service("/ingest", opener=opener)
