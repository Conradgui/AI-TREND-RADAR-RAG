#!/bin/bash

# Start an already configured local AI Trend Radar RAG installation.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f .env ]; then
  echo "尚未完成首次配置。请先双击 setup.command。"
  read -r -p "按回车键退出..."
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker Desktop 尚未运行。请启动 Docker Desktop 后重试。"
  read -r -p "按回车键退出..."
  exit 1
fi

RAG_PORT="$(sed -n 's/^RAG_PORT=//p' .env | tail -n 1)"
if [[ ! "$RAG_PORT" =~ ^[0-9]+$ ]]; then
  RAG_PORT=8001
fi
RAG_URL="http://127.0.0.1:${RAG_PORT}"

echo "正在启动 AI Trend Radar RAG（首次启动会下载镜像并预热检索模型）..."
docker compose up -d --build

echo "等待服务就绪（首次索引会在后台补全）..."
for attempt in {1..180}; do
  if curl -fsS "${RAG_URL}/health" >/dev/null 2>&1; then
    echo "服务已就绪。打开：${RAG_URL}"
    echo "首次运行时，最新日报会优先进入索引；历史语料继续在后台补全，可在 System 面板查看进度。"
    break
  fi
  sleep 1
done

if ! curl -fsS "${RAG_URL}/health" >/dev/null 2>&1; then
  echo "服务暂未在 180 秒内就绪。请查看：docker compose logs -f app"
  read -r -p "按回车键退出..."
  exit 1
fi

if command -v open >/dev/null 2>&1; then
  open "$RAG_URL"
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$RAG_URL"
fi
