# 2026-08-21 主线对齐与下一阶段 Gate

## 1. 产品目标

AI Trend Radar RAG 的当前目标不是继续堆叠 RAG 技术模块，而是打通一个可信、可解释、可评估的用户闭环：

```text
用户原问题
  -> 保真理解与有序任务分类
  -> 同一 Route Contract 驱动改写、检索、证据分层和回答合同
  -> Agentic GraphRAG 召回与重排
  -> 结构化 Answer Envelope
  -> 可读 UI + 精确引用 / 跳转
```

产品成功标准是：用户问“最近的重要动态”“某条记录”“如何演变”“这个说法是否成立”时，系统能选择正确任务、召回正确证据、按正确结构回答，并让用户回到具体 Daily Item，而不是只展示技术上合法但产品上不完整的结果。

## 2. 当前已实现事实

以下结论有代码、测试或运行证据支持：

- Canonical Corpus 已转向原子 `Daily Signal Observation`，公开身份使用 `ATR-YYYYMMDD-XXXXXX`。
- 日报、周报、月报的职责已分开；周/月报与渲染后的 Markdown 不作为主向量语料重复入库。
- A–E 五类 Task Route、Route Contract、Prompt Registry、Answer Envelope 等目标模块和正式 ADR 已建立。
- v3 Ordered Query Frame 的 Schema、L2 投影、supporting A、联网权限、澄清状态和 provider-compatible strict tool 已通过离线合同测试。
- v3 三条旧缺陷回归 Canary 为 3/3，但它们只是回归证据，不是泛化证据。
- v3.1 新 20 条 Blind 的 primary route 90%、web permission 100%、clarification 100%、L3 legal/replay 100%，说明架构骨架可以保留。
- 当前 Docker 已清理为单一项目栈；容器停止时只需 `docker compose up -d`，不得重建或删除数据卷。

## 3. 当前未达标事实

v3.1 新 Blind 的产品完整率只有 50%，不能接正式 Agent。主要问题集中在 Query Frame 的细粒度语义合同：

1. `important_news` 被过度升级成 `trend_clusters`；
2. 复合问题丢失明确 supporting delivery；
3. 同一实体跨时间比较被误分为普通 E comparison；
4. timeline 与 longitudinal trend 边界不稳；
5. unresolved reference 会错误清空本来明确的 delivery；
6. protected / delivery / web evidence 的字段职责曾有重复标注冲突。

这些问题发生在检索之前。此时调整 Top-K、reranker、Neo4j、Prompt Registry 或 UI 都不会修复根因。

## 4. 架构判断

保留现有“一个 Route Contract 贯穿输入与输出”的方向，不引入通用 Router 框架替代当前产品语义合同。LangChain / LlamaIndex 等 Router 能执行路由结果，但不会替项目定义 A–E 的用户任务、主辅交付、联网权限和引用约束；现在引入只会增加依赖与调试面。

当前最值得形成深模块的 seam 是：

```text
understand_ordered_query_v3(query, context)
  -> OrderedSemanticFrameV3 + RouteContractV2
```

调用方只需要知道 Query、可选公开上下文与版本化合同；Prompt、Provider Schema、sanitizer、L2 校验和模型适配应留在模块内部。分类通过新 Blind 前，QueryRewritePlan、检索策略和正式 Agent 接入继续保持分离。

## 5. 下一阶段：v3.2 Prompt-only Gate

### 范围

- 只修改 `rag/ordered_frame_client_v3.py` 的语义 Prompt；
- 允许同步修正直接描述该 Prompt 合同的测试与执行记录；
- 不改 Schema、L2、Route Contract、RAG、Prompt Registry、正式 Agent、Web UI、Docker 镜像或索引。

### 决策边界

1. 只有用户明确要求聚类、分组或模式归纳时才使用 `trend_clusters`；普通动态 / 新闻请求保持 `important_news`。
2. 不同 task family 的明确交付必须保留并按原顺序输出。
3. 同一实体跨时间变化属于 C；不同实体 / 产品属性比较属于 E。
4. 有离散里程碑才使用 timeline；连续多年变化使用 longitudinal trend。
5. unresolved reference 与 delivery 正交：对象待澄清不等于动作不明确。
6. delivery、web permission 与 protected span 各自只保存本字段证据，不重复塞入。

