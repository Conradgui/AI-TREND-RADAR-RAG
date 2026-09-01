# AI Trend Radar RAG Target Architecture Spec

> 2026-08-26 当前覆盖：复用已有模块，先闭合产品链，不以增加架构层为目标。当前状态见 [CURRENT_CONTROL.md](../CURRENT_CONTROL.md)，执行合同见 [G0–G4 计划](../plans/2026-08-26-g0-g4-implementation-and-stage-gates.md)。下方 Current state 是历史快照；最新事实见 [全局缺口基线](../plans/2026-08-26-global-gap-and-closure-baseline.md)。

## 0. 当前架构不变量与最小实现

1. 日报原子条目是检索/引用单位，ATR 独立且稳定；日报 Markdown、周报/月报只浏览，不能重复进入主索引。
2. 已有 A–E 路由、Prompt Registry、Answer Envelope 应复用：问题 → 意图/主体 → 路由/改写 → 混合召回 → 相关性分层与层内排序 → 对应 Prompt → 证据校验 → 可读 UI 与跳转。
3. 主体别名与关系分开。已知主体优先确定性匹配，未知主体才有限调用模型；候选、已验证、否决/撤销分状态，有证据才晋级。先完成一条“未知→核验→下次复用”闭环，不建设泛化学习平台。
4. 不为接框架而改系统。只有现有模块无法满足具体失败用例时才比较成熟替代方案；记录维护成本、迁移风险与产品收益，安装前遵守权限要求。
5. 热路径只放回答所需的工作；关系核验、统计、非必要补全移出等待链。缓存不把旧新闻答案当成新动态。
6. 图谱和向量更新采用可观察的 generation 与安全降级，不假称跨库事务；先验失败恢复，再恢复无人值守更新。
7. 本地容器优先重连/启动，不因每次更新重建；云端发布与本地激活分开验收。研究成果增值是 G5，不阻塞本轮收敛。

### 0.1 诊断优先于组件升级

架构优化必须沿“规范化输入 → 候选召回 → 排序/证据准入 → 受约束生成 → 用户结果”逐层定位。某层没有业务 Gold 证明失败时，不允许用增加模型调用、替换 Embedding、默认多查询/HyDE、增加 Reranker 或引入新框架作为预防性改造。

- 日报以 `DailyCorpusItem/Occurrence` 为原子检索单位，不套用通用 500–1000 token 窗口再次混切；只有未来长正文证据需要独立的父子/窗口策略。
- Query Rewrite 是按需能力：确定性主体、ATR、标题和清晰任务走快速路径；只有语义鸿沟、复合任务或首轮证据不足时才受限改写。
- 图检索服务关系、时间演化和聚合问题；描述性查找仍以词法/向量为主。图和向量互补，不把任一通道视为默认升级版。
- 生成前必须完成证据准入，生成后校验 Evidence ID 与关键 Claim 的对应关系；高成本 LLM Judge 只用于抽样审计，不进入默认在线热路径。
- 评估分层且按任务报告：检索关注 Hit/Recall、排名与主答案精度；生成关注忠实度、相关性和边界；产品关注完成率、追问/澄清、跳转、延迟与恢复。禁止把不兼容任务压成一个全局 F1。
- 更新使用稳定身份、内容指纹、影子 generation 和可回滚切换。当前日报级时效只需定时任务，不为“可能需要实时”预装消息队列。

Date: 2026-06-22

## 1. Purpose

This spec defines the target architecture for AI Trend Radar RAG.

It exists to keep implementation work aligned with the product goal: a grounded AI research cockpit, not a generic chatbot with scattered tools.

## 2. Target Product Shape

AI Trend Radar RAG should become an internal-first, evidence-governed research system.

The mature system should:

- sync fresh AI Trend Radar corpus;
- retrieve and cite internal evidence;
- use external search only when internal evidence is insufficient or freshness is required;
- inspect high-value external sources through safe deep fetch;
- separate internal evidence, external evidence, conflicts, and uncertainty;
- support repeatable trend research workflows;
- later reduce two-project friction through a unified local demo workspace;
- consider a full local app only if repeated use proves it is worth the cost.

## 3. Architecture Layers

### 3.1 Data Layer

Role:

- bring AI Trend Radar reports, topic pools, search index, and manifest data into this project.

Current state:

- fresh corpus sync exists;
- local digest files and manifest are available;
- topic-pool compatibility exists.

Target state:

- corpus sync is automated and CI-visible;
- data freshness is measurable;
- sync failures are explicit.

### 3.2 Index Layer

Role:

- turn corpus data into retrievable vector and graph indexes.

Current state:

- ChromaDB vector path is populated and verified locally;
- Neo4j graph runtime is verified through Docker Compose and local structural benchmark.

Target state:

