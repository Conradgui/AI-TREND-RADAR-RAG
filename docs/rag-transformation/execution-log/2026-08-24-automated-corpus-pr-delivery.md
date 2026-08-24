# 2026-08-24 Automated Corpus PR Delivery 执行记录

## 本阶段边界

- 将 hosted 语料发布出口改为 `automation/corpus-sync → PR → robot merge → Pages`。
- 本地阶段未创建真实 PR；首次 GitHub Runner 验证安排在发布收敛 Gate 3。
- 未连接或修改本地 Docker、Chroma、Neo4j。

## TDD 证据

1. RED：新增 workflow 合同后为 `1 failed, 12 passed`，证明旧 workflow 缺少专用分支、PR 权限和合并状态 Gate。
2. GREEN：实现最小 PR 发布出口后，workflow 合同为 `13 passed`。
3. 回归：sync corpus `17 tests OK`；manifest/search-index `18 passed`；`git diff --check` 通过。

## 实现结果

- 固定专用语料分支 `automation/corpus-sync`，并沿用已有 publish concurrency。
- 同步、规范化、ATR 编号和 corpus contract 全部完成后才提交。
- 无变化时输出 `changed=false`，不推分支、不创建空 PR。
- 有变化时只向专用分支 `HEAD:$CORPUS_UPDATE_BRANCH` 推送，再创建或复用 PR。
- 机器人执行 squash merge，并用 `--match-head-commit` 绑定本轮已通过门禁的 commit SHA；只有读取到 PR 状态为 `MERGED` 并输出 `merged=true` 后 Pages 才能继续。
- 无变化时不创建空 PR，也不重复部署 Pages。
- publish job 权限为 `contents: write` 与 `pull-requests: write`；仓库默认 workflow 权限保持只读。

## 仓库设置审计

- 默认分支：`main`。
- 仓库：public。
- main 分支保护：未启用。
- rulesets：无。
- Actions 默认权限：`read`。
- GitHub 将“允许 Actions 创建/批准 PR”合并为 `can_approve_pull_request_reviews` 设置；用户已明确授权长期权限变更，现已通过仓库 API 设置并复核为 `true`。
- `allow_auto_merge`：当前为 `false`，但本实现使用测试后立即机器人合并，不依赖 GitHub 延迟 auto-merge 设置。

## 待真实 Runner 验证

workflow 进入默认分支后，先手动触发 `dry_run=true` 验证只读同步，再触发一次正式发布路径验证专用分支、PR 与合并门禁。通过前不宣称自动语料发布已完全闭环。

## Stage Gate 结论

Terra 复核结论：`SHIP`。

- 无变化、有变化、已有 PR、PR 头漂移和合并失败路径均已失败关闭。
- Pages 只在本轮 PR 确认为 `MERGED` 后运行。
- 仓库权限前置条件已闭合；唯一未闭合证据是真实 GitHub Runner 上的 `gh pr merge` 行为。
