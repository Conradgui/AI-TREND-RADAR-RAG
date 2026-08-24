# RAG 检索质量基线与零召回退化复盘（2026-08-07）

## 一、结论先行

用户问题“最近有什么热门趋势？”的截图故障，不是知识库没有内容，而是两个层面叠加：

1. **运行时稳定性故障**：后台增量写入 Chroma 后，服务长期持有的 collection 句柄查询报 `Error finding id`；混合检索器将异常吞掉并返回空列表，最终被误报为“知识库没有可靠证据”。
2. **健康态质量不足**：重启 app 后虽然恢复召回，但 URL 银标集上的 macro Precision@10 仅 11.82%、Recall@10 为 37.63%、F1@10 为 15.35%，说明查询规划、实体过滤、排序和拒答边界仍有系统性问题。

因此，“重启后能回答”只能证明服务恢复，不能证明检索质量合格。

## 二、测试对象与证据边界

- 数据集：`retrieval-quality-dataset-2026-08-07.json`
- 题量：12（11 道可回答题 + 1 道虚构事实拒答题）
- 语料快照：最新日期 2026-08-07；Chroma 6285 chunks
- 测试路径：真实 Chroma + Neo4j + HybridRetriever + citation admission
- 不调用 DeepSeek，避免生成模型波动污染检索指标
- 标签等级：**silver（银标）**。URL 由当前索引和仓库证据预标；对外发布前仍需人工复核，不能冒充人工 gold set。
- 周报/月报遵循 ADR-0002，仅供浏览，不作为相关文档标签。

## 三、指标定义

- “准确率”采用查询成功率：可回答题至少命中 1 条相关证据；不可回答题不返回内部证据。
- Precision@10：前 10 个位置中相关结果的比例。
- Recall@10：标注相关集被找回的比例。
- F1@10：Precision 与 Recall 的调和平均。
- MRR：第一条相关结果的平均倒数排名。
- NDCG@10：高相关结果是否排在更前面。

传统分类 Accuracy 不适合直接衡量排序检索，因此报告中不把“准确率”与 Precision 混为一谈。

## 四、最终基线

| 指标 | 结果 |
|---|---:|
| 查询成功率（本文口径的 Accuracy） | 75.00% |
| 正确拒答率 | 0.00% |
| Macro Precision@10 | 11.82% |
| Macro Recall@10 | 37.63% |
| Macro F1@10 | 15.35% |
| MRR | 40.69% |
| NDCG@10 | 31.59% |
| Micro Precision@10 | 11.82% |
| Micro Recall@10 | 22.03% |
| Micro F1@10 | 15.38% |

> 注意：Precision@10 使用标准的 10 个位置作分母。系统因去重、缺失 citation metadata 或单来源上限只返回少于 10 条时，空缺位置同样体现为未提供相关结果。结果文件另含 `precision_at_returned`，可用于区分“结果少但较纯”与“结果本身噪声大”。

## 五、逐题结果

| ID | 场景 | 命中/相关 | P@10 | R@10 | F1@10 | 结论 |
|---|---|---:|---:|---:|---:|---|
| RQ01 | 最近热门趋势 | 2/15 | 20.00% | 13.33% | 16.00% | 能召回，但低分资讯挤占高分官方候选 |
| RQ02 | OpenAI 最近动态 | 2/8 | 20.00% | 25.00% | 22.22% | 首条正确，但召回覆盖不足 |
| RQ03 | Anthropic/Claude 动态 | 0/8 | 0 | 0 | 0 | 严重漏召回 |
| RQ04 | RAG/向量库开源项目 | 2/9 | 20.00% | 22.22% | 21.05% | 能命中少量项目，噪声仍高 |
| RQ05 | Product Hunt MCP | 2/3 | 20.00% | 66.67% | 30.77% | 来源过滤有效，但前列仍混入噪声 |
| RQ06 | AI Agent 开源项目 | 1/6 | 10.00% | 16.67% | 12.50% | “开源”约束没有落实 |
| RQ07 | 精确标题 Apple | 1/2 | 10.00% | 50.00% | 16.67% | 正确项只排第 3 |
| RQ08 | 精确标题 Economic Exchange | 1/1 | 10.00% | 100% | 18.18% | 找到但只排第 4 |
| RQ09 | Fable 5 safeguards | 0/1 | 0 | 0 | 0 | 精确实体/标题漏召回 |
| RQ10 | OpenAI/Apple 事件簇 | 1/5 | 10.00% | 20.00% | 13.33% | 泛 OpenAI 结果挤占事件证据 |
| RQ11 | DeepMind 气旋预测 | 1/1 | 10.00% | 100% | 18.18% | 第一条正确，但 query planner 错判为 OKF/ALM 比较 |
| RQ12 | 虓构 GPT-99 | 0/0 | — | — | — | 返回 5 条近似但无关结果，拒答失败 |

## 六、根因证据链

### P0：检索异常被吞成空结果

- 日志在增量摄取后出现：`[hybrid] vector search failed: Error executing plan: Internal error: Error finding id`。
- `HybridRetriever._safe_vector_search()` 捕获所有异常并返回 `[]`。
- 上层只看到“没有 chunks”，于是把系统错误当作语料为空。
- 仅重启 app、不重建索引后，同一句问题恢复 5 条内部引用，证明数据仍在，失效的是运行时句柄。

### P0：查询扩展污染精确语义

- Claude/Anthropic 查询被统一追加 `Claude Code Artifacts plugins developer tools`，即使问题问的是 Fable safeguards。
- OpenAI 查询被统一追加 `GPT agent developer model`，导致事件簇和精确标题被泛化。
- 任何包含 `Google` 的查询都被追加 `OKF ALM Wiki knowledge framework user preference`；气旋预测问题因此被错误标成 technical comparison。

