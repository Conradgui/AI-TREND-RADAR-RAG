"""Release contracts for the repository's GitHub Actions data pipeline."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = PROJECT_ROOT / ".github" / "workflows"


def _workflow(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def _workflow_data(name: str) -> dict:
    return yaml.load(_workflow(name), Loader=yaml.BaseLoader)


def test_ci_installs_rag_test_dependencies_before_running_p0_suite():
    """A clean GitHub runner must not call the Python suite without its deps."""
    source = _workflow("ci.yml")
    install = "python -m pip install -r rag/requirements-dev.txt"

    assert "permissions:\n  contents: read" in source
    assert install in source
    assert source.index(install) < source.index("pnpm rag:check:p0")

    dev_requirements = (
        PROJECT_ROOT / "rag" / "requirements-dev.txt"
    ).read_text(encoding="utf-8")
    assert "-r requirements.txt" in dev_requirements
    for required in ("pytest", "pytest-asyncio", "httpx", "PyYAML"):
        assert required in dev_requirements
    assert "ACTIONLINT_VERSION=1.7.12" in source
    assert "sha256sum --check" in source
    assert "actionlint .github/workflows/*.yml" in source


def test_workflow_contracts_are_part_of_the_p0_ci_command():
    package = json.loads((PROJECT_ROOT / "package.json").read_text(encoding="utf-8"))
    p0_command = package["scripts"]["rag:test:p0"]

    assert "rag/tests/test_workflow_contracts.py" in p0_command
    assert "rag/tests/test_release_package.py" in p0_command
    assert "rag.tests.test_corpus_contract" in p0_command


def test_corpus_sync_is_the_only_scheduled_corpus_owner():
    """The RAG repo consumes upstream artifacts; legacy producers stay manual."""
    sync = _workflow("rag-corpus-sync.yml")

    assert "schedule:" in sync
    assert "workflow_dispatch:" in sync
    assert "dry_run:" in sync
    assert "UPSTREAM_CORPUS_URL" in sync
    assert "python -m rag.sync_corpus" in sync
    assert "corpus-manifest.json" in sync
    assert "validate:" in sync
    assert "publish:" in sync
    assert "contents: read" in sync
    assert "contents: write" in sync
    assert "cancel-in-progress: false" in sync
    install = 'python -m pip install "pytest>=8,<9"'
    assert install in sync
    assert sync.index(install) < sync.index("python -m pytest")
    assert "--result-json sync-diagnostics.json" in sync
    assert "sync-validation.log" in sync
    assert "actions/upload-artifact@" in sync
    assert "if: ${{ always() }}" in sync

    for legacy in ("daily-digest.yml", "weekly-digest.yml", "monthly-digest.yml"):
        source = _workflow(legacy)
        assert "workflow_dispatch:" in source
        assert "schedule:" not in source


def test_pages_deploys_only_after_successful_corpus_sync():
    source = _workflow("deploy-pages.yml")
    builder = (PROJECT_ROOT / "scripts" / "build-pages-site.sh").read_text(
        encoding="utf-8"
    )

    assert "workflow_call:" in source
    assert "workflow_run:" not in source
    assert "workflow_dispatch:" not in source
    assert "scripts/build-pages-site.sh" in source
    assert "path: _site" in source
    assert "path: ." not in source
    assert "python -m rag.corpus_contract --check-existing" in builder

    for caller in ("rag-corpus-sync.yml", "corpus-producer-self-managed.yml"):
        caller_source = _workflow(caller)
        assert "needs: publish" in caller_source
        assert "needs.publish.result == 'success'" in caller_source
        assert "uses: ./.github/workflows/deploy-pages.yml" in caller_source


def test_self_managed_producer_is_manual_and_secret_preflighted():
    source = _workflow("corpus-producer-self-managed.yml")
    workflow = _workflow_data("corpus-producer-self-managed.yml")

    assert "workflow_dispatch:" in source
    assert "schedule:" not in source
    assert "type: choice" in source
    assert "DEEPSEEK_API_KEY" in source
    assert "ANTHROPIC_API_KEY" in source
    assert "OPENAI_API_KEY" in source
    assert "OPENROUTER_API_KEY" in source
    assert "Missing required secret" in source
    assert "python -m rag.corpus_contract --source-mode self_managed" in source
    assert "corpus-manifest.json" in source
    assert "inputs.publish" in source
    assert "contents: read" in source
    assert "contents: write" in source
    assert "models: read" in source
    assert "github-models" in source
    assert "github-models) runtime_provider=\"github-copilot\"" in source
    assert workflow["concurrency"]["cancel-in-progress"] == "false"
    assert "corpus-publish" in workflow["concurrency"]["group"]
    assert "concurrency" not in workflow["jobs"]["publish"]

    publish_steps = workflow["jobs"]["publish"]["steps"]
    step_names = [step.get("name", "") for step in publish_steps]
    assert step_names.index("Download generated corpus") < step_names.index(
        "Rebuild corpus contract before commit"
    ) < step_names.index("Commit generated corpus")


def test_all_corpus_publishers_share_one_non_cancelling_concurrency_group():
    publishers = (
        "rag-corpus-sync.yml",
        "corpus-producer-self-managed.yml",
        "daily-digest.yml",
        "weekly-digest.yml",
        "monthly-digest.yml",
    )
    for workflow in publishers:
        source = _workflow(workflow)
        if workflow == "corpus-producer-self-managed.yml":
            assert "corpus-publish" in _workflow_data(workflow)["concurrency"]["group"]
        else:
            assert "group: corpus-publish" in source, workflow
        assert "cancel-in-progress: false" in source, workflow


def test_legacy_manual_producers_rebuild_contract_and_deploy_through_shared_gate():
    for workflow in ("daily-digest.yml", "weekly-digest.yml", "monthly-digest.yml"):
        source = _workflow(workflow)
        data = _workflow_data(workflow)
        producer_job = "digest" if workflow == "daily-digest.yml" else workflow.split("-")[0]
        assert "python -m rag.corpus_contract --source-mode self_managed" in source
        assert "corpus-manifest.json" in source
        assert "uses: ./.github/workflows/deploy-pages.yml" in source
        assert data["jobs"]["deploy-pages"]["needs"] == producer_job
        assert data["jobs"]["deploy-pages"]["permissions"] == {
            "contents": "read",
            "pages": "write",
            "id-token": "write",
        }
        assert data["permissions"] == {"contents": "read"}
        producer_permissions = data["jobs"][producer_job]["permissions"]
        assert producer_permissions["contents"] == "write"
        if producer_job == "digest":
            assert producer_permissions["issues"] == "write"


def test_pages_allowlist_script_excludes_repository_internals():
    source = (PROJECT_ROOT / "scripts" / "build-pages-site.sh").read_text(
        encoding="utf-8"
    )

    for public_path in ("index.html", "manifest.json", "feed.xml", "digests"):
        assert public_path in source
    for private_path in (".git", ".env", "rag/data", "node_modules"):
        assert private_path not in source


def test_official_actions_are_pinned_to_immutable_commit_shas():
    """Mutable major tags can move; production workflows pin reviewed commits."""
    protected_actions = {
        "actions/checkout",
        "actions/setup-node",
        "actions/setup-python",
        "pnpm/action-setup",
        "actions/configure-pages",
        "actions/upload-pages-artifact",
        "actions/deploy-pages",
        "actions/upload-artifact",
        "actions/download-artifact",
    }

    for workflow in WORKFLOWS.glob("*.yml"):
        source = workflow.read_text(encoding="utf-8")
        for action, revision in re.findall(r"uses:\s+([^@\s]+)@([^\s#]+)", source):
            if action in protected_actions:
                assert re.fullmatch(r"[0-9a-f]{40}", revision), (
                    f"{workflow.name}: {action}@{revision} is not immutable"
                )


def test_automation_guide_explains_modes_secrets_and_default_branch_boundary():
    source = (PROJECT_ROOT / "docs" / "github-automation.zh.md").read_text(
        encoding="utf-8"
    )

    for required in (
        "托管语料同步",
        "自维护数据源",
        "UPSTREAM_CORPUS_URL",
        "DEEPSEEK_API_KEY",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
        "PRODUCTHUNT_TOKEN",
        "GITEE_TOKEN",
        "默认分支",
        "周报、月报",
        "不参与向量化或图谱化",
    ):
        assert required in source
