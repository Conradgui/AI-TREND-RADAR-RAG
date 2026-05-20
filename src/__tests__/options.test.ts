import { describe, expect, it } from "vitest";
import { getReportLangs, shouldSaveSourceReports } from "../options.ts";

describe("runtime options", () => {
  it("defaults to Chinese reports only", () => {
    expect(getReportLangs(undefined)).toEqual(["zh"]);
  });

  it("supports explicit Chinese and English reports", () => {
    expect(getReportLangs("zh,en")).toEqual(["zh", "en"]);
  });

  it("ignores unsupported languages and deduplicates", () => {
    expect(getReportLangs("en,fr,en")).toEqual(["en"]);
    expect(getReportLangs("fr")).toEqual(["zh"]);
  });

  it("saves source reports only when explicitly enabled", () => {
    expect(shouldSaveSourceReports(undefined)).toBe(false);
    expect(shouldSaveSourceReports("0")).toBe(false);
    expect(shouldSaveSourceReports("1")).toBe(true);
  });
});
