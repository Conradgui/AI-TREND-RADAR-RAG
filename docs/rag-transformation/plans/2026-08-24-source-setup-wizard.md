# 数据源配置向导实施计划

## 目标

让首次部署用户在 Web UI 中理解并生成自动语料配置，同时保持 GitHub Secrets 的权限边界清晰。

## 已确认的公开行为

1. 向导不读取、不保存、也不要求用户在浏览器中填写任何 Secret 值。
2. 默认推荐托管语料；选择自维护模式后，生成仓库 Variables、Provider Secret 名称和 `config.yml` 的 `sources` 片段。
3. GitHub 设置链接根据用户填写的 `owner/repo` 生成，支持 Fork 后使用。
4. 页面必须明确说明配置尚未写入 GitHub，不能把“生成配置”呈现为“保存成功”。
5. Agent、System 状态、报告浏览和搜索行为保持不变。

## 执行顺序

- [x] 先写浏览器验收测试，覆盖安全边界、模式切换、配置生成和动态链接。
- [x] 在 System 面板增加“配置自动语料”入口和分步向导。
- [x] 只把非敏感选择保存到 `localStorage`，不新增后端写接口。
- [x] 运行定向 E2E、前端检查和项目测试。
- [x] 通过后提交到 `main` 并核验 GitHub Actions。

## 验证记录

- 配置向导 E2E：2/2 通过。
- Dashboard 安全与同源回归：16/16 通过。
- TypeScript / ESLint / Prettier：通过。
- Node 单元测试：17 个文件、270 个用例通过。
- 真实视觉验收：深色主题 System 面板中无溢出，模式、来源、输出和安全提示可见。
- 发布提交：`c6e0531`，GitHub Actions [CI #32726271524](https://github.com/Conradgui/AI-TREND-RADAR-RAG/actions/runs/32726271524) 全部通过。

## 不在本阶段做

- 不申请 GitHub 写权限，不自动修改仓库 Variables 或 Secrets。
- 不引入 GitHub App/OAuth。
- 不重建 RAG 索引，不改变抓取器和现有语料。
- 不重构现有单文件前端架构。
