# Narrow Semantic Decisions v1 执行记录

- 日期：2026-08-13
- 状态：离线实现与 Gate 补强完成，等待最终独立 Stage Gate
- 正式流量影响：无
- API 调用：无

## 为什么停止旧方向

新的 50 条封存盲测中，Route Contract v2 影子理解器路线准确率仅 60%，20 个路线错误中 19 个静默落入 E。随后两个模型 fallback 小样也未过 Gate：

- Rich SemanticParse：2/3 结构/语义有效，平均 13.501 秒；
- Lean strict/non-thinking：1/3 结构/语义有效，完整投影 0/3，尽管平均延迟已降到 2.478 秒。

因此失败根因不是简单 Top K、Prompt 长度或思考时长，而是让一个开放式模型合同同时承担语义抽取、任务主次和产品路由裁决。继续调 Prompt 会追逐可见样本。

## 新边界

L1 只回答五个窄问题，并附 Query 原文字面证据：单条定位、近期动态集合、跨时间/实体结构、可核验主张、解释/比较。L2 才把这些事实映射为 A–E。

失败策略从“默认 E”改为 fail-closed：

- 未解析指代 → 澄清；
- 任一关键判断 uncertain → 澄清；
- 没有明确交付 → 澄清；
- 两个交付使用同一证据起点、主次无法判断 → 澄清。

## TDD

### Red

新增测试后，`rag.narrow_semantic_decisions_v1` 尚不存在，测试在收集阶段失败。

### Green

执行：

```bash
PYTHONPATH=.test-deps:. python3 -m pytest -q \
  rag/tests/test_narrow_semantic_decisions_v1.py \
  rag/tests/test_fast_query_path_v1.py \
  rag/tests/test_lean_task_atom_v1.py \
  rag/tests/test_lean_task_atom_strict_client.py
```

首次结果：

```text
39 passed in 0.14s
```

其中 12 条可见校准全部符合预期，并验证 B+D 与 D+B 的主次会随明确交付顺序变化。

## 第一次独立 Stage Gate

监管结论为 `CONDITIONAL`，发现四个阻断：L1 可伪造 Query、无效 confidence 不参与裁决、一个交付的多维表达会被误当多个交付、上下文 ATR 引用没有进入投影。

按最小复杂度修正：

1. 从 L1 Schema 删除 `original_query`，校验器必须接收调用方真实 Query；
2. 删除没有裁决价值的 `confidence`；
3. E 的证据片段若包裹/重叠更具体 A/B/C/D 交付，则视为表达方式而非独立路线；
4. 增加 `resolved_references`，严格验证字面指代、bare ATR ID 与公开上下文，并贯穿投影。

补强后执行窄合同、新旧 Fast/Lean、旧 Route v2 回归：

```text
84 passed in 0.21s
```

## 获批影子端到端投影

在最终 Narrow Decisions Gate 通过后，只按监管批准范围增加：

```text
L0 真实 Query
  → L1 可见 fixture
  → L2 窄判断投影
  → 完整 Route Contract v2 / clarification
```

验证点：

- 12 条 fixture 均生成 Schema + semantic 合法合同或明确 clarification；
- B+D / D+B supporting contracts 与任务顺序一致；
- `不要联网` 只能由真实 Query 推导并贯穿为 `forbidden`；
- 左右上下文指代只输出 bare ATR ID；
- L1 uncertain 时不得生成任何 Route Contract；
- 篡改上下文 ATR ID、删除 supporting contract 均被拒绝。

执行相关回归：

```text
97 passed, 28 subtests passed in 0.36s
```

本轮仍未证明 L0 到 L1 的泛化抽取能力，未调用 API、未扩展数据集、未创建盲测，也未接入正式链。

## 第二次端到端 Stage Gate 补强

监管复核端到端合同后发现三项缺口：禁网权限三字段不一致、关键标题/主题字面量未受保护、部分标题被误当精确导航。

最小修正：

- L1 增加 `protected_spans`，由真实 Query 校验并直接贯穿 Route Contract；
- L1 增加 `item_locator_precision = none / partial / exact`；partial 只能生成 `item_disambiguation`、低于 1 的置信度和明确歧义；
- 四种禁网表达同时满足 `web_permission=forbidden`、无 `web_requested`、并进入 protected terms。

