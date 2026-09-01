from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOCTOR = PROJECT_ROOT / "doctor.command"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _doctor_environment(tmp_path: Path, *, services: str) -> tuple[dict[str, str], Path]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    calls = tmp_path / "docker-calls.log"
    env_file = tmp_path / ".env"
    env_file.write_text(
        "LLM_PROVIDER=deepseek\n"
        "DEEPSEEK_API_KEY=test-key\n"
        "NEO4J_PASSWORD=test-password\n"
        "RAG_PORT=8001\n",
        encoding="utf-8",
    )
    _write_executable(
        fake_bin / "docker",
        "#!/bin/sh\n"
        f"printf '%s\\n' \"$*\" >> {calls!s}\n"
        "if [ \"$1 $2 $3 $4\" = \"compose ps --status running\" ]; then\n"
        f"  printf '%s\\n' '{services}'\n"
        "elif [ \"$1 $2 $3 $4\" = \"compose images -q app\" ]; then\n"
        "  echo existing-image\n"
        "fi\n"
        "exit 0\n",
    )
    _write_executable(
        fake_bin / "curl",
        "#!/bin/sh\n"
        "printf '%s' '{\"status\":\"ok\",\"configured\":true,"
        "\"neo4j_connected\":true,\"chromadb_chunks\":4133,"
        "\"provider\":\"deepseek\",\"retriever_mode\":\"hybrid\"}'\n",
    )
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "ATR_DOCTOR_ENV_FILE": str(env_file),
        "ATR_DOCTOR_WAIT_SECONDS": "1",
    }
    return env, calls


def test_check_mode_reports_healthy_without_mutating_compose(tmp_path: Path) -> None:
    env, calls = _doctor_environment(tmp_path, services="app\nneo4j")

    result = subprocess.run(
        [str(DOCTOR), "--check"],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=5,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "基础设施检查通过" in result.stdout
    assert "compose up" not in calls.read_text(encoding="utf-8")


def test_repair_mode_starts_existing_stack_without_rebuild(tmp_path: Path) -> None:
    env, calls = _doctor_environment(tmp_path, services="")

    result = subprocess.run(
        [str(DOCTOR)],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=5,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "基础设施检查通过" in result.stdout
    docker_calls = calls.read_text(encoding="utf-8")
    assert "compose up -d --no-build" in docker_calls
    assert "compose up -d --build" not in docker_calls
