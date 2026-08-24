# SemanticParseV1 首轮基础设施无效运行

- 运行日期：2026-08-13
- 状态：`infra-invalid`
- 报告：`docs/rag-transformation/evals/semantic-parse-v1-diagnostic-results-2026-08-13.json`

## 现象

- 12/12 解析失败；11 条返回缺少 required fields 的残缺 JSON，1 条 JSON 被截断。
- token usage 在异常捕获路径未取得，因此报告中的 0 token 不是“未调用 API”，而是观测缺口。
- 该轮 route=0、span=0 等数字是派生自无有效 parse 的占位结果，不能用于评价语义架构或模型质量。

## 单条诊断

同一模型 `deepseek-v4-flash`、temperature=0、JSON object 的单条诊断返回完整 9 个顶层字段，但 completion token 为 `1120/1200`，说明原 1200 上限过于贴边并导致批量结构不稳定。

## 受控修复

- max tokens 调整为 2400；其他模型、Prompt、temperature、timeout、retry 不变。
- 先运行 3 条跨路线 canary；必须 3/3 parse Schema/semantic valid 才可运行 12 条。
- 本报告永久保留，不覆盖，不计入质量提升。
