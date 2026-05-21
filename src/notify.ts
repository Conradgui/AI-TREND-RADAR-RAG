/**
 * Telegram notification — reads manifest.json and sends a message
 * with links to the latest reports. Skips silently if secrets are not set.
 *
 * Required env vars:
 *   TELEGRAM_BOT_TOKEN  — bot token from @BotFather
 *   TELEGRAM_CHAT_ID    — channel/group/user chat ID
 * Optional:
 *   PAGES_URL           — GitHub Pages base URL (defaults to the public deployment)
 */

import fs from "node:fs";
import path from "node:path";
import { NOTIFY_LABELS } from "./i18n.ts";
import type { ReportHighlights } from "./prompts-data.ts";

export interface Highlights {
  zh: ReportHighlights;
  en: ReportHighlights;
}

interface TopicPoolCandidate {
  title: string;
  url: string;
  source?: string;
  category: string;
  score: number;
  action: string;
  angle?: string;
  summary?: string;
  recommendedTopic?: string;
  reason: string;
  evidence?: string[];
}

interface TopicPool {
  candidates: TopicPoolCandidate[];
}

const TELEGRAM_SAFE_LIMIT = 3400;
const PAGES_URL_DEFAULT = "https://conradgui.github.io/AI-TREND-RADAR";

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function reportUrl(pagesUrl: string, date: string, report: string): string {
  if (report === "ai-topic-radar") {
    return `${pagesUrl}/digests/${date}/ai-topic-radar.html`;
  }
  return `${pagesUrl}/#${date}/${report}`;
}

async function sendTelegram(text: string): Promise<void> {
  const BOT_TOKEN = process.env["TELEGRAM_BOT_TOKEN"] ?? "";
  const CHAT_ID = process.env["TELEGRAM_CHAT_ID"] ?? "";
  if (!CHAT_ID) {
    console.log("[notify] TELEGRAM_CHAT_ID not set — skipping.");
    return;
  }
  const url = `https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_id: CHAT_ID,
      text,
      parse_mode: "HTML",
      disable_web_page_preview: true,
    }),
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Telegram API ${res.status}: ${body}`);
  }
}

async function sendTelegramMessages(messages: string[]): Promise<void> {
  for (const text of messages) {
    await sendTelegram(text);
  }
}

