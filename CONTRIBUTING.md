# 贡献指南

感谢您对 AI Trend Radar RAG 项目的关注！我们欢迎各种形式的贡献。

## 如何贡献

### 报告 Bug

1. 在 [GitHub Issues](https://github.com/Conradgui/AI-TREND-RADAR-RAG/issues) 中搜索是否已有类似问题
2. 如果没有，创建一个新的 Issue
3. 使用 Bug 报告模板，提供尽可能详细的信息

### 提出新功能

1. 在 [GitHub Issues](https://github.com/Conradgui/AI-TREND-RADAR-RAG/issues) 中提出新功能建议
2. 说明功能的使用场景和预期效果
3. 等待社区讨论和维护者反馈

### 提交代码

1. **Fork** 仓库
2. **创建** 特性分支：`git checkout -b feature/your-feature`
3. **提交** 更改：`git commit -m 'Add some feature'`
4. **推送** 到分支：`git push origin feature/your-feature`
5. **创建** Pull Request

## 开发环境

### 前置条件

- Docker Desktop（运行完整本地 RAG 栈）
- Python 3.11+（修改 `rag/` 并运行 Python 测试时需要）
- Node.js / pnpm（仅修改上游日报生产流水线或运行前端工程检查时需要）

### 设置开发环境

```bash
# 1. 克隆仓库
git clone https://github.com/Conradgui/AI-TREND-RADAR-RAG.git
cd AI-TREND-RADAR-RAG

# 2. 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 3. 安装 RAG 开发依赖
pip install -r rag/requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 添加API密钥

# 5. 启动数据库和开发服务器
docker compose up -d neo4j
python -m rag.server
```

### 运行测试

```bash
# Python测试
pytest rag/tests/

# 只有改动上游生产流水线时才需要 TypeScript 测试
pnpm test

# 完整检查
pnpm rag:check:p0
```

## 代码规范

### Python

- 遵循 PEP 8 规范
- 使用类型注解
- 编写文档字符串
- 保持函数简短（<50行）

### TypeScript

- 遵循 ESLint 规范
- 使用 TypeScript 类型
- 编写 JSDoc 注释

### 提交信息

使用 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```
<type>(<scope>): <subject>

<body>

<footer>
```

类型：
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式
- `refactor`: 重构
- `test`: 测试
- `chore`: 构建/工具

## Pull Request 规范

### PR 标题

使用与提交信息相同的格式：

```
feat(agent): add context-aware agent entry
```

### PR 描述

包含以下内容：
1. **问题描述**：这个 PR 解决了什么问题？
2. **解决方案**：如何解决的？
3. **测试**：如何验证的？
4. **截图**：如果有 UI 变更，提供截图

### PR 检查清单

- [ ] 代码符合规范
- [ ] 测试通过
- [ ] 文档更新
- [ ] 无安全漏洞
- [ ] 无性能问题

## 代码审查

### 审查标准

1. **功能正确**：代码实现了预期功能
2. **代码质量**：代码清晰、可维护
3. **测试覆盖**：有足够的测试
4. **安全性**：无安全漏洞
5. **性能**：无性能问题

### 审查流程

1. 维护者审查代码
2. 提出改进建议
3. 贡献者修改代码
4. 维护者批准合并

## 社区准则

### 行为准则

- 尊重他人
- 建设性讨论
- 包容不同观点
- 避免人身攻击

### 沟通方式

- GitHub Issues：报告 Bug、提出建议
- GitHub Discussions：社区讨论
- Pull Requests：代码贡献

## 许可证

本项目采用 MIT 许可证。贡献代码即表示您同意将代码以 MIT 许可证发布。

## 致谢

感谢所有贡献者的付出！

---

**[⬆ 回到顶部](#贡献指南)**
