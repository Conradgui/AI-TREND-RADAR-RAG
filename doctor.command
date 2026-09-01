#!/bin/bash

# One-command infrastructure diagnosis and safe repair for local Docker use.
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

MODE="repair"
OPEN_UI="false"
for argument in "$@"; do
  case "$argument" in
    --check) MODE="check" ;;
    --open) OPEN_UI="true" ;;
    --help|-h)
      echo "用法: ./doctor.command [--check] [--open]"
      echo "  默认      检查并安全恢复 Docker 服务（不删除数据、不重建已有镜像）"
      echo "  --check   只检查，不修改运行状态"
      echo "  --open    检查通过后打开 Web UI"
      exit 0
      ;;
    *) echo "未知参数: $argument" >&2; exit 2 ;;
  esac
done

ENV_FILE="${ATR_DOCTOR_ENV_FILE:-${SCRIPT_DIR}/.env}"
WAIT_SECONDS="${ATR_DOCTOR_WAIT_SECONDS:-600}"

env_value() {
  awk -F= -v key="$1" '
    $0 !~ /^[[:space:]]*#/ && $1 == key {
      sub(/^[^=]*=/, ""); value=$0
    }
    END { print value }
  ' "$ENV_FILE" 2>/dev/null
}

fail() {
  echo "❌ $1" >&2
  return 1
}

echo "AI Trend Radar 基础设施自检"
echo "模式: $([ "$MODE" = "check" ] && echo "只检查" || echo "检查并安全修复")"

if [ ! -f "$ENV_FILE" ]; then
  fail "未找到本地配置 .env。首次使用请双击 setup.command。"
  exit 1
fi

PROVIDER="$(env_value LLM_PROVIDER)"
PROVIDER="${PROVIDER:-deepseek}"
case "$PROVIDER" in
  deepseek) PROVIDER_KEY="$(env_value DEEPSEEK_API_KEY)" ;;
  anthropic) PROVIDER_KEY="$(env_value ANTHROPIC_API_KEY)" ;;
  openai) PROVIDER_KEY="$(env_value OPENAI_API_KEY)" ;;
  *) fail "LLM_PROVIDER=${PROVIDER} 不受支持。"; exit 1 ;;
esac
if [ -z "$PROVIDER_KEY" ]; then
  fail "${PROVIDER} 的 API Key 未配置。请运行 setup.command 或编辑 .env。"
  exit 1
fi
if [ -z "$(env_value NEO4J_PASSWORD)" ]; then
  fail "NEO4J_PASSWORD 未配置。请运行 setup.command。"
  exit 1
fi
echo "✅ 本地配置完整（密钥未输出）"

if ! command -v docker >/dev/null 2>&1; then
  fail "未找到 Docker。请先安装 Docker Desktop。"
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  if [ "$MODE" = "check" ]; then
    fail "Docker Desktop 尚未就绪。"
    exit 1
  fi
  # This helper may open Docker Desktop on macOS and only waits for its daemon.
  source "${SCRIPT_DIR}/scripts/docker-desktop.sh"
  if ! ensure_docker_ready; then
    exit 1
  fi
fi
echo "✅ Docker 引擎可用"

if ! docker compose version >/dev/null 2>&1; then
  fail "当前 Docker 未提供 Compose v2。请升级 Docker Desktop。"
  exit 1
fi
if ! docker compose config --quiet >/dev/null 2>&1; then
  fail "docker-compose.yml 或 .env 配置无效。运行 docker compose config 查看详情。"
  exit 1
fi
echo "✅ Compose 配置有效"

RUNNING_SERVICES="$(docker compose ps --status running --services 2>/dev/null || true)"
if ! printf '%s\n' "$RUNNING_SERVICES" | grep -qx app || \
   ! printf '%s\n' "$RUNNING_SERVICES" | grep -qx neo4j; then
  if [ "$MODE" = "check" ]; then
    fail "app 或 neo4j 容器没有运行。"
    exit 1
  fi
  if docker compose images -q app 2>/dev/null | grep -q .; then
    echo "正在恢复现有容器、镜像和数据卷（不重新构建）…"
    docker compose up -d --no-build || exit 1
  else
    echo "本机没有应用镜像，执行首次构建（数据卷仍会保留）…"
    docker compose up -d --build || exit 1
  fi
else
  echo "✅ app 与 neo4j 容器正在运行"
fi

RAG_PORT="$(env_value RAG_PORT)"
case "$RAG_PORT" in
  ''|*[!0-9]*) RAG_PORT=8001 ;;
esac
RAG_URL="http://127.0.0.1:${RAG_PORT}"
HEALTH=""
STARTED_AT="$(date +%s)"

while :; do
  HEALTH="$(curl -fsS --max-time 5 "${RAG_URL}/health" 2>/dev/null || true)"
  if printf '%s' "$HEALTH" | grep -q '"status":"ok"'; then
    break
  fi
  if [ "$MODE" = "check" ]; then
    break
  fi
  NOW="$(date +%s)"
  if [ $((NOW - STARTED_AT)) -ge "$WAIT_SECONDS" ]; then
    break
  fi
  sleep 2
done

if ! printf '%s' "$HEALTH" | grep -q '"status":"ok"'; then
  fail "服务未在 ${WAIT_SECONDS} 秒内就绪。请运行 docker compose logs --tail=100 app。"
  exit 1
fi

if ! printf '%s' "$HEALTH" | grep -q '"neo4j_connected":true'; then
  if [ "$MODE" = "repair" ]; then
    echo "Neo4j 容器已运行但应用连接中断，正在调用安全重连接口…"
    RAG_API_KEY="$(env_value RAG_API_KEY)"
    if [ -n "$RAG_API_KEY" ]; then
      curl -fsS --max-time 30 -X POST -H "X-API-Key: ${RAG_API_KEY}" \
        "${RAG_URL}/runtime/reconnect-databases" >/dev/null 2>&1 || true
    else
      curl -fsS --max-time 30 -X POST \
        "${RAG_URL}/runtime/reconnect-databases" >/dev/null 2>&1 || true
    fi
    HEALTH="$(curl -fsS --max-time 10 "${RAG_URL}/health" 2>/dev/null || true)"
  fi
fi

if ! printf '%s' "$HEALTH" | grep -q '"neo4j_connected":true'; then
  fail "Neo4j 尚未连接；未执行重建或数据删除。"
  exit 1
fi
if printf '%s' "$HEALTH" | grep -q '"chromadb_chunks":0'; then
  fail "Chroma 索引为空；为保护数据，Doctor 不会自动重建索引。"
  exit 1
fi

echo "✅ Neo4j 已连接"
echo "✅ Chroma 索引可用"
echo "✅ Provider: ${PROVIDER}；检索链路: hybrid"
echo "✅ 基础设施检查通过：${RAG_URL}"

if [ "$OPEN_UI" = "true" ]; then
  if command -v open >/dev/null 2>&1; then
    open "$RAG_URL"
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$RAG_URL"
  fi
fi
