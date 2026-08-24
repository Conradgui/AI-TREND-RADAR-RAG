# Stage 2：Observation 查询视图与产品流程执行记录

日期：2026-08-11
状态：Stage Gate `CONDITIONAL PASS`

## 本阶段目标

在不回退 ATR 原子条目和 Observation 图谱模型的前提下，打通三类用户价值路径：

1. 侧边栏可按时间、来源、分类筛选，并从匹配结果直达具体 ATR 条目；
2. 时间线、关系探索、事实核验使用各自的检索约束和回答契约；
3. UI 与 Agent 引用显示同一条目的稳定身份、可读文本和本地跳转地址。

## 失败测试先行

- `rag/tests/test_retrieval_gateway.py`
  - 时间线任务必须要求图通道，并只保留目标实体相关结果；
  - 关系任务必须要求图通道；
  - 事实核验不能把“单次亏损”自动判为“商业成功被反驳”。
- `rag/tests/test_hybrid_retriever.py`
  - 图检索必须遍历 `Entity -> Observation -> Topic/DailyDigest`；
  - 引用身份必须是 ATR，且带具体条目 `local_url`。
- `src/__tests__/search-document.test.ts`、`rag/tests/test_ingest.py`
  - 标题、摘要及推荐内容中的 HTML entity 必须被解码后再展示。
- `rag/tests/test_dashboard_readability.py`
  - 时间、来源、分类筛选器必须初始化并触发条目级搜索。

## 实现摘要

- `rag/retrieval_gateway.py`：按任务族设置图通道要求；对实体任务进行聚焦过滤；记录过滤前后数量。
- `rag/query_understanding.py`：补充 Apple/苹果实体识别，避免把具体实体问题退化为泛检索。
- `rag/retriever/hybrid.py`：图检索切换到 Observation 级证据，返回 ATR 身份与本地跳转地址。
- `rag/prompt_registry.py`：收紧 claim verification 契约；没有直接否定证据时返回“证据不足”。
- `src/search-document.ts`、`rag/ingest.py`：在规范化边界统一解码用户可见字段，不改变原始证据身份。
- `index.html`：修复时间、来源、分类筛选初始化及筛选触发；搜索结果保持条目级直达。

## 自动化验证

- Python `unittest`：32 条相关测试通过。
- Pytest：Prompt Registry 与 Dashboard 可读性 10 条测试通过。
- Vitest：搜索文档 12 条、manifest 15 条测试通过。
- TypeScript：`tsc --noEmit` 通过。

## 真实环境验证

### Neo4j

真实图查询能返回 `Observation.id = ATR-*`、日期和具体 `localUrl`，证明图谱证据不再只能回到日报首页。

### DeepSeek

- 时间线问题：从 6 条夹杂 Android/Angular 的引用，收敛为 4 条 OpenAI/Apple 相关引用。
- 事实核验：从“亏损即 contradicted”的错误结论，修正为 `insufficient`，并明确单一负面信号不足以否定宽泛商业成功命题。
- 实测总耗时约 26–30 秒，仍是下一阶段的体验债务。

### 浏览器

- 时间、来源、分类下拉已有真实选项；独立筛选实测分别为近 7 天 208 条、OpenAI 72 条、模型与技术突破 239 条；
- 模糊检索 `Claude mathematical` 返回 3 条；
- 点击结果直达 `/item/ATR-20260811-604C0F`；
- 条目标题、摘要、推荐选题和推荐理由均未残留 `&#x27;`；
- Agent 询问 `ATR-20260811-604C0F 是什么？` 成功返回条目证据且未超时。

## 当前风险与边界

1. 容器启动后的图谱维护会同时占用 app 与 Neo4j 的高 CPU；维护期间页面和健康接口可能超时。容器没有重启或丢失数据，但该行为影响首次使用，需由 Stage Gate 判断是否为发布阻断项。
2. Neo4j 对部分多节点 `MATCH` 报笛卡尔积性能提示；当前身份字段均有唯一约束，未发现结果错误，但写入效率需要后续收敛。
3. 少量上游条目本身缺摘要，属于采集/规范化质量问题，不应由 UI 伪造摘要。
4. 本阶段只证明任务路由与产品主路径改善，不代表全量 Recall/Precision/F1 已达到发布门槛。

## P0 运行隔离修复与复验

独立质量监管首次检查时，后台一日更新使 app/Neo4j 同时高负载，页面与健康接口超时，因此 Stage Gate 初判为 FAIL。针对该阻断项完成了以下最小修复：

- `/health` 改为轻量 readiness probe；跨库校验只保留在 `/health/consistency`；
- 多日期图谱更新不再每个日期刷新一次全局 Topic rollup，而是在整批完成后刷新一次；
- 多节点关系写入改为顺序 `MATCH`，消除 Neo4j 笛卡尔积提示；
- Docker 默认限制嵌入线程和 app/Neo4j CPU 配额，避免后台维护抢占全部本机资源。

TDD 结果：

- 新增健康探针、批次 rollup、非笛卡尔关系和 Compose 资源边界测试；
- 首轮按预期 4 项失败；
- 实现后相关 49 条 pytest 通过。

真实运行复验：

- 服务启动后 `/health` 首次成功响应约 `0.40s`；
- `graph_maintenance` 高峰期 `/health` 响应约 `0.16s`；
- 高峰期 app CPU 约 `28%`、Neo4j 约 `107%`，不再同时占满 3–5 个核心；
- 维护期间运行时降级为 `vector-only`，真实 DeepSeek ATR 问答仍成功，总耗时约 `16.4s`；
- 维护结束后自动回到 `hybrid / ready`；最新图谱日期为 `2026-08-11`，一日增量状态为 `updated`。

结论：后台更新仍有优化空间，但已不再阻断首页、健康检查和现有 Agent 主路径，原 P0 发布阻断条件已解除。

## 独立质量监管结论

修复后由同一只读质量监管 Agent 复审：

- Gate：`CONDITIONAL PASS`；
- P0：无；
- 产品流程：8.5/10；
- 架构方向：8.7/10；
- 测试证据：8.0/10。

Gate 关闭前又完成两项机械收尾：

- 修复最后一处 `Document -> DailyDigest` 的笛卡尔 `MATCH`；
- 重新生成 `manifest.json`、`feed.xml`、`digests/search-index.json` 与 `corpus-manifest.json`。

最终发布包及运行隔离相关测试：17/17 通过。

`CONDITIONAL` 的边界是：一次真实增量更新已证明主流程可用，但连续多日运行、故障恢复、任务族 Recall/Precision/F1 与浏览器自动化 E2E 仍需下一阶段提供长期证据。

## Gate 判定要求

只有同时满足以下条件才进入下一阶段：

- 产品路径可操作，而非只通过单元测试；
- Observation/ATR 身份贯穿图谱、引用和 UI；
- 时间线与事实核验没有已知的方向性错误；
- 后台维护对前台可用性的影响有明确分级和后续动作。