新增退化测试后，相关回归：

```text
104 passed, 28 subtests passed in 0.43s
```

## 证据边界

这 12 条是可见校准和退化测试，只能证明合同内部一致、L2 可解释、失败可关闭；不能证明 L1 能从新 Query 泛化抽取这些判断，也不能当作 RAG 召回或最终回答质量。

“第一个证据片段决定主任务”当前只是透明、低成本的启动规则，不是永恒产品规则。下一阶段必须用未见的多任务 Query 检查：礼貌性前置语、从属句、否定句和“先给结论再补背景”等表达是否会让文本顺序偏离用户真正的主要交付。

## 仍禁止

- 不调用 DeepSeek；
- 不接正式 Query understanding、检索、Prompt Registry、聊天或 Web UI；
- 不创建新的正式盲测成绩声明；
- 不以 12/12 声称泛化完成。

## 2026-08-15 L0→L1 可见 Gate

新增真实 Query 公共 seam、DeepSeek strict/non-thinking adapter、一次语义纠错上限和完整合同评估器。所有调用均为可见校准，不是盲测。

结果：

| 运行 | 完整合同 | 平均延迟 | 最大延迟 | 结论 |
|---|---:|---:|---:|---|
| 三条 canary | 路线 3/3；复核发现保真外壳缺口 | 2.228s | 2.425s | 补强评分后继续 |
| 十二条首次校准 | 9/12 | 3.095s | 7.146s | FAIL |
| 通用确定性修复后十二条复测 | 11/12 | 2.116s | 4.690s | FAIL |
| `NSD-007` 定点复测 | 0/1 | 5.366s | 5.366s | FAIL |

连续失败项为“左右 ATR 条目 + 句内主张代词”的复合指代。当前候选被 REJECT：不得冻结、不得生成未见盲测、不得接生产。下一候选必须删除模型输出中的 protected/locator/reference 职责，只保留五维判断和逐字证据。

## 2026-08-15 dimensions-only L1 v2 替换进展

v2 已把模型输出缩减为五个语义维度，引用、locator、protected spans 和权限全部交回确定性 Query Facts。离线 12 条装配一致性通过，相关回归 79/79。

真实 Canary 特意改为 NSD-003、NSD-007、NSD-009，覆盖组合交付、此前连续失败的左右 ATR 引用，以及无上下文指代。结果 3/3，平均 1.744 秒、最大 2.263 秒，三条均一次生成合法 tool call。

该结果只证明固定可见 Canary 已通过；它不是不可见泛化证据。独立质量监管已调用但尚未在限定窗口返回，因此一次性 12 条可见校准仍等待 Gate 结论。

### 独立监管与一次性可见校准

独立监管最终返回 `REVISE`，但允许一次性运行 12 条真实可见校准作为诊断。结果为 12/12，平均 1.396 秒、最大 1.730 秒，12 条均一次输出合法 tool call，总计 14,076 tokens。

监管同时指出：fixture 12/12 只证明装配一致性；任意 Latin token 先行词捷径和无标签 ATR 顺序 fallback 可能误解析。两项均先补失败测试再移除，修正后聚焦回归 81/81。真实校准原始结果没有覆盖或重跑。

当前仍不宣称泛化或生产可用；下一 Gate 是冻结候选合同并创建由隔离 Agent 编写的全新不可见盲测。

### 冻结 Gate

第二次独立监管返回 `GO`，允许冻结和创建隔离盲测，仍禁止正式流量。已固定模型 Prompt、dimensions-only Schema、Query Facts、assembler、Narrow Decisions、L2 和评估器的 SHA-256；冻结清单为 `evals/dimensions-only-l1-v2-freeze-manifest-2026-08-15.json`。

### Blind 审计与 v2 STOP

原始评分为 0/15，但原 Gold 和评分器均违反既有标注合同，因此原 Blind Gate 无效。独立监管完成逐条裁决后，仅使用已封存 predictions 生成回顾性分数：主路线 64.3%、权限 35.7%、保真词 micro-F1 34.5%、澄清 precision 20%、完整合同 6.7%。

这批 Query 已永久解封为校准资产。v2 因模型维度重叠、确定性事实层职责过载、supporting A 硬异常与权限/澄清失真正式 `STOP`；不得在同一批 Query 上修复后重跑并重新声称 blind。
