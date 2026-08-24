# Stage 3：RAG 稳定性与质量执行记录

日期：2026-08-10
分支：`claude/rag-transformation-checkpoints`
计划：`docs/rag-transformation/plans/2026-08-10-stage-3-rag-stability-and-quality.md`
当前状态：3A 实施完成，等待独立 Gate Review；3B 尚未开始

## 1. 本轮实施范围

### 3A-0：评估合同

- 新建 Silver v2 overlay：`docs/rag-transformation/evals/retrieval-quality-dataset-2026-08-10-silver-v2.json`。
- v1 保持不变；v2 明确 `needs_human_review=true`，未冒充 Gold。
- 每题可使用独立 `metric_cutoff` 与 `time_policy`，并自动计算 Precision/Recall/F1 理论上限。
- 评估器支持 `vector-only` 与 `hybrid` 两种模式，并记录 QueryPlan、通道状态、目标快照和运行模式。

### 3A-1：结构化错误与图要求

- vector/graph 通道返回 `success / empty / error / timeout`，不再把异常吞成空结果。
- optional graph 故障为 `degraded`；required graph 故障固定为：
  - `status="partial_error"`
  - `error_code="required_graph_unavailable"`
- required graph 故障时保留有限文本线索，但在进入 LLM 前阻止跨日关系/趋势强结论。
- consistency 后端故障 fail-closed，不再让两个空集合得到假绿色。

### 3A-2：单写者与 generation snapshot

- Docker entrypoint 不再并行启动第二个 `rag.corpus_update` 进程；Server 是唯一更新协调者。
- 新增 verified generation manifest、原子 active pointer、previous 回退和失败 staging 记录。
- 新索引在 staging 完整构建；成功后一次性重建 VectorStore、Retriever 与 Agent。
- 新请求先切到 vector-only；旧 generation 请求通过 lease 排空后，才开始 Neo4j 图更新。
- Neo4j 按日期使用一个事务，失败时不恢复 Hybrid。
- `/ingest` 与启动自动更新共用 `IndexBuildCoordinator`；索引维护期间禁止切换检索模式。
- Chroma client 在 staging 完成、旧 generation 排空与服务关闭时显式 `close()`。

## 2. 方向性质量基线

文件：`docs/rag-transformation/evals/retrieval-quality-vector-only-directional-2026-08-10.json`

限制：本地 Chroma 最新约 2026-08-05，Silver v2 目标快照为 2026-08-10，因此只用于诊断，不能作为最终发布分数。

| 指标 | 当前方向性结果 |
|---|---:|
| 查询数 | 32 |
| 正例 / hard negative | 11 / 21 |
| Query success accuracy | 9.38% |
| Correct rejection rate | 0% |
| Macro P / R / F1 | 12.73% / 8.03% / 9.54% |
| Micro P / R / F1 | 6.58% / 8.47% / 7.41% |

诊断结论：

1. exact title RQ07 可 Hit@1，但 RQ08/RQ09 失败，支持增加 exact/lexical 通道，而不是先换大 embedding。
2. 宽泛题大量召回 `ai-topic-radar` 报告块，说明候选类型、融合和多样性合同需要修复。
3. hard negative 全部返回最近邻，说明当前没有置信度拒答，不等于 21 题都存在真实证据。
4. 固定公司泛词扩展、旧全局 source cap 和 Hybrid 分数量纲仍属于 3B 工作，不在 3A 声称解决。

## 3. Chroma 真实压力验证

正式证据：`docs/rag-transformation/evals/snapshot-stability-2026-08-10.json`

### 首次运行暴露的问题

- 未调用 Chroma `Client.close()`；测试成功切换至 `gen-097` 后资源滞留。
- 该运行没有伪报完成，也没有写成正式通过证据。
- 根因定位到 Chroma 1.5.9 `SharedSystemClient` 对每个 persist path 保留 System；仅丢弃 Python 包装对象不足以释放。

### 修复后正式运行

| 项目 | 结果 |
|---|---|
| 循环 | 100 / 100 |
| `Error finding id` | 0 |
| 总耗时 | 47.485 秒 |
| Python | 3.12.13 |
| Chroma | 1.5.9 |
| 平台 | macOS 15.5 arm64 |
| Embedding | `chroma-default` |
| 数据路径 | 临时隔离目录，不触碰正式索引 |

## 4. 测试证据

- 评估、错误语义、generation、租约、Server、图事务定向测试：全部通过。
- 3A 完整改动后的全仓测试：`389 passed in 3.94s`，`git diff --check` 通过。
- 修复 Chroma close 后定向测试：`38 passed in 3.83s`。
- graph-required 与聊天阻断测试：`49 passed in 0.15s`。

## 5. 尚未完成与证据边界

1. Docker daemon 在本阶段开始时不可用，因此还没有最新真实 Docker + Neo4j Hybrid 热更新证据。
2. Silver v2 仍需 Conrad/独立人工审阅，未升级 Gold。
3. 3B 的 lexical/exact、Query Planning、真实 RRF、intent-aware diversity、embedding bake-off 与拒答校准尚未执行。
4. 方向性 vector-only 低分是待修复基线，不是发布通过证明。
5. 首次卡住的临时压力测试进程曾因执行额度限制无法由工具终止；它只访问系统临时目录，不访问 Docker 或正式索引。

## 6. Gate 3A

当前等待独立质量监管 Agent 复审。只有 P0=0、P1=0 才进入 3B；若发现阻塞问题，先写回本记录并修复、复测。
