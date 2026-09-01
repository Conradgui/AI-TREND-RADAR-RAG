# 2026-08-25 后端延迟优化一手资料摘录

## 证据边界

本文件只使用官方文档、官方源码仓库或原始论文。它用于验证架构机制是否已有成熟先例，
不表示本项目应整套迁移到对应产品或框架。

## 1. 确定性 Workflow 与 Agent loop

LangGraph 官方把 workflow 定义为具有预定代码路径的系统，把 agent 定义为会动态决定流程和工具使用的系统；
其自定义 workflow 支持条件分支、并行和把 Agent 作为其中一个节点，而不是让 Agent 接管整个流程。

- 来源：[LangGraph：Workflows and agents](https://docs.langchain.com/oss/python/langgraph/workflows-agents)
- 来源：[LangChain：Custom workflow](https://docs.langchain.com/oss/python/langchain/multi-agent/custom-workflow)
- 对本项目：**Adopt 机制，不换框架**。项目已经依赖 LangGraph，应把 A/B 和常规 C/D/E 写成可预测 workflow，
  只把确实不可预先确定的补证步骤交给受限 Agent。

Microsoft 的 Agentic RAG 架构指南也明确指出，每个推理步骤都会增加模型调用；应限制工具迭代、记录
模型推理、工具执行和结果处理的分阶段耗时。其示例估计标准 RAG 一次搜索+生成约 2–3 秒，
而 3–5 次工具调用的 Agentic RAG 可能达到 8–15 秒；具体数值不是本项目 SLA，但方向直接支持
“普通问题不应默认多轮 Agent”。

- 来源：[Azure Architecture Center：Develop an Agentic RAG Solution](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/rag/rag-agentic)
- 对本项目：**Adopt 预算与可观测性思想**，不引入 Azure 运行时。

## 2. 简单请求跳过 LLM 查询规划

Azure AI Search 官方提供 `minimal / low / medium` 三档检索推理：`minimal` 直接跳过 LLM query planning，
获得最低成本和延迟；`low` 只做一轮计划；`medium` 只在首轮证据不足时追加一次迭代。

- 来源：[Azure AI Search：Set the retrieval reasoning effort](https://learn.microsoft.com/en-us/azure/search/agentic-retrieval-how-to-set-retrieval-reasoning-effort)
- 对本项目：**Adopt 分档思想**：A/B 明确请求为 minimal；歧义 C/D/E 最多一次语义路由；只有证据门
  判定不足时才允许一次纠错迭代。

## 3. 并行混合检索与分阶段排序

Azure agentic retrieval 的查询执行会把子查询并行发往选中的知识源，再合并和排序；minimal 模式也可直接
执行文本和向量检索。

- 来源：[Azure AI Search：Agentic Retrieval Overview](https://learn.microsoft.com/en-us/azure/search/agentic-retrieval-overview)
- 对本项目：**Borrow** 并行 fan-out / merge 的执行模式，但通道必须由 A–E 策略选择，不能每次全开。

Anthropic 的 Contextual Retrieval 给出标准混合检索流程：BM25 与 embedding 分别召回，做融合去重，
再把 Top-K 交给生成模型；其测试还显示 reranking 可以改善召回，但明确提醒 reranking 会增加延迟和成本，
候选数量需按具体场景实验。

- 来源：[Anthropic：Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval)
- 对本项目：**Adopt BM25/Vector 融合原则；Borrow reranking**。本项目已有 SQLite FTS5、Chroma 和 RRF，
  不需要为了复用原则重写索引；先修并行与路由，再用固定检索集决定是否加入本地 reranker。

Vespa 官方的 phased ranking 使用廉价 first phase 处理较多候选，只在 Top-N 上运行昂贵 second/global phase，
并用 rerank-count 给计算量设硬上限。

- 来源：[Vespa：Phased Ranking](https://docs.vespa.ai/en/ranking/phased-ranking.html)
- 对本项目：**Borrow 两阶段排序原则，不引入 Vespa**：RRF/任务约束作为廉价第一阶段；只有 Top-N 才进入
  可选 cross-encoder 或复杂排序。

## 4. 证据不足才联网

CRAG 原始论文使用轻量 retrieval evaluator 判断检索质量，并据置信度触发不同动作；静态语料不足时才把
Web 作为纠错扩展，而不是所有请求默认联网。

- 来源：[CRAG 原始论文](https://arxiv.org/abs/2401.15884)
- 对本项目：**Adopt 条件纠错思想，但先用确定性 Evidence Sufficiency Gate**。当前不应再添加一个远程
  LLM evaluator；先以结果数量、时间、新鲜度、来源等级、实体匹配和冲突状态门控 Web。

## 5. 本地语义路由

Semantic Router 官方仓库展示了“route utterances + embedding encoder + threshold”的本地语义决策，
无匹配时可以返回 `None`，并支持本地 Hugging Face encoder。

- 来源：[aurelio-labs/semantic-router](https://github.com/aurelio-labs/semantic-router)
- 对本项目：**候选，不立即引入**。它能降低远程路由等待，但不能定义 A–E 的产品语义；当前真实 Query、
  人工 Gold 和稳定阈值不足。先使用高置信确定性模式 + 一次远程歧义兜底，积累数据后再 bake-off。

## 6. 一次结构化生成与本地校验

DeepSeek 官方 strict function calling 会按开发者提供的 JSON Schema 约束 tool call 输出；JSON Output 也可
要求有效 JSON，但官方提示偶尔可能返回空内容。

- 来源：[DeepSeek：Strict Tool Calls](https://api-docs.deepseek.com/guides/tool_calls)
- 来源：[DeepSeek：JSON Output](https://api-docs.deepseek.com/guides/json_mode)
- 对本项目：**Adopt strict Answer Envelope + 本地 Schema/证据 ID 校验**。不能因为有 strict 模式就省略
  本地验证；失败时优先确定性降级，而不是默认第二次模型修格式。

## 7. 流式反馈

LangGraph 官方 streaming 支持 `messages` token、`updates` 状态和 `custom` 自定义事件；这些模式可同时用于
正文 token 和检索进度，而不是等待完整答案后再人为切块。

- 来源：[LangGraph：Streaming](https://docs.langchain.com/oss/python/langgraph/streaming)
- 来源：[LangGraph：Event streaming](https://docs.langchain.com/oss/python/langgraph/event-streaming)
- 对本项目：**Adopt**。继续保留可核验阶段事件；低风险回答可以真实 token streaming，高风险核验路线
  则应在结论校验后解锁，不能展示隐藏思维链。

## 8. DeepSeek Context Cache

DeepSeek Context Caching 默认开启，只有重复前缀才能命中；官方提供 `prompt_cache_hit_tokens` 和
`prompt_cache_miss_tokens` 监控字段。它可降低重复长前缀的成本和首 token 延迟，但不保证 100% 命中。

- 来源：[DeepSeek：Context Caching](https://api-docs.deepseek.com/guides/kv_cache/)
- 对本项目：**Borrow 作为成本优化，不作为架构修复**。稳定 System Prompt 与证据合同放在消息前部有利于
  命中，但缓存不能消除不必要的路由调用、ReAct 循环或串行检索。

## 9. 方案结论

| 机制 | 决策 |
|---|---|
| Workflow-first、Agent-on-demand | Adopt |
| A/B 跳过 LLM query planning | Adopt |
| 按路线选择并行检索通道 | Adopt |
| 廉价融合后只重排 Top-N | Adopt 原则；reranker 待实验 |
| Evidence Sufficiency Gate 后条件联网 | Adopt |
| 本地 Semantic Router | 先 bake-off，暂不接生产 |
| Strict Answer Envelope + 本地校验 | Adopt |
| 二次 LLM 修复引用格式 | Reject（普通路线） |
| LangGraph token/custom event streaming | Adopt |
| DeepSeek context cache | Borrow，不能替代编排改造 |
| 整套迁移 Azure/Vespa/Haystack | Reject；借机制即可 |
