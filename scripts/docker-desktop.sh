#!/bin/bash

# Shared, intentionally narrow Docker Desktop readiness check for the local
# launchers. It can open Docker Desktop and wait for its daemon, but never
# creates, removes, or changes project data by itself.

ensure_docker_ready() {
  if docker info >/dev/null 2>&1; then
    return 0
  fi

  if [[ "$(uname -s)" == "Darwin" ]] && command -v open >/dev/null 2>&1; then
    echo "Docker Desktop 尚未运行，正在尝试打开…"
    open -a Docker >/dev/null 2>&1 || true
  fi

  echo "正在等待 Docker Desktop 就绪…"
  for attempt in {1..120}; do
    if docker info >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done

  echo "Docker Desktop 未能在 120 秒内就绪。请确认它已安装并完成启动。" >&2
  return 1
}
