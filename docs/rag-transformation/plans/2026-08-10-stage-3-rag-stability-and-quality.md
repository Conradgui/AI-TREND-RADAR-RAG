# Stage 3：RAG 稳定性、检索合同与质量提升计划

日期：2026-08-10
状态：独立监管 APPROVE（P0=0、P1=0），进入 3A 实施
分支：`claude/rag-transformation-checkpoints`

## 1. 目标与证据边界

本阶段不把“回答看起来流畅”当作 RAG 质量，而要解决三类已经有代码和运行证据的问题：

1. **稳定性**：Chroma/Neo4j 异常会被吞成空列表；Docker 正常启动会让 updater 与 Server 两个进程同时读写同一嵌入式 Chroma；删除后再添加会破坏 last-known-good。
2. **检索合同**：图通道绕过 metadata filter，名义 RRF 没有成为最终排序分，固定查询扩展会污染精确语义，中文空格分词会把词法分打成 0。
3. **评估可信度**：现有 12 题银标证明系统质量差，但部分“最近”标签落在 14 天过滤窗外，固定 source cap 又让若干 Recall 目标数学上不可达，因此不能直接拿它做发布 Gate。

冻结证据：

- 2026-08-07 Hybrid 银标：Macro P@10 11.82%、R@10 37.63%、F1@10 15.35%、MRR 40.69%、正确拒答率 0%。
- 当前本地 vector-only：6,098 chunks，最新索引约 2026-08-05；仓库公开语料已到 2026-08-10，不能把两者冒充同一快照。
- Docker daemon 当前未运行，不能声称完成了最新真实 Hybrid/热更新验证。
- Stage 2 Search Document 已提供稳定 `content_id`、`occurrence_id`、`local_url`，但现有 RAG ingestion 仍用数组 index 生成 citation ID。

## 2. 产品与架构决策

### 2.1 单写者与 generation snapshot

短期不新增独立 Chroma Server，也不继续容忍两个进程直接打开同一持久化目录。Server 成为本地索引唯一协调者；新向量 generation 在独立 staging 目录全量构建、校验后，连同 retriever 与 Agent 一次性发布。构建失败时丢弃 staging，旧 generation 继续服务；这样牺牲少量构建时间和磁盘空间，换取“不再靠重启恢复”的用户体验。

Neo4j 不做完整 generation 主键迁移，而采用明确状态机：vector staging 验证后先发布新的 vector-only snapshot，阻止新请求进入旧 Hybrid；等待旧 Hybrid lease 排空后，再按单日期事务更新图；全部成功并验证后才发布新 Hybrid。图更新失败则保持 vector-only，标记 graph unavailable，绝不让部分更新图重新进入回答路径。这个方案比完整图版本系统简单，但真正隔离了在途请求和半成品图。

### 2.2 三个检索子系统，按意图启用

- lexical：内部先做标准化标题/稳定 ID exact，再用 SQLite FTS5 `trigram`；1–2 个汉字使用确定性 substring/bigram 降级；
- vector：Chroma 多语言语义召回；
- graph：只有关系、趋势关联或明确实体扩展问题才启用，不参与所有普通问题。

每个通道先独立取 Top N，再用同量纲 RRF 融合；来源质量、业务 score、新鲜度只能作为有限、可解释的 intent-aware boost，禁止直接把 0–1 向量分与 50–98 图业务分相乘。

### 2.3 Search Document 是条目身份源

`digests/search-index.json` 成为 topic candidate 的 parent identity 与 citation local URL 来源。RAG chunk 保留 `content_id`、`occurrence_id`、`local_url`、canonical URL 与来源族；日报正文 chunk 仍独立存在，但周报/月报继续只供浏览、不向量化。

### 2.4 银标 v2，不伪造 Gold

先把 12 题修成时间合同一致的 silver v2，并增加 20–30 道 hard negative/近似虚构题；所有标签保留依据与 reviewer 状态。只有 Conrad 或独立人工审阅确认后才升级为 gold v1。算法实验不能通过删除失败题、放宽标签或扩大 `top_k` 来“刷分”。

## 3. 执行顺序与验证表

