# Stage 3 执行记录：结构化证据与分任务评估

日期：2026-08-12

## 已完成

### 1. 结构化实体证据链

- 新增集中实体身份模块 `rag/entity_identity.py`。
- ingestion 和 lexical metadata 写入稳定 `entity_ids`。
- citation 层透传 `entity_ids`。
- Gateway 优先使用结构化实体过滤；旧索引缺字段时才降级文本匹配。
- 复现并修复了“真正 OpenAI 条目被过滤、正文偶然提及 OpenAI 的噪声反而保留”的失败场景。

### 2. 冻结运行分任务评估

- `offline_evaluation` 继续负责 dataset/run/revision/partial-run 边界验证。
- 非导航任务复用 `eval_retrieval_quality.score_query()`，不再另造指标实现。
- RQ01 缺少独立趋势簇标签时明确标记 `relevance_labels_missing`，不生成伪指标。
- RQ02 literal calibration：
  - correct F1@10 = 0.3333
  - degraded F1@10 = 0.1111
  - wrong F1@10 = 0.0
- 这些数字只证明评估器有辨别力，不代表系统当前真实 F1。

### 3. Claim Verification 三态契约

- Prompt 固定 `supported / contradicted / insufficient`。
- 使用隐藏机器结果，后端解析后从用户正文移除。
- 校验 evidence IDs、理由、缺失判据和 direct refutation。
- `contradicted` 没有直接反证时判定契约无效。
- FastAPI `ChatResponse` 暴露独立 `claim_verification` 字段。

### 4. 回归与真实基线

- 相关核心测试：137 passed。
- 离线评估模块恢复为不依赖 Neo4j/Chroma 的可导入边界。
- 当前线上索引：`gen-20260811T131923-a5eb8484`，3609 chunks，hybrid ready。
- 一条真实 DeepSeek 本地 RAG 请求：总耗时 51.50s；retrieval 37.23s；agent 13.16s；5 citations；未联网。

### 5. 影子迁移与自动发布 Gate

- 影子索引 `shadow-20260812T034248-cc4206ae` 构建完成，但未激活：
  - 目标条目 / 输出向量 / lexical：3663 / 3663 / 3663；
  - ATR 唯一编号覆盖率：100%；
  - 无法映射旧条目：0；
  - 新 embedding：0，全部复用已有向量；
  - entity_id 覆盖率：20.09%，记录为后续质量缺口。
- 启动时自动同步另行发布了正式代 `gen-20260812T033725-59dcafc6`；这不是影子接口越权，而是启动更新任务的既有产品行为。
- 已把完整性规则提升为所有正式发布的共同硬门槛：
  `target_document_count = output_record_count = chunk_count = lexical_count`，且 ATR 覆盖率为 100%；检查发生在 manifest、promote、activate 之前。

### 6. 精确标题导航修复

- 实测 `Apple Is Getting This Wrong` 曾把包含英文原题的中文转载与官方完整标题同标为 `exact_title`，并按 ATR ID 排序，导致转载排第一。
- 根因是 lexical 层没有区分“标准化标题完全相等”与“较长标题包含查询”。
- 修复后：完整相等标题优先，较长包含标题降级为 `title_contains_query`；自然语言“标题 + 讲了什么”仍保留导航路径。
- 新正式代 Gateway 快速结果：
  - 热门趋势：5 条、3 个来源、约 0.89 秒；
  - Apple 原题：官方完整标题第一，约 96ms；
  - OpenAI Economic 原题：唯一命中，约 100ms；
  - AgentSky：唯一命中，约 21ms。

### 7. 回归结果

- Stage 3 相关回归：152 passed。
- 新增发布门槛与导航排序的聚焦回归：52 passed。

### 8. 真实 DeepSeek Stage Gate

独立监管 Agent 先给出 CONDITIONAL PASS，限定最多执行两条真实问题。

1. `最近有什么热门趋势？`
   - 状态：ready；仅内部语料；5 条引用、3 个来源；无联网、无超时；
   - retrieval 1.79s，DeepSeek 生成 32.58s，总计 35.49s；
   - 产品判断：可用且可追踪，但不同条目的原文证据深度不均。
2. `OpenAI 最近有哪些重要动态？`
   - 初测 retrieval 60.31s，总计 75.28s；
   - 5 条引用中 3 条来自 5 月，不符合“最近”的用户预期；
   - 根因：Gateway 在 trace 中构建了近 14 天 metadata filter，但没有把 filter 传给底层检索；属于计划层和执行层接线断裂。

按 Stage Gate 约束停止扩测，先写失败测试再修复。修复后：

- 相关回归：56 passed；Stage 3 全回归更新为 162 passed；
- 已部署容器中的无 LLM 检索结果日期为 2026-08-11、08-07、08-07、08-12、08-02，全部落在 2026-07-30 至 08-12 的近 14 天窗口；
- 检索仍需约 20.96s，是下一阶段性能问题；
- 当前 `date` 表示日报收录日期，不等于原文发布时间，因此“后来收录的旧文章”仍可能进入近期结果。

## 证据边界

- 运行中的容器已经包含 Stage 3 代码，当前正式索引为 `gen-20260812T033725-59dcafc6`。
- 51.50 秒 DeepSeek 请求仍是迁移前基线；尚未产生 Stage 3 迁移后的真实问答结果。
- 12 条集合仍处于 gold candidate / human review pending，不能称为正式 release benchmark。
- 通用热门趋势 RQ01 尚无独立趋势簇标签，无法计算可信 Recall/F1。

## 当前 Stage Gate

最终结论：**CONDITIONAL PASS，可以结束 Stage 3。**

1. 两条真实用户路径均能完成；时间过滤接线缺陷已复现、修复并部署。
2. 真实问答只验证用户路径、路由、引用和时延，不把未人工标注的数据称为 P/R/F1。
3. entity_id 20.09% 覆盖率、检索通道性能、收录日期与原文发布日期混用仍是下一阶段问题，不在本阶段伪装为已解决。
4. 下一阶段唯一最高优先目标：建立 `publication_date / ingested_at / observed_at / report_date` 四类时间语义，先解决“最新动态”的事实时间边界。

## 已知后续问题

- 混合检索单次耗时 37 秒，metadata 迁移不会自动解决，需要单独做通道级性能诊断。
- 实体注册表目前是保守的小集合；应由后续 corpus entity enrichment 扩展，不能无限手写主题别名。
