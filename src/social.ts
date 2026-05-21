/**
 * Social media content generator — uses LLM to produce platform-specific
 * articles from daily digests.
 *
 * Usage:
 *   pnpm xiaohongshu          # latest day → xiaohongshu
 *   pnpm wechat               # last 7 days → wechat weekly
 *   pnpm wechat:monthly       # last 30 days → wechat monthly
 *
 * Reads API keys from .env (local only).
 */

import "dotenv/config";
import fs from "node:fs";
import path from "node:path";
import { callLlm } from "./report.ts";

const DIGESTS_DIR = "digests";
const SOCIAL_DIR = "social";

function saveSocialFile(content: string, filename: string): string {
  fs.mkdirSync(SOCIAL_DIR, { recursive: true });
  const filepath = path.join(SOCIAL_DIR, filename);
  fs.writeFileSync(filepath, content, "utf-8");
  return filepath;
}

// Reports to include as source material (zh only)
const SOURCE_REPORTS = ["ai-cli", "ai-agents", "ai-web", "ai-trending", "ai-hn"];

function getRecentDates(n: number): string[] {
  const dateRe = /^\d{4}-\d{2}-\d{2}$/;
  return fs
    .readdirSync(DIGESTS_DIR)
    .filter((d) => dateRe.test(d) && fs.statSync(path.join(DIGESTS_DIR, d)).isDirectory())
    .sort()
    .reverse()
    .slice(0, n);
}

function loadReports(date: string, truncate = 3000): string {
  const sections: string[] = [];
  for (const report of SOURCE_REPORTS) {
    const filePath = path.join(DIGESTS_DIR, date, `${report}.md`);
    if (fs.existsSync(filePath)) {
      const content = fs.readFileSync(filePath, "utf-8");
      sections.push(`## [${report}]\n\n${content.slice(0, truncate)}`);
    }
  }
  return sections.join("\n\n---\n\n");
}

function loadMultiDayReports(days: number, truncate: number): { dateRange: string; content: string } {
  const dates = getRecentDates(days);
  if (dates.length === 0) throw new Error("No digest directories found");

  const sections: string[] = [];
  for (const date of dates) {
    const dayContent = loadReports(date, truncate);
    if (dayContent) {
      sections.push(`# ${date}\n\n${dayContent}`);
    }
  }
  if (sections.length === 0) throw new Error(`No reports found in the last ${days} days`);

  const dateRange = `${dates[dates.length - 1]} ~ ${dates[0]}`;
  return { dateRange, content: sections.join("\n\n===\n\n") };
}

function buildXiaohongshuPrompt(reports: string, date: string): string {
  return `你是一位 AI 技术领域的内容创作者，风格平实专业，擅长简洁地传达技术动态。

以下是 ${date} 的 AI 生态日报原始内容：

${reports}

---

请基于以上内容，生成一篇小红书日报笔记，要求：

**标题**：简洁明了，15-25 字，概括当日核心动态

**正文**（500-800 字）：
1. 一句话概括今天 AI 领域的整体动态
2. 精选 5-8 个当日要点，每个要点：
   - 用简短的小标题（可适当用 emoji 区分类别）
   - 1-2 句话说清楚事实和意义
   - 语言简练，不夸大
3. 结尾一句话总结
4. 最后加 3-5 个话题标签（#AI #开源 等）

**风格要求**：
- 语气平实，像写技术简报，不要夸张或煽情
- 段落短小，适合手机阅读
- 技术术语保留原文，不需要刻意通俗化
- 陈述事实为主，少用感叹号和夸张形容词
- 不要加任何链接（小红书不支持外链）

直接输出标题和正文，不要加额外说明。`;
}

function buildWechatPrompt(dateRange: string, reports: string): string {
  return `你是一位专注 AI 领域的公众号作者，文风专业但可读性强，擅长把一周的技术动态梳理成结构清晰、有深度的周刊长文。

以下是 ${dateRange} 这一周的 AI 生态日报原始内容（按日期倒序排列）：

${reports}

---

请基于以上一周的内容，生成一篇微信公众号周刊文章，要求：

**标题**：专业有力，20-35 字，体现本周核心看点，包含日期范围

**正文**（3000-5000 字）：

1. **本周速览**（200-300 字）：概括本周 AI 领域最重要的 5-8 件事，让读者 30 秒内获取核心信息

2. **AI CLI 工具周报**：各主流 AI 编程工具本周的关键进展
   - 重要版本发布和功能更新
   - 各工具的发展方向对比
   - 社区活跃度和讨论热点

3. **AI Agent 生态**：Agent 框架和项目本周的关键动向
   - 新功能、新项目、生态合作
   - 行业格局变化和趋势判断

4. **开源趋势与社区热点**：本周 GitHub Trending 和 Hacker News 的重要信号
   - 持续上榜的热门项目（说明持续热度）
   - 新出现的值得关注的项目
   - 社区讨论的核心话题演变

5. **官方动态**（如有）：Anthropic、OpenAI 等公司本周的重要发布

6. **本周观点**（300-500 字）：基于一周的数据，给出更有深度的判断
   - 本周最值得关注的趋势信号
   - 跨天对比中发现的模式（某个话题持续升温、某类项目集中出现等）
   - 对开发者的实操建议
   - 下周展望

**风格要求**：
- 专业但不晦涩，面向有一定技术背景的读者
- 使用 Markdown 格式，包括标题层级、加粗、列表
- 每个章节之间用分隔线（---）隔开
- 关键数据（star 数、版本号等）要保留
- 善于发现跨天的趋势和规律，不要简单罗列每天的内容
- 结尾附注：数据来源为 AI Topic Radar 项目（https://github.com/Conradgui/AI-TREND-RADAR）

直接输出标题和正文，不要加额外说明。`;
}

