import { describe, it, expect, afterEach } from "vitest";
import { buildMessage, buildTopicPoolMessages, type Highlights } from "../notify.ts";

const BASE_URL = "https://example.com/radar";

describe("buildMessage", () => {
  const origPagesUrl = process.env["PAGES_URL"];

  afterEach(() => {
    if (origPagesUrl !== undefined) {
      process.env["PAGES_URL"] = origPagesUrl;
    } else {
      delete process.env["PAGES_URL"];
    }
  });

  it("builds a daily message with zh + en reports", () => {
    const msg = buildMessage("2026-03-09", ["ai-cli", "ai-cli-en", "ai-agents", "ai-agents-en"], BASE_URL);
    expect(msg).toContain("AI Topic Radar");
    expect(msg).toContain("2026-03-09");
    expect(msg).toContain("📡");
    // zh links
    expect(msg).toContain(`${BASE_URL}/#2026-03-09/ai-cli`);
    expect(msg).toContain("AI CLI 工具");
    // en links
    expect(msg).toContain(`${BASE_URL}/#2026-03-09/ai-cli-en`);
    expect(msg).toContain("AI CLI Tools");
  });

  it("shows weekly icon and suffix for weekly reports", () => {
    const msg = buildMessage("2026-03-09", ["ai-weekly", "ai-weekly-en"], BASE_URL);
    expect(msg).toContain("📅");
    expect(msg).toContain("周报");
  });

  it("shows monthly icon and suffix for monthly reports", () => {
    const msg = buildMessage("2026-03-09", ["ai-monthly", "ai-monthly-en"], BASE_URL);
    expect(msg).toContain("📆");
    expect(msg).toContain("月报");
  });

  it("monthly takes priority over weekly", () => {
    const msg = buildMessage("2026-03-09", ["ai-weekly", "ai-monthly"], BASE_URL);
    expect(msg).toContain("📆");
    expect(msg).toContain("月报");
  });

  it("renders zh-only reports without en link", () => {
    const msg = buildMessage("2026-03-09", ["ai-hn"], BASE_URL);
    expect(msg).toContain("HN 社区动态");
    expect(msg).not.toContain("HN Community");
  });

  it("links the main topic radar report to the standalone html", () => {
    const msg = buildMessage("2026-03-09", ["ai-topic-radar"], BASE_URL);
    expect(msg).toContain(`${BASE_URL}/digests/2026-03-09/ai-topic-radar.html`);
  });

  it("includes Web UI and RSS links", () => {
    const msg = buildMessage("2026-03-09", ["ai-cli"], BASE_URL);
    expect(msg).toContain("🌐 Web UI");
    expect(msg).toContain("RSS");
    expect(msg).toContain(`${BASE_URL}/feed.xml`);
  });

  it("strips trailing slash from pagesUrl", () => {
    const msg = buildMessage("2026-03-09", ["ai-cli"], BASE_URL + "/");
    expect(msg).not.toContain("//feed.xml");
    expect(msg).toContain(`${BASE_URL}/feed.xml`);
  });

  it("includes highlights when provided", () => {
    const highlights: Highlights = {
      zh: {
        "ai-cli": ["Claude Code 发布 v1.2.0", "Gemini CLI 修复 streaming"],
        "ai-agents": ["OpenClaw 新增 MCP 支持"],
      },
      en: {
        "ai-cli": ["Claude Code releases v1.2.0"],
      },
    };
    const msg = buildMessage(
      "2026-03-09",
      ["ai-cli", "ai-cli-en", "ai-agents", "ai-agents-en"],
      BASE_URL,
      highlights,
    );
    expect(msg).toContain("◦ Claude Code 发布 v1.2.0");
    expect(msg).toContain("◦ Gemini CLI 修复 streaming");
    expect(msg).toContain("◦ OpenClaw 新增 MCP 支持");
  });

  it("works without highlights (null)", () => {
    const msg = buildMessage("2026-03-09", ["ai-cli", "ai-cli-en"], BASE_URL, null);
    expect(msg).toContain("AI CLI 工具");
    expect(msg).not.toContain("◦");
  });

  it("works without highlights (undefined)", () => {
    const msg = buildMessage("2026-03-09", ["ai-cli", "ai-cli-en"], BASE_URL);
    expect(msg).toContain("AI CLI 工具");
    expect(msg).not.toContain("◦");
  });
});

