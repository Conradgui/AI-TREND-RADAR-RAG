# M8：Markdown / UI 渲染与引用跳转策略

## 目标

将经过验证的 Answer Envelope 确定性投影成用户可读结果；渲染器不能改变事实、顺序、层级或链接。

## 接口

```text
render(AnswerEnvelope, Surface, Locale) -> Markdown | UIModel
```

Markdown 和 Web UI 共享同一 Answer Envelope，不让模型分别写两份答案。

## 呈现策略

- Primary 直接展示；Supplementary 与 Background 可折叠但不能丢正文；
- 内部语料与联网证据使用不同标记；
- 无摘要时不显示虚假的“展开摘要”；
- 引用标签显示日期、来源和短标题；
- 本地条目点击到 `#YYYY-MM-DD/ai-topic-radar/item/ATR-...`；
- 外部来源使用独立跳转图标；
- 图谱推断关系明确显示“推断”，不伪装成原始来源；
- UI 只使用安全 Markdown 子集或受控组件，不渲染模型任意 HTML。

## 身份链

```text
ATR Daily Item ID
→ Evidence Ledger Record
→ 请求内 E 编号
→ Claim.evidence_ids
→ Citation ViewModel
→ 本地 deep link / 外部原文链接
```

任何一环缺失都不能显示为正式引用。链接和元数据由服务端注入，不接受模型生成 URL。

## 流式体验

可以先流式展示真实执行状态（理解、召回、重排、生成、校验），但正式答案卡片应在完整 JSON 校验后原子提交。不要公开模型隐含思维链，可展示简洁 `method_summary`。

## 评价

ATR deep-link 准确率、外部链接准确率、无效展开控件率、内部/外部标记正确率、渲染前后证据顺序一致率、XSS 安全测试、主答案扫描任务完成时间。

Markdown 基础遵循 [CommonMark](https://spec.commonmark.org/spec)，HTML/DOM 安全遵循 [OWASP XSS Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html)。
