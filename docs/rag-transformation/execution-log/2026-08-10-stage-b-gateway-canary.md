# Stage B：Evidence Retrieval Gateway Canary——执行记录

日期：2026-08-10
分支：`claude/rag-transformation-checkpoints`
计划：`docs/rag-transformation/plans/2026-08-10-stage-b-evidence-retrieval-gateway.md`
状态：`PASS`（仅限 Gateway 小样本 Gate）

## 1. 为什么先做 Canary

Conrad 明确要求：重大改动不能先全量推进再用大范围失败来发现问题。因而在 Server、Agent、Web UI 接入前，先以实际 `2026-08-05` 本地索引执行 5 个小样本用户路径。

本次检查的公开 seam 是：

```text
retrieve(ResearchRequest) -> EvidenceBundle
```

测试不读取 Gateway 的私有排序函数，不调用 LLM 或联网 API，也不写入或重建索引。

## 2. 变更

- 新增 `rag/retrieval_gateway.py`：统一 Navigator、Trend Discovery 与旧 Evidence Search 回退。
- 新增 `rag/eval_gateway_canary.py`：读取 Gateway 输出，判定用户可见的条目、稳定链接、来源多样性和非空回退条件。
- 新增 `rag/tests/test_eval_gateway_canary.py`：先以 RED 状态验证评估器不存在，再实现最小 evaluator。
- 扩展 `rag/tests/test_retrieval_gateway.py`：增加“实体识别不得覆盖精确标题导航”的回归测试。
- 新增 `docs/rag-transformation/evals/gateway-canary-2026-08-05.json`：冻结与当前本地索引一致的 Canary 合同。

## 3. RED → GREEN 证据

### 3.1 第一轮 RED

```text
ModuleNotFoundError: No module named 'rag.eval_gateway_canary'
```

含义：Canary 评估器还不存在。随后只实现了读取 `EvidenceBundle` 的 evaluator，不改检索路径。

### 3.2 第二轮 RED

```text
expected: item_navigation
actual: evidence_research
query: Introducing The Openai Economic Research Exchange
```

根因：查询理解把带 OpenAI 实体的完整标题误归类为趋势发现，Navigator 被过宽的 discovery 判断禁止。

修复：精确标题命中优先于宽泛 discovery intent；generic trend 仍然只在“无实体、无来源、无主题”的情况下走聚合路径。

### 3.3 GREEN

```text
.venv/bin/python -m pytest rag/tests/test_retrieval_gateway.py \
  rag/tests/test_eval_gateway_canary.py \
  rag/tests/test_lexical_store.py \
  rag/tests/test_chat_service.py -q
35 passed in 1.82s
```

## 4. 实际索引 Canary

执行命令：

```text
.venv/bin/python -m rag.eval_gateway_canary \
  --lexical-path /private/tmp/atr-lexical-through-2026-08-05.sqlite3 \
  --output docs/rag-transformation/evals/gateway-canary-results-2026-08-10.json
```

| 检查项 | 结果 |
|---|---|
| 标签快照 | 2026-08-05 |
| Chroma 最新日期 / 文档数 | 2026-08-05 / 6,098 |
| Lexical 最新日期 / 条目数 | 2026-08-05 / 3,287 |
| Canary 通过数 | 5 / 5 |
| Gate | `true` |

报告见：`docs/rag-transformation/evals/gateway-canary-results-2026-08-10.json`。

## 5. 全量回归

```text
.venv/bin/python -m pytest -q
422 passed in 12.46s
```

## 6. 不应过度解读的结论

1. 5/5 不等于检索 Precision/Recall/F1 达标。趋势题目前只验证了“有足够、去重、跨来源的候选”，没有经过人类相关性标注。
2. 该 Gate 没有覆盖 Hybrid/Neo4j、外部搜索、深度抓取、DeepSeek 回答生成或浏览器交互。
3. 宽泛“OpenAI 最近动态”仍然是 Evidence Search 的回退路径；其高质量标准必须由冻结快照上的人工标注集来定义，而不能由本 Gate 代替。

## 7. 下一步准入结论

允许进入后续的**有限集成**：将 Gateway 注入 Server 请求状态、保留旧路径作为回退，并在 API 层增加可观测 trace。正式接入前仍应为 Server 请求增加单独的 RED/GREEN 测试；Web UI 需要独立的交互验收，而不是直接假设其已通过。

## 8. 有限 Server 接入——执行结果

### 目标

避免出现两类隐性断链：

1. `/chat` 使用 Gateway、`/chat/stream` 却继续使用旧路径；
2. 索引 generation 或检索模式切换后，Gateway 仍引用已退休的 retriever。

### 实施

- `RagState` 新增只读 `retrieval_gateway` 字段；它与 `chat_retriever` 同时创建、同时通过 `dataclasses.replace()` 更换。
- Server 启动、generation 发布、Graph 恢复、retriever mode 切换都会重新绑定 Gateway。
- 普通与流式聊天端点均显式传入 Gateway。
- 发现并修复耗时统计缺口：Chat 编排不会再用 Gateway 后开始的局部计时覆盖 Gateway 自己的完整检索耗时。

### RED → GREEN

1. 新增 HTTP contract 测试时，`RagState` 不认识 `retrieval_gateway`，出现：

```text
TypeError: RagState.__init__() got an unexpected keyword argument 'retrieval_gateway'
```

2. 新增 Gateway 耗时断言时，预期 `123.0ms`、实际显示 `2.99ms`，复现了指标被覆盖的问题。
3. 修复后：

```text
.venv/bin/python -m pytest \
  rag/tests/test_chat_service.py::ChatServiceTests::test_gateway_controls_initial_evidence_path_and_exposes_trace \
  rag/tests/test_server_chat_response.py \
  rag/tests/test_server_chat_stream.py -q
13 passed in 5.66s
```

### 最终复验

```text
.venv/bin/python -m rag.eval_gateway_canary ...
5/5 passed

.venv/bin/python -m pytest -q
424 passed in 9.11s

git diff --check
通过
```

### 当前边界

此接入只覆盖 API contract 和 Gateway 的请求状态绑定；不声称浏览器 UI、DeepSeek 输出或混合图检索已经验收。下一张卡片必须是 Web UI 的独立用户路径测试，而不是继续扩大后端改动。