- Chroma vector index and Neo4j graph index are both populated and tested;
- entities, topics, sources, dates, and evidence relationships are normalized;
- graph edges preserve evidence and confidence.

### 3.3 Retrieval Layer

Role:

- choose how to retrieve evidence for a question.

Current state:

- deterministic query understanding exists;
- metadata filters and vector-only fallback exist;
- hybrid retrieval slice 1 exists.

Target state:

- hybrid vector plus graph retrieval is reliable;
- reranking is evaluated;
- retrieval quality is benchmarked against golden questions.

### 3.4 Evidence Layer

Role:

- preserve source truth and prevent unsupported claims.

Current state:

- internal citations exist;
- external citation schema exists;
- source quality classification exists;
- Tavily external evidence can be merged into chat;
- safe URL fetch and injectable deep fetch exist.

Target state:

- external source fetching is runtime-gated;
- deep-fetch results are evaluated;
- source conflict handling exists;
- answer generation always exposes evidence boundary and uncertainty.

### 3.5 Agent Layer

Role:

- coordinate tools without losing control.

Current state:

- deterministic tool routing contract exists;
- external search and fetch_url steps are traceable;
- full LangGraph-style workflow is not implemented.

Target state:

- simple questions stay cheap;
- complex questions follow a bounded multi-step workflow;
- tool calls have budgets, traces, fallback behavior, and failure reasons;
- LangGraph or a similar official framework is considered only when workflow complexity justifies it.

#### 3.5.1 Workflow 与 Agentic RAG 的产品边界

本项目采用混合控制权，而不是把所有流程交给模型：

| 问题形状 | 默认控制方式 | 原因 |
|---|---|---|
| ATR/标题/描述定位、单次明确检索 | 确定性 Workflow | 更快、可复现、无需模型猜工具 |
| 热门趋势候选生成与固定排序 | Workflow + 候选受限 Graph | 先保证一致产品口径，再用图补结构证据 |
| 跨来源比较、复杂时间线、内部证据缺口 | 受控 Agentic RAG | 需要分解、动态选源或一次迭代补证据 |
| 高风险主张核验 | Workflow 硬边界 + Agent 辅助 | 模型可组织证据，但不能自行改变证据准入规则 |

Agentic RAG 的最小运行合同是：`Route Contract → Plan/Tool Choice → Observation → Evidence Sufficiency Check → Answer Envelope`。每个请求必须有工具次数、总时长、联网/深抓权限、最大纠偏次数和停止原因。系统不展示或持久化隐藏思维链，只展示可审计的工具、证据和阶段状态。

#### 3.5.2 规划、工具、记忆与恢复

- **规划**：只对复杂任务生成短计划；单步任务禁止为了“像 Agent”而进入 ReAct 循环。首版最多一次证据不足后的重新规划，不引入 ToT/GoT。
- **工具**：检索、Graph、Web、Deep Fetch 都是有 schema、权限和错误语义的工具；工具返回失败与空结果必须区分。
- **短期状态**：当前请求的步骤、预算、工具 trace 和 Evidence Ledger，随请求结束而结束。
- **长期记忆**：只保存经核验的主体别名/关系反馈和版本信息；用户对话、模型猜测和思维链不能直接成为知识。
- **恢复**：超时、图不可用或 Web 失败时，返回已完成步骤、证据范围和可行动的下一步；不能静默重试到超时。

这意味着本项目在面试中应被准确描述为“确定性 Workflow 为骨架、受控 Agentic RAG 处理复杂证据任务”，而不是“全自主多 Agent”。后者当前既未实现，也不符合延迟和成本目标。

### 3.6 Evaluation Layer

Role:

- make quality measurable.

Current state:

- golden questions exist;
- corpus availability, query plan, live chat, answer policy, tool routing, external evidence, and external answer quality checks exist.

Target state:

- golden questions expand beyond the first five;
- benchmarks compare internal-only, internal-plus-external, and research-workflow modes;
- evaluation outputs guide roadmap priority.
- each score records dataset revision, task family, raw counts and failure examples;
- component experiments are triggered by diagnosed metrics and compared on the same frozen inputs;
- offline retrieval/answer checks and online user-flow signals remain separate but traceable.
- Agentic evaluation separately measures route-to-agent correctness, tool selection, useful-step ratio, stop correctness, grounded task completion, budget compliance, recovery quality and end-to-end latency; it cannot be replaced by answer fluency.

### 3.6.1 Research Artifact Layer

Role:

- convert retrieved evidence into durable, reviewable research outputs.

Current state:

- deterministic Trend Brief Markdown assembly exists;
- `python -m rag.generate_trend_brief` exists;
- the module is wired into the canonical P0 check;
- first real local artifact smoke generated `trend-brief-rag-2026-06-24.md`.
- explicit `--mode live-external` request planning exists and is P0-covered;
- live external Trend Brief runtime smoke generated `trend-brief-rag-live-external-2026-06-24.md`;
- live external source quality remains weak/generic.

