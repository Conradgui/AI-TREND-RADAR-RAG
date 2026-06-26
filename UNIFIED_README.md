# AI Trend Radar RAG - Unified Workspace

**版本**: 1.0
**最后更新**: 2026-06-25

---

## 概述

AI Trend Radar RAG 是一个本地AI研究驾驶舱，用于读取AI趋势报告、进行智能问答和生成研究制品。

### 核心功能

- 📊 **趋势报告**：每日抓取15+公开数据源，生成中文选题池
- 🤖 **智能问答**：基于本地知识库的Agent问答（带引用）
- 📝 **研究制品**：生成Trend Brief研究制品
- 🔍 **证据追溯**：所有证据可追溯、可验证

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

## 快速开始

### 方式一：自动设置（推荐）

```bash
# 克隆仓库
git clone https://github.com/Conradgui/AI-TREND-RADAR-RAG.git
cd AI-TREND-RADAR-RAG

# 切换到Claude工作分支
git checkout claude/rag-transformation-checkpoints

# 运行设置脚本
chmod +x setup.sh
./setup.sh
```

### 方式二：手动设置

#### 1. 配置环境

```bash
# 复制配置文件
cp .env.unified.example .env

# 编辑.env，添加你的API密钥
nano .env
```

#### 2. 设置Python环境

```bash
# 创建虚拟环境
python3 -m venv .venv

# 激活虚拟环境
source .venv/bin/activate

# 安装依赖
pip install -r rag/requirements.txt
```

#### 3. 设置Node.js环境

```bash
# 安装依赖
pnpm install
```

#### 4. 启动Neo4j（可选）

```bash
# 使用Docker启动Neo4j
docker-compose up -d neo4j
```

#### 5. 运行数据管道

```bash
# 运行数据管道
pnpm start

# 生成清单
pnpm manifest
```

#### 6. 运行RAG摄取

```bash
# 摄取数据到ChromaDB和Neo4j
python -m rag.ingest
```

#### 7. 启动RAG服务器

```bash
# 启动服务器
python -m rag.server
```

#### 8. 访问仪表盘

打开浏览器访问：http://localhost:8001

---

## 项目结构

```
AI-TREND-RADAR-RAG/
├── .env.unified.example    # 统一配置示例
├── setup.sh                # 统一设置脚本
├── UNIFIED_README.md       # 本文件
├── index.html              # 仪表盘UI
├── src/                    # TypeScript数据管道
│   ├── index.ts
│   ├── config.ts
│   └── ...
├── rag/                    # Python RAG引擎
│   ├── server.py           # FastAPI服务器
│   ├── config.py           # 配置管理
│   ├── agent/              # Agent模块
│   ├── retriever/          # 检索模块
│   ├── graphrag/           # 图谱模块
│   └── ...
├── docs/                   # 文档
│   └── rag-transformation/ # RAG转型文档
├── digests/                # 报告数据
├── assets/                 # 静态资源
└── docker-compose.yml      # Docker配置
```

---

## 配置说明

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| LLM_PROVIDER | LLM提供商 | deepseek |
| DEEPSEEK_API_KEY | DeepSeek API密钥 | - |
| NEO4J_URI | Neo4j连接URI | bolt://localhost:7687 |
| NEO4J_PASSWORD | Neo4j密码 | password |
| RAG_PORT | RAG服务器端口 | 8001 |

### 搜索Provider（可选）

| 变量 | 说明 |
|------|------|
| BRAVE_API_KEY | Brave Search API密钥 |
| TAVILY_API_KEY | Tavily Search API密钥 |
| EXA_API_KEY | Exa Search API密钥 |
| SERPAPI_API_KEY | SerpAPI密钥 |
| GITHUB_TOKEN | GitHub API令牌 |

---

## API 文档

### 端点总览

