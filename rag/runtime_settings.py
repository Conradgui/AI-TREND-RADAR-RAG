"""Persist non-secret dashboard preferences across local service restarts."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path


DEFAULT_PATH = Path(__file__).parent / "data" / "runtime-settings.json"
_LOCK = threading.Lock()
_ALLOWED_KEYS = {"web_search_enabled", "deep_fetch_enabled"}


def load_runtime_settings(
    *,
    path: Path = DEFAULT_PATH,
    deep_fetch_default: bool = False,
) -> dict[str, bool]:
    defaults = {
        "web_search_enabled": True,
        "deep_fetch_enabled": bool(deep_fetch_default),
    }
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError, TypeError):
        return defaults
    if not isinstance(payload, dict):
        return defaults
    return {
        key: payload.get(key) if isinstance(payload.get(key), bool) else default
        for key, default in defaults.items()
    }


def save_runtime_setting(
    key: str,
    enabled: bool,
    *,
    path: Path = DEFAULT_PATH,
    deep_fetch_default: bool = False,
) -> dict[str, bool]:
    if key not in _ALLOWED_KEYS:
        raise ValueError(f"Unsupported runtime setting: {key}")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        settings = load_runtime_settings(
            path=target,
            deep_fetch_default=deep_fetch_default,
        )
        settings[key] = bool(enabled)
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.",
            dir=str(target.parent),
            text=True,
        )
        try:
            with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
                json.dump(settings, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, target)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
    return settings
