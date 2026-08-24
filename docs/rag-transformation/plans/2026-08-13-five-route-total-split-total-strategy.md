# 五路“总—分—总”RAG 策略设计计划

- 日期：2026-08-13
- 状态：已完成并通过 Stage Gate；未修改正式业务链
- 输入：用户确认的总—分—总链路、ADR-0004、ADR-0005、Query Evidence Routing Contract v1

## 目标

为 AI Trend Radar 固化一条端到端、可解释、可评估的链路：原始 Query 先形成统一 Query Frame，再进入五类稳定任务路线；每条路线拥有输入改写、检索视图、相关性分层、层内排序、Prompt Envelope 与结构化输出合同；最终由确定性渲染器生成 Markdown/UI，而不是把 JSON 直接展示给用户。

## 交付物

1. 可点击的 Mermaid 总图与普通链接索引；
2. 五类任务路线定义；
3. 每个模块独立策略文档；
4. 总策略文档；
5. ADR 与独立 Changelog；
6. 独立质量监管 Agent 的 Stage Gate 结论。

## 工作边界

- 本阶段不修改 `rag/query_understanding.py`、`rag/retrieval_gateway.py`、`rag/prompt_registry.py` 或正式聊天链；
- 不接入新框架、不调用 DeepSeek、不重建索引；
- 不把未经小样验证的 Top K 或权重写成正式默认；
- 策略必须复用 ATR ID、原子语料、Neo4j、关键词/向量索引、Evidence Ledger 和 deep link。

## 已确认路线

- A：Item Navigation；精确 ATR ID / 标题导航，确定性构造回答；
- B：Trend Discovery；回答“最近发生了什么、什么值得关注”；
- C：Temporal Relation Exploration；回答“如何演变、彼此有什么关系、形成什么结构”；
- D：Claim Verification；判断支持、反驳或证据不足；
- E：Evidence Research；解释、比较或深挖问题。

字母只用于产品沟通和图示；正式合同使用语义化名称。

## Stage Gate 结果

- 独立质量监管结论：产品与架构方向通过；发现的 Candidate/Ledger 准入、A 路由旁路、Graph/Web 融合和上游值定位矛盾均已修订；
- B/C 产品边界于 2026-08-13 获用户确认；
- 下一阶段仅实现 Route Contract v2 Schema 与 route-balanced 小样，不直接替换正式链路。

## Stage Gate

质量监管 Agent 必须检查：

1. 输入改写与输出 Prompt 是否由同一个 Route Contract 驱动；
2. 五类是否覆盖当前真实用户路径且避免重叠覆盖；
3. Graph、向量、关键词和 Web 的边界是否符合任务需要；
4. JSON 是内部合同而非用户呈现；
5. 引用、ATR ID、原始链接与本地 deep link 是否贯穿全链；
6. 成本、延迟、失败和回滚是否可执行。