describe("buildTopicPoolMessages", () => {
  it("builds complete topic pool messages from topic-pool candidates", () => {
    const messages = buildTopicPoolMessages(
      "2026-03-09",
      {
        candidates: [
          {
            title: "OpenAI research launch",
            url: "https://openai.com/research",
            category: "模型与技术突破",
            score: 88,
            action: "深挖",
            summary: "OpenAI 发布新的科研模型能力信号。",
            recommendedTopic: "OpenAI 科研模型能力到哪一步了？（模型能力变化与技术路线）",
            reason: "值得优先深挖：模型能力变化明显。",
            evidence: ["来源：OpenAI", "热度信号：1000", "关键词：research"],
          },
          {
            title: "New AI product",
            url: "https://example.com/product",
            category: "AI 产品与用户入口",
            score: 70,
            action: "入池",
            summary: "一个新的 AI 产品入口值得观察。",
            recommendedTopic: "New AI product 为什么值得关注？（用户入口、使用场景与产品体验）",
            reason: "适合进入今日选题池：产品入口清晰。",
            evidence: ["来源：Product Hunt"],
          },
        ],
      },
      BASE_URL,
    );
    const msg = messages.join("\n");

    expect(msg).toContain("今日 Top 深挖选题");
    expect(msg).toContain("入池选题");
    expect(msg).toContain("OpenAI research launch");
    expect(msg).toContain("OpenAI 发布新的科研模型能力信号。");
    expect(msg).toContain("OpenAI 科研模型能力到哪一步了？（模型能力变化与技术路线）");
    expect(msg).toContain("New AI product");
    expect(msg).toContain("一个新的 AI 产品入口值得观察。");
    expect(msg).toContain(`${BASE_URL}/digests/2026-03-09/ai-topic-radar.html`);
    expect(msg).toContain(`${BASE_URL}/feed.xml`);
  });

  it("falls back to reason and angle when summary or recommended topic is missing", () => {
    const messages = buildTopicPoolMessages(
      "2026-03-09",
      {
        candidates: [
          {
            title: "Fallback item",
            url: "https://example.com/fallback",
            category: "企业落地与行业应用",
            score: 80,
            action: "深挖",
            angle: "适合从行业场景、落地成本和业务价值角度切入",
            reason: "值得优先深挖：来自旧 topic-pool。",
            evidence: [],
          },
        ],
      },
      BASE_URL,
    );
    const msg = messages.join("\n");

    expect(msg).toContain("摘要：值得优先深挖：来自旧 topic-pool。");
    expect(msg).toContain("Fallback item 为什么值得关注？（行业场景、落地成本和业务价值）");
  });

  it("splits long Telegram messages", () => {
    const candidates = Array.from({ length: 20 }, (_, index) => ({
      title: `Long item ${index}`,
      url: `https://example.com/${index}`,
      category: "AI 产品与用户入口",
      score: index < 8 ? 80 : 70,
      action: index < 8 ? "深挖" : "入池",
      summary: "这是一段较长的摘要，用来触发 Telegram 消息拆分。".repeat(12),
      recommendedTopic: `Long item ${index} 为什么值得关注？（用户入口、使用场景与产品体验）`,
      reason: "适合进入今日选题池：内容较长。",
      evidence: ["来源：测试"],
    }));

    const messages = buildTopicPoolMessages("2026-03-09", { candidates }, BASE_URL);

    expect(messages.length).toBeGreaterThan(1);
    expect(messages.every((msg) => msg.length <= 3400)).toBe(true);
  });
});