function splitTelegramMessages(text: string, limit = TELEGRAM_SAFE_LIMIT): string[] {
  if (text.length <= limit) return [text];
  const chunks: string[] = [];
  const blocks = text.split(/\n(?=## |📡 |📅 |📆 |<a )/);
  let current = "";

  for (const block of blocks) {
    if (!current) {
      current = block;
      continue;
    }
    if (`${current}\n${block}`.length <= limit) {
      current = `${current}\n${block}`;
      continue;
    }
    chunks.push(current);
    current = block;
  }
  if (current) chunks.push(current);

  return chunks.flatMap((chunk) => {
    if (chunk.length <= limit) return [chunk];
    const lines = chunk.split("\n");
    const lineChunks: string[] = [];
    let currentLineChunk = "";
    for (const line of lines) {
      if (!currentLineChunk) {
        currentLineChunk = line;
      } else if (`${currentLineChunk}\n${line}`.length <= limit) {
        currentLineChunk = `${currentLineChunk}\n${line}`;
      } else {
        lineChunks.push(currentLineChunk);
        currentLineChunk = line;
      }
    }
    if (currentLineChunk) lineChunks.push(currentLineChunk);
    return lineChunks;
  });
}

function shortEvidence(candidate: TopicPoolCandidate): string {
  return (candidate.evidence ?? []).slice(0, 3).join("；");
}

function fallbackRecommendedTopic(candidate: TopicPoolCandidate): string {
  if (candidate.recommendedTopic) return candidate.recommendedTopic;
  const angle = candidate.angle?.replace(/^适合从/, "").replace(/角度切入$/, "") || candidate.category;
  return `${candidate.title} 为什么值得关注？（${angle}）`;
}

function renderTopicItem(candidate: TopicPoolCandidate, index: number): string {
  const summary = candidate.summary || candidate.reason;
  const evidence = shortEvidence(candidate);
  return [
    `${index}. <a href="${escapeHtml(candidate.url)}">${escapeHtml(candidate.title)}</a>`,
    `分数/动作：${candidate.score} / ${escapeHtml(candidate.action)}`,
    `分类：${escapeHtml(candidate.category)}`,
    `摘要：${escapeHtml(summary)}`,
    `推荐选题：${escapeHtml(fallbackRecommendedTopic(candidate))}`,
    `推荐理由：${escapeHtml(candidate.reason)}`,
    evidence ? `证据：${escapeHtml(evidence)}` : "",
  ]
    .filter(Boolean)
    .join("\n");
}

export function buildTopicPoolMessages(date: string, topicPool: TopicPool, pagesUrl?: string): string[] {
  const PAGES_URL = (pagesUrl ?? process.env["PAGES_URL"] ?? PAGES_URL_DEFAULT).replace(/\/$/, "");
  const deepDive = topicPool.candidates.filter((item) => item.action === "深挖").slice(0, 6);
  const pool = topicPool.candidates.filter((item) => item.action === "入池").slice(0, 10);

  const sections = [
    `📡 <b>AI Topic Radar · ${date}</b>`,
    "",
    "## 今日 Top 深挖选题",
    deepDive.length ? deepDive.map(renderTopicItem).join("\n\n") : "暂无。",
    "",
    "## 入池选题",
    pool.length ? pool.map(renderTopicItem).join("\n\n") : "暂无。",
    "",
    `<a href="${PAGES_URL}/digests/${date}/ai-topic-radar.html">今日完整报告</a> · <a href="${PAGES_URL}">🌐 Web UI</a> · <a href="${PAGES_URL}/feed.xml">⊕ RSS</a>`,
  ];

  return splitTelegramMessages(sections.join("\n"));
}

export function buildMessage(
  date: string,
  reports: string[],
  pagesUrl?: string,
  highlights?: Highlights | null,
): string {
  const PAGES_URL = (pagesUrl ?? process.env["PAGES_URL"] ?? PAGES_URL_DEFAULT).replace(/\/$/, "");
  const baseReports = reports.filter((r) => !r.endsWith("-en"));
  const isWeekly = baseReports.includes("ai-weekly");
  const isMonthly = baseReports.includes("ai-monthly");

  const icon = isMonthly ? "📆" : isWeekly ? "📅" : "📡";
  const suffix = isMonthly ? " 月报" : isWeekly ? " 周报" : "";
  const lines: string[] = [`${icon} <b>AI Topic Radar${suffix} · ${date}</b>`];

  // Daily reports first, then rollups
  const ordered = [
    ...baseReports.filter((r) => !r.includes("weekly") && !r.includes("monthly")),
    ...baseReports.filter((r) => r.includes("weekly") || r.includes("monthly")),
  ];

  const zhHighlights = highlights?.zh ?? {};

  for (const r of ordered) {
    const zhLabel = NOTIFY_LABELS[r]?.zh ?? r;
    const zhUrl = reportUrl(PAGES_URL, date, r);
    const enKey = `${r}-en`;

    lines.push(""); // blank line before each report section
    if (reports.includes(enKey)) {
      const enLabel = NOTIFY_LABELS[r]?.en ?? "EN";
      const enUrl = reportUrl(PAGES_URL, date, enKey);
      lines.push(`• <a href="${zhUrl}">${zhLabel}</a>  ·  <a href="${enUrl}">${enLabel}</a>`);
    } else {
      lines.push(`• <a href="${zhUrl}">${zhLabel}</a>`);
    }

    // Add highlights as indented sub-items
    const items = zhHighlights[r];
    if (items?.length) {
      for (const h of items) {
        lines.push(`  ◦ ${escapeHtml(h)}`);
      }
    }
  }

  lines.push(`\n<a href="${PAGES_URL}">🌐 Web UI</a>  ·  <a href="${PAGES_URL}/feed.xml">⊕ RSS</a>`);
  return lines.join("\n");
}

async function main(): Promise<void> {
  const BOT_TOKEN = process.env["TELEGRAM_BOT_TOKEN"] ?? "";
  if (!BOT_TOKEN) {
    console.log("[notify] TELEGRAM_BOT_TOKEN not set — skipping.");
    return;
  }

  if (!fs.existsSync("manifest.json")) {
    console.log("[notify] manifest.json not found — skipping.");
    return;
  }

  const { dates } = JSON.parse(fs.readFileSync("manifest.json", "utf-8")) as {
    dates: { date: string; reports: string[] }[];
  };

  const latest = dates?.[0];
  if (!latest) {
    console.log("[notify] manifest is empty — skipping.");
    return;
  }
  const { date, reports } = latest;

  const topicPoolPath = path.join("digests", date, "topic-pool.json");
  if (fs.existsSync(topicPoolPath)) {
    try {
      const topicPool = JSON.parse(fs.readFileSync(topicPoolPath, "utf-8")) as TopicPool;
      const messages = buildTopicPoolMessages(date, topicPool);
      console.log(`[notify] Sending Telegram topic pool for ${date} (${messages.length} message(s))…`);
      await sendTelegramMessages(messages);
      console.log("[notify] Done!");
      return;
    } catch {
      console.log("[notify] Failed to parse topic-pool.json — falling back to highlights.");
    }
  }

  // Load highlights if available
  let highlights: Highlights | null = null;
  const highlightsPath = path.join("digests", date, "highlights.json");
  if (fs.existsSync(highlightsPath)) {
    try {
      highlights = JSON.parse(fs.readFileSync(highlightsPath, "utf-8")) as Highlights;
    } catch {
      console.log("[notify] Failed to parse highlights.json — sending without highlights.");
    }
  }

  const text = buildMessage(date, reports, undefined, highlights);

  console.log(`[notify] Sending Telegram message for ${date} (${reports.length} reports)…`);
  await sendTelegramMessages(splitTelegramMessages(text));
  console.log("[notify] Done!");
}

main().catch((e: unknown) => {
  console.error("[notify]", e instanceof Error ? e.message : e);
  process.exit(1);
});
