#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "$0")/.." && pwd)"
project_python="$project_root/.venv/bin/python"

if [[ -x "$project_python" ]]; then
  exec "$project_python" "$@"
fi

exec python3 "$@"