function buildWechatMonthlyPrompt(dateRange: string, reports: string): string {
  return `你是一位专注 AI 领域的公众号作者，文风专业但可读性强，擅长从一个月的海量信息中提炼出清晰的脉络和深刻的洞察。

以下是 ${dateRange} 这一个月的 AI 生态日报原始内容（按日期倒序排列，每天的内容已做摘要）：

${reports}

---

请基于以上一个月的内容，生成一篇微信公众号月报文章，要求：

**标题**：专业有深度，20-35 字，体现本月最重要的主题，包含月份

**正文**（5000-8000 字）：

1. **月度总览**（300-500 字）：用清晰的叙事概括本月 AI 开源生态的整体走势，点明 3-5 个月度级别的关键事件或转折点

2. **AI 编程工具演进**：本月各 CLI 工具的发展轨迹
   - 重大版本发布和里程碑（按时间线梳理）
   - 各工具的战略方向分化或趋同
   - 月度活跃度变化和社区规模对比
   - 值得关注的技术架构变化

3. **AI Agent 生态格局**：本月 Agent 领域的全景分析
   - 新入场的重要项目
   - 生态格局变化（谁在上升、谁在沉寂）
   - 技术路线之争（如果有）
   - 商业化进展

4. **开源趋势深度分析**：从一个月的 GitHub Trending 和 HN 数据中提炼规律
   - 持续霸榜的项目（说明为什么能持续热门）
   - 昙花一现 vs 持续增长的项目对比
   - 本月涌现的新技术方向或范式
   - 社区关注焦点的月度迁移

5. **大厂动态回顾**：Anthropic、OpenAI 等公司本月的重要动作
   - 产品发布节奏和战略意图
   - 对开源生态的影响

6. **月度深度观点**（500-800 字）：
   - 本月最重要的 3 个趋势信号，逐一分析
   - 从月度维度看到的、日报/周报看不到的规律
   - 对未来 1-3 个月的预判
   - 给不同角色的建议（开发者 / 技术管理者 / 创业者）

**风格要求**：
- 深度分析而非信息罗列，体现月度视角的独特价值
- 使用 Markdown 格式，包括标题层级、加粗、列表
- 每个章节之间用分隔线（---）隔开
- 关键数据要保留，适当做月度对比
- 有明确的观点和判断，不要只做信息搬运
- 结尾附注：数据来源为 AI Topic Radar 项目（https://github.com/Conradgui/AI-TREND-RADAR）

直接输出标题和正文，不要加额外说明。`;
}

type Platform = "xiaohongshu" | "wechat" | "wechat:monthly";

async function generate(platform: Platform): Promise<void> {
  if (platform === "xiaohongshu") {
    const dates = getRecentDates(1);
    if (dates.length === 0) throw new Error("No digest directories found");
    const date = dates[0]!;
    const reports = loadReports(date);
    if (!reports) throw new Error(`No reports found for ${date}`);

    console.log(`[social] Generating xiaohongshu article for ${date}…`);
    const content = await callLlm(buildXiaohongshuPrompt(reports, date), 4096);
    const filepath = saveSocialFile(content, `${date}-xiaohongshu.md`);
    console.log(`[social] Saved to ${filepath}`);
  } else if (platform === "wechat") {
    const { dateRange, content: reports } = loadMultiDayReports(7, 2000);
    const latestDate = getRecentDates(1)[0]!;

    console.log(`[social] Generating wechat weekly article for ${dateRange}…`);
    const content = await callLlm(buildWechatPrompt(dateRange, reports), 16384);
    const filepath = saveSocialFile(content, `${latestDate}-wechat.md`);
    console.log(`[social] Saved to ${filepath}`);
  } else {
    // wechat:monthly — use 30 days, smaller truncation per day to fit context
    const { dateRange, content: reports } = loadMultiDayReports(30, 1000);
    const latestDate = getRecentDates(1)[0]!;

    console.log(`[social] Generating wechat monthly article for ${dateRange}…`);
    const content = await callLlm(buildWechatMonthlyPrompt(dateRange, reports), 16384);
    const filepath = saveSocialFile(content, `${latestDate}-wechat-monthly.md`);
    console.log(`[social] Saved to ${filepath}`);
  }
}

const VALID_PLATFORMS: Platform[] = ["xiaohongshu", "wechat", "wechat:monthly"];
const platform = process.argv[2] as Platform | undefined;
if (!platform || !VALID_PLATFORMS.includes(platform)) {
  console.error("Usage: tsx src/social.ts <xiaohongshu|wechat|wechat:monthly>");
  process.exit(1);
}

generate(platform).catch((e: unknown) => {
  console.error("[social]", e instanceof Error ? e.message : e);
  process.exit(1);
});
