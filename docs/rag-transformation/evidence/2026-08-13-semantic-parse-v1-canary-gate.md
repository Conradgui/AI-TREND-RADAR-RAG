# SemanticParseV1 3 条 Canary Gate

- 日期：2026-08-13
- 状态：`FAILED / STOPPED`
- 报告：`docs/rag-transformation/evals/semantic-parse-v1-canary-2400-results-2026-08-13.json`
- 正式链路影响：无

## Gate 结果

| 指标 | 结果 | 要求 |
|---|---:|---:|
| Parse Schema / semantic valid | 2/3 | 3/3 |
| Route | 2/3 | 观察项 |
| A 自然标题导航 | 1/1 | 观察项 |
| 可靠运行 | 2/3 | 3/3 |
| 平均延迟 | 13.501 秒 | 尚未设生产 Gate |
| Token | 4891 / 3 条 | 记录成本代理值 |

按监管约束，未达到 3/3 后立即停止，没有运行 12 条。

## 有效观察

- A 的自然语言完整标题导航从旧实现失败变为正确，说明“通用语义结构而非已知实体词表”的方向有价值。
- 复合 B+D 请求仍返回残缺合同，2400 token 仍不能保证结构可靠。
- D 的上下文反证请求主路线正确，但模型把证据步骤误标为独立 supporting、把“需要读取正文”误当 Query 歧义，并把 ATR ID 与标题一起写入 `item_id`，说明 rich parse 给模型的自由度过高。
- 即使成功，单次约 7–19 秒；若所有 Query 都先调用模型，会抵消流式回答等后续体验优化。

## 架构止损

不再增加 token 或直接替换模型后重复 12 条。`SemanticParseV1` rich contract 实验停止，保留为诊断证据。

下一候选架构：

1. **Deterministic Fast Path**：通用解析 ATR、完整/片段标题、日期/来源/数量、联网权限、左右上下文和明确任务动作；不依赖实体白名单。
2. **Lean Task Atom Fallback**：只有复合或低置信 Query 才调用模型，模型只输出一个主 Task Atom、可选独立 supporting Task Atoms、未解析指代和置信度；不输出 route/policy、subjects 大表、constraints 大表或最终答案。
3. **Deterministic Projection**：L2 仍唯一决定 Route Contract；保真 span 由 Query 中的通用字面切片与 Task Atom target span 合并，模型不得编造。
4. **No silent E fallback**：fast path 与模型 fallback 都失败时进入消歧，而不是默认 E。

## 下一小样建议

- 先做纯离线 fast path 覆盖 6 条（4 条 A、禁网 B、明确 D），目标 route 6/6、权限 100%、延迟 <10ms。
- 再用 lean fallback 只跑 3 条复合请求，必须 3/3 合同合法、平均延迟显著低于 rich parse，才允许组合评估 12 条。
- 仍不接生产，不创建新盲测。