### Gate 顺序

1. 离线红灯：当前 Prompt 合同测试必须能够捕获旧行为。
2. 最小绿灯：只修改 Prompt，使目标测试与相关离线回归通过。
3. 代码 / 产品 Gate：确认没有新增关键词词表、确定性猜测或职责泄漏。
4. 经 Gate 允许后，最多运行一次 7 条已解封 DeepSeek 校准；失败即停止。
5. 只有 7 条校准达到既定门槛，才设计新的双重标注 Blind；仍不得直接接生产。

### 7 条校准门槛

- ordered delivery exact >= 6/7；
- primary route = 5/5 resolved cases（2 条 clarification 没有 Route Contract，不能伪造 primary route 分母）；
- web permission = 7/7；
- clarification precision / recall = 100% / 100%；
- 每题一次、零重试；
- 平均延迟 <= 8 秒，最大 <= 12 秒。

## 6. 明确暂停项

在 v3.2 Gate 完成前暂停：

- 全量索引重建或检索参数调优；
- 新 Router / Agent 框架引入；
- UI 视觉重构；
- QueryRewritePlan 与多查询 fan-out；
- 新 Blind、Benchmark 或项目发布宣称；
- 为单个实体增加关键词补丁。

## 8. 2026-08-21 执行状态

- v3.2 Prompt-only 离线相关测试：42/42 通过；
- 质量监管最终裁决：GO，Agent 已关闭；
- 7 条已解封 DeepSeek 校准：7/7 执行、0 error；
- v3.2 路由门槛全部通过；
- L1 protected span F1 为 76.5%，需与 L2 投影分层评估；
- v3.2 新双标注 Blind 已完成：20/20、0 error，但 Gate 未通过；primary route 95%、web 100%、
  clarification recall 75%、protected span F1 71.5%、product complete 20%。
- 本批已永久解封为诊断资产，不得重跑或再次宣称 Blind。
- 下一 Gate：v3.3“LLM 语义任务 + 确定性可观测护栏”6 条可见校准；通过后再设计全新 Blind。
- v3.3 可见校准已完成：独立监管修复评分器跨字段补分后 APPROVE；恢复网络运行 6/6、
  合同级 product complete 100%、平均/最大 1.972/2.836 秒。该结果只证明旧缺陷回归修复，
  下一 Gate 更新为“全新未见 Blind 设计与冻结”，仍不得直接接正式 Agent。
- v3.4 全新双标注 Blind 已完成：15/15 执行、零错误、零重试；Ordered Frame delivery
  15/15，但合同级 product complete 8/15，正式 Gate 失败。独立归因显示主路由架构可保留，
  需要先修 claim/source/time/指代/否定约束公共 seam，并修订跨字段重复与 span 完全匹配的
  评估口径。
- v3.4 不得重跑或追溯改分。下一 Gate 为 v3.5 的 6 条可见 TDD 校准；在 Gate 通过前，
  Query Rewrite、Retrieval/GraphRAG、Prompt Registry、正式 Agent 继续暂停。
- 用户已决定先停止新增语料并调稳现有系统。运行时固定为
  `gen-20260821T074117-404548ad`（2026-08-21，4133 chunks），启动同步默认关闭；后续
  v3.5、检索、重排、Prompt 和端到端 Gate 均使用这份固定语料。详见
  `2026-08-21-frozen-corpus-system-tuning.md`。

## 7. 工作区治理风险

当前分支为 `claude/rag-transformation-checkpoints`，但工作区包含大量跨阶段未提交变更和实验产物。下一次 checkpoint 前必须按“正式运行代码 / 测试 / 决策文档 / 评估证据 / 生成资产”分类审查，不能把所有未跟踪文件一次性提交，也不能在未审查时清理用户已有改动。
