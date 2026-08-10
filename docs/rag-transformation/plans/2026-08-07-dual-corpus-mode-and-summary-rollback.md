# 双语料模式与摘要回滚计划

日期：2026-08-07

## 目标

1. 恢复日报 Markdown 原始摘要呈现，不再由前端折叠、替换或补写摘要。
2. 为开箱即用与自主管理数据源设计两种生产模式，同时保持同一套校验、入库和浏览链路。

## 产品边界

- 默认托管模式：从官方 AI-TREND-RADAR Pages 单向同步已发布报告；新用户无需配置采集 API。
- 自建生产模式：在本仓库运行已有 TypeScript 采集器；用户通过 GitHub Secrets 配置 LLM 与可选数据源 API。
- 日报进入向量与图谱索引；周报、月报只供浏览。
- 两种模式最终必须产出相同的报告目录和 manifest 契约，RAG 不感知上游来源差异。

## 切换机制候选

### A. 注释/取消注释 workflow 代码

优点是直观；缺点是用户必须修改代码，会制造 fork 差异、合并冲突和错误缩进，维护成本高。

### B. GitHub Repository Variable（推荐）

设置 `RADAR_DATA_MODE=managed` 或 `self-hosted`，workflow 根据变量选择同步或自产。用户只改仓库设置，不改代码；后续升级仍可直接合并。

## 验证表

1. 摘要回滚 → 验证：HTML 中不存在摘要折叠控件，Markdown 摘要原样显示。
2. 模式契约设计 → 验证：两种模式输出同一 manifest 与 digests 结构。
3. 默认模式 → 验证：无数据源 Secrets 时仍可同步并发布。
4. 自建模式 → 验证：缺少必需 Secrets 时预检明确失败；配置完整时可生成日报。
5. 入库边界 → 验证：日报被索引，周报/月报被排除。

## Stage Gate

- Gate 1：摘要回滚测试通过。
- Gate 2：确认使用 Repository Variable，而非编辑 workflow 注释。
- Gate 3：实现双模式 Actions、预检和文档。
- Gate 4：在干净 clone 中分别验证默认模式与自建模式配置路径。

