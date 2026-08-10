# RAG 与中文模糊搜索成熟方案调研计划

日期：2026-08-10

## 目标

基于当前 ChromaDB + Neo4j + 静态日报/站内搜索实现，研究中文模糊查询、实体与同义词解析、混合检索、rerank，以及从搜索结果深链到具体词条的成熟方案，并形成可执行的架构比较。

## 成功标准

- 结论以官方文档、论文或官方源码为主要证据，不以营销二手文替代。
- 明确区分仓库已实现事实、外部产品能力、架构建议与待验证假设。
- 比较继续自研、全文搜索引擎、轻量站内索引、共享 Search Document 层四类方案。
- 给出“模糊词 → 具体条目 → 稳定深链”的端到端数据与查询契约。
- 推荐路线包含阶段、验收指标、回滚边界和暂不采用项。

## 执行记录

1. 已读取 `web-access` 与 `research` 技能；Chrome CDP 未连接，公开资料改用 WebSearch/WebFetch。
2. 已确认仓库存在未提交修改；本任务只新增研究与计划文档，不修改或覆盖现有实现。
3. 已完成第一轮仓库审计：现有 dashboard 搜索按“天”过滤全文；RAG 为 Chroma 向量 + Neo4j 实体全文索引 + RRF；引用只跳到日报，不定位具体条目。
4. 已完成一手资料取证：覆盖 Elasticsearch/OpenSearch、Neo4j、Chroma、Meilisearch、Typesense、Pagefind、MiniSearch、FlexSearch、Qdrant、Weaviate、LlamaIndex、RRF/实体链接/rerank 论文与官方模型资料。
5. 已完成方案矩阵与推荐架构：共享逻辑 Search Document、分离站内条目索引与 RAG chunk 索引；近期采用轻量站内索引并保留 Chroma + Neo4j，暂不新增 OpenSearch/Elasticsearch 常驻服务。
6. 已完成最终文档与范围核验：研究文档明确区分仓库事实、外部能力事实和架构判断；未修改代码或现有产物。
