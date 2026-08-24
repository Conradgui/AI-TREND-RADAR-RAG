# 2026-08-24 检索契约、筛选恢复与数据库重连执行记录

## 本阶段边界

冻结语料与正式 Agent 接线保持不变。本阶段只修复三个既定问题：

1. Route Contract v2 到检索 Gateway 的 shadow 接线；
2. 侧边栏时间、来源、分类的一键清除；
3. 已运行服务与 Neo4j 连接中断后的安全重连。

## 模型路由

- 主会话（Sol / Medium）：产品边界、架构决策、补丁整合。
- Terra / High：跨模块事实审计、Stage Gate、质量与方向复核。
- 未启用额外执行 Agent：本轮实现规模小且写集高度耦合，继续拆分会增加上下文与合并成本。

## 已完成

### Route Contract shadow

- Gateway 接收 request-scoped Route Contract；正式 Agent 尚未切换。
- 完整 JSON Schema、跨字段语义和绝对日期范围均在检索前 fail closed。
- A–E 路由 fixtures 使用各自合法 policy ID；未知路由和策略错配不会调用检索适配器。
- Terra 首审 `FIX_FIRST` 后完成修复；绝对日期、shadow 边界继续保持。

### 筛选器

- 时间、来源、分类区域新增“清除筛选”。
- 只清除三项筛选，不清除关键词。
- 索引加载中、加载失败或当前没有筛选时按钮禁用。
- Playwright 明确验证“有关键词时清除筛选仍保留关键词和结果”。

### 数据库恢复

- System 面板在 Neo4j 未连接时显示“重新连接数据库”。
- 后端恢复端点只连接已有 Neo4j，并基于当前最新运行时重建内存 retriever、Agent 与 Gateway。
- 不执行 shell、不控制 Docker、不初始化 Schema、不重建索引、不修改 generation 或数据卷。
- 端点沿用管理 API Key 保护；失败保留最后可用运行时。
- `start.command` 仍是整个 Compose 栈停止后的唯一推荐启动入口：复用镜像和数据卷，不默认重建。

## 验证证据

- Python 定向回归：`84 passed, 33 subtests passed`。
- Playwright 筛选器回归：`2 passed`。
- `git diff --check`：通过。
- Docker 只读状态：app 与 Neo4j 均为 `healthy`；本阶段未重建、未删除容器或数据卷。

## 自动化链路审计

GitHub Actions 仍未达到“抓取后自动编号并进入完整 RAG”的标准。详细证据与 P0 修复顺序见：

- `docs/rag-transformation/evidence/2026-08-24-github-actions-ingestion-id-audit.md`

在该审计 Gate 通过前，继续冻结自动入库。
