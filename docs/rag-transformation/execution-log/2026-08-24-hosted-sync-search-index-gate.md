# 2026-08-24 Hosted Sync → ATR Search Index Gate 执行记录

## 本阶段边界

- 只修复 hosted GitHub Actions 的公开语料同步、规范化、浏览搜索索引和 corpus contract 发布闸门。
- 未连接 Docker、Chroma 或 Neo4j；未恢复自动入库；未修改 ATR 编号算法或其他业务代码。
- 实际修改限于 workflow、workflow 合同测试、搜索索引生成器的失败关闭边界、对应测试和本执行记录。

## TDD 证据

1. 基线：使用仓库已有 `.venv` 运行原合同测试，`10 passed`。
2. RED：先加入 P0 合同断言、尚未修改 workflow 时，`3 failed, 9 passed`；失败分别暴露完整 Python 依赖、publish Node/pnpm 依赖和 hosted contract 边界缺口。
3. 二次 RED：Terra 发现结构合法但内容结构错误的 `topic-pool.json` 会被静默当作空数组；新增生成器合同测试后为 `2 failed, 15 passed`。
4. GREEN：生成器对非法 JSON、缺少 `candidates`、非数组 `candidates` 全部失败关闭；生成器测试为 `18 passed`，workflow 合同测试为 `12 passed`。

## 实现结果

- validate runner 只安装合同测试实际需要的 `pytest` 与 `PyYAML`，避免下载无关 RAG 运行时依赖。
- publish runner 使用仓库现有 immutable action SHA，设置 Node 22、读取 `package.json` 的 `pnpm@9.15.9`，并执行 `pnpm install --frozen-lockfile`。
- `rag.sync_corpus` 之后依次执行 `pnpm manifest`、`python -m rag.corpus_contract --source-mode hosted`，之后才允许 `git add`/commit。
- 合同测试锁定依赖安装、顺序、提交制品和不触碰本地 RAG 的边界。
- `generateSearchIndex(...)` 不再把非法 topic pool 当成零候选：语法错误或结构错误都会以异常终止发布；合法的空数组仍可生成空日语料。

## 验证

- `.venv/bin/python -m unittest rag.tests.test_sync_corpus`：`17 tests OK`。
- `pnpm exec vitest run src/__tests__/generate-manifest.test.ts`：`18 passed`。
- YAML 解析：通过。
- `git diff --check`：通过。
- 本机未安装 `actionlint`，因此未执行 actionlint；immutable-SHA 合同测试已随 12 项测试通过。

## 临时语料真实链路

为避免覆盖正式仓库制品，将现有 `digests/` 复制到 `/tmp/atr-hosted-gate.VUn6bI`，实际运行与 publish job 相同的生成和合同步骤：

1. `generate-manifest.ts`：生成 `64` 个日期、`30` 个 feed 条目；将 `3558` 条候选规范化为 `3550` 个独立搜索文档。
2. `corpus_contract.py --source-mode hosted`：生成包含 `160` 个公开文件的合同，revision 为 `5f8d3620e87d8df349408ff2a4955cec777a2970f504d1dc4432b80ca7cd44b7`。
3. `corpus_contract.py --check-existing`：同一 revision 校验通过。
4. 编号校验：`3550/3550` 个文档均有唯一 `daily_item_id`，非法 ATR 编号 `0` 个；格式为 `ATR-YYYYMMDD-XXXXXX`。

这证明的是 GitHub hosted 公开语料制品链路；没有宣称本地 Chroma/Neo4j 已同步。

## 残余风险

- 未在 GitHub 托管 Runner 上实际触发 workflow；本地临时目录验证覆盖了相同的生成器与 corpus contract 命令，但 GitHub 权限、网络和 push 仍需首次真实 Action 运行证明。
- 尚不能据此声称 Chroma/Neo4j 已更新；本阶段只闭合 hosted 公开制品链路。

## Stage Gate 结论

Terra 质量监管复核结论：`SHIP`。

- 非法 JSON 与结构非法 topic pool 均已失败关闭。
- `sync → manifest → hosted contract → commit` 顺序成立。
- 临时目录真实制品、ATR 唯一性和合同 revision 已被独立复核。
- 唯一残余风险是尚未在 GitHub 托管 Runner 上完成首次真实发布；首次 Action 仍需观察网络、权限与 push 结果。
