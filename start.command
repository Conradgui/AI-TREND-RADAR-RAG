#!/bin/bash

# AI Trend Radar RAG - 一键启动脚本
# 双击此文件即可启动完整的RAG系统

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

print_info "=========================================="
print_info "  AI Trend Radar RAG - 一键启动"
print_info "=========================================="
echo ""

# 步骤1: 检查Python环境
print_info "步骤 1/6: 检查Python环境..."
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 未安装，请先安装 Python 3"
    read -p "按回车键退出..."
    exit 1
fi
print_success "Python 3 已安装: $(python3 --version)"

# 步骤2: 检查并激活虚拟环境
print_info "步骤 2/6: 检查Python虚拟环境..."
if [ ! -d ".venv" ]; then
    print_warning "虚拟环境不存在，正在创建..."
    python3 -m venv .venv
    print_success "虚拟环境已创建"
fi

# 激活虚拟环境
source .venv/bin/activate
print_success "虚拟环境已激活"

# 步骤3: 检查并安装Python依赖
print_info "步骤 3/6: 检查Python依赖..."
if [ ! -f ".venv/.deps_installed" ]; then
    print_warning "正在安装Python依赖（首次运行需要几分钟）..."
    pip install -q -r rag/requirements.txt
    touch .venv/.deps_installed
    print_success "Python依赖已安装"
else
    print_success "Python依赖已安装"
fi

# 步骤4: 检查并启动Neo4j
print_info "步骤 4/6: 检查Neo4j数据库..."
if ! docker ps 2>/dev/null | grep -q "ai-trend-radar-rag-claude"; then
    print_warning "Neo4j未运行，正在启动..."
    docker-compose up -d neo4j
    print_success "Neo4j已启动"
    print_info "等待Neo4j就绪（约10秒）..."
    sleep 10
else
    print_success "Neo4j已运行"
fi

# 步骤5: 同步最新数据（从GitHub AI-TREND-RADAR）
print_info "步骤 5/6: 同步最新数据..."
if [ -f "scripts/sync-from-github.sh" ]; then
    bash scripts/sync-from-github.sh
else
    print_warning "跳过数据同步（脚本不存在）"
fi

# 步骤6: 启动RAG服务器
print_info "步骤 6/6: 启动RAG服务器..."
print_info "正在启动服务器（端口 8001）..."

# 启动服务器（后台运行）
source .venv/bin/activate
nohup python -m rag.server > rag-server.log 2>&1 &
SERVER_PID=$!

# 等待服务器启动
print_info "等待服务器就绪..."
for i in {1..30}; do
    if curl -s http://localhost:8001/health > /dev/null 2>&1; then
        print_success "RAG服务器已启动"
        break
    fi
    sleep 1
done

# 检查服务器是否启动成功
if ! curl -s http://localhost:8001/health > /dev/null 2>&1; then
    print_error "RAG服务器启动失败，请检查日志: rag-server.log"
    read -p "按回车键退出..."
    exit 1
fi

# 打开浏览器
print_info "正在打开浏览器..."
if command -v open &> /dev/null; then
    # macOS
    open http://localhost:8001
elif command -v xdg-open &> /dev/null; then
    # Linux
    xdg-open http://localhost:8001
elif command -v start &> /dev/null; then
    # Windows (WSL)
    start http://localhost:8001
else
    print_warning "无法自动打开浏览器，请手动访问: http://localhost:8001"
fi

echo ""
print_success "=========================================="
print_success "  AI Trend Radar RAG 已启动！"
print_success "=========================================="
echo ""
print_info "访问地址: http://localhost:8001"
print_info "服务器日志: rag-server.log"
echo ""
print_info "功能说明："
print_info "  - 📊 仪表盘：查看AI趋势报告"
print_info "  - 🤖 Agent：智能问答（点击右上角AGENT按钮）"
print_info "  - ⚙️  系统状态：查看系统信息（点击右上角SYSTEM按钮）"
print_info "  - 📋 Briefs：查看研究制品（点击右上角BRIEFS按钮）"
echo ""
print_info "按 Ctrl+C 停止服务器"
echo ""

# 保持脚本运行，等待用户退出
wait $SERVER_PID