### 3A-0A：冻结与修复评估标签合同（先于算法）

| 实施 | 验证 |
|---|---|
| 冻结旧 v1，不覆盖原始 JSON | v1 checksum 和指标保持不变 |
| 新建 silver v2，区分 `strict_recent`、`current_relevance`、`exact_title`、`event_cluster`、`unanswerable` | 每题的 time policy 与相关集日期一致；人工审阅状态显式 |
| 对每类问题自动计算 Hit/Precision/Recall/F1 的理论上限 | Gate 不超过可达上限；精确标题题不再被固定 P@10 错误惩罚 |
| 支持 vector-only 与 hybrid 两种运行模式 | Docker 不可用时只输出 vector-only，不伪装 Hybrid |

### 3A-0B：建立可扩展评估 envelope

首版只记录已经存在的 corpus revision、index generation、embedding id、完整 QueryPlan 与通道状态。exact/lexical/RRF/boost 在对应生产通道实现时再加入候选和分数组件，避免提前设计不存在的数据结构。

### 3A-1：结构化错误语义

1. 建立通道级 `success / empty / error / timeout` outcome。
2. graph optional 失败且文本通道成功时为 `degraded`，可以回答文本证据支持的部分；graph required 失败时请求目标未完成，机器状态固定为 `status="partial_error"`、`error_code="required_graph_unavailable"`。此时可以附带文本线索，但必须阻止关系、跨日聚合和趋势强结论；vector/lexical 成功不能把 required graph 故障降格为普通成功。
3. consistency 后端查询失败必须为 `unavailable/error`，禁止两个空集合得到“consistent=true”。
4. 错误只向用户返回可行动摘要，内部 error code 与 generation 写日志/metrics。

验证：

- `test_vector_failure_is_error_not_empty`
- `test_graph_failure_is_degraded_not_empty`
- `test_all_channels_fail_is_error`
- `test_required_graph_failure_returns_partial_error_and_blocks_relational_claims`
- `test_consistency_backend_failure_is_not_consistent`

### 3A-2：单写者、staging 与完整 runtime snapshot

1. Docker entrypoint 不再后台启动第二个直接写 Chroma 的进程。
2. Server 内 `IngestionCoordinator` 串行协调更新；active vector generation 只读，staging 使用独立目录。
3. staging 全量构建并校验 count/date/fingerprint；失败不改 active pointer。
4. 成功后同时构建新的 vector store、retriever 和 Agent，再一次性替换完整 `RagState`；旧快照允许在途请求完成。
5. retriever mode 切换同样重建 Agent，避免工具闭包继续引用旧 retriever。
6. snapshot manager 为每次 chat/search 提供 lease；发布 vector-only 后等待旧 Hybrid lease 排空，再开始图写入。
7. 图写入至少按日期收敛到事务；图失败时不发布新 Hybrid，保留可解释的 vector-only last-known-good。
8. active pointer 使用临时文件 + `os.replace` 原子切换；启动校验 active，损坏时回退最近 verified generation。
9. 默认保留 active + previous；只有旧 generation 无 lease 后才进入清理。执行任何实际删除前打印精确 generation 清单；设置可配置磁盘上限，禁止无界增长。
10. 启动自动同步、`POST /ingest` 与内部 corpus update 必须委托同一个 Coordinator；服务运行时，CLI ingestion 转调受认证 API/Coordinator，或拒绝直接写 active generation。
11. graph maintenance 期间 retriever-mode 不能恢复 Hybrid；自动同步、手动 ingest、模式切换并发时只允许一个写者和一个状态机决定发布。

验证：

- `test_failed_staging_build_preserves_last_known_good`
- `test_reader_never_observes_delete_add_gap`
- `test_snapshot_swap_rebuilds_agent_tools`
- `test_inflight_request_finishes_on_old_snapshot`
- `test_graph_update_waits_for_old_hybrid_lease_to_drain`
- `test_graph_failure_does_not_publish_hybrid_generation`
- `test_corrupt_active_pointer_recovers_previous_verified_generation`
- `test_concurrent_auto_update_ingest_and_mode_switch_keep_single_writer`
- 真实 Chroma 100 轮“查询 → staging update → snapshot swap → 查询”，`Error finding id = 0`

