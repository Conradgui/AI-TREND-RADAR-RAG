import { describe, it, expect } from "vitest";
import {
  parseSitemapUrls,
  isSitemapIndex,
  extractTitle,
  extractText,
  urlCategory,
  titleFromUrl,
  emptyState,
  fetchSiteContent,
} from "../web.ts";

// ---------------------------------------------------------------------------
// parseSitemapUrls
// ---------------------------------------------------------------------------

describe("parseSitemapUrls", () => {
  it("parses urls with loc and lastmod", () => {
    const xml = `
      <urlset>
        <url>
          <loc>https://example.com/page1</loc>
          <lastmod>2026-03-09</lastmod>
        </url>
        <url>
          <loc>https://example.com/page2</loc>
          <lastmod>2026-03-08</lastmod>
        </url>
      </urlset>`;
    const result = parseSitemapUrls(xml);
    expect(result).toHaveLength(2);
    expect(result[0]).toEqual({ loc: "https://example.com/page1", lastmod: "2026-03-09" });
    expect(result[1]).toEqual({ loc: "https://example.com/page2", lastmod: "2026-03-08" });
  });

  it("handles urls without lastmod", () => {
    const xml = `<urlset><url><loc>https://example.com/page</loc></url></urlset>`;
    const result = parseSitemapUrls(xml);
    expect(result).toHaveLength(1);
    expect(result[0]).toEqual({ loc: "https://example.com/page", lastmod: undefined });
  });

  it("returns empty array for empty XML", () => {
    expect(parseSitemapUrls("")).toEqual([]);
    expect(parseSitemapUrls("<urlset></urlset>")).toEqual([]);
  });

  it("handles whitespace in loc/lastmod", () => {
    const xml = `<urlset><url><loc>  https://example.com/page  </loc><lastmod>  2026-03-09  </lastmod></url></urlset>`;
    const result = parseSitemapUrls(xml);
    expect(result[0]!.loc).toBe("https://example.com/page");
    expect(result[0]!.lastmod).toBe("2026-03-09");
  });
});

// ---------------------------------------------------------------------------
// isSitemapIndex
// ---------------------------------------------------------------------------

