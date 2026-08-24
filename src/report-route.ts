const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
const REPORT_RE = /^[a-z0-9][a-z0-9-]{0,63}$/;
const OCCURRENCE_RE = /^(?:ATR-\d{8}-[A-F0-9]{6}|[a-f0-9]{32})$/;

/** Parsed dashboard route for either a report or one stable item occurrence. */
export interface ReportRoute {
  date: string;
  report: string;
  occurrenceId: string | null;
}

/** Parse only canonical report and item-detail hash routes. */
export function parseReportRoute(hash: string): ReportRoute | null {
  const segments = hash.replace(/^#/, "").split("/");
  const [date, report, marker, occurrenceId] = segments;
  if (!date || !report || !DATE_RE.test(date) || !REPORT_RE.test(report)) return null;

  if (segments.length === 2) return { date, report, occurrenceId: null };
  if (segments.length === 4 && marker === "item" && occurrenceId && OCCURRENCE_RE.test(occurrenceId)) {
    return { date, report, occurrenceId };
  }
  return null;
}

/** Format a validated route without encoding its path separators. */
export function formatReportRoute(route: ReportRoute): string {
  if (!DATE_RE.test(route.date) || !REPORT_RE.test(route.report)) {
    throw new Error("Invalid report route");
  }
  if (route.occurrenceId === null) return `#${route.date}/${route.report}`;
  if (!OCCURRENCE_RE.test(route.occurrenceId)) throw new Error("Invalid occurrence id");
  return `#${route.date}/${route.report}/item/${route.occurrenceId}`;
}
