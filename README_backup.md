# AI Trend Radar RAG

**[AI Trend Radar](https://github.com/Conradgui/AI-TREND-RADAR) 的扩展版本**——包含数据管道的全部代码 + Graph RAG + Agentic RAG 智能查询层。

> **项目关系**：[AI-TREND-RADAR](https://github.com/Conradgui/AI-TREND-RADAR) 是数据管道（采集 → 评分 → 报告 → 分发），本仓库是它的超集，在数据管道基础上增加了知识图谱、向量检索和 Agent 对话能力。两个仓库共享同一份 `.env` 配置和 `digests/` 数据目录。

> **AI coding assistant handoff**：任何 AI 编程辅助工具接手本仓库前，请先阅读 [`AGENTS.md`](./AGENTS.md) 和 [`docs/rag-transformation/AI_HANDOFF.md`](./docs/rag-transformation/AI_HANDOFF.md)。RAG 转型工作的当前路线、Loop、证据标准和阶段边界以 `docs/rag-transformation/` 为准；旧 README 中的架构描述需要结合当前代码复核后再引用。

---

AI Trend Radar 面向 AI 内容运营和产品调研，每天抓取公开 AI 信号（国内外共 15+ 数据源），生成一份中文"值得写、值得测、值得深挖"的选题池，并通过 HTML、Web UI、RSS、Telegram、飞书和 GitHub Actions 分发。它不是一个简单的信息搬运脚本，而是把分散的 AI 行业信号转成可排序、可解释、可交付的选题决策流：先采集公开证据，再用评分框架判断优先级，最后沉淀成报告、结构化数据和自动化分发链路。

**本仓库在此基础上增加了智能对话能力**——通过 Neo4j 知识图谱构建选题实体之间的关系网络，通过 ChromaDB 向量搜索实现跨报告的语义检索，再由 LangGraph ReAct Agent 编排多个检索工具，让用户可以用自然语言直接查询历史选题数据、分析趋势、获取选题推荐。

### 开发方向：Nexus-inspired Knowledge Engine

```
Nexus-inspired Knowledge Engine
= Agentic RAG                          — Agent 自主决定何时检索、用哪个工具、如何综合
+ Pre-runtime Knowledge Compilation    — 每日 ingestion 阶段预编译知识制品
+ Knowledge Artifact Layer             — 结构化知识实体（话题图谱、趋势轨迹、实体关系）
+ Structured Knowledge Query           — 声明式查询（Cypher + 语义混合）
+ Evidence & Governance Layer          — 每条结论可追溯到原始数据源和评分证据
+ Evaluation Feedback Loop             — 选题质量反馈驱动评分权重和分类规则的持续优化
```

当前进度：基础 Graph RAG（知识图谱构建 + 混合检索 + 6 工具 Agent）已完成，后续迭代预编译知识制品和声明式查询层。

## 使用指南

### 仪表盘使用指南

仪表盘是系统的主要界面，提供报告浏览、AI 对话、系统状态查看和 Brief 制品管理功能。

#### 界面布局

```
┌─────────────────────────────────────────────────────────────┐
│  📡 AI Topic Radar    [RSS] [AGENT] [SYSTEM] [BRIEFS] [◐]  │
├──────────┬──────────────────────────────────────────────────┤
│          │                                                  │
│ REPORTS  │              报告内容区域                         │
│          │                                                  │
│ 搜索框   │         （Markdown 渲染）                         │
│          │                                                  │
│ 2026-06  │                                                  │
│   └ 24   │                                                  │
│     └ .. │                                                  │
│   └ 23   │                                                  │
│          │                                                  │
└──────────┴──────────────────────────────────────────────────┘
```

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

#### 聊天界面

```
┌────────────────────────────┐
│  ● AI Agent            [✕] │
├────────────────────────────┤
│                            │
│  🤖 你好！我是 AI Topic    │
│     Radar 的智能助手...    │
│                            │
│  [热门趋势] [推荐选题]     │
│  [Claude 动态]             │
│                            │
├────────────────────────────┤
│  [输入消息...]         [➤] │
└────────────────────────────┘
```

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

#### 预设问题

点击欢迎界面的预设问题标签，快速开始对话。

#### 注意事项

- Agent 功能需要本地 RAG 服务运行（`python -m rag.server`）
- 静态模式下（GitHub Pages）无法使用 Agent 功能
- 对话历史保存在浏览器内存中，刷新页面后清空

---

### 系统状态查看指南

系统状态面板显示服务的运行状态、配置信息和数据库连接情况。

#### 打开系统面板

点击右上角的 **SYSTEM** 按钮打开系统状态面板。

#### 系统面板内容

```
┌────────────────────────────┐
│  ● 系统状态            [✕] │
├────────────────────────────┤
│  服务配置                   │
│  ├ 服务状态    ● ai-trend- │
│  │             radar-rag   │
│  ├ LLM Provider  deepseek  │
│  └ 检索模式    [hybrid]    │
│                            │
│  数据库                     │
│  ├ Neo4j       ● 已连接    │
│  └ ChromaDB    1250 chunks │
│                            │
│  数据源                     │
│  ├ 最新语料    2026-06-24  │
│  ├ 搜索Provider brave,...  │
│  ├ 联网搜索    [已启用]    │
│  └ └ 深度抓取  [未启用]    │
│                            │
│  版本                       │
│  └ 服务版本    0.2.0       │
└────────────────────────────┘
```

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

#### Briefs 列表

```
┌────────────────────────────┐
│  ● Trend Briefs        [✕] │
├────────────────────────────┤
│                            │
│  ┌──────────────────────┐  │
│  │ RAG 技术趋势分析     │  │
│  │ [2026-06-24] [deep]  │  │
│  └──────────────────────┘  │
│                            │
│  ┌──────────────────────┐  │
│  │ AI Agent 生态研究     │  │
│  │ [2026-06-23] [stan..]│  │
│  └──────────────────────┘  │
│                            │
└────────────────────────────┘
```

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

## 它能做什么？

| 能力 | 示例问题 |
|------|----------|
| 趋势分析 | "最近 RAG 领域有什么新进展？" |
| 话题查询 | "OpenAI 最近发布了什么？" |
| 选题推荐 | "给我推荐几个值得深挖的选题" |
| 跨源对比 | "中英文社区对大模型的讨论有什么不同？" |
| 关系图谱 | "LangChain 和哪些项目有关系？" |

## 架构

```
AI-TREND-RADAR（数据管道）
    pnpm digest → digests/YYYY-MM-DD/*.md + topic-pool.json
        ↓
AI-TREND-RADAR-RAG（本项目）
    python -m rag.ingest → Neo4j 知识图谱 + ChromaDB 向量库
    python -m rag.server  → http://localhost:8001（Chat UI + API）
        ↓
LangGraph ReAct Agent（6 个工具）
    ├── search            — 搜索任何内容（自动混合图+向量 RRF 融合）
    ├── topic_trend       — 话题趋势分析（分数变化、热度走向）
    ├── entity_info       — 实体详情和关系网络
    ├── daily_overview    — 某日选题概览
    ├── source_coverage   — 跨数据源对比分析
    └── recommend         — 选题推荐（基于评分和趋势）
```

### 核心设计思路

**Agentic RAG（智能检索增强生成）**：不是简单的"检索 + 回答"，而是让 Agent 自主决定何时检索、用哪个工具检索、如何综合多次检索结果。当用户问"最近有什么趋势"时，Agent 会先用 `recommend` 获取热门选题，再用 `topic_trend` 分析变化，最后综合生成回答。

**Graph RAG（图谱检索增强生成）**：通过 Neo4j 知识图谱把分散的选题数据组织成结构化的关系网络。话题通过 `APPEARED_ON` 关系连接到日期，通过 `DISCOVERED_VIA` 连接到数据源，实体通过 `MENTIONS` 连接到话题。这让 Agent 不仅能搜索内容，还能查询关系——"谁和谁有关"、"某个话题在哪些源出现过"。

## 快速开始

### 前置条件

- Python 3.11+
- Docker（用于 Neo4j）
- 一个 LLM API Key（DeepSeek / OpenAI / Anthropic 均可）

### 安装与运行

```bash
# 1. 克隆项目
git clone https://github.com/Conradgui/AI-TREND-RADAR-RAG.git
cd AI-TREND-RADAR-RAG

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env，设置 LLM_PROVIDER 和对应的 API_KEY

# 2b.（可选）配置 Gitee Token 以获取 Gitee 热门项目数据
# 前往 https://gitee.com/profile/personal_access_tokens 创建只读 Token
# 在 .env 中取消注释并填入：GITEE_TOKEN=your_token
# 如需在 GitHub Actions 中使用，还需在仓库 Settings → Secrets 中添加 GITEE_TOKEN

# 3. 安装依赖 + 启动 Neo4j
pnpm setup:rag

# 4. 生成数据 + 摄取 + 启动服务
pnpm digest
python -m rag.ingest
python -m rag.server

# 5. 打开浏览器
# http://localhost:8001
```

首次打开会显示配置页面，填写 LLM Provider 和 API Key 后进入 Chat 界面。

## 技术栈

| 层 | 技术 | 用途 |
|---|------|------|
| 知识图谱 | Neo4j 5 | 话题、实体、来源的关系网络 |
| 向量库 | ChromaDB | 日报内容的语义嵌入和搜索 |
| Agent 框架 | LangGraph | ReAct 模式的智能对话代理 |
| LLM | LangChain | Anthropic / OpenAI / DeepSeek 封装 |
| 后端 | FastAPI | HTTP API 服务 |
| 前端 | 原生 HTML/JS | 对话界面（marked.js 渲染 Markdown） |
| 数据管道 | TypeScript (原有) | 15+ 数据源采集 + 日报生成 |
| 容器 | Docker | Neo4j 数据库 |

## 知识图谱 Schema

```cypher
-- 节点
(:Topic {id, name, category, totalScore, mentionCount, firstSeen, lastSeen})
(:Entity {id, name, type})
(:Source {id, name, type: "international"|"chinese"|"official"})
(:Document {id, title, date, reportType, content})
(:DailyDigest {date, candidateCount, generatedAt})

-- 关系
(:Topic)-[:APPEARED_ON {score, action}]->(:DailyDigest)
(:Topic)-[:DISCOVERED_VIA]->(:Source)
(:Entity)-[:MENTIONS]->(:Topic)
(:Document)-[:PART_OF]->(:DailyDigest)

-- 索引
CREATE CONSTRAINT topic_id FOR (t:Topic) REQUIRE t.id IS UNIQUE
CREATE FULLTEXT INDEX entity_search FOR (e:Entity) ON EACH [e.name, e.description]
```

## API 端点

### 端点总览

| 端点 | 方法 | 说明 | 认证 |
|------|------|------|------|
| `/` | GET | 仪表盘首页 | 无 |
| `/chat` | GET | Chat UI 页面（兼容旧路由） | 无 |
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

返回仪表盘完整的系统状态信息，包括服务配置、数据库连接、数据源状态等。

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
| `provider` | string | 当前 LLM 提供商（anthropic/openai/deepseek） |
| `neo4j_connected` | boolean | Neo4j 数据库连接状态 |
| `chromadb_chunks` | number | ChromaDB 中的向量块数量 |
| `retriever_mode` | string | 检索模式（hybrid/vector-only/graph-only） |
| `deep_fetch_enabled` | boolean | 深度抓取是否启用 |
| `search_providers` | string[] | 已配置的搜索 Provider 列表 |
| `latest_corpus_date` | string | 最新语料日期（YYYY-MM-DD） |
| `service_version` | string | 服务版本号 |
| `web_search_enabled` | boolean | 联网搜索是否启用 |

**使用场景**：
- 仪表盘系统状态面板调用此接口显示系统信息
- 监控系统健康状态
- 调试配置问题

---

#### GET `/briefs`

列出所有 Trend Brief 研究制品，包括标题、生成日期、模式等元数据。

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
    },
    {
      "title": "AI Agent 生态研究",
      "topic": "",
      "generated_date": "2026-06-23",
      "mode": "standard",
      "source_quality": "",
      "path": "docs/rag-transformation/briefs/trend-brief-agent-2026-06-23.md"
    }
  ]
}
```

**响应字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `briefs` | array | Brief 制品列表 |
| `briefs[].title` | string | Brief 标题 |
| `briefs[].topic` | string | 主题（目前为空） |
| `briefs[].generated_date` | string | 生成日期（YYYY-MM-DD） |
| `briefs[].mode` | string | 生成模式（deep/standard） |
| `briefs[].source_quality` | string | 来源质量（目前为空） |
| `briefs[].path` | string | Brief 文件相对路径 |

**使用场景**：
- 仪表盘 Briefs 面板显示制品列表
- 点击 Brief 后通过 `/{path}` 获取完整内容

---

#### POST `/chat`

Agent 对话入口，接收用户消息并返回 AI 生成的回答，包含引用和推理过程。

**请求**：
```
POST http://localhost:8001/chat
Content-Type: application/json
```

**请求体**：
```json
{
  "message": "最近 RAG 领域有什么新进展？",
  "history": [
    {"role": "user", "content": "你好"},
    {"role": "assistant", "content": "你好！有什么可以帮你的？"}
  ],
  "context": {
    "report": "ai-topic-radar",
    "date": "2026-06-24",
    "topic": "RAG"
  }
}
```

**请求字段说明**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `message` | string | 是 | 用户消息（最大 2000 字符） |
| `history` | array | 否 | 对话历史（用于上下文理解） |
| `history[].role` | string | 是 | 角色（user/assistant） |
| `history[].content` | string | 是 | 消息内容 |
| `context` | object | 否 | 报告上下文（可选） |
| `context.report` | string | 否 | 当前报告名称 |
| `context.date` | string | 否 | 当前报告日期 |
| `context.topic` | string | 否 | 当前主题 |

**响应** (200 OK)：
```json
{
  "answer": "最近 RAG 领域有几个重要进展：\n\n1. **混合检索成为主流**：结合向量搜索和图谱检索的混合方案获得广泛采用...\n2. **Agentic RAG 兴起**：让 Agent 自主决定何时检索、用哪个工具...",
  "citations": [
    {
      "date": "2026-06-24",
      "source": "ai-topic-radar",
      "title": "RAG 技术演进",
      "excerpt": "混合检索方案在多个基准测试中表现优异...",
      "url": "https://example.com/article"
    }
  ],
  "query_understanding": {
    "intent": "trend_analysis",
    "entities": ["RAG"],
    "time_range": "recent"
  },
  "tool_trace": {
    "summary": "使用 topic_trend 工具分析 RAG 趋势，然后使用 recommend 获取相关选题",
    "tools_used": ["topic_trend", "recommend"]
  }
}
```

**响应字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `answer` | string | AI 生成的回答（Markdown 格式） |
| `citations` | array | 引用来源列表 |
| `citations[].date` | string | 来源日期 |
| `citations[].source` | string | 来源名称 |
| `citations[].title` | string | 来源标题 |
| `citations[].excerpt` | string | 相关摘录 |
| `citations[].url` | string | 原始链接（可选） |
| `query_understanding` | object | 查询理解信息 |
| `tool_trace` | object | 工具使用跟踪 |
| `tool_trace.summary` | string | 推理过程摘要 |
| `tool_trace.tools_used` | string[] | 使用的工具列表 |

**错误响应**：

| 状态码 | 说明 |
|--------|------|
| 503 | Agent 未初始化（检查 Neo4j 连接和 API Key 配置） |
| 500 | 处理失败（服务器内部错误） |

**使用场景**：
- 仪表盘 Agent 聊天面板
- API 集成
- 自动化查询

---

#### POST `/config`

保存 API 配置到 `.env` 文件（需要 API Key 认证）。

**请求**：
```
POST http://localhost:8001/config
Content-Type: application/json
X-API-Key: your-api-key
```

**请求体**：
```json
{
  "provider": "deepseek",
  "api_key": "sk-xxx",
  "neo4j_uri": "bolt://localhost:7687",
  "neo4j_password": "password"
}
```

**响应** (200 OK)：
```json
{
  "status": "ok",
  "message": "Configuration saved. Please restart the server."
}
```

**注意**：保存配置后需要重启服务器才能生效。

---

#### POST `/config/web-search`

切换联网搜索状态（需要 API Key 认证）。

**请求**：
```
POST http://localhost:8001/config/web-search?enabled=true
X-API-Key: your-api-key
```

**响应** (200 OK)：
```json
{
  "status": "ok",
  "web_search_enabled": true
}
```

---

#### POST `/config/deep-fetch`

切换深度抓取状态（需要 API Key 认证）。

**请求**：
```
POST http://localhost:8001/config/deep-fetch?enabled=true
X-API-Key: your-api-key
```

**响应** (200 OK)：
```json
{
  "status": "ok",
  "deep_fetch_enabled": true
}
```

---

#### POST `/config/retriever-mode`

设置检索模式（需要 API Key 认证）。

**请求**：
```
POST http://localhost:8001/config/retriever-mode?mode=hybrid
X-API-Key: your-api-key
```

**可选模式**：
- `hybrid`：混合检索（Neo4j + ChromaDB）
- `vector-only`：仅向量检索
- `graph-only`：仅图谱检索（未实现）

**响应** (200 OK)：
```json
{
  "status": "ok",
  "retriever_mode": "hybrid"
}
```

---

#### GET `/health`

健康检查端点，返回服务基本状态。

**请求**：
```
GET http://localhost:8001/health
```

**响应** (200 OK)：
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

#### POST `/ingest`

触发数据摄取，将 `digests/` 目录中的数据导入 Neo4j 和 ChromaDB（需要 API Key 认证）。

**请求**：
```
POST http://localhost:8001/ingest
X-API-Key: your-api-key
```

**响应** (200 OK)：
```json
{
  "status": "ok",
  "dates_ingested": 5
}
```

## 目录结构

```
rag/
├── config.py           # 配置（读取项目 .env）
├── server.py           # FastAPI 服务入口
├── ingest.py           # 数据摄取脚本
├── graphrag/           # Neo4j 知识图谱层
│   ├── driver.py       # 连接管理
│   ├── schema.py       # Schema 定义
│   └── builder.py      # 图谱构建器
├── retriever/          # 检索层
│   ├── vector_store.py # ChromaDB 向量库
│   └── hybrid.py       # 混合检索器
├── agent/              # Agent 层
│   ├── agent.py        # LangGraph ReAct Agent
│   ├── tools.py        # 6 个工具定义
│   └── prompts.py      # 系统提示词
├── web/                # Chat UI
│   └── chat.html       # 对话界面 + 配置页面
└── tests/              # 测试
```

## 与 AI Trend Radar 的关系

本仓库是 [AI-TREND-RADAR](https://github.com/Conradgui/AI-TREND-RADAR) 的**超集**——包含其全部代码，外加 RAG 层。两个仓库的 `src/`（TypeScript 数据管道）代码完全一致。

```
AI-TREND-RADAR（数据管道）          AI-TREND-RADAR-RAG（本项目 = 数据管道 + RAG）
├── 抓取 15+ 数据源                 ├── [同左] 全部数据管道代码
├── 生成日报/周报/月报              ├── Neo4j 知识图谱
├── 输出到 digests/                 ├── ChromaDB 向量搜索
├── GitHub Pages 展示               ├── LangGraph ReAct Agent（6 工具）
└── 评分框架（商业影响/热度/新鲜度）  ├── Chat UI（http://localhost:8001）
                                    └── MCP Worker（Cloudflare）