| 端点 | 方法 | 说明 | 认证 |
|------|------|------|------|
| `/` | GET | 仪表盘首页 | 无 |
| `/chat` | POST | Agent 对话入口 | 无 |
| `/health` | GET | 健康检查 | 无 |
| `/dashboard/status` | GET | 系统状态详情 | 无 |
| `/briefs` | GET | Trend Brief 制品列表 | 无 |
| `/config` | POST | 保存 API 配置 | API Key |
| `/config/web-search` | POST | 切换联网搜索 | API Key |
| `/config/deep-fetch` | POST | 切换深度抓取 | API Key |
| `/config/retriever-mode` | POST | 设置检索模式 | API Key |
| `/ingest` | POST | 触发数据摄取 | API Key |

### 详细 API 文档

#### GET `/dashboard/status`

返回仪表盘完整的系统状态信息。

**请求**：
```
GET http://localhost:8001/dashboard/status
```

**响应** (200 OK)：
```json
{
  "service": "ai-trend-radar-rag",
  "configured": true,
  "provider": "deepseek",
  "neo4j_connected": true,
  "chromadb_chunks": 1250,
  "retriever_mode": "hybrid",
  "deep_fetch_enabled": false,
  "search_providers": ["brave", "tavily"],
  "latest_corpus_date": "2026-06-24",
  "service_version": "0.2.0",
  "web_search_enabled": true
}
```

**响应字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `service` | string | 服务名称 |
| `configured` | boolean | 是否已配置 API Key |
| `provider` | string | 当前 LLM 提供商 |
| `neo4j_connected` | boolean | Neo4j 连接状态 |
| `chromadb_chunks` | number | 向量块数量 |
| `retriever_mode` | string | 检索模式（hybrid/vector-only） |
| `deep_fetch_enabled` | boolean | 深度抓取状态 |
| `search_providers` | string[] | 搜索 Provider 列表 |
| `latest_corpus_date` | string | 最新语料日期 |
| `service_version` | string | 服务版本 |
| `web_search_enabled` | boolean | 联网搜索状态 |

---

#### GET `/briefs`

列出所有 Trend Brief 研究制品。

**请求**：
```
GET http://localhost:8001/briefs
```

**响应** (200 OK)：
```json
{
  "briefs": [
    {
      "title": "RAG 技术趋势分析",
      "topic": "",
      "generated_date": "2026-06-24",
      "mode": "deep",
      "source_quality": "",
      "path": "docs/rag-transformation/briefs/trend-brief-rag-2026-06-24.md"
    }
  ]
}
```

---

#### POST `/chat`

Agent 对话入口。

**请求**：
```
POST http://localhost:8001/chat
Content-Type: application/json
```

**请求体**：
```json
{
  "message": "最近 RAG 领域有什么新进展？",
  "history": [],
  "context": {}
}
```

**响应** (200 OK)：
```json
{
  "answer": "AI 生成的回答...",
  "citations": [
    {
      "date": "2026-06-24",
      "source": "ai-topic-radar",
      "title": "来源标题",
      "excerpt": "相关摘录",
      "url": "https://example.com"
    }
  ],
  "query_understanding": {},
  "tool_trace": {
    "summary": "推理过程",
    "tools_used": ["topic_trend"]
  }
}
```

---

#### GET `/health`

健康检查端点。

**响应**：
```json
{
  "status": "ok",
  "configured": true,
  "neo4j_connected": true,
  "chromadb_chunks": 1250,
  "provider": "deepseek",
  "retriever_mode": "hybrid",
  "deep_fetch_enabled": false
}
```

---

## 使用指南

### 仪表盘使用指南

仪表盘是系统的主要界面，提供报告浏览、AI 对话、系统状态查看和 Brief 制品管理功能。

#### 界面布局

- **顶部导航栏**：显示品牌标识和功能按钮（RSS、AGENT、SYSTEM、BRIEFS、主题切换）
- **左侧边栏**：报告列表，按月份和日期分组，支持搜索
- **主内容区**：报告内容显示，支持 Markdown 渲染

