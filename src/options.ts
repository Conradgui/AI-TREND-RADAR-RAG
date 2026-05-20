import type { Lang } from "./i18n.ts";

const SUPPORTED_LANGS = new Set<Lang>(["zh", "en"]);

export function getReportLangs(raw = process.env["REPORT_LANGS"]): Lang[] {
  if (!raw?.trim()) return ["zh"];

  const langs = raw
    .split(",")
    .map((lang) => lang.trim())
    .filter((lang): lang is Lang => SUPPORTED_LANGS.has(lang as Lang));

  return langs.length ? Array.from(new Set(langs)) : ["zh"];
}

export function shouldSaveSourceReports(raw = process.env["SAVE_SOURCE_REPORTS"]): boolean {
  return raw === "1";
}
