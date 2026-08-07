<div align="center">

# 📡 AI Trend Radar RAG

**把公开 AI 趋势日报变成可追问、可核验的本地研究驾驶舱。**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Docker Compose](https://img.shields.io/badge/Deploy-Docker%20Compose-2496ED.svg)](https://docs.docker.com/compose/)
[![Python](https://img.shields.io/badge/Runtime-Python%203.12-3776AB.svg)](Dockerfile)

[3 分钟开始](#3-分钟开始) · [产品能力](#它解决什么问题) · [部署说明](docs/deployment.zh.md) · [配置说明](docs/configuration-rag.zh.md) · [排错](docs/troubleshooting-rag.zh.md) · [贡献](CONTRIBUTING.md)

</div>

---

## 它解决什么问题

AI Trend Radar 每天会产出公开的 AI 趋势报告，但“读很多日报”不等于“能快速形成有依据的判断”。本项目只消费上游公开报告：它把报告同步到本地，建立向量与图谱索引，并让 Agent 在当前请求的**证据账本**范围内回答问题、展示可点击引用。

它适合需要持续追踪 AI 产品、模型、研究与行业变化的人：先浏览日报，再问“近三天哪些趋势值得深挖”“OpenAI 的产品动向有哪些证据”“哪些信号来自联网搜索”。

| 能力 | 用户得到什么 |
| --- | --- |
| 本地研究驾驶舱 | 按日浏览报告；长表格可横向滚动、调整阅读密度、展开摘要 |
| Graph + Vector RAG | 从文本相似度与实体/时间关系两条路径找证据 |
| 证据型 Agent | 回答绑定本次检索到的证据记录，而非把“相关链接”混作结论依据 |
| 可控联网搜索 | 默认内部语料优先；开启后只在时效性或证据不足时补充外部来源，并标记外部内容 |
| 增量同步 | 每次容器启动检查上游变化，只重新索引新增或变更的日报；失败时继续使用最后成功索引 |

### 与上游项目的边界

[`AI-TREND-RADAR`](https://github.com/Conradgui/AI-TREND-RADAR) 是内容生产者：采集、评分、生成日报、通过 GitHub Actions 发布。本仓库是内容消费者：单向同步公开报告、建立本地索引、提供检索与问答。

两者不共享本地目录、数据库或密钥。本仓库不会回写、修改或替代上游的日报生产流程。

## 3 分钟开始

### 开始前只需要两样东西

1. [Docker Desktop](https://www.docker.com/products/docker-desktop/) 已安装并正在运行。
2. 一个模型 Provider 的 API Key（DeepSeek、Anthropic 或 OpenAI，推荐 DeepSeek）。

不需要预装 Python、Node.js、Neo4j 或 pnpm。

### 第一次使用

```bash
git clone https://github.com/Conradgui/AI-TREND-RADAR-RAG.git
cd AI-TREND-RADAR-RAG
```

然后双击配置向导：

| 系统 | 打开方式 |
| --- | --- |
| macOS / Linux | 双击 `setup.command`；若系统阻止执行，在终端运行一次 `chmod +x setup.command && ./setup.command` |
| Windows | 双击 `setup.bat` |

向导只会询问 Provider 和 API Key，自动生成本地 Neo4j 密码并写到 `.env`。`.env` 已被 Git 忽略，绝不应提交。首次运行会下载 Docker 镜像、安装容器内依赖并预热检索模型；这些准备完成后页面会打开。

完成后打开 [http://127.0.0.1:8001](http://127.0.0.1:8001)。首次语料索引会在后台继续：**仓库已附带的最新日报优先可检索，历史报告随后补齐**；之后才检查上游是否有更新。即使上游暂时不可达，System 面板也会显示“上游同步失败（本地语料可用）”，Agent 仍只基于已建立的证据回答。以后只需双击 `start.command` 或 `start.bat`。

> 一键启动的真实边界：Docker Desktop 和你自己的 Provider Key 无法被项目替你安装或提供；除此之外的 Python、依赖与数据库都在 Docker 容器中处理。

## 第一次体验建议

1. 在左侧输入 `Open AI`（带空格也可以），搜索会聚焦包含 `OpenAI` 的报告日期。
2. 拖动侧栏右边缘，或点页头的 `NAV` 收起导航，让报告表格获得更多空间。
3. 用“表格阅读密度”滑条切换紧凑、标准、舒展；摘要默认收束，点“展开摘要”查看全文。
4. 点击醒目的 `AGENT`，先问“最近三天有哪些值得关注的 AI 产品趋势？”。
5. 在 Agent 输入框上方选择“自动 / 关闭 / 开启”联网搜索策略。外部内容会和内部语料分组标记，不会伪装成日报证据。

## 本地运维

```bash
# 查看服务与启动过程（含同步/索引日志）
docker compose logs -f app

# 暂停服务，数据仍会保留
docker compose stop

# 再次启动
docker compose up -d

# 校验 Compose 配置语法（不输出密钥）
docker compose config --quiet
```

不要把 `docker compose down -v` 当作普通停止命令：它会删除本项目的 Neo4j 与 RAG 本地数据卷。需要彻底重建索引时，请先阅读[部署与数据迁移说明](docs/deployment.zh.md)。

## GitHub 自动化的发布边界

仓库包含 `RAG Corpus Sync`：它每天从上游公开站点拉取新日报，并把可审计的语料变化提交回本仓库。GitHub 的定时工作流只在仓库**默认分支**稳定运行；当前 GitHub Pages 工作流也固定发布默认分支。

这意味着功能分支上的工作流文件可以被手动触发来验证，但不会替代默认分支的长期自动化。推荐顺序是：功能分支完成测试与干净克隆验收 → 代码审查 → 合并到默认分支 → 每日同步与 Pages 发布生效。

## 配置层级

首次向导只处理“能聊天”的最小配置。其他能力按需开启，不会打扰第一次使用：

| 层级 | 何时需要 | 入口 |
| --- | --- | --- |
| 必需 | 第一次启动 | Provider + API Key（`setup.command` / `setup.bat`） |
| 可选 | 希望 Agent 查找最新外部资料 | `.env` 中配置任意一个搜索 Provider key，然后在页面开启联网搜索 |
| 高级 | 需要把 API 暴露给其他客户端 | `RAG_API_KEY` 与反向代理；本地浏览器仪表盘默认不保存该密钥 |

完整变量含义、Provider 切换与安全边界见[配置说明](docs/configuration-rag.zh.md)。

## 架构概览

```mermaid
flowchart LR
  UPSTREAM["AI-TREND-RADAR\n公开日报"] -->|"单向同步"| CORPUS["本地语料"]
  CORPUS --> VECTOR[("ChromaDB\n语义检索")]
  CORPUS --> GRAPH[("Neo4j\n实体/时间关系")]
  VECTOR --> RAG["混合检索与证据账本"]
  GRAPH --> RAG
  RAG --> AGENT["AI Agent"]
  WEB["可选权威外部来源"] -."按需补充".-> AGENT
  AGENT --> UI["本地 Web 驾驶舱\n:8001"]
```

“证据账本”是一次提问实际取到、可以支撑当前答案的证据集合。Agent 不应拿账本外的内容伪装成引用；更完整的术语约定见 [`CONTEXT.md`](CONTEXT.md)。

## 文档地图

| 我想做什么 | 阅读 |
| --- | --- |
| 首次部署、迁移旧 Docker 数据、重建索引 | [部署说明](docs/deployment.zh.md) |
| 切换 Provider、开启联网搜索、保护密钥 | [配置说明](docs/configuration-rag.zh.md) |
| 解决启动、页面、Agent、数据库问题 | [故障排除](docs/troubleshooting-rag.zh.md) |
| 参与开发或跑测试 | [贡献指南](CONTRIBUTING.md) |
| 了解安全边界与漏洞报告 | [安全说明](SECURITY.md) |
| 准备发布版本 | [发布检查清单](docs/release-checklist.zh.md) |
| 维护上游日报生产流水线 | 上游的 [`docs/`](https://github.com/Conradgui/AI-TREND-RADAR/tree/main/docs)（不是本地 RAG 的运行前置） |

## 开发与测试

Docker 是普通用户默认路径。只有参与开发时才需要本地 Python 环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r rag/requirements.txt
pytest rag/tests -q
```

对 UI 或发布包的改动，至少运行：

```bash
pytest rag/tests/test_release_package.py rag/tests/test_dashboard_readability.py rag/tests/test_dashboard_same_origin.py -q
docker compose config
```

## 贡献、安全与许可证

欢迎贡献。提交前请阅读[贡献指南](CONTRIBUTING.md)、[行为准则](CODE_OF_CONDUCT.md)与[安全说明](SECURITY.md)。

本项目使用 [MIT License](LICENSE)。
