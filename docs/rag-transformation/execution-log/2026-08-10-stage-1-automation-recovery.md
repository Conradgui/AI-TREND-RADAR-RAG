# Stage 1 自动化与数据链路恢复执行记录

日期：2026-08-10
分支：`claude/rag-transformation-checkpoints`
状态：独立质量监管批准本地代码 Gate；云端激活待默认分支决策

## 目标与验证表

| 步骤 | 可验证目标 | 结果 |
| --- | --- | --- |
| CI 可复现 | 干净 runner 明确安装 Node 与 Python 测试依赖 | 通过 |
| 模式拆分 | 只有托管同步有 schedule；自维护生产器只手动运行 | 通过 |
| 权限最小化 | 默认只读，只有 publish job 申请 `contents: write` | 通过 |
| 语料合同 | 公开文件具备 schema、revision、checksum、size、complete | 通过 |
| 发布边界 | Pages 只上传 `_site` allowlist | 通过 |
| 失败诊断 | dry-run、结构化 JSON、日志 Artifact、新鲜度 warning | 通过 |
| 用户启用 | 文档列出默认/高级模式、Secrets/Variables 和默认分支限制 | 通过 |
| 真实上游 | 无写入 dry-run 能完整下载并判断幂等 | 通过 |

## 实现证据

### 1. 工作流与权限

- `RAG Corpus Sync` 是唯一计划任务，默认从公开 Pages 同步日报及可浏览的周/月报，不要求模型或新闻源 Secret。
- `Corpus Producer (self-managed)` 仅支持手动运行；先做 Provider Secret preflight，默认 `publish=false`。
- Daily、Weekly、Monthly 旧生产器保留但改为手动，避免两条生产链路同时定时写入。
- CI 与同步工作流显式安装各自所需 Python 测试依赖。
- 所有官方 Actions 引用固定为核验过的 40 位 commit SHA，避免可移动 tag 产生供应链漂移。
- Pages 是可复用 workflow；托管与自维护模式都只有真实 publish job 成功后调用，dry-run 不部署。脚本只复制首页、清单、RSS、搜索索引和按日期公开制品。
- 所有可能写语料的 publish job 共用 `corpus-publish` 互斥组，且不取消已经开始的发布。
- 自维护模式在 `publish=true` 时锁住“生成→校验→发布”完整事务，并记录起始 commit；默认分支中途变化会明确失败并要求重跑，不允许旧 Artifact 覆盖新语料。
- CI 从官方 release 下载固定 `actionlint 1.7.12`，校验 SHA-256 后执行，workflow 语法检查可在干净 runner 复现。

### 2. 语料与发布合同

- 新增 `corpus-manifest.json`：`schema_version=1`、deterministic revision、每个文件 SHA-256、大小、content type、`retrieval_eligible` 与 `complete=true`。
- 日报 Markdown 与 topic pool 标记为可检索；Weekly、Monthly 等 rollup 只浏览、不进入 RAG。
- 同步端拒绝路径穿越、非法 report name、超过 10 MB 的单文件、坏 JSON 与空 Markdown。
- 下载阶段先完成整批校验再写入；单文件使用临时文件 + `os.replace` 原子替换，失败保留最后好版本。
- dry-run 输出机器可读诊断；上游超过 3 天未更新时产生 GitHub warning，但不因周末或正常停更直接破坏同步。
- RSS 与报告、搜索索引属于同一批同步事务；`feed.xml` 会校验 XML 后原子写入，避免页面语料已更新但订阅仍停留在旧日期。
- 只有日报 Markdown 与 topic pool 参与检索日期指纹；周报/月报变化可更新浏览制品，但不会误触发日报向量重建。
- 语料合同会重算 revision，并拒绝未知来源模式、重复路径、空合同、缺失必需公开文件和非法字段类型。
- Pages 构建使用只读 `--check-existing`：现存合同必须与实时公开 allowlist 完全相等，合同外多一个公开文件也会阻断发布。
- 网络读取在 10 MB + 1 byte 处停止，避免先把任意大响应完整读入内存。

### 3. 用户路径

- `README.md` 不再要求普通用户部署上游项目。
- `docs/github-automation.zh.md` 给出默认托管、自维护数据源、Secrets、Variables、Actions 手动验证和故障定位。
- 明确说明：本地 `.env` 不会上传到 GitHub；本地 Web UI 当前不索取 GitHub 写权限或管理仓库 Secrets。

## 红灯—绿灯记录

1. CI 契约红灯：缺少 `permissions: contents: read` → 增加最小只读权限 → 通过。
2. Pages 集成红灯：`web-state.json` / `.DS_Store` 被发布 → 改为显式 allowlist builder → 通过。
3. gitlink 契约红灯：缺 `.gitmodules` → 登记 `project-verifier-skill` 的固定上游地址 → 通过。
4. 同步 workflow 契约红灯：干净 runner 直接调用 pytest → 增加轻量 pytest 安装步骤 → 通过。
5. 诊断契约红灯：没有结构化 freshness 结果和 Artifact → 增加 JSON、日志与非阻断告警 → 通过。
6. 监管复核红灯：dry-run 也会触发 Pages、自维护发布不触发 Pages → 改为发布成功后调用共享部署 workflow → 通过。
7. 监管复核红灯：周/月报未持续同步 → 同步供浏览并保持 `retrieval_eligible=false` → 通过。
8. 第二轮监管红灯：RSS 未进入同步事务 → 纳入同步计划、XML 校验、原子写入与 publish staging → 通过。
9. 第二轮监管红灯：周/月报变化进入日期指纹 → 指纹和 `changed_dates` 只接受日报检索制品 → 通过。
10. 第二轮监管红灯：Pages 可被独立手动部署，旧生产器可绕过合同 → Pages 改为纯复用 workflow，所有旧生产器生成并提交合同后才调用共享部署闸门 → 通过。
11. 第三轮监管红灯：自维护 Artifact 可能覆盖并发的新语料 → 完整事务并发锁 + 起始 commit 校验 + 提交前重建合同 → 通过。
12. 第三轮监管红灯：陈旧合同仍可能携带合同外文件发布 → 增加 exact contract validation，并在 Pages 构建前强制执行 → 通过。
13. 第三轮监管红灯：workflow 测试可能字符串假绿、CI 不运行 actionlint → 引入 YAML job 图断言，CI 固定版本与 checksum 安装 actionlint → 通过。
14. 监管 P2：legacy 顶层写权限会被通知 job 继承 → 顶层降为只读，仅 producer job 获得所需写权限 → 通过。

