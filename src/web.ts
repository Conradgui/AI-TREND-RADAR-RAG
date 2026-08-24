/**
 * Web content fetching for AI company news/blog/research.
 *
 * Strategy:
 *   - Discover article URLs via sitemaps (no date filter needed — lastmod is reliable)
 *   - Compare with stored state to find new/updated URLs
 *   - Fetch content only for new URLs; on first run, cap at MAX_CONTENT_FETCH_FIRST_RUN per site
 *   - After every run, mark ALL discovered URLs as seen so future runs stay incremental
 *
 * State is persisted in digests/web-state.json (committed to git by the Actions workflow).
 */

import fs from "node:fs";
import path from "node:path";
import { extractFromHtml } from "@extractus/article-extractor";
import { extractFromXml } from "@extractus/feed-extractor";
import { sleep } from "./date.ts";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface WebPageItem {
  url: string;
  title: string;
  lastmod: string;
  /** First-party feed publication time when the source exposes one. */
  publishedAt?: string;
  /** Sitemap or page update time; never treated as publication time. */
  updatedAt?: string;
  /** Short source-grounded description for report display. */
  summary: string;
  /** Longer article text for analysis and RAG ingestion. */
  content: string;
  site: "anthropic" | "openai" | "deepmind";
  category: string;
}

interface SiteState {
  lastChecked: string;
  /** url → lastmod string (or "seen" if no lastmod available) */
  seenUrls: Record<string, string>;
}

export interface WebState {
  anthropic: SiteState;
  openai: SiteState;
  deepmind: SiteState;
}

export interface WebFetchResult {
  site: "anthropic" | "openai" | "deepmind";
  siteName: string;
  isFirstRun: boolean;
  newItems: WebPageItem[];
  /** Total URLs discovered in sitemap (for context in the report) */
  totalDiscovered: number;
}

// ---------------------------------------------------------------------------
// Site config
// ---------------------------------------------------------------------------

interface SiteConfig {
  name: string;
  /** Standard first-party feeds used for discovery and concise descriptions. */
  feedUrls?: string[];
  /** For single sitemaps: URL to fetch */
  sitemapUrl: string;
  /** For single sitemaps: only keep URLs starting with these path prefixes */
  prefixes?: string[];
  /** For sitemap indexes: named sub-sitemaps to fetch */
  subSitemapNames?: string[];
  /** URL template for sub-sitemaps; {name} is replaced with each sub-sitemap name */
  subSitemapTemplate?: string;
  /** Whether article pages are expected to be reachable from CI. */
  fetchArticlePages?: boolean;
}

const SITE_CONFIGS: Record<"anthropic" | "openai" | "deepmind", SiteConfig> = {
  anthropic: {
    name: "Anthropic (Claude)",
    sitemapUrl: "https://www.anthropic.com/sitemap.xml",
    prefixes: ["/news/", "/research/", "/engineering/", "/learn/"],
  },
  openai: {
    name: "OpenAI",
    feedUrls: ["https://openai.com/news/rss.xml"],
    sitemapUrl: "https://openai.com/sitemap.xml",
    subSitemapNames: [
      "research",
      "publication",
      "release",
      "company",
      "engineering",
      "milestone",
      "learn-guides",
      "safety",
      "product",
    ],
    subSitemapTemplate: "https://openai.com/sitemap.xml/{name}/",
    fetchArticlePages: false,
  },
  deepmind: {
    name: "Google DeepMind",
    sitemapUrl: "https://deepmind.google/sitemap.xml",
    prefixes: ["/blog/", "/research/", "/discover/"],
  },
};

/** Max articles to fetch full content for on the very first run (per site). */
const MAX_CONTENT_FETCH_FIRST_RUN = 25;
/** Characters of page text forwarded to the LLM per article. */
const MAX_CONTENT_LENGTH = 1_500;
/** Polite delay between individual page GETs (ms). */
const FETCH_DELAY_MS = 300;
/** Per-request timeout (ms). */
const FETCH_TIMEOUT_MS = 10_000;

// ---------------------------------------------------------------------------
// HTTP helpers
// ---------------------------------------------------------------------------

const WEB_HEADERS = {
  "User-Agent": "Mozilla/5.0 (compatible; ai-topic-radar/1.0; +https://github.com/Conradgui/AI-TREND-RADAR)",
  Accept: "text/html,application/xml,text/xml,*/*",
  "Accept-Language": "en-US,en;q=0.9",
};

async function httpGet(url: string): Promise<string> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const resp = await fetch(url, { headers: WEB_HEADERS, signal: controller.signal });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return await resp.text();
  } finally {
    clearTimeout(timer);
  }
}

export type WebTextFetcher = (url: string) => Promise<string>;

interface FeedItem {
  url: string;
  title: string;
  summary: string;
  published: string;
}

function normalizeUrl(url: string): string {
  try {
    const parsed = new URL(url);
    parsed.hash = "";
    parsed.search = "";
    if (!parsed.pathname.endsWith("/")) parsed.pathname += "/";
    return parsed.toString();
  } catch {
    return url;
  }
}

