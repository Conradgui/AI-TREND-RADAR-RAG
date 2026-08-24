import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, it, expect } from "vitest";
import { toRfc822, escapeXml, generateSearchIndex, getReportFiles } from "../generate-manifest.ts";

const tempRoots: string[] = [];

afterEach(() => {
  for (const root of tempRoots.splice(0)) fs.rmSync(root, { recursive: true, force: true });
});

// ---------------------------------------------------------------------------
// toRfc822
// ---------------------------------------------------------------------------

describe("toRfc822", () => {
  it("formats a known date correctly", () => {
    // 2026-03-09 is a Monday
    const date = new Date(Date.UTC(2026, 2, 9, 14, 30, 0));
    const result = toRfc822(date);
    expect(result).toBe("Mon, 09 Mar 2026 14:30:00 +0000");
  });

  it("pads single-digit day and hours", () => {
    const date = new Date(Date.UTC(2026, 0, 5, 3, 7, 9));
    const result = toRfc822(date);
    expect(result).toBe("Mon, 05 Jan 2026 03:07:09 +0000");
  });

  it("handles midnight correctly", () => {
    const date = new Date(Date.UTC(2026, 5, 15, 0, 0, 0));
    const result = toRfc822(date);
    expect(result).toContain("00:00:00 +0000");
  });

  it("handles end of year", () => {
    const date = new Date(Date.UTC(2026, 11, 31, 23, 59, 59));
    const result = toRfc822(date);
    expect(result).toContain("Dec 2026");
    expect(result).toContain("23:59:59");
  });
});

// ---------------------------------------------------------------------------
// escapeXml
// ---------------------------------------------------------------------------

describe("escapeXml", () => {
  it("escapes ampersand", () => {
    expect(escapeXml("A & B")).toBe("A &amp; B");
  });

  it("escapes angle brackets", () => {
    expect(escapeXml("<tag>")).toBe("&lt;tag&gt;");
  });

  it("escapes double quotes", () => {
    expect(escapeXml('say "hello"')).toBe("say &quot;hello&quot;");
  });

  it("handles multiple escapes in one string", () => {
    expect(escapeXml('A & B < C > D "E"')).toBe("A &amp; B &lt; C &gt; D &quot;E&quot;");
  });

  it("returns unchanged string if no special chars", () => {
    expect(escapeXml("plain text")).toBe("plain text");
  });

  it("handles empty string", () => {
    expect(escapeXml("")).toBe("");
  });
});

describe("getReportFiles", () => {
  it("defaults to the main report and Chinese rollups", () => {
    expect(getReportFiles(["zh"], false)).toEqual(["ai-topic-radar", "ai-weekly", "ai-monthly"]);
  });

  it("includes source reports only when explicitly enabled", () => {
    expect(getReportFiles(["zh"], true)).toContain("ai-web");
    expect(getReportFiles(["zh"], false)).not.toContain("ai-web");
  });

  it("includes English reports only when requested", () => {
    const reports = getReportFiles(["zh", "en"], true);
    expect(reports).toContain("ai-cli-en");
    expect(reports).toContain("ai-weekly-en");
  });
});

describe("generateSearchIndex", () => {
  it("builds versioned item documents from candidates and excludes rollups", () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), "search-index-"));
    tempRoots.push(root);
    const digestsDir = path.join(root, "digests");
    const dateDir = path.join(digestsDir, "2026-08-05");
    fs.mkdirSync(dateDir, { recursive: true });
    fs.writeFileSync(
      path.join(dateDir, "topic-pool.json"),
      JSON.stringify({
        candidates: [
          {
            title: "OpenAI update",
            summary: "Official summary",
            source: "OpenAI",
            url: "https://openai.com/index/update/",
            score: 98,
          },
        ],
      }),
    );

    const outputPath = path.join(digestsDir, "search-index.json");
    const artifact = generateSearchIndex(
      [
        {
          date: "2026-08-05",
          reports: ["ai-topic-radar", "ai-weekly", "ai-monthly"],
        },
      ],
      { digestsDir, outputPath, generated: "2026-08-05T00:00:00.000Z" },
    );

    expect(artifact).toMatchObject({
      schema_version: 2,
      id_scheme: "atr-v1",
      source_candidate_count: 1,
      document_count: 1,
    });
    expect(artifact.documents[0]).toMatchObject({
      title: "OpenAI update",
      report_id: "ai-topic-radar",
      report_type: "daily",
    });
    expect(JSON.parse(fs.readFileSync(outputPath, "utf8"))).toEqual(artifact);
  });

  it("fails the build when a source candidate cannot be represented", () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), "search-index-gap-"));
    tempRoots.push(root);
    const digestsDir = path.join(root, "digests");
    const dateDir = path.join(digestsDir, "2026-08-05");
    fs.mkdirSync(dateDir, { recursive: true });
    fs.writeFileSync(
      path.join(dateDir, "topic-pool.json"),
      JSON.stringify({ candidates: [{ source: "Missing title" }] }),
    );

    expect(() =>
      generateSearchIndex([{ date: "2026-08-05", reports: ["ai-topic-radar"] }], {
        digestsDir,
        outputPath: path.join(digestsDir, "search-index.json"),
      }),
    ).toThrow(/coverage mismatch/);
  });

  it.each([
    ["missing candidates", {}],
    ["non-array candidates", { candidates: "invalid" }],
  ])("fails closed for a structurally invalid topic pool: %s", (_label, pool) => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), "search-index-invalid-pool-"));
    tempRoots.push(root);
    const digestsDir = path.join(root, "digests");
    const dateDir = path.join(digestsDir, "2026-08-05");
    fs.mkdirSync(dateDir, { recursive: true });
    fs.writeFileSync(path.join(dateDir, "topic-pool.json"), JSON.stringify(pool));

    expect(() =>
      generateSearchIndex([{ date: "2026-08-05", reports: ["ai-topic-radar"] }], {
        digestsDir,
        outputPath: path.join(digestsDir, "search-index.json"),
      }),
    ).toThrow(/invalid topic pool structure/i);
  });

  it("fails closed for invalid topic pool JSON", () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), "search-index-invalid-json-"));
    tempRoots.push(root);
    const digestsDir = path.join(root, "digests");
    const dateDir = path.join(digestsDir, "2026-08-05");
    fs.mkdirSync(dateDir, { recursive: true });
    fs.writeFileSync(path.join(dateDir, "topic-pool.json"), "{not-json");

    expect(() =>
      generateSearchIndex([{ date: "2026-08-05", reports: ["ai-topic-radar"] }], {
        digestsDir,
        outputPath: path.join(digestsDir, "search-index.json"),
      }),
    ).toThrow(/invalid topic pool json/i);
  });
});
