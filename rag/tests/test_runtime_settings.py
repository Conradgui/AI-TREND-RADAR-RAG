"""Tests for non-secret runtime preference persistence."""

from rag.runtime_settings import load_runtime_settings, save_runtime_setting


def test_runtime_settings_round_trip_without_storing_credentials(tmp_path):
    path = tmp_path / "runtime-settings.json"

    save_runtime_setting("web_search_enabled", False, path=path)
    save_runtime_setting("deep_fetch_enabled", True, path=path)

    assert load_runtime_settings(path=path) == {
        "web_search_enabled": False,
        "deep_fetch_enabled": True,
    }
    content = path.read_text(encoding="utf-8")
    assert "API_KEY" not in content
    assert "api_key" not in content


def test_runtime_settings_corruption_falls_back_to_safe_defaults(tmp_path):
    path = tmp_path / "runtime-settings.json"
    path.write_text("not json", encoding="utf-8")

    assert load_runtime_settings(path=path, deep_fetch_default=True) == {
        "web_search_enabled": True,
        "deep_fetch_enabled": True,
    }


def test_first_web_setting_write_preserves_environment_deep_fetch_default(tmp_path):
    path = tmp_path / "runtime-settings.json"

    save_runtime_setting(
        "web_search_enabled",
        False,
        path=path,
        deep_fetch_default=True,
    )

    assert load_runtime_settings(path=path) == {
        "web_search_enabled": False,
        "deep_fetch_enabled": True,
    }
