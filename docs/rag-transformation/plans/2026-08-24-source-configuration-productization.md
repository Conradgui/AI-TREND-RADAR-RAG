# 2026-08-24 数据源配置产品化计划

## 产品目标

普通用户只配置一个模型 Provider 即可使用托管语料；进阶用户可以逐个启用自己的信息来源，系统自动完成抓取、规范化、摘要、ATR 编号、日报生成与后续索引。

## 当前证据

- `config.yml` 目前只管理 GitHub 仓库列表。
- 大多数抓取源硬编码在 `src/index.ts`，尚不能被统一配置控制。
- `Corpus Producer (self-managed)` 已能选择模型 Provider，但来源凭证主要依赖 GitHub Secrets，缺少统一状态与前置校验。
- Web UI 尚无真正控制生产管线的数据源配置接口，因此不能先做表面 GUI。

## 目标状态模型

每个来源使用三态配置：

- `auto`：条件满足时运行；缺少可选凭证时明确跳过。
- `enabled`：用户明确要求运行；缺少必要凭证时校验失败。
- `disabled`：不调用连接器。

## Stage Gate 1：两来源纵向小样

**状态：已通过（2026-08-24）。**

选择两个具有代表性的来源：

- Hacker News：无需凭证。
- Product Hunt：需要 `PRODUCTHUNT_TOKEN`。

验收：

1. 同一配置解析器输出 `ready / skipped / error / disabled` 状态；
2. 未激活来源的连接器不会被调用；
3. `pnpm sources:check` 给出人可读诊断并对错误配置返回非零退出码；
4. 自维护 GitHub Action 在抓取前执行同一校验；
5. 不改变默认托管语料同步路径，不影响 RAG 召回与现有日报格式。

## 后续阶段

仅在 Gate 1 通过后推进：

1. ~~将其余来源机械迁移到注册表；~~ **已完成：15 类现有非 GitHub 连接器已统一接入。**
2. 提供只暴露安全非密钥字段的后端配置接口；
3. 在 System 中增加数据源向导；
4. GitHub Secrets 继续通过 GitHub 原生安全界面配置，未来再评估 GitHub App/OAuth；
5. 做一次干净 Fork 的自维护定时生产验证。

自动运行编排已完成：`CORPUS_MODE` 保证托管与自维护计划任务互斥；自维护任务通过专用分支和自动 PR 发布。仍待完成的是干净 Fork 的真实 Secrets/权限验证。

## 已验证证据

- TypeScript 配置、唯一编号和搜索制品：58 项通过；
- Python Action、原子入库与 GraphRAG 合同：62 项通过；
- `pnpm sources:check` 真实运行：Hacker News `ready`，未配置 Token 的 Product Hunt 在 `auto` 模式为 `skipped`；
- GitHub Action 明确保证 `sources:check` 先于 `digest`。

GUI 暂不直接写 GitHub 配置：本地页面无法在没有 GitHub 授权的情况下修改云端仓库和 Secrets。后续 GUI 必须先明确采用“本地运行配置器”还是“GitHub App/OAuth 仓库配置器”，不能提供看似成功、实际不影响 Action 的假开关。

## 非目标

- 本阶段不新增数据源；
- 不重构日报、RAG 或 Prompt 路由；
- 不把 GitHub Token 存入浏览器；
- 不同时启用托管同步与自维护生产的定时任务。
