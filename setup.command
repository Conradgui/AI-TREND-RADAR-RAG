#!/bin/bash

# First-run local setup: collect only the required provider key, then start Docker.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

source "${SCRIPT_DIR}/scripts/docker-desktop.sh"
if ! ensure_docker_ready; then
  read -r -p "按回车键退出..."
  exit 1
fi

if [ -f .env ]; then
  echo ".env 已存在，为保护已有配置，本向导不会覆盖它。"
  echo "如需重新配置，请先备份并手动删除 .env 后再运行本向导。"
  read -r -p "按回车键启动已有配置..."
  exec "${SCRIPT_DIR}/start.command"
fi

echo "AI Trend Radar RAG 首次配置"
echo "只需一个模型 Provider 的 API Key；密钥仅保存在本机 .env，不会写入 Git。"
read -r -p "请选择 Provider [deepseek/anthropic/openai]（默认 deepseek）: " PROVIDER
PROVIDER="${PROVIDER:-deepseek}"

case "$PROVIDER" in
  deepseek|anthropic|openai) ;;
  *)
    echo "不支持的 Provider：$PROVIDER"
    read -r -p "按回车键退出..."
    exit 1
    ;;
esac

printf "请输入 %s API Key（输入不会显示）: " "$PROVIDER"
read -r -s PROVIDER_KEY
echo
if [ -z "$PROVIDER_KEY" ]; then
  echo "API Key 不能为空。"
  read -r -p "按回车键退出..."
  exit 1
fi

if command -v openssl >/dev/null 2>&1; then
  NEO4J_PASSWORD="$(openssl rand -hex 18)"
else
  NEO4J_PASSWORD="radar-$(date +%s)-local"
fi

umask 077
cat > .env <<EOF
LLM_PROVIDER=$PROVIDER
DEEPSEEK_API_KEY=$( [ "$PROVIDER" = "deepseek" ] && printf '%s' "$PROVIDER_KEY" )
ANTHROPIC_API_KEY=$( [ "$PROVIDER" = "anthropic" ] && printf '%s' "$PROVIDER_KEY" )
OPENAI_API_KEY=$( [ "$PROVIDER" = "openai" ] && printf '%s' "$PROVIDER_KEY" )
NEO4J_PASSWORD=$NEO4J_PASSWORD
RAG_ENABLE_DEEP_FETCH=false
RAG_CORPUS_RECHECK_DAYS=30
EOF

echo "配置已保存到本机 .env。现在开始启动服务。"
exec "${SCRIPT_DIR}/start.command"