### 3B-1：稳定条目投影与 lexical 索引

1. 由 Search Document 投影 topic candidate chunk metadata 和稳定 citation/local URL。
2. 构建 SQLite FTS5 `trigram` lexical 索引；1–2 个汉字走 substring/bigram 降级；索引文件与 vector generation 使用同一个 generation manifest。
3. exact-title 与 lexical 通道在 vector/graph 之前独立运行；CDATA/tracking URL 在 ingestion 边界清洗。
4. 不为 OpenAI 单独写特殊抓取逻辑；source/entity canonicalization 使用可扩展 registry，alias 只表示同一实体。

验证：精确标题 Hit@1、稳定 citation deep link、1/2/3 字中文查询、`Open AI` 规范化、hard negative 不误命中；同时在生产 `python:3.12-slim` 镜像验证 FTS5/trigram 能力，不只依赖宿主机。

### 3B-2：Query Planning 与通道合同

1. 删除公司触发即追加泛词的固定扩展；原问题始终保留。
2. 只有同时出现 OKF/ALM 时才进入 Google knowledge comparison。
3. 明确标题/事件问题不追加 `agent/model/plugins` 等泛词。
4. metadata filter 由所有启用通道执行；图通道至少做同合同 post-filter，并在过滤后不足时可有界扩大候选池。
5. entity canonical form 只 boost，不默认 hard filter；source-specific 查询可以 hard filter。
6. QueryPlan 增加 `graph_requirement = disabled | optional | required`：精确标题/普通内容禁用；公司动态/宽泛趋势可选；明确关系、跨日趋势和实体关联聚合必需。required 图失败时可展示有限文本证据，但必须明确“关系分析不可用”，不得输出关系强结论。

验证：RQ03/RQ09 Hit@5，RQ11 不再误判 OKF/ALM，Product Hunt 查询无 Dev.to 泄漏。

### 3B-3：真实 RRF、意图化排序与多样性

1. 通道结果携带 canonical identity、rank、raw score；融合只用 rank-based RRF。
2. exact-title 是有界强 boost；`recent_trend` 才使用 freshness 与业务 score；source quality 通过 source family registry 统一映射。
3. 宽泛趋势在排序后做来源多样化；公司/来源/事件问题不使用全局 cap=2。
4. 输出分数组件到 eval，不在最终用户引用中暴露工程噪声。

验证：exact-title MRR ≥ 0.8；公司题 Recall 不再受 cap=2 数学限制；宽泛趋势来源覆盖不下降。

### 3B-4：Embedding bake-off 与拒答校准

只有在 exact/lexical/planner/RRF 修复后，才比较：

- 当前 Chroma 默认模型；
- `intfloat/multilingual-e5-small`；
- `BAAI/bge-m3` 仅作为离线可选上界，不默认安装到产品镜像。

模型选择同时看 Recall@50、中文/中英混合题、索引体积、构建耗时和查询 P95。若小型多语言模型没有显著收益，则保持当前模型；不得因为“更大更新”就默认采用。

拒答使用 20–30 道 hard negative 校准 Top1 分数、margin、exact/lexical/semantic 通道一致性；目标为正确拒答率 ≥90%，可回答 Hit Rate 下降不超过 5 个百分点。

## 4. 安装与下载清单（执行前再次确认版本/许可证）

本阶段默认实现不需要新增搜索服务：SQLite FTS5 来自 Python 标准库，当前环境已验证 `trigram` 可用。

可能发生的可选下载：

1. `intfloat/multilingual-e5-small`：离线 embedding bake-off；不会直接进入默认 Docker。
2. `BAAI/bge-m3`：只在磁盘/时间允许时做上界实验，体积较大。
3. 若当前 Chroma 版本通过真实 100 轮热更新测试，则将 `chromadb` 从宽泛 `>=0.5.0` 收窄到验证过的兼容范围；版本结论必须来自实验，不先拍脑袋锁版本。

## 5. Gate 与发布门槛

### Gate 3A：稳定性

