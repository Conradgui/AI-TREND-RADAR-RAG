"""Safe URL fetching and lightweight page extraction for external citations."""

from __future__ import annotations

import html
import http.client
import ipaddress
import re
import socket
import ssl
import urllib.error
from copy import deepcopy
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse


DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_MAX_BYTES = 1_000_000
DEFAULT_TEXT_LIMIT = 3000
USER_AGENT = "AI-Trend-Radar-RAG/0.1 (+local research assistant)"


class _UnsafeRedirectError(Exception):
    """Raised before following a redirect to a disallowed network target."""


class _RedirectLimitError(Exception):
    """Raised when an external source redirects too many times."""


def fetch_url(
    url: str,
    resolver=None,
    transport=None,
    connection_factory=None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> dict:
    """Fetch and extract a URL with basic SSRF-oriented safety checks."""
    safety_error = _validate_url_for_fetch(url, resolver=resolver)
    if safety_error:
        return _fetch_result(url=url, ok=False, error=safety_error)

    if transport is None:
        transport = lambda target, target_headers, target_timeout, target_max_bytes: _default_transport(
            target,
            target_headers,
            target_timeout,
            target_max_bytes,
            resolver=resolver,
            connection_factory=connection_factory,
        )
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html, text/plain;q=0.9,*/*;q=0.1"}
    try:
        raw = transport(url, headers, timeout, max_bytes)
    except _UnsafeRedirectError:
        return _fetch_result(url=url, ok=False, error="blocked_redirect_target")
    except _RedirectLimitError:
        return _fetch_result(url=url, ok=False, error="redirect_limit_exceeded")
    except urllib.error.HTTPError as exc:
        return _fetch_result(url=url, ok=False, error=f"http_{exc.code}", status_code=exc.code)
    except urllib.error.URLError:
        return _fetch_result(url=url, ok=False, error="network_error")
    except Exception:
        return _fetch_result(url=url, ok=False, error="fetch_failed")

    final_url = raw.get("final_url", url)
    if final_url != url and _validate_url_for_fetch(final_url, resolver=resolver):
        # Custom transports are checked after returning as a defence-in-depth
        # fallback. The default transport validates before every redirect.
        return _fetch_result(url=url, ok=False, error="blocked_redirect_target", final_url=final_url)

    body = raw.get("body", b"")
    if isinstance(body, bytes):
        text = body.decode("utf-8", errors="replace")
    else:
        text = str(body or "")

    content_type = raw.get("content_type", "")
    if "html" in content_type.lower() or "<html" in text.lower():
        title, extracted = _extract_html_text(text)
    else:
        title, extracted = "", _normalize_whitespace(text)

    return _fetch_result(
        url=url,
        ok=True,
        error="",
        status_code=raw.get("status_code"),
        final_url=final_url,
        content_type=content_type,
        title=title,
        text_excerpt=extracted[:DEFAULT_TEXT_LIMIT],
    )


def deepen_external_citations(citations: list[dict], fetcher=None) -> list[dict]:
    """Attach deep-fetch records to external citations that need deeper verification."""
    fetcher = fetcher or fetch_url
    deepened = []
    for citation in citations:
        updated = deepcopy(citation)
        if citation.get("evidence_type") == "external" and citation.get("needs_deep_fetch"):
            updated["deep_fetch"] = fetcher(citation.get("url", ""))
        deepened.append(updated)
    return deepened


def _validate_url_for_fetch(url: str, resolver=None) -> str:
    parsed = urlparse(str(url or ""))
    if parsed.scheme not in {"http", "https"}:
        return "unsupported_url_scheme"
    if not parsed.hostname:
        return "missing_hostname"
    hostname_is_ip = _parse_ip_address(parsed.hostname) is not None

    resolver = resolver or _resolve_hostname
    try:
        addresses = resolver(parsed.hostname)
    except Exception:
        return "hostname_resolution_failed"

    if not addresses:
        return "hostname_resolution_failed"

    if any(
        _is_private_or_local_address(address, allow_managed_proxy=not hostname_is_ip)
        for address in addresses
    ):
        return "blocked_private_or_local_address"

    return ""


def _resolve_hostname(hostname: str) -> list[str]:
    infos = socket.getaddrinfo(hostname, None)
    return sorted({info[4][0] for info in infos})


def _is_private_or_local_address(address: str, allow_managed_proxy: bool = False) -> bool:
    ip = _parse_ip_address(address)
    if ip is None:
        return True
    if allow_managed_proxy and _is_managed_proxy_address(ip):
        return False
    return any([
        ip.is_private,
        ip.is_loopback,
        ip.is_link_local,
        ip.is_multicast,
        ip.is_reserved,
        ip.is_unspecified,
    ])


def _parse_ip_address(address: str):
    try:
        return ipaddress.ip_address(address)
    except ValueError:
        return None


def _is_managed_proxy_address(ip) -> bool:
    """Allow public hostnames resolved through common local/network proxy ranges."""
    return ip in ipaddress.ip_network("198.18.0.0/15")


def _default_transport(
    url: str,
    headers: dict,
    timeout: int,
    max_bytes: int,
    resolver=None,
    connection_factory=None,
    max_redirects: int = 5,
) -> dict:
    resolver = resolver or _resolve_hostname
    connection_factory = connection_factory or _open_pinned_connection
    current_url = url

    for redirect_count in range(max_redirects + 1):
        parsed = urlparse(current_url)
        try:
            addresses = resolver(parsed.hostname)
        except Exception as exc:
            raise _UnsafeRedirectError(current_url) from exc
        hostname_is_ip = _parse_ip_address(parsed.hostname) is not None
        if not addresses or any(
            _is_private_or_local_address(address, allow_managed_proxy=not hostname_is_ip)
            for address in addresses
        ):
            raise _UnsafeRedirectError(current_url)

        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        connection = connection_factory(parsed.scheme, parsed.hostname, port, addresses[0], timeout)
        path = parsed.path or "/"
        if parsed.query:
            path += f"?{parsed.query}"
        request_headers = dict(headers)
        default_port = 443 if parsed.scheme == "https" else 80
        request_headers["Host"] = parsed.hostname if port == default_port else f"{parsed.hostname}:{port}"
        try:
            connection.request("GET", path, headers=request_headers)
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                location = response.getheader("Location")
                if not location:
                    raise urllib.error.HTTPError(current_url, response.status, "redirect_without_location", {}, None)
                if redirect_count >= max_redirects:
                    raise _RedirectLimitError(current_url)
                current_url = urljoin(current_url, location)
                continue
            return {
                "status_code": response.status,
                "final_url": current_url,
                "content_type": response.getheader("Content-Type", ""),
                "body": response.read(max_bytes),
            }
        finally:
            connection.close()

    raise _RedirectLimitError(current_url)


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, hostname: str, connect_ip: str, port: int, timeout: int):
        super().__init__(hostname, port=port, timeout=timeout)
        self._connect_ip = connect_ip

    def connect(self):
        self.sock = socket.create_connection(
            (self._connect_ip, self.port),
            self.timeout,
            self.source_address,
        )


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, hostname: str, connect_ip: str, port: int, timeout: int):
        super().__init__(hostname, port=port, timeout=timeout, context=ssl.create_default_context())
        self._connect_ip = connect_ip

    def connect(self):
        raw_socket = socket.create_connection(
            (self._connect_ip, self.port),
            self.timeout,
            self.source_address,
        )
        self.sock = self._context.wrap_socket(raw_socket, server_hostname=self.host)


def _open_pinned_connection(scheme: str, hostname: str, port: int, connect_ip: str, timeout: int):
    if scheme == "https":
        return _PinnedHTTPSConnection(hostname, connect_ip, port, timeout)
    return _PinnedHTTPConnection(hostname, connect_ip, port, timeout)


def _fetch_result(
    url: str,
    ok: bool,
    error: str,
    status_code: int | None = None,
    final_url: str = "",
    content_type: str = "",
    title: str = "",
    text_excerpt: str = "",
) -> dict:
    return {
        "ok": ok,
        "url": url,
        "final_url": final_url or url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "status_code": status_code,
        "content_type": content_type,
        "title": title,
        "text_excerpt": text_excerpt,
        "error": error,
    }


class _ReadableHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._skip_depth:
            return
        cleaned = _normalize_whitespace(html.unescape(data))
        if not cleaned:
            return
        if self._in_title:
            self.title_parts.append(cleaned)
        else:
            self.text_parts.append(cleaned)


def _extract_html_text(raw_html: str) -> tuple[str, str]:
    parser = _ReadableHTMLParser()
    parser.feed(raw_html)
    title = _normalize_whitespace(" ".join(parser.title_parts))
    text = _normalize_whitespace(" ".join(parser.text_parts))
    return title, text


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()