```

两个项目共享同一份 `.env` 配置和 `digests/` 数据目录。主仓库的 `rag/`、`services/agentdb/`、`mcp/` 是从本仓库引入的实验性代码副本。

## 架构参考：Pinecone Nexus

本项目的整体架构参考了 **Pinecone Nexus** 的"知识引擎"理念——将分散的数据预编译为结构化的知识制品（Knowledge Artifacts），让 Agent 查询时直接获取已组织好的知识，而非每次从原始文档中检索。

当前实现覆盖了 Nexus 架构的前两层（Agentic RAG + 基础知识图谱），后续迭代方向：

| Nexus 层 | 当前状态 | 下一步 |
|----------|---------|--------|
| Agentic RAG | ✅ LangGraph ReAct Agent + 6 工具 | 优化工具选择策略 |
| Pre-runtime Knowledge Compilation | ✅ 每日 ingestion 预构建图谱 | 增量更新 + 去重 |
| Knowledge Artifact Layer | ✅ Topic/Entity/Source/Document 节点 | 增加趋势轨迹制品 |
| Structured Knowledge Query | ⚠️ 基础 Cypher + 语义混合 | 声明式查询模板 |
| Evidence & Governance Layer | ⚠️ 选题有 evidence 字段 | 完整溯源链 |
| Evaluation Feedback Loop | 🔲 未开始 | 评分权重自适应 |

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

**可选配置项**：
- `NEO4J_URI`：Neo4j 连接地址（默认 `bolt://localhost:7687`）
- `NEO4J_PASSWORD`：Neo4j 密码（默认 `password`）
- 搜索 Provider API Key（Brave/Tavily/Exa 等）

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

**docker-compose.yml 示例**：

```yaml
version: '3.8'

services:
  neo4j:
    image: neo4j:5
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      - NEO4J_AUTH=neo4j/password
    volumes:
      - neo4j_data:/data

  rag-server:
    build: .
    ports:
      - "8001:8001"
    env_file:
      - .env
    depends_on:
      - neo4j

volumes:
  neo4j_data:
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

##### 3. HTTPS 配置

```bash
# 安装 Certbot
sudo apt install certbot python3-certbot-nginx

# 获取证书
sudo certbot --nginx -d your-domain.com
```

##### 4. 进程管理（systemd）

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

##### 5. 日志管理

```bash
# 查看实时日志
sudo journalctl -u rag-server -f

# 查看最近日志
sudo journalctl -u rag-server -n 100
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

## License

MIT