#### 报告浏览

1. **选择日期**：点击左侧边栏的月份和日期展开报告列表
2. **查看报告**：点击报告名称加载内容
3. **语言切换**：部分报告提供中英文版本，使用 ZH/EN 按钮切换
4. **搜索功能**：在搜索框输入关键词，快速定位包含该关键词的日期

#### 主题切换

点击右上角的 ◐ 按钮切换深色/浅色主题。

---

### Agent 聊天使用指南

Agent 聊天是系统的核心功能，基于 LangGraph ReAct Agent 实现智能问答。

#### 打开聊天面板

点击右上角的 **AGENT** 按钮打开聊天面板。

#### 功能特性

1. **智能问答**：输入自然语言问题，Agent 会自动选择合适的工具进行检索和回答
2. **引用来源**：回答下方显示参考来源，点击可跳转到对应报告
3. **推理过程**：显示 Agent 的推理过程和使用的工具
4. **对话历史**：支持多轮对话，自动保留上下文（最近 20 轮）

#### 示例问题

| 类型 | 示例问题 |
|------|----------|
| 趋势分析 | "最近 RAG 领域有什么新进展？" |
| 话题查询 | "OpenAI 最近发布了什么？" |
| 选题推荐 | "给我推荐几个值得深挖的选题" |
| 跨源对比 | "中英文社区对大模型的讨论有什么不同？" |
| 关系图谱 | "LangChain 和哪些项目有关系？" |

#### 注意事项

- Agent 功能需要本地 RAG 服务运行（`python -m rag.server`）
- 静态模式下（GitHub Pages）无法使用 Agent 功能
- 对话历史保存在浏览器内存中，刷新页面后清空

---

### 系统状态查看指南

系统状态面板显示服务的运行状态、配置信息和数据库连接情况。

#### 打开系统面板

点击右上角的 **SYSTEM** 按钮打开系统状态面板。

#### 状态说明

| 状态项 | 说明 |
|--------|------|
| 服务状态 | 显示服务名称和运行状态（绿色圆点表示正常） |
| LLM Provider | 当前使用的 LLM 提供商 |
| 检索模式 | 当前检索模式，点击可切换（hybrid/vector-only） |
| Neo4j | Neo4j 数据库连接状态（绿色/红色圆点） |
| ChromaDB | ChromaDB 中的向量块数量 |
| 最新语料 | 最新的数据日期 |
| 搜索Provider | 已配置的搜索 API |
| 联网搜索 | 是否启用联网搜索，点击可切换 |
| 深度抓取 | 是否启用深度抓取（仅联网搜索启用时显示） |
| 服务版本 | 当前服务版本号 |

#### 交互功能

1. **切换检索模式**：点击检索模式按钮在 hybrid 和 vector-only 之间切换
2. **切换联网搜索**：点击联网搜索按钮启用/禁用联网搜索
3. **切换深度抓取**：点击深度抓取按钮启用/禁用深度抓取

---

### Brief 制品使用指南

Brief 制品是 AI 生成的研究报告，基于选题数据进行深度分析。

#### 打开 Briefs 面板

点击右上角的 **BRIEFS** 按钮打开 Briefs 面板。

#### 查看 Brief 内容

1. 点击 Brief 卡片查看完整内容
2. 内容以 Markdown 格式渲染
3. 点击"← 返回列表"回到列表页

#### Brief 元数据

| 字段 | 说明 |
|------|------|
| 标题 | Brief 研究主题 |
| 生成日期 | Brief 生成日期 |
| 模式 | 生成模式（deep/standard） |

---

## 开发指南

### 本地开发环境搭建

#### 前置条件

- Python 3.11+
- Node.js 18+
- Docker（用于 Neo4j）
- pnpm（推荐）或 npm

#### 步骤 1：克隆项目

```bash
git clone https://github.com/Conradgui/AI-TREND-RADAR-RAG.git
cd AI-TREND-RADAR-RAG
```