- 检索错误误报为空结果 = 0。
- consistency 后端失败不再假绿。
- 100 轮真实 Chroma snapshot 循环无 `Error finding id`。
- 更新失败保留 last-known-good；snapshot swap 同时替换 retriever 与 Agent。

### Gate 3B：检索质量

在经人工确认前使用 silver v2 作为 provisional floor，不称 gold。标签冻结并计算理论上限后再把具体数字写入 Gate，指标按意图分开：

- exact-title：Hit@1、MRR、NDCG；目标 MRR ≥0.8，但需先确认标签；
- 趋势/公司多文档题：Recall@10、NDCG@10、Precision@returned，并报告相对理论上限达成率；
- unanswerable：hard-negative 正确拒答率，暂定 ≥90%，同时要求可回答 Hit Rate 下降不超过 5 个百分点；
- 整体：使用意图化 cutoff 的 Macro F1 或相对上限达成率，不再把所有题强塞进固定 P@10。

共同门槛：

- 每条 topic candidate citation 有稳定 item local URL；
- vector-only 与 Hybrid 指标分别报告，禁止混写。

若指标未达标，必须输出逐题失败与消融结果，不通过扩大 `k`、删除题目或放宽时间合同绕过 Gate。

## 6. 回滚与非目标

- 每个 generation 都有 manifest 与 active pointer；回滚是切回 last-known-good，不删除旧索引。
- generation 默认保留 active + previous；更旧项只有在无 lease 且列出精确清单后才按磁盘策略清理。
- 不在本阶段引入 Elasticsearch/OpenSearch、独立 Chroma Server或新的向量数据库。
- 不把周报/月报加入 RAG。
- 不修改摘要生产或 UI 视觉；Stage 4 只消费本阶段稳定的状态、引用和条目合同。
- 不在 Docker daemon 未运行时声称通过真实 Hybrid/Neo4j Gate。

## 7. 监管节奏

1. 本计划先由独立 Agent 按产品价值、架构边界、测试可达性审阅。
2. 3A 完成后单独 Gate Review；未通过不得进入质量调参。
3. 3B 每个实验只改变一个主要变量，结果落盘。
4. Stage 结束做 Standards/Spec 双轴复审，再建立 Claude 分支 checkpoint。

## 8. 首轮监管意见处置

| 级别 | 意见 | 修订 |
|---|---|---|
| P0 | 旧 Hybrid 仍会看到同一 Neo4j 的半成品更新 | 增加 vector-only 发布 → Hybrid lease drain → 单日期事务图更新 → 验证后恢复 Hybrid 状态机 |
| P0 | 固定 P@10 Gate 接近当前标签理论天花板 | silver v2 自动计算上限；按 exact、多文档、拒答拆分指标，具体阈值后置冻结 |
| P1 | FTS5 trigram 不支持 1–2 字中文短词 | 增加 exact/substring/bigram 降级和 Docker 镜像验证 |
| P1 | graph required 边界不清 | QueryPlan 增加 disabled/optional/required 意图矩阵 |
| P1 | 3A 评估字段依赖尚未实现通道 | 拆为标签合同与可扩展 envelope，通道分数组件随实现补充 |
| P1 | generation 缺少恢复和磁盘生命周期 | 原子 pointer、损坏回退、active+previous、lease 后清理与磁盘上限 |
| P2 | exact 不应膨胀成独立生命周期系统 | 工程上归入 lexical 子系统的确定性优先层 |
| P2 | 100 轮证据只对验证环境有效 | 测试证据必须记录 Chroma/Python/embedding/corpus/OS/路径版本 |
| P1（复审） | `/ingest`、自动更新、CLI 和模式切换可能绕过单写者 | 所有服务内写入口统一委托 Coordinator；CLI 运行态转调 API 或拒绝；maintenance 禁止恢复 Hybrid，并新增并发测试 |
| P1（复审） | graph-required 失败的 `error/degraded` 合同矛盾 | optional 固定为 degraded；required 固定为 `partial_error` + `required_graph_unavailable`，可展示文本线索但阻止关系强结论 |

最终监管结论：**APPROVE**。剩余 P0=0、P1=0；允许进入 Stage 3A 实施。
