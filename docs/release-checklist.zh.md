# 发布检查清单

## 发布前

- [ ] `.env`、日志、数据库卷和 Provider key 没有被提交。
- [ ] `docker compose config` 能在一个填好本地 `.env` 的干净目录通过。
- [ ] `docker compose up -d --build` 后，`/health` 返回成功。
- [ ] 新用户路径已验证：克隆 → 双击配置向导 → 粘贴 key → 打开 8001 → 发送一个 Agent 问题。
- [ ] `pytest rag/tests -q` 通过；针对 UI/发布包至少跑 README 中列出的回归测试。
- [ ] README 的安装命令、文档链接、LICENSE、SECURITY、CONTRIBUTING 均存在且可读。
- [ ] 不存在把“联网搜索线索”伪装成内部日报证据的展示问题。

## 发布后

- [ ] 在 GitHub 页面检查 README 首屏是否清楚传达：面向谁、能解决什么、三分钟如何开始。
- [ ] 使用新 clone 的目录验证 Docker 卷不会与其他同名项目容器冲突。
- [ ] 为首个 Issue/Discussion 准备排错信息：系统版本、`docker compose ps`、脱敏后的 app 日志。
