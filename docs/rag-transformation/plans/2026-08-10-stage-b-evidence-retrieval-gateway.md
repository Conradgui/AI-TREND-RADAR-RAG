# Stage B：Evidence Retrieval Gateway 与两条优先路径

日期：2026-08-10
状态：Gateway、Chat API/Stream 已接入并通过回归；Web UI 独立验收尚未开始
上位决策：`2026-08-10-rag-architecture-reassessment.md`
前置 Gate：`2026-08-10-stage-a-task-based-evaluation-contract.md`

## 1. 产品目标

把 Agent、后端搜索与后续 Web UI 搜索共同需要的“理解问题 → 选择检索路径 → 返回可审计证据”集中到一个深模块中。本阶段优先解决两个用户可见问题：

1. 用户说“最近有什么热门趋势？”时，不再把这句话当作普通相似度查询；
2. 用户输入一个标题或近似标题时，返回具体条目与稳定跳转位置，而不是日报级结果。

## 2. 已确认的 seam

唯一外部 interface：

```python
retrieve(ResearchRequest) -> EvidenceBundle
```

### ResearchRequest

调用方只需要提供：

- 用户原始问题；
- 当前可用语料日期；
- 返回数量；
- 可选页面上下文。

调用方不需要知道向量、FTS5、Neo4j、RRF、日期过滤或去重规则。

### EvidenceBundle

统一返回：

- `status` 与错误语义；
- `task_family`；
- request analysis；
- 可进入 Evidence Ledger 的 Evidence Records；
- 每条路径的执行 trace；
- 耗时与降级信息。

## 3. 本阶段内部路径

### 3.1 Navigator

适用：标题、部分标题、稳定条目 ID、页面内直达搜索。

实现：

- 优先使用现有 SQLite FTS5 / 标题匹配；
- exact title 命中时切换到 `item_navigation`；
- Evidence Record 必须保留 `occurrence_id`、`content_id`、`local_url` 和原始来源 URL；
- 无 exact title 时降级到 Evidence Search，不伪造导航命中。

### 3.2 Trend Discovery

适用：最近热点、近期趋势、值得关注的方向。

实现：

- 从最近时间窗的 `topic_candidate` 结构化条目读取候选；
- 使用 `content_id` 或规范化标题去重；
- 按候选分数、新鲜度、内容完整度做确定性排序；
- 对单一来源和单一类别做上限约束，避免榜单被一个来源占满；
- 返回的是 Evidence Records；LLM 只负责解释它们为何构成趋势，不负责凭空选条目。

### 3.3 Evidence Search 回退

其他问题继续使用现有 lexical/vector/graph 检索，但从此作为 Gateway 的内部 adapter。Stage B 不改变 embedding，不安装 reranker，不重建图模型。

## 4. 为什么不引入整套外部框架

Haystack、LlamaIndex 的 Router 能编排路径，但不会自动定义本产品的“热点趋势”“条目导航”“事实核验”成功标准。整套迁移会引入第二套文档模型和运行配置，却仍需要我们自己实现上述产品路径。

本阶段只复用现有成熟能力：SQLite FTS5、Chroma、Neo4j 和当前证据账本；把它们放到 Gateway 的内部 adapter 后面。未来可以替换 adapter，而不改变调用方 interface。

## 5. TDD 验证表

1. Navigator tracer bullet → 验证：自然语言中包含完整标题时，第一条 Evidence Record 是目标条目并带 `local_url`。
2. Navigator 降级 → 验证：无精确标题时不会错误标记为 `item_navigation`。
3. Trend tracer bullet → 验证：“最近有什么热门趋势？”不调用通用相似度查询，而从结构化近期候选形成结果。
4. 趋势去重 → 验证：相同 `content_id` 或规范化标题只保留一次。
5. 趋势多样性 → 验证：单一来源不超过 2 条、单一类别不超过 3 条（候选不足时不填充伪结果）。
6. 趋势新鲜度 → 验证：同等分数下较新的 Publication Record 排名更高。
7. 错误语义 → 验证：结构化 adapter 故障与“没有候选”分别返回 `error` / `empty`。
8. 聊天接入 → 验证：chat response 的 `query_understanding` 记录 `task_family` 与 Gateway trace，引用进入同一个 Evidence Ledger。
9. 向后兼容 → 验证：未配置 Gateway 时旧 `retriever` 路径仍能运行。
10. 全量回归 → 验证：`rag/tests` 全部通过，`git diff --check` 通过。

## 6. 明确不做

