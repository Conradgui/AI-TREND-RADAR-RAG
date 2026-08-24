# LeanTaskAtomV1 三条 Canary Gate

- 日期：2026-08-13
- 状态：`INFRA-INVALID / STOPPED`
- 报告：`docs/rag-transformation/evals/lean-task-atom-v1-canary-results-2026-08-13.json`
- 冻结报告 SHA-256：`39ea9170a03b3e07e2726ff049d9c6c5ddd2589ec43975791bf98c2ee749d7b6`
- 正式链路影响：无

## 原始结果

| 指标 | 结果 | Gate |
|---|---:|---:|
| Schema + semantic valid | 0/3 | 3/3 |
| 语义投影全对 | 0/3 | 3/3 |
| 平均延迟 | 7.030 秒 | <= 8 秒 |
| 最大延迟 | 7.409 秒 | <= 12 秒 |
| 可观测 completion tokens | 0 | <= 600/条 |

三条调用均返回了可解析的 JSON object，但对象不含 `main`、`supporting`、`references`、`confidence`、`ambiguities`。执行器按约束立即停止，没有扩大到 12 条。

## 官方接口复核后的判定

本次结果不能用于否定 Lean Task Atom 架构，也不能计入模型能力成绩，原因是调用契约错误：

1. 请求使用 `response_format={"type":"json_object"}`；DeepSeek 官方只承诺它输出合法 JSON，不承诺符合指定 JSON Schema。
2. 当前模型是 `deepseek-v4-flash`，官方文档说明其思考模式默认开启；请求没有显式传入 `thinking.disabled`，不符合“轻量、低延迟语义解析”的实验目标。
3. DeepSeek 官方提供的 Schema 强约束方案是 Beta strict function calling：`/beta` Base URL、`strict: true`、所有 object 字段 required、`additionalProperties: false`。
4. 评估器在 Schema 校验失败时丢失了原始 JSON 和 usage，导致结果文件无法进一步解释模型到底输出了什么；这是可观测性缺口。

因此，本轮状态从普通 `FAILED` 更正为 `INFRA-INVALID`：失败事实保留，但不归因于产品分类、Lean Schema 或 DeepSeek 语义能力。

## 止损与下一步边界

- 保留已经通过 Gate 的 Deterministic Fast Path，不回滚。
- 不重复相同 `json_object` 调用，不增加 token，不扩大样本。
- 只有质量监管批准后，才允许固定同三条样本执行一次 strict function calling 替代 Canary。
- 替代 Canary 必须显式关闭思考、零重试、三次上限，并保存原始 tool-call arguments、finish reason、usage 和延迟。
- 替代 Canary 未达到 3/3 时，停止模型 fallback 路线，进入产品级架构裁决；不得接入正式聊天、检索或 Web UI。

## 一手资料边界

判断依据来自 DeepSeek 官方 API 文档的 JSON Output、Thinking Mode、Tool Calls strict mode 与当前模型说明。搜索引擎仅用于定位这些官方页面，不作为能力结论本身。
