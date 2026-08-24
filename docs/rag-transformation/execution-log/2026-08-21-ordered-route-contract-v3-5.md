# 2026-08-21 Ordered Route Contract v3.5 可见校准

## 范围

本阶段只修 Query Contract 的公共 seam，不修改冻结语料、索引、检索参数、Prompt Registry、
正式 Agent 或 Web UI。

公共接口：

```text
understand_ordered_query_v3(query, context)
  -> OrderedSemanticFrameV3 + RouteContractV2
```

## TDD 结果

离线可见用例覆盖：

1. 无公开前件的裸指代失败关闭；
2. Query 中直接事实进入 `claims`；
3. 显式假设进入 `claims`；
4. 任意已保护机构可投影为官方来源约束，不维护厂商词表；
5. 会改变回答范围的否定约束进入 `protected_terms`；
6. 绝对时间范围同时保留原文、起点和终点。

实现保持在公共合同：

- `claim_spans` 是 Ordered Frame 的精确 Query span，并投影到 Route Contract `claims`；
- 裸指代护栏只在无 public context 且同一 Query 中没有更早的明确 subject 时触发；
- 官方来源从 `protected_terms` 与“官方”的相邻关系投影，不增加实体名单；
- 绝对时间兼容旧 `value`，新增 `surface/start/end` 供检索和 Prompt 消费。

## 验证证据

- v3.5 离线可见小样：10/10；
- Ordered Frame、v3.3/v3.4 相关回归、Schema 与评分器测试：
  `95 passed, 28 subtests passed`；
- Python 编译与 `git diff --check`：通过；
- 一次 6 题 DeepSeek 可见校准：6/6 执行、零重试；首轮 5/6 产品行为正确。唯一失败是
  内容型否定未进入 `protected_spans`；同轮还观察到专用字段向 `protected_spans` 重复。
- 未重跑该可见校准。基于失败证据增加通用内容否定护栏，并在 sanitizer 去除
  subject/source/claim/web 与 protected 的交叉重复；相关离线回归通过。
- 未新增 Blind；未修改活动索引。

## 首轮监管 BLOCK 与修复

独立监管首次裁决为 BLOCK：来源依赖 protected、来源短语可能成为代词前件、时间边界缺少
强不变量。修复后：

- Ordered Frame 增加专用 `subject_spans/source_spans/claim_spans`；
- 来源、时间、权限和否定约束不再充当“它”的前件；
- 无前件“这项发布”要求澄清；
- `absolute_range` Schema 必须包含 `surface/start/end`，反向区间失败关闭；
- 旧 absolute contract 不再静默进入检索，必须从 `original_query` 重新理解后再使用。

第二次监管裁决为 `APPROVE_WITH_ACTIONS`：允许进入固定语料、影子模式的检索调优，但不得
直接接正式 Agent。前件范围已明确为“同一 Query 内更早的明确 subject”，并已消除 Prompt
对专用字段与 `protected_spans` 的矛盾描述。

## 尚未宣称

- 这些结果证明合同 seam 和旧回归兼容，不证明真实模型泛化；
- 尚未允许 Query Rewrite、Retrieval/GraphRAG 或正式 Agent 消费 v3.5；
- 是否进入检索调优由第二次独立质量监管 Gate 决定。
