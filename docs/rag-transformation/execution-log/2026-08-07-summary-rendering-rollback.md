# 摘要呈现回滚执行记录

日期：2026-08-07

## 现象

日报摘要列出现空白单元格却显示“展开摘要”，短摘要也出现无效果按钮。

## 根因证据

- Git 历史显示摘要折叠 CSS/JavaScript 由 `af80285` 引入，最初页面没有摘要专用 DOM 改写。
- `digests/2026-08-05/ai-topic-radar.md` 中 Apple、OpenAI Economic Research Exchange、Codex 三条记录的摘要字段本身为空。
- 因而存在两个独立问题：前端假交互，以及上游采集未生成摘要。

## 本次改动

- 删除摘要行数限制、包装节点和展开/收起按钮。
- 保留表格横向滚动与阅读密度控制。
- 增加回归测试，禁止前端再次替换 Markdown 摘要。

## 验证

- 红灯：新增测试在旧实现上因存在“展开摘要”而失败。
- 绿灯：`rag/tests/test_dashboard_readability.py` 与 `rag/tests/test_dashboard_same_origin.py` 共 18 项通过。

## 未混入本次修复的后续问题

空摘要属于报告生产质量问题，应在采集/生成阶段校验与降级，不应由展示层猜测或伪造内容。