### P0：中文词法重排实际退化为零分

- `_calculate_relevance_score()` 使用 `query.lower().split()`。
- 中文问句通常不会按词切开，整句成为一个 token，与中英文混合 chunk 几乎不可能完全相等。
- 综合分采用乘法，相关性为 0 会把 RRF、来源质量和新鲜度全部归零，排序退化为原顺序/偶然顺序。

### P1：权威来源映射与真实 source 值不一致

- `SOURCE_QUALITY_MAP` 没有 OpenAI、Anthropic (Claude)、Google DeepMind。
- GitHub 只匹配精确字符串 `GitHub`，而索引值是 `GitHub Search:rag` 等。
- 这些官方或 primary 来源因此默认按 secondary（0.4）处理。

### P1：趋势排序没有使用业务热度分

- recent reranker 只混合原始检索 rank 与日期新鲜度。
- 候选自带的 `score`（例如 98）没有进入该阶段；RQ01 中 51/53 分资讯排在 98 分官方候选前。

### P1：实体约束没有落实到 metadata filter

- metadata filter 只支持 content type、source 和 date。
- QueryPlan 虽提取 OpenAI、Claude、Anthropic 等 entities，却没有转化为过滤或 boost。
- 结果中会混入 Product Hunt、Dev.to 和 generic report chunks。

### P1：没有相似度/置信度拒答阈值

- 虚构的 `Quantum Banana GPT-99` 仍返回 5 条近似结果。
- 当前系统只要向量库能给最近邻，就会把最近邻当作可用证据，无法区分“最接近”与“足够相关”。

### P2：引用多样性上限是固定规则

- 每个 source 最多 2 条引用，对宽泛趋势问题可防止单一厂商霸屏。
- 但对“OpenAI 最近动态”会人为限制 Recall。该规则应按意图动态化，而不是全局固定。

### P2：数据规范化仍有缺口

- 6285 个 chunks 中有 66 个 URL 仍带 `<![CDATA[...]]>` 包装。
- 这会影响去重、点击和 URL 级评估身份，应在 ingestion 入口统一清洗。

## 七、优化路线图（先后顺序不可颠倒）

### Stage 1 — 稳定性与真实错误（P0）

1. 让 vector/graph 子检索返回结构化状态，至少一条必需检索通道异常时不得伪装成 `empty`。
2. 消除“服务长期读 + 后台进程原地改同一 Chroma collection”的句柄失效路径。
   - 短期：后台更新完成后原子重建并替换 retriever snapshot。
   - 中期：staging collection 构建、校验后切换 active snapshot，避免读写同一索引。
3. 加回归测试：更新前查询成功 → 执行增量更新 → 同一服务进程继续查询成功；若失败必须状态为 `error`。

验收：检索错误误报率 0%；热更新后连续查询无 `Error finding id`。

### Stage 2 — Query Planning（P0）

1. 将“规则命中”从简单包含关系改为场景化规则：只有同时出现 OKF/ALM 才注入 Google knowledge terms。
2. 精确标题、专有名词和事件簇优先保留原查询，不追加泛化词。
3. 增加 entity/source_family/category filter 或 boost；补齐 `Anthropic (Claude)`、GitHub family 等规范化映射。

验收：RQ03、RQ09 从 0 命中提升到至少 Hit@5；RQ11 不再被判为 OKF/ALM。

### Stage 3 — 候选生成与排序（P1）

1. 移除不适用于中文的空格分词乘法项；采用 embedding score + BM25/全文匹配 + 业务 score + freshness 的可解释加权。
2. 对 `recent_trend` 使用 `topic_candidate.score` 和日期，并在同事件/同 URL 去重后做来源多样化。
3. 对 exact-title 先走规范化标题精确/模糊匹配，再回退向量检索。
4. 将单来源上限改为意图相关：宽泛趋势保留多样性，公司/来源限定问题提高或取消上限。

验收：银标 macro Precision@10 ≥ 45%，Recall@10 ≥ 55%，F1@10 ≥ 50%；精确标题 MRR ≥ 0.8。

### Stage 4 — 拒答与数据卫生（P1/P2）

1. 用校准集确定相似度/重排置信阈值，不能拍脑袋设常数。
2. 无结果与低置信结果进入保守拒答或可选联网搜索，不直接把近邻当证据。
3. ingestion 统一清理 CDATA URL、tracking 参数和 source canonical name。

验收：不可回答控制集正确拒答率 ≥ 90%；CDATA URL chunks 新增量为 0。

### Stage 5 — 持续评估（P1）

1. Conrad/第二位审阅者复核银标集，升级为 gold v1。
2. 每次修改检索规划、embedding、chunk、rerank 或 ingestion 后自动跑离线 eval。
3. GitHub Action 输出指标变化；跌破阈值阻止发布，但不阻止数据定时同步。

## 八、验证结果

- 新增评分器单元测试：5/5 通过。
- Python 测试全集：250/250 通过。
- 真实检索基线：12/12 已执行并保存原始 citations、filter、耗时和逐题指标。
- 本阶段未调用 DeepSeek，也未修改生产索引或检索算法。

## 九、产物

- 计划：`docs/rag-transformation/plans/2026-08-07-retrieval-quality-evaluation.md`
- 数据集：`docs/rag-transformation/evals/retrieval-quality-dataset-2026-08-07.json`
- 原始基线：`docs/rag-transformation/evals/retrieval-quality-baseline-2026-08-07.json`
- 评估器：`rag/eval_retrieval_quality.py`
- 单元测试：`rag/tests/test_eval_retrieval_quality.py`
