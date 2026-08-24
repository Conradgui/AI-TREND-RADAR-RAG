import { describe, expect, it } from "vitest";
import { formatReportRoute, parseReportRoute } from "../report-route.ts";

describe("report route", () => {
  it("keeps legacy date/report routes valid", () => {
    expect(parseReportRoute("#2026-08-05/ai-topic-radar")).toEqual({
      date: "2026-08-05",
      report: "ai-topic-radar",
      occurrenceId: null,
    });
  });

  it("parses stable item detail routes", () => {
    const occurrenceId = "ATR-20260805-A1B2C3";
    expect(parseReportRoute(`#2026-08-05/ai-topic-radar/item/${occurrenceId}`)).toEqual({
      date: "2026-08-05",
      report: "ai-topic-radar",
      occurrenceId,
    });
  });

  it("rejects malformed dates, report names, and occurrence ids", () => {
    expect(parseReportRoute("#2026-8-5/ai-topic-radar")).toBeNull();
    expect(parseReportRoute("#2026-08-05/../secret")).toBeNull();
    expect(parseReportRoute("#2026-08-05/ai-topic-radar/item/not-a-hash")).toBeNull();
  });

  it("formats routes without encoding path separators into one segment", () => {
    const occurrenceId = "ATR-20260805-B2C3D4";
    expect(
      formatReportRoute({
        date: "2026-08-05",
        report: "ai-topic-radar",
        occurrenceId,
      }),
    ).toBe(`#2026-08-05/ai-topic-radar/item/${occurrenceId}`);
  });

  it("keeps legacy 32-character occurrence routes readable during migration", () => {
    const occurrenceId = "a".repeat(32);
    expect(parseReportRoute(`#2026-08-05/ai-topic-radar/item/${occurrenceId}`)?.occurrenceId).toBe(
      occurrenceId,
    );
  });
});
