# M6：Prompt Package 注册表策略

## 目标

用同一 Route Contract 选择输入改写策略、检索证据形状、Prompt 模板和输出 Schema，避免两端语义漂移。

本模块只处理 B–E。A 不编译 Prompt Package，而由版本化 `answer_builder_contract_id` 驱动确定性 `NavigationAnswer` 构造。

## 接口

```text
compile(RouteContract, EvidenceBundleV2, RuntimePolicy) -> PromptPackage
```

Prompt Package 固定包含：安全与证据边界、任务目标、原问题与问题框架、分层证据、输出 Schema、证据不足策略和预算。Prompt 没有改变 route、层级或链接的权限。

## 五路合同

| 路由 | Prompt 重点 | JSON 合同 |
|---|---|---|
| B | 主动态/补充/背景分开；多事件才能称趋势 | `TrendAnswer` |
| C | 时间或关系组织；confirmed/inferred 分开 | `TemporalRelationAnswer` |
| D | supported/contradicted/insufficient；判据绑定证据 | `VerificationAnswer` |
| E | 结论—证据；比较维度对称；明确局限 | `ResearchAnswer` |

## 版本同步

对 B–E，`route_contract_id`、`rewrite_policy_id`、`retrieval_policy_id`、`prompt_contract_id` 和 `output_schema_id` 必须属于同一兼容版本。A 则交叉校验 `answer_builder_contract_id` 与 `output_schema_id`。不兼容一律 fail closed。

## 不交给 Prompt 的责任

- 从大批噪声中完成检索；
- 重做相关性分层和排序；
- 补造标题、日期、摘要或 URL；
- 接受 Ledger 外 Evidence ID；
- 手写最终 HTML 或重新安排 UI 层级。

## 评价

路由—Prompt 一致率、required evidence shape 满足率、无证据时正确拒答率、未知 Evidence ID 率、Prompt token 数和版本兼容失败可解释率。