- 不迁移到 Haystack、LlamaIndex 或 RAGFlow；
- 不换 embedding；
- 不引入 reranker；
- 不改变 Corpus Sync 和 Canonical Producer；
- 不把 Rollup Report 纳入向量化；
- 不在本阶段实现 claim verification 或新 Graph schema；
- 不让 LLM 决定最终候选集合。

## 7. 自审

### 通过项

- interface 小，调用方只需要理解 ResearchRequest 与 EvidenceBundle；
- 复杂度从 Agent、Web UI 与 retriever 调用点收回 Gateway，具备 locality；
- Navigator、Trend Discovery、Evidence Search 是真实变化的多个 adapter/path，seam 不是假抽象；
- 测试通过公开 interface，不依赖内部排序函数；
- 旧检索保留为回退，实施可逆。

### 风险与处理

1. 当前结构化候选中的 `score` 来自上游选题评分，不等于用户相关性。本阶段仅用于 generic trend；focused entity research 仍走 Evidence Search。
2. 标题去重不能处理语义相同但标题完全不同的事件。本阶段先用稳定 `content_id` 与规范化标题；语义聚类需在拥有人工趋势标注后验证。
3. 当前 FTS5 索引可能不存在于旧 generation。Gateway 必须在该 adapter 缺失时显式降级，不能让聊天崩溃。
4. Web UI 前端切换到 Gateway 需要独立 UI Stage；本阶段先建立统一后端 seam 与聊天接入，不在巨型静态 HTML 中同步重构 UI。

### 自审结论

`APPROVE`：Stage B 可以实施。范围集中在统一 seam 和两条高价值路径，不提前锁死 embedding、reranker 或外部框架选择。

## 8. Canary Gate（实施前的小样本验证）

### 目的

在把 Gateway 扩展到 Server、Agent 和 Web UI 前，先确认它在**同一份实际索引快照**上确实改善了两条目标路径，且不会把原有证据变为空。这个 Gate 只检查公开 seam `retrieve(ResearchRequest) -> EvidenceBundle`，不检查私有排序函数。

### 已执行的样本与结果

数据集：`docs/rag-transformation/evals/gateway-canary-2026-08-05.json`
结果：`docs/rag-transformation/evals/gateway-canary-results-2026-08-10.json`

| 路径 | 验证条件 | 结果 |
|---|---|---|
| 泛趋势发现 | 至少 3 条去重 Evidence Records、至少 2 个来源、单一来源不超过 2 条 | 通过 |
| Apple 精确标题 | Top-1 为目标条目且带 `local_url` | 通过 |
| OpenAI Economic Research Exchange 精确标题 | Top-1 为目标条目且带 `local_url` | 通过 |
| AgentSky 精确标题 | Top-1 为目标条目且带 `local_url` | 通过 |
| 宽泛 OpenAI 近期动态 | Gateway 不得把原有非空证据退化为空 | 通过 |

快照一致性也已验证：向量库 6,098 个文档、词条索引 3,287 个条目，二者最新语料日期均为 `2026-08-05`。Gate 结果为 `5/5 passed`。

### Canary 暴露并已修复的问题

“Introducing The Openai Economic Research Exchange”含有实体名，查询理解曾把它归为宽泛趋势发现，从而绕过了精确标题导航。修复后，generic trend 仍优先走聚合路径；只要结构化索引给出 `exact_title`，明确标题就优先进入 Navigator。

### 证据边界

Canary **不能**证明 Precision、Recall、F1 或最终回答质量；它也没有测试 Neo4j、联网搜索、DeepSeek 和 Web UI。它只证明：本阶段的 Gateway 改动没有破坏这 5 条代表性用户路径，可以安全进入下一步的有限集成。

## 9. 有限 Server 接入 Gate

本次只做后端请求边界接入：`RagState` 持有与当前 retriever 同生命周期的 Gateway，普通 `/chat` 与流式 `/chat/stream` 都把它传给编排层。索引 generation 发布或检索模式切换时，也同时重建 Gateway，避免它继续引用旧 retriever。

验证：

1. `/chat`、`/chat/stream` 的 HTTP contract 测试确认 Gateway 会被传入；
2. Gateway 耗时不会被后续编排的局部计时错误覆盖；
3. 重新运行同一 `2026-08-05` Canary：`5/5 passed`；
4. 全量回归：`424 passed in 9.11s`；
5. `git diff --check` 通过。

这不等于 Web UI 已完成。UI 仍需要以“泛趋势回答能显示趋势 Evidence Records”和“精确标题可以直达条目”为单独的浏览器验收路径。
