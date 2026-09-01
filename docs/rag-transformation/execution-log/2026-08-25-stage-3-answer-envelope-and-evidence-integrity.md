# Stage 3：单次生成、Answer Envelope 与证据完整性执行记录

- 日期：2026-08-25
- 状态：Gate 通过
- 范围：Direct Composer 输出合同、证据校验与确定性展示；未调用真实模型、未重建 Docker

## 已实现合同

- Direct Composer 只允许一次模型调用；
- 模型必须输出 `answer-envelope/1.0` JSON 对象；
- `body_markdown` 是面向用户的正文，UI 不展示原始 JSON；
- `evidence_ids` 必须与正文 `[E#]` 首次出现顺序完全一致；
- 未知、重复、缺失或错序证据编号均被拒绝；
- 正式 C 类路线必须引用已检索到的必需 Graph 证据；
- 非法 JSON、代码围栏、覆盖不足均确定性 fail-closed；
- 不调用第二个模型修复格式或引用。

## Gate 中发现并修复的阻断

1. `temporal_relation_exploration` 未纳入必需图证据任务族；已补齐并新增正式路由回归。
2. JSON 代码围栏曾被宽松剥离；已改为严格拒绝。
3. 重复 `evidence_ids` 曾被静默去重；已改为显式报错并拒绝。

## 验证证据

```text
851 passed, 36 subtests passed in 6.39s
python -m compileall -q rag: PASS
git diff --check: PASS
独立质量监管关键 Gate: 64 passed, 3 subtests passed, PASS
```

## 证据边界与下一阶段

- 已证明：机器包络、证据账本、Markdown 展示与一次生成在测试 seam 中闭环。
- 尚未证明：真实 DeepSeek 是否稳定遵守 JSON 合同及各路线真实耗时。
- 下一阶段：分路线总预算、阶段事件、超时/取消指标和阻塞 I/O 边界。
