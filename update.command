#!/bin/bash

# Explicit update entry point. Use only after pulling a new project version or
# changing application code, dependencies, or the Dockerfile.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f .env ]; then
  echo "尚未完成首次配置。请先双击 setup.command。"
  read -r -p "按回车键退出..."
  exit 1
fi

source "${SCRIPT_DIR}/scripts/docker-desktop.sh"
if ! ensure_docker_ready; then
  read -r -p "按回车键退出..."
  exit 1
fi

echo "正在按当前项目代码更新服务镜像（Neo4j 与 RAG 数据卷会保留）..."
docker compose up -d --build

echo "更新已发起。请双击 start.command 等待服务就绪并打开页面。"
read -r -p "按回车键退出..."