#### 步骤 2：配置环境

```bash
# 复制配置文件
cp .env.unified.example .env

# 编辑配置文件
nano .env
```

**必须配置的项**：
- `LLM_PROVIDER`：选择 LLM 提供商（anthropic/openai/deepseek）
- 对应的 API Key（如 `DEEPSEEK_API_KEY`）

#### 步骤 3：设置 Python 环境

```bash
# 创建虚拟环境
python3 -m venv .venv

# 激活虚拟环境
source .venv/bin/activate

# 安装依赖
pip install -r rag/requirements.txt
```

#### 步骤 4：设置 Node.js 环境

```bash
# 安装依赖
pnpm install
```

#### 步骤 5：启动 Neo4j

```bash
# 使用 Docker 启动 Neo4j
docker-compose up -d neo4j

# 等待 Neo4j 就绪（约 10 秒）
sleep 10
```

#### 步骤 6：运行数据管道

```bash
# 运行数据管道（抓取数据源、生成日报）
pnpm start

# 生成清单文件
pnpm manifest
```

#### 步骤 7：运行数据摄取

```bash
# 将数据导入 Neo4j 和 ChromaDB
python -m rag.ingest
```

#### 步骤 8：启动 RAG 服务器

```bash
# 启动服务器
python -m rag.server
```

#### 步骤 9：访问应用

打开浏览器访问：http://localhost:8001

---

### 测试运行指南

#### 测试结构

```
rag/tests/
├── test_config.py                  # 配置测试
├── test_chat_service.py           # 聊天服务测试
├── test_citations.py              # 引用功能测试
├── test_answer_policy.py          # 回答策略测试
├── test_batch_evidence.py         # 批量证据测试
├── test_deep_fetch_policy.py      # 深度抓取策略测试
├── test_eval_*.py                 # 评估测试套件
└── ...
```

#### 运行所有测试

```bash
# 激活虚拟环境
source .venv/bin/activate

# 运行所有测试
python -m pytest rag/tests/ -v
```

#### 运行特定测试

```bash
# 运行单个测试文件
python -m pytest rag/tests/test_chat_service.py -v

# 运行单个测试函数
python -m pytest rag/tests/test_chat_service.py::test_chat_basic -v

# 运行匹配关键字的测试
python -m pytest rag/tests/ -k "citation" -v
```

#### 测试覆盖率

```bash
# 安装覆盖率工具
pip install pytest-cov

# 运行测试并生成覆盖率报告
python -m pytest rag/tests/ --cov=rag --cov-report=html

# 查看报告
open htmlcov/index.html
```

#### 评估测试

评估测试用于验证 Agent 的回答质量：

```bash
# 运行所有评估测试
python -m pytest rag/tests/test_eval_*.py -v

# 运行特定评估
python -m pytest rag/tests/test_eval_golden.py -v
python -m pytest rag/tests/test_eval_answer_policy.py -v
```

#### TypeScript 测试

```bash
# 运行 TypeScript 测试
pnpm test

# 运行完整检查（lint + test + type check）
pnpm rag:check:p0
```

---

### 部署指南

#### 本地部署

最简单的部署方式是本地运行：

```bash
# 1. 完成环境搭建（参考"本地开发环境搭建"）

# 2. 启动服务
python -m rag.server

# 3. 访问 http://localhost:8001
```

#### Docker 部署

使用 Docker Compose 部署完整服务：

```bash
# 1. 配置环境变量
cp .env.unified.example .env
# 编辑 .env 填写配置

# 2. 启动所有服务
docker-compose up -d

# 3. 查看日志
docker-compose logs -f
```

#### 生产环境部署

##### 1. 环境变量配置

```bash
# 生产环境必须修改的配置
RAG_API_KEY=<strong-random-key>  # 修改默认 API Key
NEO4J_PASSWORD=<strong-password> # 修改默认密码
DEBUG=false
LOG_LEVEL=info
```

