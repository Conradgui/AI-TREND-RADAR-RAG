<div align="center">

# 📡 AI Trend Radar RAG

**本地AI研究驾驶舱 — 基于RAG的智能趋势分析系统**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![Neo4j](https://img.shields.io/badge/Neo4j-5-purple.svg)](https://neo4j.com/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-latest-orange.svg)](https://www.trychroma.com/)

[快速开始](#-快速开始) •
[功能特性](#-功能特性) •
[API文档](#-api文档) •
[部署指南](#-部署指南) •
[贡献指南](#-贡献指南)

</div>

---

## 📖 目录

<details>
<summary>点击展开目录</summary>

- [项目简介](#-项目简介)
- [功能特性](#-功能特性)
- [快速开始](#-快速开始)
- [详细安装](#-详细安装)
- [使用指南](#-使用指南)
- [API文档](#-api文档)
- [架构设计](#-架构设计)
- [部署指南](#-部署指南)
- [开发指南](#-开发指南)
- [故障排除](#-故障排除)
- [路线图](#-路线图)
- [贡献指南](#-贡献指南)
- [许可证](#-许可证)

</details>

---

## 🎯 项目简介

**AI Trend Radar RAG** 是 [AI Trend Radar](https://github.com/Conradgui/AI-TREND-RADAR) 的扩展版本——在数据管道基础上叠加了 Graph RAG 与 Agentic RAG 智能查询层。

### 核心价值

- 📊 **智能分析**：基于RAG技术，从15+数据源自动分析AI趋势
- 🤖 **Agent问答**：支持自然语言查询，提供带引用的智能回答
- 📝 **研究制品**：自动生成Trend Brief研究制品
- 🔍 **证据可溯**：所有回答都有可追溯的引用来源

### 项目关系

> **AI-TREND-RADAR** 是数据管道（采集 → 评分 → 报告 → 分发），本仓库是它的超集，在数据管道基础上增加了知识图谱、向量检索和 Agent 对话能力。两个仓库共享同一份 `.env` 配置和 `digests/` 数据目录。

### 技术栈

| 层 | 技术 | 用途 |
|---|---|---|
| 数据管道 | TypeScript | 数据抓取和处理 |
| 知识图谱 | Neo4j 5 | 实体关系网络 |
| 向量库 | ChromaDB | 向量检索 |
| Agent框架 | LangGraph | 工具编排 |
| LLM | LangChain | 多provider支持 |
| 后端 | FastAPI | API服务 |
| 前端 | 原生HTML/JS | 用户界面 |

---

## ✨ 功能特性

### 📊 智能趋势分析

- 每日抓取15+公开数据源（GitHub、Product Hunt、Hacker News、ArXiv等）
- 自动生成中文选题池
- 支持趋势追踪和热度分析

### 🤖 Agent问答

- 支持自然语言查询
- 自动选择检索策略（内部语料优先，可选联网搜索）
- 提供带引用的智能回答
- 支持6个内置工具：search、topic_trend、entity_info、daily_overview、source_coverage、recommend

### 📝 研究制品

- 自动生成Trend Brief
- 支持多种模式（local-only、live-external）
- 可追溯的证据链

### 🔍 证据可溯

- 所有回答都有引用来源
- 支持内部/外部证据区分
- 可追溯到原始数据源

---

## 🚀 快速开始

### 方式一：一键启动（推荐）

**macOS / Linux：**
```bash
# 双击 start.command 文件
# 或在终端运行：
chmod +x start.command
./start.command
```

**Windows：**
```cmd
# 双击 start.bat 文件
# 或在命令行运行：
start.bat
```

脚本会自动：
1. ✅ 检查Python环境
2. ✅ 创建虚拟环境
3. ✅ 安装依赖
4. ✅ 启动Neo4j数据库
5. ✅ 同步最新数据（从GitHub AI-TREND-RADAR）
6. ✅ 启动RAG服务器
7. ✅ 打开浏览器

### 方式二：手动安装

```bash
# 1. 克隆仓库
git clone https://github.com/Conradgui/AI-TREND-RADAR-RAG.git
cd AI-TREND-RADAR-RAG

# 2. 切换到工作分支
git checkout claude/rag-transformation-checkpoints

# 3. 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# 或 .venv\Scripts\activate  # Windows

# 4. 安装依赖
pip install -r rag/requirements.txt

# 5. 配置环境变量
cp .env.example .env
# 编辑 .env，添加你的API密钥

# 6. 启动Neo4j
docker-compose up -d neo4j

# 7. 同步数据
bash scripts/sync-from-github.sh

# 8. 启动服务器
python -m rag.server
```

### 方式三：Docker部署

```bash
# 构建并启动所有服务
docker-compose up -d

# 访问 http://localhost:8001
```

---

## 📦 详细安装

### 前置条件

| 依赖 | 版本 | 用途 |
|------|------|------|
| Python | 3.11+ | RAG引擎 |
| Node.js | 18+ | 数据管道 |
| Docker | 20+ | Neo4j数据库 |
| pnpm | 8+ | 包管理器 |

### 安装步骤

#### 1. 安装Python

```bash
# macOS
brew install python@3.11

# Ubuntu/Debian
sudo apt update
sudo apt install python3.11 python3.11-venv

# Windows
# 从 https://www.python.org/downloads/ 下载安装
```

#### 2. 安装Node.js

```bash
# macOS
brew install node@18

# Ubuntu/Debian
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install nodejs

# Windows
# 从 https://nodejs.org/ 下载安装
```

#### 3. 安装Docker

```bash
# macOS
brew install --cask docker

# Ubuntu/Debian
sudo apt install docker.io docker-compose

# Windows
# 从 https://www.docker.com/products/docker-desktop 下载安装
```

#### 4. 安装pnpm

```bash
npm install -g pnpm
```

---

## 📘 使用指南

### 仪表盘

1. 访问 http://localhost:8001
2. 左侧边栏选择日期和报告
3. 查看报告内容

### Agent问答

1. 点击右上角"AGENT"按钮
2. 输入问题，如"最近有什么热门趋势？"
3. 查看带引用的智能回答

**示例问题**：
- "最近有什么热门趋势？"
- "推荐值得深挖的选题"
- "Claude最近有什么动态？"
- "RAG技术有什么发展？"

### 系统状态

1. 点击右上角"SYSTEM"按钮
2. 查看系统状态信息
3. 监控服务健康状态

### Briefs制品

1. 点击右上角"BRIEFS"按钮
2. 查看Trend Brief制品列表
3. 点击查看详细内容

---

## 📚 API文档

### 核心端点

| 端点 | 方法 | 说明 | 认证 |
|------|------|------|------|
| `/` | GET | 仪表盘首页 | ❌ |
| `/health` | GET | 健康检查 | ❌ |
| `/dashboard/status` | GET | 系统状态 | ❌ |
| `/briefs` | GET | Briefs列表 | ❌ |
| `/chat` | POST | Agent聊天 | ❌ |
| `/config` | POST | 配置管理 | ✅ |
| `/ingest` | POST | 数据摄取 | ✅ |
| `/metrics` | GET | 指标统计 | ❌ |
| `/metrics/recent` | GET | 最近指标 | ❌ |
| `/health/consistency` | GET | 数据一致性 | ❌ |

### 请求示例

#### Agent聊天

```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "最近有什么热门趋势？",
    "history": [],
    "context": {}
  }'
```

#### 系统状态

```bash
curl http://localhost:8001/dashboard/status
```

#### Briefs列表

```bash
curl http://localhost:8001/briefs
```

### 响应格式

#### Agent聊天响应

```json
{
  "answer": "根据AI Trend Radar内部语料...",
  "citations": [
    {
      "evidence_type": "internal",
      "date": "2026-06-21",
      "source": "InfoQ 中国",
      "title": "OpenAI最新动态",
      "citation_id": "2026-06-21/infoq-cn/1",
      "excerpt": "..."
    }
  ],
  "query_understanding": {
    "intent": "recent_trend",
    "topics": ["RAG"],
    "needs_web_search": false
  },
  "tool_trace": {
    "tools_used": ["search_corpus"],
    "evidence_sources": ["internal"],
    "total_calls": 1,
    "summary": "使用了 search_corpus；基于内部语料；共 3 条引用"
  }
}
```

---

## 🏗️ 架构设计

### 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    用户界面层                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │   仪表盘    │  │   Agent     │  │   Briefs    │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    API服务层                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │   FastAPI   │  │   /chat     │  │   /status   │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    Agent层                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │   LangGraph │  │   6个工具   │  │   提示词    │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    检索层                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │   向量检索  │  │   图检索    │  │   混合检索  │     │
│  │  (ChromaDB) │  │  (Neo4j)    │  │   (RRF)     │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    数据层                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │   语料库    │  │   知识图谱  │  │   向量库    │     │
│  │  (digests/) │  │  (Neo4j)    │  │  (ChromaDB) │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────────────────────────────────────────────┘
```

### 数据流

```
AI-TREND-RADAR (GitHub)
        │
        ▼
   数据同步脚本 (scripts/sync-from-github.sh)
        │
        ▼
   digests/ 目录
        │
        ▼
   数据摄取 (python -m rag.ingest)
        │
        ├────────────────┐
        ▼                ▼
   ChromaDB          Neo4j
   (向量索引)        (图索引)
        │                │
        └────────┬───────┘
                 ▼
           混合检索器
           (RRF融合)
                 │
                 ▼
             Agent
           (LangGraph)
                 │
                 ▼
           API响应
          (带引用)
                 │
                 ▼
             用户界面
```

---

## 🚢 部署指南

### 本地部署

```bash
# 1. 克隆仓库
git clone https://github.com/Conradgui/AI-TREND-RADAR-RAG.git
cd AI-TREND-RADAR-RAG

# 2. 配置环境
cp .env.example .env
# 编辑 .env 添加API密钥

# 3. 一键启动
./start.command
```

### Docker部署

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 生产环境部署

#### 1. Nginx反向代理

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

#### 2. HTTPS配置

```bash
# 安装Certbot
sudo apt install certbot python3-certbot-nginx

# 获取证书
sudo certbot --nginx -d your-domain.com
```

#### 3. systemd服务

```ini
[Unit]
Description=AI Trend Radar RAG
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/AI-TREND-RADAR-RAG
ExecStart=/path/to/AI-TREND-RADAR-RAG/.venv/bin/python -m rag.server
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## 🛠️ 开发指南

### 本地开发环境

```bash
# 1. 克隆仓库
git clone https://github.com/Conradgui/AI-TREND-RADAR-RAG.git
cd AI-TREND-RADAR-RAG

# 2. 安装依赖
pip install -r rag/requirements.txt
pnpm install

# 3. 启动开发服务器
python -m rag.server

# 4. 运行测试
pytest rag/tests/
pnpm test
```

### 项目结构

```
AI-TREND-RADAR-RAG/
├── rag/                          # Python RAG引擎
│   ├── server.py                 # FastAPI服务器
│   ├── config.py                 # 配置管理
│   ├── chat_service.py           # 聊天服务
│   ├── consistency.py            # 数据一致性校验
│   ├── metrics.py                # 指标收集
│   ├── agent/                    # Agent模块
│   ├── retriever/                # 检索模块
│   ├── graphrag/                 # 图谱模块
│   └── tests/                    # 测试
├── src/                          # TypeScript数据管道
├── index.html                    # 仪表盘UI
├── digests/                      # 报告数据
├── docs/                         # 文档
├── scripts/                      # 脚本
│   └── sync-from-github.sh       # 数据同步脚本
├── start.command                 # macOS启动脚本
├── start.bat                     # Windows启动脚本
└── docker-compose.yml            # Docker配置
```

### 常用命令

```bash
# 启动服务器
python -m rag.server

# 数据摄取
python -m rag.ingest

# 运行测试
pytest rag/tests/

# 同步数据
bash scripts/sync-from-github.sh

# 代码检查
pnpm lint
```

---

## ❓ 故障排除

### 常见问题

#### 1. Neo4j连接失败

**症状**：`Neo4j connection failed`

**解决方案**：
```bash
# 检查Neo4j是否运行
docker ps | grep neo4j

# 启动Neo4j
docker-compose up -d neo4j

# 等待启动
sleep 10
```

#### 2. API密钥错误

**症状**：`API key not configured`

**解决方案**：
```bash
# 检查.env文件
cat .env

# 确保密钥正确配置
# LLM_PROVIDER=deepseek
# DEEPSEEK_API_KEY=your_key_here
```

#### 3. 端口被占用

**症状**：`Port already in use`

**解决方案**：
```bash
# 查找占用端口的进程
lsof -i :8001

# 终止进程
kill -9 <PID>
```

#### 4. 数据同步失败

**症状**：`manifest.json not found`

**解决方案**：
```bash
# 手动同步数据
bash scripts/sync-from-github.sh

# 或手动下载
git clone --depth 1 https://github.com/Conradgui/AI-TREND-RADAR.git
cp -r AI-TREND-RADAR/digests/* digests/
```

---

## 🗺️ 路线图

### 已完成

- [x] P0: 数据同步 + RAG基础
- [x] P1: 检索质量 + Agent控制
- [x] P2: Trend Brief工作流
- [x] Stage 2.4: 本地产品流
- [x] Stage 2.5: Agent能力闭合
- [x] Stage 2.6: 证据选择质量
- [x] Stage 2.7: 统一工作区

### 进行中

- [ ] 集成测试完善
- [ ] 性能优化
- [ ] 文档完善

### 计划中

- [ ] 用户反馈收集
- [ ] 评估体系建立
- [ ] 持续改进机制

---

## 🤝 贡献指南

### 如何贡献

1. **Fork** 仓库
2. **创建** 特性分支 (`git checkout -b feature/AmazingFeature`)
3. **提交** 更改 (`git commit -m 'Add some AmazingFeature'`)
4. **推送** 到分支 (`git push origin feature/AmazingFeature`)
5. **创建** Pull Request

### 贡献类型

- 🐛 **Bug修复**：修复已知问题
- ✨ **新功能**：添加新功能
- 📝 **文档**：改进文档
- 🧪 **测试**：添加测试
- 🎨 **设计**：改进UI/UX

### 代码规范

- Python: PEP 8
- TypeScript: ESLint
- 提交信息: Conventional Commits

---

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

---

## 🙏 致谢

- [LangChain](https://github.com/langchain-ai/langchain) - LLM框架
- [LangGraph](https://github.com/langchain-ai/langgraph) - Agent框架
- [FastAPI](https://github.com/tiangolo/fastapi) - Web框架
- [Neo4j](https://neo4j.com/) - 图数据库
- [ChromaDB](https://www.trychroma.com/) - 向量数据库
- [marked](https://github.com/markedjs/marked) - Markdown渲染
- [DOMPurify](https://github.com/cure53/DOMPurify) - XSS防护

---

## 📞 联系方式

- **GitHub**: [Conradgui/AI-TREND-RADAR-RAG](https://github.com/Conradgui/AI-TREND-RADAR-RAG)
- **Issues**: [GitHub Issues](https://github.com/Conradgui/AI-TREND-RADAR-RAG/issues)

---

<div align="center">

**[⬆ 回到顶部](#-ai-trend-radar-rag)**

</div>
