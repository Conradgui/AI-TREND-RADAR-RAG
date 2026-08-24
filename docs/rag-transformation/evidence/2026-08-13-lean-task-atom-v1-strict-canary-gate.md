# LeanTaskAtomV1 Strict 三条 Canary Gate

- 日期：2026-08-13
- 状态：`FAILED / STOPPED`
- 报告：`docs/rag-transformation/evals/lean-task-atom-v1-strict-canary-results-2026-08-13.json`
- 报告 SHA-256：`03a256ddce2f439c60d30a082c96a2ed82155948d7688f835d6252799c751b0a`
- 正式链路影响：无

## 调用合同

- 官方端点：`api.deepseek.com`
- 模型：`deepseek-v4-flash`（调用前锁定）
- Base URL：`/beta`
- Thinking：`disabled`
- Function：单一强制 tool choice，`strict=true`
- max tokens：800
- timeout：45 秒
- retries：0
- 样本：固定 `RC2-SG-017`、`RC2-SG-020`、`RC2-SG-039`

## Gate 结果

| 指标 | 结果 | 要求 |
|---|---:|---:|
| Schema + semantic valid | 1/3 | 3/3 |
| 语义投影全对 | 0/3 | 3/3 |
| 平均延迟 | 2.478 秒 | <= 8 秒 |
| 最大延迟 | 2.659 秒 | <= 12 秒 |
| 平均 completion tokens | 186.33 | <= 600 |

性能 Gate 全部通过，可靠性和语义 Gate 失败。按预先约定立即停止，没有扩大到 12 条，也没有重试。

## 三类失败证据

### RC2-SG-017：提供方结构可靠性失败

模型返回了一个 tool call，但 arguments 内部在字符串中嵌入未转义的 ASCII 双引号，导致 JSON 无法解析。即使使用官方 Beta strict function calling，也不能把第三方结构输出当作无需本地校验的可信输入。

### RC2-SG-020：产品语义分类失败

结构合法，但模型把“汇总近 30 天重要动态”的主动作选为 `research`，投影到 E `evidence_research`，而产品 Gold 是 B `trend_discovery`；同时把可核验主张误标为 unresolved reference，并把整个命令句当成 protected term。说明开放式 Task Atom action 仍承担了过多产品裁决。

### RC2-SG-039：引用身份合同失败

模型把公开上下文中的 `ATR ID + 标题` 一起写入 `resolved_value`，而引用合同要求 bare ATR ID。服务端校验正确拒绝该输出。

## 架构结论

本轮已经把“接口误用”与“架构/模型不可靠”分开验证：

- 非思考 + strict 后，延迟从约 7 秒降至约 2.5 秒，性能问题已基本关闭；
- 但结构、产品语义和引用身份三类可靠性仍同时失败；
- 因此，不再通过增加 prompt、token 或重试修补同一个开放式 Lean fallback。

候选转向：

1. 保留已过 Gate 的 Deterministic Fast Path，处理明确的 A–E 请求和权限约束。
2. 将复杂请求拆成窄的 route-neutral semantic decisions，而不是一次生成完整 Task Atom：例如“是否要求近期新闻集合”“是否要求跨时间关系”“是否存在可判真伪主张”“是否要求单条导航”“是否要求解释/比较”。
3. L2 决策表仍是唯一产品路线裁决者；模型不能直接输出 route、policy 或最终答案。
4. 任一窄判断无效或冲突时进入 clarification，不允许静默默认 E。
5. 在新的离线合同和退化测试通过前，不接正式检索、Prompt Registry、聊天或 Web UI。

## 一手资料

- DeepSeek JSON Output：只保证合法 JSON，并提示可能返回空内容。
- DeepSeek Thinking Mode：V4 默认开启，可显式关闭。
- DeepSeek Tool Calls strict mode：要求 `/beta`、`strict=true`、所有 object 字段 required、`additionalProperties=false`。

官方合同说明了预期能力，但本项目仍以真实三条返回作为可用性判据；官方声明不能替代本地输入校验和产品语义评估。