## 验证快照

| 检查 | 结果 |
| --- | --- |
| `actionlint .github/workflows/*.yml` | 通过 |
| workflow + release contracts | 21/21 通过 |
| release package contracts | 11/11 通过 |
| corpus contract focused | 5/5 通过 |
| corpus sync focused | 17/17 通过 |
| `pnpm rag:check:p0` | 242 unittest + 36 pytest 通过 |
| `pnpm test` | 228/228 Vitest 通过 |
| `pnpm lint` | 通过 |
| `pnpm typecheck` | 通过 |
| `pnpm format:check` | 通过 |
| `git diff --check` | 通过 |
| 真实托管同步 + 二次 dry-run | `downloaded=63`、`failed=0`、`changed_files=-`、`changed_dates=-` |
| 新鲜度诊断 | upstream/local `2026-08-10`，age `0`，`fresh` |
| RSS 新鲜度 | 最新日期 `2026-08-10`，与语料最新日期一致 |
| 语料合同 | revision `d0615bade31433c66f079ff10f274e7d9fc6cf0a42a7f35d8ddf34afad69b6dc`，160 files，通过 |

## 环境发现

当前父目录名包含英文冒号：`Graph RAG :claude`。pnpm 运行脚本时会把含冒号的绝对 PATH 拆开，导致已安装的 `eslint` 等显示 `command not found`；使用相对 `./node_modules/.bin` 注入 PATH 后，真实检查全部通过。GitHub runner 和正常克隆目录不受此本机路径问题影响。

## 尚未宣称完成的事项

1. 定时任务尚未云端上线，因为 workflow 仍只在 Claude 功能分支；GitHub 只为默认分支注册 schedule。
2. 尚未在 GitHub Actions UI 从默认分支执行一次 `dry_run=true` 和一次真实 publish。
3. 站内条目搜索、深链、RAG 指标提升和 UI 重构属于 Stage 2–4，不以本阶段测试替代。

## 独立质量监管结论

- 最终结论：批准 Stage 1 本地代码 Gate。
- 阻断项：P0 = 0，P1 = 0。
- 非阻断 P2：CI 的 push 分支过滤仍假设默认分支为 `main`；陈旧生产快照保护已有独立反例验证，但还可补充更直接的 workflow 回归断言。
- 监管 Agent 独立复跑了合同、同步、工作流、release、Python、前端与 actionlint，并确认审计前后没有修改工作树。

## Gate 决策

Stage 1 的代码、合同、文档和本地真实上游验证已通过独立监管，满足本地代码 Gate。下一步需要 Conrad 明确决定何时把经过审查的工作流进入默认分支；在此之前可以继续 Stage 2 的本地开发，但不能声称每日云端自动化已生效。

## Draft PR 云端 CI 复核

- Stage 1 checkpoint `b3d9ca1` 已推送到 `claude/rag-transformation-checkpoints`，并创建 Draft PR #1；未合并或直接修改 `main`。
- PR CI run `31363767006` 在安装 actionlint 阶段失败，后续 lint/test 均被跳过；这不是产品测试失败。
- 真实根因有两项：release asset 架构名误写为 `linux_x86_64`（官方为 `linux_amd64`），且 SHA-256 误用了 `darwin_arm64` 归档。
- 新增 workflow 合同回归断言后先得到 1 个失败、9 个通过；修复资源名与 SHA 后得到 10/10 通过。
- 从 actionlint 官方 GitHub Release 下载 `actionlint_1.7.12_linux_amd64.tar.gz` 后，本地实测 SHA-256 为 `8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8`，与 workflow 固定值一致。
- 该失败说明原本“固定版本 + checksum”的方向正确，但本地 Gate 缺少对远端 asset 名称与平台 checksum 配对的直接断言；现已补齐。
- 修复 actionlint 后，PR CI run `31364395731` 已通过 actionlint、lint、format、typecheck 与 224 个 Vitest，但在 RAG P0 导入 `rag.sync_corpus` 时失败。
- 第二次失败根因是 Python 版本兼容性：`summary.replace('|', r'\|')` 被直接写在 f-string 表达式内；本机 Python 3.12 可解析，但 CI 的 Python 3.11 明确报 `f-string expression part cannot include a backslash`。
- 已用本机真实 Python 3.11 先复现红灯，再把转义计算移到 f-string 外；随后 Python 3.11 编译通过、17/17 同步测试通过、21/21 发布契约通过，完整 `pnpm rag:check:p0` 重新达到 242 unittest + 36 pytest 全绿。
- 该问题暴露出本地默认解释器高于项目 CI 最低版本时的兼容性盲区；后续发布 Gate 必须保留 Python 3.11 云端检查，不能仅依赖开发机高版本解释器。