function seenAt(seenUrls: Record<string, string>, normalizedUrl: string): string | undefined {
  const legacyUrl = normalizedUrl.endsWith("/") ? normalizedUrl.slice(0, -1) : `${normalizedUrl}/`;
  return seenUrls[normalizedUrl] ?? seenUrls[legacyUrl];
}

async function fetchFeedItems(cfg: SiteConfig, getText: WebTextFetcher): Promise<Map<string, FeedItem>> {
  const items = new Map<string, FeedItem>();
  for (const feedUrl of cfg.feedUrls ?? []) {
    try {
      const xml = await getText(feedUrl);
      const feed = extractFromXml(xml, { descriptionMaxLen: 0 });
      for (const entry of feed.entries ?? []) {
        if (!entry.link) continue;
        const url = normalizeUrl(entry.link);
        items.set(url, {
          url,
          title: entry.title?.trim() ?? "",
          summary: entry.description?.trim() ?? "",
          published: entry.published ?? "",
        });
      }
    } catch (err) {
      console.error(`  [web/feed] Failed to read ${feedUrl}: ${err}`);
    }
  }
  return items;
}

// ---------------------------------------------------------------------------
// Sitemap parsing (plain-text XML; no DOM needed)
// ---------------------------------------------------------------------------

export function parseSitemapUrls(xml: string): Array<{ loc: string; lastmod?: string }> {
  const results: Array<{ loc: string; lastmod?: string }> = [];
  for (const block of xml.match(/<url>[\s\S]*?<\/url>/g) ?? []) {
    const loc = block.match(/<loc>\s*(.*?)\s*<\/loc>/)?.[1];
    const lastmod = block.match(/<lastmod>\s*(.*?)\s*<\/lastmod>/)?.[1];
    if (loc) results.push({ loc, lastmod });
  }
  return results;
}

export function isSitemapIndex(xml: string): boolean {
  return /<sitemapindex[\s>]/.test(xml);
}

// ---------------------------------------------------------------------------
// HTML content extraction
// ---------------------------------------------------------------------------

