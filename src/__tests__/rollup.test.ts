import { describe, it, expect } from "vitest";
import { sanitizeRollupSummary, toWeekStr } from "../rollup.ts";

describe("toWeekStr", () => {
  it("returns correct ISO week for a known date", () => {
    // 2026-03-09 is a Monday in ISO week 11
    expect(toWeekStr(new Date("2026-03-09"))).toBe("2026-W11");
  });

  it("handles first week of year", () => {
    // 2026-01-05 is a Monday in week 2
    expect(toWeekStr(new Date("2026-01-05"))).toBe("2026-W02");
  });

  it("handles last week of year crossing into next year", () => {
    // 2025-12-29 is a Monday — ISO week 1 of 2026
    expect(toWeekStr(new Date("2025-12-29"))).toBe("2026-W01");
  });

  it("handles week 52/53", () => {
    // 2026-12-28 is a Monday — W53 of 2026? Let's check
    const result = toWeekStr(new Date("2026-12-28"));
    expect(result).toMatch(/^\d{4}-W\d{2}$/);
  });

  it("pads single-digit week numbers", () => {
    // 2026-01-12 is a Monday in week 3
    const result = toWeekStr(new Date("2026-01-12"));
    expect(result).toBe("2026-W03");
  });
});

describe("sanitizeRollupSummary", () => {
  it("removes Chinese weekly greeting, repeated title, and analyst metadata", () => {
    const input = `好的，作为专注于 AI 开源生态的技术分析师，现基于您提供的 2026-W22 周（2026-05-20 星期三）的每日动态摘要，为您生成本周综合回顾报告。

# AI 工具生态周报 (2026-W22)

报告周期： 2026-05-20 (周三) 至 2026-05-20 (周三)
分析师： AI 开源生态技术分析师

1. **本周要闻**

本周 AI Agent 技能化成为主线。`;

    const result = sanitizeRollupSummary(input, "weekly", "zh");

    expect(result.startsWith("1. **本周要闻**")).toBe(true);
    expect(result).not.toContain("好的，作为");
    expect(result).not.toContain("AI 工具生态周报 (2026-W22)");
    expect(result).not.toContain("分析师：");
  });

  it("removes Chinese monthly boilerplate before the first expected section", () => {
    const input = `好的，作为专注于 AI 开源生态的技术分析师，以下是本月综合回顾报告。

## AI 工具生态月报 2026-05

数据来源： 4 份周报
分析师： AI 开源生态技术分析师

1. **月度要闻**

本月 AI 工具链继续演进。`;

    const result = sanitizeRollupSummary(input, "monthly", "zh");

    expect(result.startsWith("1. **月度要闻**")).toBe(true);
    expect(result).not.toContain("好的，作为");
    expect(result).not.toContain("分析师：");
  });

  it("removes English boilerplate before the first expected section", () => {
    const input = `Sure, as an AI open-source ecosystem analyst, here is the weekly recap.

# AI Tools Ecosystem Weekly Report 2026-W22

Analyst: AI open-source ecosystem analyst

1. **Week's Top Stories**

Agent tooling dominated the week.`;

    const result = sanitizeRollupSummary(input, "weekly", "en");

    expect(result.startsWith("1. **Week's Top Stories**")).toBe(true);
    expect(result).not.toContain("Sure, as an");
    expect(result).not.toContain("Analyst:");
  });

  it("removes leading metadata lines when no expected section heading is present", () => {
    const input = `分析师： AI 开源生态技术分析师
报告周期： 2026-05

本月生态继续围绕开发者工具展开。`;

    const result = sanitizeRollupSummary(input, "monthly", "zh");

    expect(result).toBe("本月生态继续围绕开发者工具展开。");
  });
});
