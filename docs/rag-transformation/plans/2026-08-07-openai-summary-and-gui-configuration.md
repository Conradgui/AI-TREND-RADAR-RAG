# OpenAI 摘要质量与 GUI 配置中心计划

日期：2026-08-07

> 官网采集部分已由 `2026-08-07-general-official-source-acquisition.md` 泛化；本文继续保留 OpenAI 回归样本和 GUI 安全边界。
>
> 复核后调整：摘要修复不与 GUI 配置中心绑定实施，也不新建复杂摘要系统。摘要执行基线见 `2026-08-07-summary-system-reassessment.md`；GUI 仍作为后续独立 Stage。

## 已确认事实

1. 2026-08-05 日报中三条 OpenAI 记录的摘要字段为空，前端没有隐藏正文。
2. `src/web.ts` 将 OpenAI 配置为 `metadataOnly: true`，只从 sitemap 获取 URL、从 slug 推断标题，并固定写入空 `content`。
3. `src/topic-radar.ts` 直接把 `item.content` 写入选题的 `summary`，因此空值进入日报。
4. OpenAI 官方 RSS 已为三条记录提供标题、发布日期、分类和 description；官方文章页也包含正文。
5. Economic Research Exchange 首次发布于 2026-06-08、在 2026-08-05 更新；当前产物没有区分“新发布”和“旧文更新”。

## 修复设计：官方 RSS 优先的多级降级

OpenAI 采集不再是“只取 sitemap 元数据”或“强行抓全文”的二选一：

1. 官方 RSS：优先提供标题、摘要、发布日期和分类。
2. 官方 sitemap：补充 RSS 覆盖窗口外的新 URL 与完整发现范围。
3. 官方页面 metadata：RSS 未命中时尝试 `description`、OpenGraph 或 JSON-LD。
4. 正文提取：仅在页面可达且提取可信时使用，不作为 GitHub Actions 成功的硬依赖。
5. 质量降级：仍无摘要时保留空值，但记录 `summary_status=missing`，并在工作流质量报告中明确计数。

不允许根据 URL 标题让 LLM猜测文章内容；摘要必须来自官方 description、官方正文或有来源标识的模型压缩结果。

数据模型同时保留 `published_at` 与 `updated_at`；旧文章发生更新时标记为“更新”，不伪装成当天新发布。

## GUI 配置中心

### 页面结构

System 面板增加“配置中心”入口，采用四步向导：

1. 运行方式：官方托管语料 / 自主管理数据源。
2. 本地模型：Provider、Base URL、模型、API Key 连通性测试。
3. 检索能力：联网搜索 Provider、自动/始终/关闭、深度抓取。
4. 自动化：展示 GitHub Actions 状态、缺失的 Variables/Secrets 和 GitHub 官方设置页入口。

### 安全边界

- 本地密钥只提交给 `127.0.0.1` 后端并写入被 Git 忽略的 `.env`；界面不回显完整值。
- 静态 Pages 不提供本地密钥表单，避免把秘密发送到错误站点。
- GitHub Secrets 不经过本项目后端；用户在 GitHub 官方 GUI 中填写。
- 第一版不要求 GitHub PAT，不用高权限令牌换取表面上的“一键完成”。

### 模式切换

- 本地配置使用 `RADAR_DATA_MODE=managed|self-hosted`。
- GitHub Actions 使用同名 Repository Variable。
- GUI 显示两处是否一致；不一致时给出明确修复入口，不静默覆盖云端设置。

## 验证表

1. OpenAI RSS 解析 → 验证：三条已知 URL 均得到非空官方摘要。
2. RSS + sitemap 合并 → 验证：URL 规范化后不重复，RSS 字段优先。
3. 发布/更新语义 → 验证：Economic Research Exchange 保留 6 月 8 日发布日期，并标记 8 月 5 日更新。
4. 降级策略 → 验证：页面抓取失败不阻断日报；空摘要被计入质量报告。
5. 日报生成 → 验证：已知三条记录摘要列非空，且内容来自官方 RSS。
6. 本地 GUI → 验证：新用户不编辑代码即可完成 Provider 与模式配置。
7. 静态安全 → 验证：Pages 模式不展示可提交密钥的表单。
8. GitHub 引导 → 验证：GUI 能列出缺失配置并打开正确的 GitHub Variables/Secrets 页面。

## Stage Gate

- Gate 1：确认 OpenAI 使用“RSS 优先、sitemap 补全”的采集策略。
- Gate 2：确认 GUI 采用“本地配置 + GitHub 官方 GUI 管理云端 Secrets”的安全边界。
- Gate 3：先测试后实现采集修复并回填受影响日报。
- Gate 4：实现配置中心与端点，完成浏览器和干净环境验证。
