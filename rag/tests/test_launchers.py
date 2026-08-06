"""Launcher contract tests for the one-click local product flow."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_container_entrypoint_runs_the_single_incremental_update_interface():
    """The image owns one non-blocking, truthful incremental update path."""
    entrypoint = (PROJECT_ROOT / "scripts" / "docker-entrypoint.sh").read_text(encoding="utf-8")

    assert "rag.corpus_update --days" in entrypoint
    assert ") &" in entrypoint
    assert "exec python -m rag.server" in entrypoint
    assert "scripts/sync-from-github.sh" not in entrypoint


def test_launchers_do_not_reintroduce_a_second_python_runtime_path():
    for launcher in ("start.command", "start.bat"):
        source = (PROJECT_ROOT / launcher).read_text(encoding="utf-8")
        assert "docker compose up -d --build" in source
        assert "rag.corpus_update" not in source