describe("isSitemapIndex", () => {
  it("detects sitemapindex tag", () => {
    expect(isSitemapIndex('<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')).toBe(true);
    expect(isSitemapIndex("<sitemapindex>")).toBe(true);
  });

  it("returns false for regular sitemap", () => {
    expect(isSitemapIndex('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// extractTitle
// ---------------------------------------------------------------------------

describe("extractTitle", () => {
  it("extracts og:title (property first)", () => {
    const html = `<meta property="og:title" content="My Title">`;
    expect(extractTitle(html)).toBe("My Title");
  });

  it("extracts og:title (content first)", () => {
    const html = `<meta content="My Title" property="og:title">`;
    expect(extractTitle(html)).toBe("My Title");
  });

  it("falls back to <title> tag", () => {
    const html = `<html><head><title>Page Title</title></head></html>`;
    expect(extractTitle(html)).toBe("Page Title");
  });

  it("prefers og:title over <title>", () => {
    const html = `<meta property="og:title" content="OG Title"><title>Fallback Title</title>`;
    expect(extractTitle(html)).toBe("OG Title");
  });

  it("returns empty string when no title found", () => {
    expect(extractTitle("<html><body></body></html>")).toBe("");
  });

  it("trims whitespace", () => {
    const html = `<title>  Spaced Title  </title>`;
    expect(extractTitle(html)).toBe("Spaced Title");
  });
});

// ---------------------------------------------------------------------------
// extractText
// ---------------------------------------------------------------------------

describe("extractText", () => {
  it("extracts text from <main> content", () => {
    const html = `<html><nav>Nav</nav><main><p>Main content</p></main><footer>Foot</footer></html>`;
    expect(extractText(html)).toBe("Main content");
  });

  it("falls back to <article> if no <main>", () => {
    const html = `<html><article><p>Article content</p></article></html>`;
    expect(extractText(html)).toBe("Article content");
  });

  it("strips script and style tags", () => {
    const html = `<main><script>alert('x')</script><style>.a{}</style><p>Clean</p></main>`;
    expect(extractText(html)).toBe("Clean");
  });

  it("decodes HTML entities", () => {
    const html = `<main>&amp; &lt; &gt; &quot; &#39; &nbsp;</main>`;
    const result = extractText(html);
    expect(result).toContain("&");
    expect(result).toContain("<");
    expect(result).toContain(">");
    expect(result).toContain('"');
    expect(result).toContain("'");
  });

  it("collapses whitespace", () => {
    const html = `<main><p>  Multiple   spaces   and\n\nnewlines  </p></main>`;
    expect(extractText(html)).toBe("Multiple spaces and newlines");
  });

  it("truncates to MAX_CONTENT_LENGTH (1500 chars)", () => {
    const html = `<main>${"A".repeat(2000)}</main>`;
    expect(extractText(html)).toHaveLength(1500);
  });
});

// ---------------------------------------------------------------------------
// urlCategory
// ---------------------------------------------------------------------------

describe("urlCategory", () => {
  it("returns first path segment", () => {
    expect(urlCategory("https://anthropic.com/news/some-article")).toBe("news");
    expect(urlCategory("https://openai.com/research/gpt-5")).toBe("research");
  });

  it("returns 'article' for root URLs", () => {
    expect(urlCategory("https://example.com/")).toBe("article");
    expect(urlCategory("https://example.com")).toBe("article");
  });

  it("returns 'article' for invalid URLs", () => {
    expect(urlCategory("not a url")).toBe("article");
  });
});

// ---------------------------------------------------------------------------
// titleFromUrl
// ---------------------------------------------------------------------------

describe("titleFromUrl", () => {
  it("converts slug to title case", () => {
    expect(titleFromUrl("https://example.com/blog/my-great-article")).toBe("My Great Article");
  });

  it("handles single-segment paths", () => {
    expect(titleFromUrl("https://example.com/about")).toBe("About");
  });

  it("returns URL for invalid input", () => {
    expect(titleFromUrl("not-a-url")).toBe("not-a-url");
  });
});

// ---------------------------------------------------------------------------
// emptyState
// ---------------------------------------------------------------------------

describe("emptyState", () => {
  it("returns valid empty state structure", () => {
    const state = emptyState();
    expect(state).toEqual({
      anthropic: { lastChecked: "", seenUrls: {} },
      openai: { lastChecked: "", seenUrls: {} },
      deepmind: { lastChecked: "", seenUrls: {} },
    });
  });

  it("returns a new object each time", () => {
    const a = emptyState();
    const b = emptyState();
    expect(a).not.toBe(b);
    a.anthropic.lastChecked = "modified";
    expect(b.anthropic.lastChecked).toBe("");
  });
});

// ---------------------------------------------------------------------------
// Official feed + sitemap collection
// ---------------------------------------------------------------------------

describe("fetchSiteContent", () => {
  it("uses the official feed description as the display summary", async () => {
    const articleUrl = "https://openai.com/index/apple-is-getting-this-wrong/";
    const exchangeUrl = "https://openai.com/index/introducing-the-openai-economic-research-exchange/";
    const educationUrl = "https://openai.com/index/learn-teach-chatgpt-work-codex/";
    const feed = `
      <rss version="2.0"><channel>
        <item>
          <title>Apple is getting this wrong</title>
          <link>${articleUrl}</link>
          <description>OpenAI addresses Apple's baseless lawsuit and explains why competition benefits developers and users.</description>
          <pubDate>Tue, 04 Aug 2026 12:00:00 GMT</pubDate>
        </item>
        <item>
          <title>Introducing the OpenAI Economic Research Exchange</title>
          <link>${exchangeUrl}</link>
          <description>OpenAI launches an exchange to study AI's impact on jobs, productivity, and the economy.</description>
          <pubDate>Mon, 08 Jun 2026 12:00:00 GMT</pubDate>
        </item>
        <item>
          <title>New ways to learn and teach with ChatGPT Work and Codex</title>
          <link>${educationUrl}</link>
          <description>Official education plugins help teachers and students learn, research, and build.</description>
          <pubDate>Tue, 04 Aug 2026 11:00:00 GMT</pubDate>
        </item>
      </channel></rss>`;
    const sitemap = `
      <urlset>
        <url><loc>${articleUrl}</loc><lastmod>2026-08-04</lastmod></url>
        <url><loc>${exchangeUrl}</loc><lastmod>2026-08-04</lastmod></url>
        <url><loc>${educationUrl}</loc><lastmod>2026-08-04</lastmod></url>
      </urlset>`;
    const fakeHttpGet = async (url: string): Promise<string> => {
      if (url === "https://openai.com/news/rss.xml") return feed;
      if (url.endsWith("/company/")) return sitemap;
      if (url.includes("/sitemap.xml/")) return "<urlset></urlset>";
      throw new Error(`Unexpected URL: ${url}`);
    };

    const result = await fetchSiteContent("openai", emptyState(), fakeHttpGet);

    expect(result.newItems).toHaveLength(3);
    expect(result.newItems).toContainEqual(
      expect.objectContaining({
        url: articleUrl,
        title: "Apple is getting this wrong",
        publishedAt: "2026-08-04T12:00:00.000Z",
        updatedAt: "2026-08-04",
        summary:
          "OpenAI addresses Apple's baseless lawsuit and explains why competition benefits developers and users.",
      }),
    );
    expect(result.newItems).toContainEqual(
      expect.objectContaining({
        url: exchangeUrl,
        summary: "OpenAI launches an exchange to study AI's impact on jobs, productivity, and the economy.",
      }),
    );
    expect(result.newItems).toContainEqual(
      expect.objectContaining({
        url: educationUrl,
        summary: "Official education plugins help teachers and students learn, research, and build.",
      }),
    );
  });

  it("keeps the page description separate from the longer article content", async () => {
    const articleUrl = "https://www.anthropic.com/news/example-release";
    const sitemap = `<urlset><url><loc>${articleUrl}</loc><lastmod>2026-08-06</lastmod></url></urlset>`;
    const html = `<!doctype html><html><head>
      <title>Example release</title>
      <meta name="description" content="A concise official description for report readers.">
    </head><body><article>
      <h1>Example release</h1>
      <p>This is the substantially longer article body used for analysis and RAG ingestion.</p>
      <p>It must not be substituted for the concise display summary.</p>
    </article></body></html>`;
    const fakeHttpGet = async (url: string): Promise<string> => {
      if (url === "https://www.anthropic.com/sitemap.xml") return sitemap;
      if (url === `${articleUrl}/` || url === articleUrl) return html;
      throw new Error(`Unexpected URL: ${url}`);
    };

    const result = await fetchSiteContent("anthropic", emptyState(), fakeHttpGet);
    const item = result.newItems[0]!;

    expect(item.summary).toBe("A concise official description for report readers.");
    expect(item.publishedAt).toBeUndefined();
    expect(item.updatedAt).toBe("2026-08-06");
    expect(item.content).toContain("substantially longer article body");
    expect(item.content).not.toBe(item.summary);
  });

  it("recognizes legacy seen URLs that do not have a trailing slash", async () => {
    const articleUrl = "https://www.anthropic.com/news/already-seen";
    const sitemap = `<urlset><url><loc>${articleUrl}</loc><lastmod>2026-08-06</lastmod></url></urlset>`;
    const state = emptyState();
    state.anthropic.lastChecked = "2026-08-06T12:00:00.000Z";
    state.anthropic.seenUrls[articleUrl] = "2026-08-06";
    const requestedUrls: string[] = [];
    const fakeHttpGet = async (url: string): Promise<string> => {
      requestedUrls.push(url);
      if (url === "https://www.anthropic.com/sitemap.xml") return sitemap;
      throw new Error(`Article page should not be fetched again: ${url}`);
    };

    const result = await fetchSiteContent("anthropic", state, fakeHttpGet);

    expect(result.isFirstRun).toBe(false);
    expect(result.newItems).toEqual([]);
    expect(requestedUrls).toEqual(["https://www.anthropic.com/sitemap.xml"]);
    expect(state.anthropic.seenUrls[articleUrl]).toBeUndefined();
    expect(state.anthropic.seenUrls[`${articleUrl}/`]).toBe("2026-08-06");
  });
});
