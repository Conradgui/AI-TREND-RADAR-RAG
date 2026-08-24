# M7：结构化 Answer Envelope 与校验策略

## 目标

Agent 产出机器可验证对象，用户不直接查看 JSON。Schema 正确只是第一层，还必须验证证据和业务语义。

## 稳定外层

```json
{
  "schema_version": "atr.answer/1.0",
  "request_id": "...",
  "route": {"primary_task_family": "trend_discovery", "answer_mode": "important_news"},
  "headline": "...",
  "summary": "...",
  "sections": [],
  "claims": [{"claim_id": "C1", "text": "...", "evidence_ids": ["E1"]}],
  "citations": [],
  "limitations": [],
  "method_summary": "..."
}
```

路由专属字段使用 JSON Schema `$defs` 与 `oneOf`，外层 claims、citations、limitations 和 route 保持稳定。

A 路由的唯一 ATR 匹配或受控消歧结果先准入 Evidence Ledger，再由服务端按照 `answer_builder_contract_id` 确定性构造 `NavigationAnswer`；B–E 才由 Agent 生成结构化对象。二者进入相同校验和渲染入口，但不意味着 A 必须调用模型。

## 校验层级

1. JSON 可解析；
2. Schema 类型、必填项与枚举有效；
3. Evidence ID 全部属于当前 Ledger；
4. ATR、标题、日期和 URL 以服务端 Ledger 为准；
5. 路由业务不变量有效，例如趋势需多事件，contradicted 需直接反证；
6. Primary/Supplementary/Background 不得被模型改层。

## DeepSeek 策略

使用 JSON mode 仍需在应用层校验。DeepSeek 官方说明 JSON Output 可能出现空内容或 token 截断，因此不能把“合法 JSON”视为业务合同成功。[官方文档](https://api-docs.deepseek.com/guides/json_mode/)

校验失败最多一次“格式修复”，只修 Schema，不重新推理事实；再次失败返回受控错误。禁止向用户展示未验证 JSON。

## 评价

Schema valid rate、业务不变量 valid rate、未知 Evidence ID 率、格式修复成功率、空/截断响应率、相同输入合同的输出稳定性。
