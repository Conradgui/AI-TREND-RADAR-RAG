#!/bin/bash

# AI Trend Radar - 从GitHub同步最新报告
# 从 GitHub 的 AI-TREND-RADAR 仓库抓取当日新报告并添加到RAG系统

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() { echo -e "${BLUE}[SYNC]${NC} $1"; }
print_success() { echo -e "${GREEN}[SYNC]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[SYNC]${NC} $1"; }
print_error() { echo -e "${RED}[SYNC]${NC} $1"; }

# 配置
GITHUB_REPO="Conradgui/AI-TREND-RADAR"
GITHUB_BRANCH="main"
LOCAL_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )/.."
DIGESTS_DIR="$LOCAL_DIR/digests"
TEMP_DIR="$LOCAL_DIR/.sync-temp"

# 获取今天的日期
TODAY=$(date +%Y-%m-%d)

print_info "=========================================="
print_info "  从 GitHub 同步最新报告"
print_info "=========================================="
echo ""
print_info "日期: $TODAY"
print_info "仓库: $GITHUB_REPO"
print_info "分支: $GITHUB_BRANCH"
echo ""

# 步骤1: 检查网络连接
print_info "步骤 1/5: 检查网络连接..."
if ! curl -s --head https://github.com > /dev/null; then
    print_error "无法连接到GitHub，请检查网络"
    exit 1
fi
print_success "网络连接正常"

# 步骤2: 创建临时目录
print_info "步骤 2/5: 创建临时目录..."
rm -rf "$TEMP_DIR"
mkdir -p "$TEMP_DIR"
print_success "临时目录已创建"

# 步骤3: 从GitHub下载最新报告
print_info "步骤 3/5: 从GitHub下载最新报告..."

# 使用GitHub API获取最新的digest文件
GITHUB_API_URL="https://api.github.com/repos/$GITHUB_REPO/contents/digests?ref=$GITHUB_BRANCH"

# 获取目录列表
print_info "获取digests目录列表..."
DIRS=$(curl -s "$GITHUB_API_URL" | python3 -c "
import sys, json
data = json.load(sys.stdin)
if isinstance(data, list):
    for item in data:
        if item['type'] == 'dir':
            print(item['name'])
" 2>/dev/null || echo "")

if [ -z "$DIRS" ]; then
    print_warning "无法获取目录列表，尝试直接下载..."
    # 备用方案：直接克隆
    git clone --depth 1 --filter=blob:none --sparse https://github.com/$GITHUB_REPO.git "$TEMP_DIR/repo"
    cd "$TEMP_DIR/repo"
    git sparse-checkout set digests
    cd "$LOCAL_DIR"
    cp -r "$TEMP_DIR/repo/digests/"* "$DIGESTS_DIR/" 2>/dev/null || true
    rm -rf "$TEMP_DIR"
    print_success "报告已下载（备用方案）"
else
    # 下载每个日期目录
    for DIR in $DIRS; do
        # 只下载最近7天的数据
        if [[ "$DIR" > "$(date -d '-7 days' +%Y-%m-%d 2>/dev/null || date -v-7d +%Y-%m-%d)" ]]; then
            print_info "下载 $DIR ..."
            mkdir -p "$DIGESTS_DIR/$DIR"

            # 获取该日期下的文件列表
            FILES_URL="https://api.github.com/repos/$GITHUB_REPO/contents/digests/$DIR?ref=$GITHUB_BRANCH"
            FILES=$(curl -s "$FILES_URL" | python3 -c "
import sys, json
data = json.load(sys.stdin)
if isinstance(data, list):
    for item in data:
        if item['type'] == 'file':
            print(item['name'])
" 2>/dev/null || echo "")

            for FILE in $FILES; do
                FILE_URL="https://raw.githubusercontent.com/$GITHUB_REPO/$GITHUB_BRANCH/digests/$DIR/$FILE"
                curl -s -o "$DIGESTS_DIR/$DIR/$FILE" "$FILE_URL"
            done

            print_success "已下载 $DIR"
        fi
    done
fi

# 步骤4: 生成manifest.json
print_info "步骤 4/5: 生成manifest.json..."

# 获取所有日期目录
DATES=$(ls -d "$DIGESTS_DIR"/*/ 2>/dev/null | xargs -I {} basename {} | sort -r)

# 生成manifest.json
python3 -c "
import json
import os
from datetime import datetime

digests_dir = '$DIGESTS_DIR'
dates = []

for date_dir in sorted(os.listdir(digests_dir), reverse=True):
    date_path = os.path.join(digests_dir, date_dir)
    if os.path.isdir(date_path):
        reports = []
        for f in os.listdir(date_path):
            if f.endswith('.md'):
                reports.append(f[:-3])  # 去掉.md后缀
        if reports:
            dates.append({
                'date': date_dir,
                'reports': sorted(reports)
            })

manifest = {
    'generated': datetime.now().isoformat(),
    'dates': dates
}

with open(os.path.join('$LOCAL_DIR', 'manifest.json'), 'w') as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)

print(f'已生成 manifest.json，包含 {len(dates)} 个日期')
"

print_success "manifest.json 已生成"

# 步骤5: 清理临时目录
print_info "步骤 5/5: 清理临时目录..."
rm -rf "$TEMP_DIR"
print_success "清理完成"

echo ""
print_success "=========================================="
print_success "  同步完成！"
print_success "=========================================="
echo ""
print_info "同步内容："
print_info "  - 报告目录: $DIGESTS_DIR"
print_info "  - 清单文件: $LOCAL_DIR/manifest.json"
echo ""
print_info "下一步："
print_info "  1. 重启RAG服务器以加载新数据"
print_info "  2. 或运行: python -m rag.ingest"
echo ""
