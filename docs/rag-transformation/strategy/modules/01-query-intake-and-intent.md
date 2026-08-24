# M1：输入保真与意图信号策略

## 目标

把用户原始 Query 转成可审计的输入事实，而不是立刻猜一个唯一 intent。Intent Signal 是分类依据，不是最终路由。

## 当前问题

当前 `QueryPlan.intent` 是单值，后出现的关键词可能覆盖前面的判断；原问题、上下文与检索扩展词也容易被拼成一个字符串。

## 目标接口

```text
capture_query(raw_query, conversation_context) -> QueryIntake
```

`QueryIntake` 必须包含原文、会话指代解析结果、ATR ID/引号/数字/日期/否定词等保真 token，以及可共存的 Intent Signals。

## 策略

1. 原文不可修改、不可覆盖；
2. 先确定性解析 ATR ID、URL、标题、实体/主题、日期、数值、来源和明确句式；
3. 提取 `navigation / recency / importance / trend / timeline / relation / verification / explanation / comparison` 等独立信号；
4. 明确实体和别名标准化，但保留用户原写法；
5. 会话补全只补指代，不把模型记忆写成用户事实；
6. 低置信和互斥理解进入 `ambiguities[]`，不静默猜测。

`protected_terms` 只承载丢失后会改变对象、范围或主张的字面片段：ID、标题、实体/主题、日期/时间窗、数值、否定与模态词（如“可能/一定”）、事实谓词和来源/联网约束。普通任务动词与“重要新闻/解释/比较”等已结构化意图不重复写入；禁止用完整 Query 作为形式化保真结果。

## 成本与失败

规则能确定时不调用模型；只有复合、指代或歧义问题允许最多一次结构化理解调用。失败时保留原 Query 并标记低置信，不生成伪精确字段。

## 评价

- 保真 token 丢失率；
- 实体/日期/否定词提取准确率；
- 复合意图信号召回率；
- 应保留歧义却被强行裁决的比例。

行业依据：Azure Agentic Retrieval 会结合 Query 与对话历史规划子查询，但 minimal 模式跳过 LLM planning，支持“确定性优先、复杂问题才升级”的策略。[官方说明](https://learn.microsoft.com/en-us/azure/search/search-agentic-retrieval-concept)