export function extractTitle(html: string): string {
  return (
    // Prefer OpenGraph title for cleaner strings
    (
      html.match(/<meta[^>]+property=["']og:title["'][^>]+content=["']([^"']{1,200})["']/i)?.[1] ??
      html.match(/<meta[^>]+content=["']([^"']{1,200})["'][^>]+property=["']og:title["']/i)?.[1] ??
      html.match(/<title[^>]*>([^<]{1,200})<\/title>/i)?.[1] ??
      ""
    ).trim()
  );
}

export function extractText(html: string): string {
  // Prefer <main> or <article> to avoid nav/header/footer boilerplate
  const source =
    html.match(/<main[^>]*>([\s\S]*?)<\/main>/i)?.[1] ??
    html.match(/<article[^>]*>([\s\S]*?)<\/article>/i)?.[1] ??
    html;

  return source
    .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, " ")
    .replace(/<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&nbsp;/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, MAX_CONTENT_LENGTH);
}

export function urlCategory(url: string): string {
  try {
    return new URL(url).pathname.split("/").filter(Boolean)[0] ?? "article";
  } catch {
    return "article";
  }
}

/** Derive a human-readable title from the last URL path segment. */
export function titleFromUrl(url: string): string {
  try {
    const slug = new URL(url).pathname.split("/").filter(Boolean).pop() ?? "";
    return slug.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  } catch {
    return url;
  }
}

// ---------------------------------------------------------------------------
// URL discovery
// ---------------------------------------------------------------------------

async function discoverUrls(
  site: "anthropic" | "openai" | "deepmind",
  getText: WebTextFetcher,
): Promise<Array<{ loc: string; lastmod?: string }>> {
  const cfg = SITE_CONFIGS[site];
  const results: Array<{ loc: string; lastmod?: string }> = [];

  if (cfg.subSitemapNames && cfg.subSitemapTemplate) {
    // Sitemap index: fetch each named sub-sitemap
    for (const name of cfg.subSitemapNames) {
      const subUrl = cfg.subSitemapTemplate.replace("{name}", name);
      try {
        const xml = await getText(subUrl);
        results.push(...parseSitemapUrls(xml));
        await sleep(100);
      } catch (err) {
        console.error(`  [web/${site}] sub-sitemap "${name}" failed: ${err}`);
      }
    }
  } else {
    // Single sitemap
    const xml = await getText(cfg.sitemapUrl);
    const all = isSitemapIndex(xml)
      ? [] // unexpected; skip rather than recurse
      : parseSitemapUrls(xml);

    const prefixes = cfg.prefixes ?? [];
    results.push(
      ...all.filter(({ loc }) => {
        try {
          return prefixes.some((p) => new URL(loc).pathname.startsWith(p));
        } catch {
          return false;
        }
      }),
    );
  }

  return results;
}

// ---------------------------------------------------------------------------
// State persistence
// ---------------------------------------------------------------------------

const STATE_FILE = path.join("digests", "web-state.json");

export function emptyState(): WebState {
  return {
    anthropic: { lastChecked: "", seenUrls: {} },
    openai: { lastChecked: "", seenUrls: {} },
    deepmind: { lastChecked: "", seenUrls: {} },
  };
}

export function loadWebState(): WebState {
  try {
    return JSON.parse(fs.readFileSync(STATE_FILE, "utf-8")) as WebState;
  } catch {
    return emptyState();
  }
}

export function saveWebState(state: WebState): void {
  fs.mkdirSync(path.dirname(STATE_FILE), { recursive: true });
  fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2), "utf-8");
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

export async function fetchSiteContent(
  site: "anthropic" | "openai" | "deepmind",
  state: WebState,
  getText: WebTextFetcher = httpGet,
): Promise<WebFetchResult> {
  const cfg = SITE_CONFIGS[site];
  const siteState = state[site];
  const isFirstRun = Object.keys(siteState.seenUrls).length === 0;

  console.log(`  [web/${site}] Discovering URLs from sitemap...`);
  const feedItems = await fetchFeedItems(cfg, getText);
  const sitemapItems = await discoverUrls(site, getText);
  const discoveredByUrl = new Map(
    sitemapItems.map((item) => [normalizeUrl(item.loc), { ...item, loc: normalizeUrl(item.loc) }]),
  );
  for (const item of feedItems.values()) {
    if (!discoveredByUrl.has(item.url)) {
      discoveredByUrl.set(item.url, { loc: item.url, lastmod: item.published });
    }
  }
  const allDiscovered = [...discoveredByUrl.values()];
  console.log(`  [web/${site}] Discovered ${allDiscovered.length} URLs`);

  // Newest first
  allDiscovered.sort((a, b) => {
    if (!a.lastmod && !b.lastmod) return 0;
    if (!a.lastmod) return 1;
    if (!b.lastmod) return -1;
    return b.lastmod.localeCompare(a.lastmod);
  });

  // New = not seen before, OR (for sites with reachable pages) lastmod is newer.
  // For metadata-only sites (e.g. OpenAI), lastmod reflects sitemap generation
  // time rather than content publication — ignore lastmod changes to avoid
  // flagging hundreds of unchanged URLs as "new" on every run.
  const newUrls = allDiscovered.filter(({ loc, lastmod }) => {
    const prev = seenAt(siteState.seenUrls, loc);
    if (!prev) return true;
    if (cfg.fetchArticlePages !== false && lastmod && lastmod > prev) return true;
    return false;
  });

  // Cap content fetches on first run to avoid excessive runtime
  const toFetch = isFirstRun ? newUrls.slice(0, MAX_CONTENT_FETCH_FIRST_RUN) : newUrls;

  console.log(
    `  [web/${site}] ${isFirstRun ? "First run" : "Incremental"}: ` +
      `${newUrls.length} new URLs, fetching content for ${toFetch.length}`,
  );

  // Build items from first-party feed metadata and, where reachable, article pages.
  const items: WebPageItem[] = [];
  if (cfg.fetchArticlePages === false) {
    for (const { loc, lastmod } of toFetch) {
      const feedItem = feedItems.get(normalizeUrl(loc));
      items.push({
        url: loc,
        title: feedItem?.title || titleFromUrl(loc),
        lastmod: feedItem?.published || lastmod || "",
        publishedAt: feedItem?.published || undefined,
        updatedAt: lastmod || undefined,
        summary: feedItem?.summary ?? "",
        content: feedItem?.summary ?? "",
        site,
        category: urlCategory(loc),
      });
    }
  } else {
    // Fetch page content sequentially with a polite delay
    for (const { loc, lastmod } of toFetch) {
      const feedItem = feedItems.get(normalizeUrl(loc));
      try {
        const html = await getText(loc);
        const article = await extractFromHtml(html, loc, {
          descriptionLengthThreshold: 1,
          contentLengthThreshold: 1,
        });
        const content = article?.content ? extractText(article.content) : extractText(html);
        items.push({
          url: loc,
          title: article?.title?.trim() || extractTitle(html) || titleFromUrl(loc),
          lastmod: lastmod ?? "",
          publishedAt: feedItem?.published || undefined,
          updatedAt: lastmod || undefined,
          summary: article?.description?.trim() ?? "",
          content,
          site,
          category: urlCategory(loc),
        });
      } catch (err) {
        console.error(`  [web/${site}] Failed to fetch ${loc}: ${err}`);
      }
      await sleep(FETCH_DELAY_MS);
    }
  }

  // Mark ALL discovered URLs as seen (not just fetched ones)
  // This ensures future runs are truly incremental
  for (const { loc, lastmod } of allDiscovered) {
    const legacyUrl = loc.endsWith("/") ? loc.slice(0, -1) : `${loc}/`;
    if (legacyUrl !== loc) delete siteState.seenUrls[legacyUrl];
    siteState.seenUrls[loc] = lastmod ?? "seen";
  }
  siteState.lastChecked = new Date().toISOString();

  return {
    site,
    siteName: cfg.name,
    isFirstRun,
    newItems: items,
    totalDiscovered: allDiscovered.length,
  };
}
