import { describe, expect, it, vi } from "vitest";

import {
  SOURCE_CATALOG,
  resolveSourceConfiguration,
  runConfiguredSource,
  summarizeSourceConfiguration,
  type SourceModes,
} from "../source-config.ts";

describe("resolveSourceConfiguration", () => {
  it("registers every non-GitHub corpus connector in one control plane", () => {
    expect(Object.keys(SOURCE_CATALOG)).toEqual([
      "anthropic",
      "openai",
      "deepmind",
      "github_trending",
      "hacker_news",
      "product_hunt",
      "arxiv",
      "hugging_face",
      "devto",
      "lobsters",
      "kr36",
      "infoq_cn",
      "gitee",
      "oschina",
      "juejin",
    ]);
  });

  it("runs a keyless auto source and skips a credentialed auto source without its token", () => {
    const states = resolveSourceConfiguration({ hacker_news: "auto", product_hunt: "auto" }, {});

    expect(states.hacker_news).toMatchObject({ active: true, status: "ready" });
    expect(states.product_hunt).toMatchObject({ active: false, status: "skipped" });
  });

  it("rejects an explicitly enabled source when its required credential is missing", () => {
    const states = resolveSourceConfiguration({ hacker_news: "auto", product_hunt: "enabled" }, {});

    expect(states.product_hunt).toMatchObject({
      active: false,
      status: "error",
      missingCredential: "PRODUCTHUNT_TOKEN",
    });
  });

  it("activates a credentialed source when its token is configured", () => {
    const states = resolveSourceConfiguration({ product_hunt: "enabled" } as SourceModes, {
      PRODUCTHUNT_TOKEN: "configured",
    });

    expect(states.product_hunt).toMatchObject({ active: true, status: "ready" });
  });
});

describe("runConfiguredSource", () => {
  it("does not call a connector when the source is disabled", async () => {
    const connector = vi.fn(async () => ({ items: ["unexpected"] }));

    const result = await runConfiguredSource(
      resolveSourceConfiguration({ hacker_news: "disabled" }, {}).hacker_news,
      connector,
      { items: [] as string[] },
    );

    expect(connector).not.toHaveBeenCalled();
    expect(result).toEqual({ items: [] });
  });
});

describe("summarizeSourceConfiguration", () => {
  it("returns a failing preflight result with the exact missing credential", () => {
    const summary = summarizeSourceConfiguration(resolveSourceConfiguration({ product_hunt: "enabled" }, {}));

    expect(summary.ok).toBe(false);
    expect(summary.lines).toContain("Product Hunt: error — 缺少 PRODUCTHUNT_TOKEN");
  });
});
