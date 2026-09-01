# Stage 5：真实运行时 Canary 验收记录

- 日期：2026-08-25
- 状态：Gate 通过（独立质量监管阻断已修复）
- 范围：冻结索引上的 A–E 真实 DeepSeek 验收；未重建 Neo4j、ChromaDB 或语料索引

## 基础设施边界

- Canary 前重建一次 `app` 容器；质量监管发现两个合同阻断后，为使运行环境包含修复，追加一次纠偏重建；
- 最终运行镜像：`sha256:9245bff47f5d7f6270045547635b5184bc71eae07e3e20df3baa41df6abbb82e`；
- `neo4j` 容器保持原实例和数据卷，未重建；
- 活跃索引世代：`gen-20260821T074117-404548ad`；
- ChromaDB：`4133` chunks；
- Neo4j 主动运行时探测：`ready`；
- 最新语料日期：`2026-08-21`，语料模式：`frozen`。

## A–E Canary 结果

| 路线 | 真实问题 | 结果 | 检索 | 生成 | 总耗时 | 模型轮次 | 引用/合同 |
|---|---|---:|---:|---:|---:|---:|---|
| A 精确导航 | `打开 ATR-20260805-99E550` | 通过 | 0.607s | 0s | 0.774s | 0 | 精确 ID 与站内链接有效 |
| B 趋势发现 | `最近有什么热门趋势？` | 通过 | 1.830s | 7.710s | 9.739s | 1 | 6 条引用，Envelope 有效 |
| C 时序/关系 | `OpenAI 和 Anthropic 最近的竞争关系发生了什么变化？` | 通过 | 10.768s | 4.892s | 15.700s | 1 | 2 个实体 + 1 个关系证据，明确不把共现写成因果 |
| D 主张核验 | `OpenAI 是否已经发布 GPT-6？` | 通过 | 2.455s | 2.614s | 5.077s | 1 | `verdict=insufficient`，4 条引用，结构合同有效 |
| E 证据研究 | `用内部证据解释 Graph RAG 和 Agentic RAG 的区别` | 通过（证据不足） | 2.541s | 3.001s | 5.565s | 1 | 未编造定义，按证据不足收口 |

补充零模型验证：`OpenAI 最近有哪些重要动态？` 走结构化重要新闻路径，0.312 秒完成、10 条引用、0 次模型调用。

## 汇总指标

- 成功样本数：5；
- P50：5.565 秒；
- P95：14.507 秒（5 个小样本按线性插值计算，仅作 Canary 指示，不作为稳定 SLA）；
- 最大值：15.700 秒；
- 总模型轮次：4；每条生成型路线均为 1 次，A 路线为 0 次；
- 第二次格式修复调用：0；
- 最终引用完整性：5/5 通过或按证据不足安全收口。

## Gate 中发现并修复的问题

1. DeepSeek Direct Composer 未显式关闭 thinking，导致 B 路线在 20 秒生成预算内超时；已关闭 thinking，并把默认最大输出限制为 1200 tokens。
2. Graph 多实体与关系查询串行执行，C 路线检索曾达到 35.97 秒；已改为有界并发，热态检索降至 10.77 秒。
3. C 路线冷态检索 17.62 秒超过原 15 秒预算；在总预算不变的前提下，将检索/生成预算由 15/45 调整为 20/40 秒。
4. Provider 在合法 JSON 中双重转义 Markdown 换行；已在展示层规范化，不改变事实或证据编号。
5. D 路线旧隐藏 HTML 注释合同与新“仅一个 JSON Envelope”合同互斥，导致 `claim_result_missing`；已把机器 verdict 合并进 Envelope 顶层 `claim_verification`，真实复测通过。

## 未被本 Gate 掩盖的质量债务

- E 路线召回内容不足以支持概念对比，并暴露旧语料日期/相关性质量问题；当前正确行为是拒绝编造，但检索质量仍需独立评估与优化。
- 零模型重要新闻回答仍存在原始摘录重复、模板感强的问题；性能通过不等于产品表达质量通过。
- 启动时间受 Python 冷导入与幂等 Schema 检查影响，部分历史启动曾达到数分钟；本次新容器约 12 秒健康，但仍需单独建立冷启动基线，不能从单次结果断言问题已消失。
- 本次仅 5 条 Canary，不能替代固定评估集上的 Recall、Precision、F1 和答案质量评估。

## 自动化验证证据

```text
相关回归：77 passed, 3 subtests passed in 1.80s
全量回归（Canary 前）：864 passed, 36 subtests passed in 5.47s
全量回归（质量监管阻断修复后）：866 passed, 36 subtests passed in 7.17s
git diff --check: PASS
新 app 容器：healthy
Neo4j：healthy / graph readiness ready
索引：ready / 未重建
```

逐请求去敏 Trace 摘要已固化为
`docs/rag-transformation/evidence/2026-08-25-stage-5-canary-trace-summary.json`，
SHA-256 为 `681fdf82675200e7a91a81e715553e08a40b1009c1488c3891e4df2aba006da6`。

## 独立质量监管复核

Terra 首轮结论为 `CONDITIONAL PASS`，提出三个阻断：路线总预算未端到端约束、
`contradicted` verdict 可不绑定机器证据、Canary 缺少持久化 Trace。已分别完成：

1. 生成超时会扣除路由与检索已经消耗的时间，新增“检索 + 生成不得突破路线总预算”回归；
2. `contradicted` 现在必须同时满足 `direct_refutation=true` 且绑定至少一个合法证据编号；
3. 增加去敏 Canary Trace 摘要及 SHA-256 校验文件。

纠偏部署后 `app` 与原 `neo4j` 容器均为 healthy，Graph readiness 为 ready；
随后仅执行 `docker builder prune -f`，回收 48.15 MB 构建缓存。未删除镜像、容器、卷或索引。

## Gate 结论

Stage 5 的后端编排目标已达到：常见路线不再经过无界 Agent 循环，A–E 都有确定路线与预算，生成型路线至多一次模型调用，Graph 路线主动验证数据库，回答合同和引用可机器校验。该结论只证明“编排与运行时闭环”，不代表检索质量、语料质量、前端体验或 GitHub Actions 已全部达到发布标准。