Target state:

- topic briefs can be generated from local corpus and graph evidence;
- generated briefs are reviewed as product artifacts, not only as test outputs;
- optional LLM-assisted summaries remain live-gated and evidence-bounded.

### 3.7 Runtime Layer

Role:

- make local and future deployed behavior predictable.

Current state:

- vector-only local runtime is verified;
- DeepSeek LLM access is verified;
- focused RAG check exists;
- live deep fetch is not enabled by default.

Target state:

- runtime toggles control external search and deep fetch;
- CI separates deterministic checks from live API checks;
- secrets remain server-side only.

### 3.8 Integration Layer

Role:

- reduce deployment friction and eventually decide whether a unified local app is warranted.

Current state:

- original UI integration and unified local workspace are explicitly out of scope for current P1 work.

Target state:

- Stage 2.5 provides a single-repo local demo workspace after the RAG core and Nexus-like cockpit mature;
- the upstream AI Trend Radar project can be included or referenced as a module;
- a full local app or desktop shell remains future vision, not current scope.

## 4. Capability Status Labels

Use these labels in roadmap and evidence files:

- `Planned`: not implemented yet.
- `Implemented`: code or data path exists.
- `Locally Verified`: deterministic local tests or smoke checks passed.
- `Live Smoke Verified`: a low-volume real API/runtime check passed.
- `CI Ready`: deterministic checks are wired into the canonical check command.
- `Production Ready`: deployable with monitoring, failure modes, cost controls, and security review.
- `Not Claimed`: intentionally not represented as complete.

Do not use "done" without specifying the status label.

## 5. Current Architecture Status

As of 2026-06-25:

- Data Layer: `Locally Verified`
- Index Layer: vector path `Locally Verified`; graph citation-ready retrieval and graph relationship paths `Live Smoke Verified`
- Retrieval Layer: query planning, first hybrid slice, mixed-source metadata filtering, citation-ready graph result metadata, live hybrid retrieval, and graph question planner service evidence `Live Smoke Verified`
- Evidence Layer: internal citations, multi-provider external citations, provider fallback, live URL deep fetch, claim-level seed checks, retrieval precision checks, and seed-level semantic contradiction checks `CI Ready`; full semantic correctness `Not Claimed`
- Agent Layer: deterministic routing `Locally Verified`; full workflow agent `Not Claimed`
- Evaluation Layer: expanded 12-question draft asset, provider quality matrix, claim-level seed, semantic contradiction seed, retrieval precision, graph reasoning, and graph question planner checks `CI Ready`
- Research Artifact Layer: deterministic Trend Brief generator `CI Ready`; first real generated artifact `Live Smoke Verified`; live external runtime `Live Smoke Verified`; external source quality gate `Live Smoke Verified`; source relevance review `Locally Verified`; batched external evidence acquisition `Live Batch Verified`; batch evidence integration `Live Artifact Verified`
- Runtime Layer: vector-only local runtime `Live Smoke Verified`; live deep fetch toggle `CI Ready`
- Integration Layer: Stage 2.5 unified local demo workspace `Planned`; full local app `Not Claimed`

## 6. Near-Term Priority

The next useful work is intentionally compressed:

1. Close G2 with one human-confirmed real-corpus evaluation package and one browser-level product verification.
2. Fix at most one diagnosed retrieval/answer bottleneck; keep Embedding, HyDE, parent-child retrieval and semantic reranking as metric-triggered experiments.
3. After G2 Gate, prove one-date incremental update with stable ATR/content fingerprint, shadow vector/graph generation, consistency check and rollback.
4. After G3 Gate, perform one clean-clone deployment and user onboarding acceptance; richer research artifacts remain later product work.

Reference calibration: [RAG question overview](https://xiaolinnote.com/ai/rag/rag_info.html), [query rewrite](https://xiaolinnote.com/ai/rag/12_query_rewrite.html), [multi-retrieval](https://xiaolinnote.com/ai/rag/13_multi_retrieval.html), [graph boundary](https://xiaolinnote.com/ai/rag/16_graph_db.html), [hallucination controls](https://xiaolinnote.com/ai/rag/17_hallucination.html), [evaluation](https://xiaolinnote.com/ai/rag/18_evaluation.html), [dynamic update](https://xiaolinnote.com/ai/rag/19_dynamic_update.html), [Agent/Workflow/工具概览](https://xiaolinnote.com/agent/concept/agent.html), [Agent 规划模式](https://xiaolinnote.com/ai/agent/14_planning.html), [Microsoft Agentic RAG 架构](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/rag/rag-agentic) and [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence). 面试资料是候选检查清单；官方架构资料用于核对能力边界；项目 Gold、运行证据和本 Spec 才是最终合同。
