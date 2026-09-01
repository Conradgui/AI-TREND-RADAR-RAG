"""Public release-package contracts for a clone-and-run local deployment."""

import subprocess
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _effective_launcher_source(name: str) -> str:
    source = (PROJECT_ROOT / name).read_text(encoding="utf-8")
    if "doctor.command" in source:
        source += (PROJECT_ROOT / "doctor.command").read_text(encoding="utf-8")
    return source


def test_compose_declares_the_complete_local_product_stack():
    """`docker compose up` must start both the app and its graph database."""
    source = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "  app:" in source
    assert "  neo4j:" in source
    assert ":8001\"" in source
    assert "NEO4J_URI: bolt://neo4j:7687" in source
    assert "container_name:" not in source
    # The current Graph RAG queries use Cypher directly.  Do not make first
    # startup depend on downloading an unused Neo4j plugin.
    assert "graph-data-science" not in source
    assert "OMP_NUM_THREADS" in source
    assert source.count("cpus:") >= 2
    assert "RAG_STARTUP_CORPUS_UPDATE_ENABLED: ${RAG_STARTUP_CORPUS_UPDATE_ENABLED:-true}" in source
    assert "RAG_CORPUS_UPDATE_INTERVAL_SECONDS" in source
    assert "RAG_UPSTREAM_CORPUS_URL" in source


def test_docker_build_keeps_local_secrets_and_development_artifacts_out():
    dockerignore = (PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8")

    assert ".env" in dockerignore
    assert ".venv" in dockerignore
    assert "node_modules" in dockerignore
    assert "rag/data/chroma" in dockerignore


def test_docker_image_prepares_the_local_embedding_model_before_first_startup():
    """First-use model download belongs to the visible image build, not hidden startup."""
    source = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "DefaultEmbeddingFunction" in source
    assert "warmup" in source


def test_example_environment_is_safe_and_ready_for_the_setup_wizard():
    source = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")

    assert "DEEPSEEK_API_KEY=" in source
    assert "DEEPSEEK_API_KEY=your_" not in source
    assert "NEO4J_PASSWORD=" in source
    assert "RAG_API_KEY=" in source


def test_setup_paths_enable_managed_corpus_updates_consistently():
    for path in (
        PROJECT_ROOT / ".env.example",
        PROJECT_ROOT / "setup.command",
        PROJECT_ROOT / "scripts" / "setup-windows.ps1",
    ):
        source = path.read_text(encoding="utf-8")
        assert "RAG_STARTUP_CORPUS_UPDATE_ENABLED=true" in source
        assert "RAG_CORPUS_UPDATE_INTERVAL_SECONDS=21600" in source
        assert "RAG_UPSTREAM_CORPUS_URL=https://conradgui.github.io/AI-TREND-RADAR" in source


def test_daily_launchers_reuse_existing_images_and_keep_rebuild_explicit():
    for launcher in ("start.command", "start.bat"):
        source = _effective_launcher_source(launcher)
        assert "docker compose up -d --no-build" in source
        assert "docker compose images -q app" in source
        assert "pip install" not in source
    assert "python -m venv" not in source

    for updater in ("update.command", "update.bat"):
        source = (PROJECT_ROOT / updater).read_text(encoding="utf-8")
        assert "docker compose up -d --build" in source
        assert "down -v" not in source

    assert "start.command" in (PROJECT_ROOT / "setup.command").read_text(encoding="utf-8")
    assert "setup-windows.ps1" in (PROJECT_ROOT / "setup.bat").read_text(encoding="utf-8")


def test_start_launchers_wait_for_the_product_health_check_before_opening_browser():
    for launcher in ("start.command", "start.bat"):
        source = _effective_launcher_source(launcher)
        assert "/health" in source
        assert "等待服务就绪" in source or "基础设施检查通过" in source


def test_windows_setup_hides_provider_key_while_writing_only_local_env_file():
    source = (PROJECT_ROOT / "scripts" / "setup-windows.ps1").read_text(encoding="utf-8")

    assert "-AsSecureString" in source
    assert "WriteAllLines" in source
    assert "Set-Content" not in source


def test_release_assets_state_the_project_license_and_security_boundary():
    license_text = (PROJECT_ROOT / "LICENSE").read_text(encoding="utf-8")
    security_text = (PROJECT_ROOT / "SECURITY.md").read_text(encoding="utf-8")

    assert "MIT License" in license_text
    assert "Copyright (c) 2026 Conradgui" in license_text
    assert "密钥" in security_text


def test_project_verifier_gitlink_has_reproducible_submodule_metadata():
    source = (PROJECT_ROOT / ".gitmodules").read_text(encoding="utf-8")

    assert 'path = .claude/skills/project-verifier-skill' in source
    assert 'url = https://github.com/Conradgui/project-verifier-skill.git' in source


def test_pages_builder_copies_only_public_digest_artifacts():
    with tempfile.TemporaryDirectory() as tmp:
        site_root = Path(tmp) / "site"
        subprocess.run(
            ["bash", "scripts/build-pages-site.sh", str(site_root)],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        published = {
            path.relative_to(site_root).as_posix()
            for path in site_root.rglob("*")
            if path.is_file()
        }

    assert "digests/search-index.json" in published
    assert "assets/vendor/minisearch/minisearch-7.2.0.umd.js" in published
    assert "assets/vendor/minisearch/LICENSE.txt" in published
    assert "digests/web-state.json" not in published
    assert not any(path.endswith(".DS_Store") for path in published)
    assert not any(path.startswith(".git/") for path in published)


def test_pages_builder_requires_auditable_contract_and_search_index():
    source = (PROJECT_ROOT / "scripts" / "build-pages-site.sh").read_text(
        encoding="utf-8"
    )

    assert "index.html manifest.json feed.xml corpus-manifest.json" in source
    assert 'for file in minisearch-7.2.0.umd.js LICENSE.txt' in source
    assert 'cp "$vendor_root/minisearch-7.2.0.umd.js"' in source
    assert 'Required public file is missing or empty: digests/search-index.json' in source
    assert "python -m rag.corpus_contract --check-existing" in source
