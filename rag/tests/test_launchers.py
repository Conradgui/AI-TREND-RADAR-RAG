"""Launcher contract tests for the one-click local product flow."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _effective_launcher_source(name: str) -> str:
    source = (PROJECT_ROOT / name).read_text(encoding="utf-8")
    if "doctor.command" in source:
        source += (PROJECT_ROOT / "doctor.command").read_text(encoding="utf-8")
    return source


def test_container_entrypoint_runs_the_single_incremental_update_interface():
    """The server process owns updates so no second process opens embedded Chroma."""
    entrypoint = (PROJECT_ROOT / "scripts" / "docker-entrypoint.sh").read_text(encoding="utf-8")

    assert "exec python -m rag.server" in entrypoint
    assert "rag.corpus_update" not in entrypoint
    assert ") &" not in entrypoint
    assert "scripts/sync-from-github.sh" not in entrypoint


def test_launchers_do_not_reintroduce_a_second_python_runtime_path():
    for launcher in ("start.command", "start.bat"):
        source = _effective_launcher_source(launcher)
        assert "docker compose up -d --build" in source
        assert "rag.corpus_update" not in source