##### 2. 反向代理配置（Nginx）

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

##### 3. 进程管理（systemd）

创建 `/etc/systemd/system/rag-server.service`：

```ini
[Unit]
Description=AI Trend Radar RAG Server
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/AI-TREND-RADAR-RAG
Environment="PATH=/path/to/AI-TREND-RADAR-RAG/.venv/bin"
ExecStart=/path/to/AI-TREND-RADAR-RAG/.venv/bin/python -m rag.server
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable rag-server
sudo systemctl start rag-server
sudo systemctl status rag-server
```

#### GitHub Pages 部署（静态模式）

仅部署前端，不包含 Agent 功能：

```bash
# 1. 构建静态文件
pnpm build

# 2. 推送到 gh-pages 分支
git subtree push --prefix dist origin gh-pages
```

**注意**：静态模式下 Agent 功能不可用，仅支持报告浏览。

---

### 常见开发任务

#### 添加新的数据源

1. 在 `src/` 目录创建新的适配器
2. 在 `src/config.ts` 中注册数据源
3. 运行数据管道测试
4. 运行数据摄取更新知识库

#### 修改 Agent 工具

1. 编辑 `rag/agent/tools.py` 添加或修改工具
2. 更新 `rag/agent/prompts.py` 中的系统提示词
3. 运行测试验证：`python -m pytest rag/tests/test_chat_service.py -v`

#### 优化检索质量

1. 调整 `rag/retriever/hybrid.py` 中的检索参数
2. 修改 `rag/retriever/vector_store.py` 中的嵌入模型
3. 运行评估测试验证：`python -m pytest rag/tests/test_eval_*.py -v`

---

## 故障排除

### 1. Neo4j连接失败

**症状**：Agent初始化失败，显示"Neo4j connection failed"

**解决方案**：
```bash
# 检查Neo4j是否运行
docker ps | grep neo4j

# 启动Neo4j
docker-compose up -d neo4j

# 等待Neo4j就绪
sleep 10
```

### 2. API密钥错误

**症状**：Agent返回错误，显示"API key not configured"

**解决方案**：
```bash
# 检查.env文件
cat .env

# 确保API密钥正确配置
# LLM_PROVIDER=deepseek
# DEEPSEEK_API_KEY=your_key_here
```

### 3. 端口被占用

**症状**：服务器启动失败，显示"Port already in use"

**解决方案**：
```bash
# 查找占用端口的进程
lsof -i :8001

# 终止进程
kill -9 <PID>

# 或修改端口
# 在.env中设置 RAG_PORT=8002
```

### 4. 数据管道失败

**症状**：数据管道运行失败

**解决方案**：
```bash
# 检查网络连接
ping google.com

# 检查Node.js版本
node --version

# 重新安装依赖
pnpm install
```

---

## 常见问题

### Q1: 如何添加新的数据源？

A1: 在`src/`目录下创建新的适配器文件，参考现有的适配器实现。

### Q2: 如何修改Agent行为？

A2: 修改`rag/agent/`目录下的文件，包括工具定义、提示词等。

### Q3: 如何优化检索质量？

A3: 修改`rag/retriever/`目录下的文件，调整重排策略、质量权重等。

### Q4: 如何部署到生产环境？

A4: 参考`docker-compose.yml`和`docs/`目录下的部署文档。

---

## 贡献指南

1. Fork仓库
2. 创建特性分支
3. 提交更改
4. 推送到分支
5. 创建Pull Request

---

## 许可证

MIT License

---

## 联系方式

- GitHub: https://github.com/Conradgui/AI-TREND-RADAR-RAG
- Issues: https://github.com/Conradgui/AI-TREND-RADAR-RAG/issues

---

## 更新日志

### v1.0 (2026-06-25)
- 初始版本
- 统一工作区结构
- 统一配置文件
- 统一设置脚本
