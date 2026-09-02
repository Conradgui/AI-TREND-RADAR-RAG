# 新手启用指南

这份指南只适用于 **AI Trend Radar RAG**：它默认消费已发布的公开日报，提供本地检索与 Agent 问答。普通用户只需部署这一个仓库；高级维护者还可以选择在本仓库运行自维护语料生产流程。

第一次使用不要配置新闻源 API：默认托管语料模式不需要它们。等本地体验稳定后，再按[GitHub 自动化与语料模式](github-automation.zh.md)选择是否维护自己的来源。

## 第 0 步：只准备两样东西

1. 安装并启动 [Docker Desktop](https://www.docker.com/products/docker-desktop/)。
2. 准备一个模型 Provider 的 API Key（DeepSeek、Anthropic 或 OpenAI；首次体验推荐 DeepSeek）。

不需要安装 Python、Node.js、Neo4j 或 pnpm。

## 第 1 步：克隆项目

```bash
git clone https://github.com/Conradgui/AI-TREND-RADAR-RAG.git
cd AI-TREND-RADAR-RAG
```

如果你是在功能分支试用，请把上面命令中的分支替换为维护者明确提供的分支名；日常用户应使用默认分支的稳定版本。

## 第 2 步：双击配置并启动

| 系统 | 操作 |
| --- | --- |
| macOS / Linux | 双击 `setup.command`。若 macOS 拦截，在终端执行一次 `chmod +x setup.command && ./setup.command`。 |
| Windows | 双击 `setup.bat`。 |

向导会让你选择 Provider、粘贴 API Key，并自动生成本地 Neo4j 密码。它会创建 `.env`，该文件只保留在你的电脑上，已被 Git 忽略。Docker Desktop 未运行时，macOS 启动器会尝试打开并等待它就绪。

首次启动会下载镜像、预热检索模型，并在后台同步和建立索引。完成后访问 [http://127.0.0.1:8001](http://127.0.0.1:8001)。

## 第 3 步：验证第一次体验

1. 从左栏打开最新日期，确认日报正文与原始摘要可以浏览。
2. 打开 `AGENT`，提问：“最近三天有哪些值得关注的 AI 产品趋势？”
3. 观察回答下方的引用；内部语料与联网搜索得到的外部内容会分组标记。侧边栏支持条目级关键词/模糊搜索和组合筛选，点击结果可直接进入条目详情，并可从详情精确定位回原日报；它不等同于只按日期聚焦报告。

首次索引期间，System 面板会显示“语料同步中”。页面可以正常浏览，Agent 只会基于已经建立的证据回答；这不是页面卡死。

## 日常使用与排错

- 以后启动：双击 `start.command`（macOS/Linux）或 `start.bat`（Windows），它会复用现有镜像与数据，不会重建。
- 拉取新版本或修改代码后：双击 `update.command`（macOS/Linux）或 `update.bat`（Windows），才会重新构建应用镜像；不会删除数据卷。
- 暂停服务但保留数据：`docker compose stop`。
- 查看启动/同步日志：`docker compose logs -f app`。
- 更换 Provider、开启联网搜索或了解安全边界：阅读[配置说明](configuration-rag.zh.md)。
- 遇到端口、页面、Agent 或数据库问题：阅读[故障排除](troubleshooting-rag.zh.md)。

## GitHub 自动化的分支边界

本仓库的 `RAG Corpus Sync` 工作流会在**默认分支**上按日拉取上游公开日报并提交可审计语料；这是 GitHub 定时工作流的运行规则。新工作流尚未进入默认分支时，通常不会出现在 Actions 的手动运行入口；功能分支应先靠本地测试和 PR 检查验证。

因此，发布流程是：先在功能分支完成代码审查和干净克隆验证，再合并到默认分支；合并后才激活每日同步与当前配置下的 GitHub Pages 发布。

默认同步不需要 Secrets。若要生成自己的日报，请使用独立的 `Corpus Producer (self-managed)` 手动工作流，并按[自动化指南](github-automation.zh.md)配置对应 Provider Secret；周报和月报只供页面浏览，不进入 RAG 索引。
