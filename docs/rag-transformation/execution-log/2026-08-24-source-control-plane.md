# 信息源控制平面执行记录

## 本轮目标

把现有抓取器纳入一套可验证的配置规则，并复核 GitHub Action 生成内容能否逐条获得 ATR 编号并进入浏览、向量和图谱管线。

## 完成项

- 新增 `auto / enabled / disabled` 三态来源合同；
- 15 类现有非 GitHub 连接器全部接入统一注册表；
- 未启用来源不调用连接器；未知来源名和非法模式直接失败；
- 新增 `pnpm sources:check`，并在自维护 Action 的付费生成前执行；
- 以 `CORPUS_MODE` 让托管与自维护定时任务互斥；默认托管，自维护需显式启用；
- 自维护自动发布改为专用语料分支 → PR → 合同校验后自动合并，不直接推默认分支；
- 更新用户文档，明确托管/自维护边界与 GitHub Secrets 安全边界；
- 修复首页缓存策略，防止部署更新后浏览器长期显示旧按钮。

## 验证

- TypeScript：58 项通过；
- Python：62 项入库/GraphRAG测试通过，15 项工作流合同复核通过；
- CLI 真实预检：Hacker News ready；Product Hunt 无 Token 时按 auto 跳过；
- `git diff --check`：通过。

## 未做与原因

- 未把 GitHub Secrets 写入本地 Web UI：会扩大权限与泄密风险；
- 未提供“本地开关即修改云端 Action”的假能力：需要 GitHub App/OAuth 或明确的提交工作流；
- 未新增来源、未修改摘要、路由、Prompt 或 RAG 排序。
