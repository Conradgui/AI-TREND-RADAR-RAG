export type PublicationDateSource =
  | "upstream_declared"
  | "legacy_adapter_contract"
  | "legacy_evidence"
  | "unknown";
export type EffectiveDateBasis = "publication_date" | "report_date_fallback";

export interface TemporalMetadata {
  report_date: string;
  publication_date: string | null;
  publication_date_source: PublicationDateSource;
  source_updated_at: string | null;
  observed_at: string;
  ingested_at: string | null;
  effective_date: string;
  effective_date_basis: EffectiveDateBasis;
  diagnostic: "invalid_upstream_declared" | "invalid_legacy_evidence" | "unverified_legacy_date" | null;
}

const ISO_DATE_PREFIX = /^(\d{4})-(\d{2})-(\d{2})(?:$|T)/;
const LEGACY_PUBLICATION_PREFIX = "发布时间：";

/** Parse only an explicit ISO date/date-time and reject normalized impossible dates. */
export function normalizeExplicitDate(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const match = ISO_DATE_PREFIX.exec(value.trim());
  if (!match) return null;
  const [, yearText, monthText, dayText] = match;
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  if (year < 2000 || year > 2100) return null;
  const probe = new Date(Date.UTC(year, month - 1, day));
  if (probe.getUTCFullYear() !== year || probe.getUTCMonth() !== month - 1 || probe.getUTCDate() !== day)
    return null;
  return `${yearText}-${monthText}-${dayText}`;
}

/** Build one auditable time contract without guessing dates from article prose. */
export function buildTemporalMetadata(
  candidate: Record<string, unknown>,
  reportDate: string,
): TemporalMetadata {
  const sourceUpdatedAt = normalizeExplicitDate(candidate.sourceUpdatedAt ?? candidate.source_updated_at);
  const structuredValue = candidate.publishedAt ?? candidate.published_at;
  if (structuredValue !== undefined && structuredValue !== null && structuredValue !== "") {
    const publicationDate = normalizeExplicitDate(structuredValue);
    if (publicationDate) {
      return published(reportDate, publicationDate, "upstream_declared", sourceUpdatedAt);
    }
    return fallback(reportDate, "invalid_upstream_declared", sourceUpdatedAt);
  }

  const evidence = Array.isArray(candidate.evidence) ? candidate.evidence : [];
  const legacyLine = evidence.find(
    (item): item is string => typeof item === "string" && item.trim().startsWith(LEGACY_PUBLICATION_PREFIX),
  );
  if (legacyLine) {
    const legacyDate = normalizeExplicitDate(
      legacyLine.trim().slice(LEGACY_PUBLICATION_PREFIX.length).trim(),
    );
    if (legacyDate) {
      if (isLegacyPublicationSource(candidate.source)) {
        return published(reportDate, legacyDate, "legacy_adapter_contract", sourceUpdatedAt);
      }
      return fallback(
        reportDate,
        "unverified_legacy_date",
        sourceUpdatedAt ?? (isLegacyUpdateOnlySource(candidate.source) ? legacyDate : null),
      );
    }
    return fallback(reportDate, "invalid_legacy_evidence", sourceUpdatedAt);
  }
  return fallback(reportDate, null, sourceUpdatedAt);
}

function isLegacyPublicationSource(value: unknown): boolean {
  if (typeof value !== "string") return false;
  return /^(Hacker News|Product Hunt|ArXiv)$/i.test(value.trim());
}

function isLegacyUpdateOnlySource(value: unknown): boolean {
  if (typeof value !== "string") return false;
  return /^(GitHub(?: Trending| Search:.*)?|Hugging Face|Gitee)$/i.test(value.trim());
}

function fallback(
  reportDate: string,
  diagnostic: TemporalMetadata["diagnostic"],
  sourceUpdatedAt: string | null,
): TemporalMetadata {
  return {
    report_date: reportDate,
    publication_date: null,
    publication_date_source: "unknown",
    source_updated_at: sourceUpdatedAt,
    observed_at: reportDate,
    ingested_at: null,
    effective_date: reportDate,
    effective_date_basis: "report_date_fallback",
    diagnostic,
  };
}

function published(
  reportDate: string,
  publicationDate: string,
  source: PublicationDateSource,
  sourceUpdatedAt: string | null,
): TemporalMetadata {
  return {
    report_date: reportDate,
    publication_date: publicationDate,
    publication_date_source: source,
    source_updated_at: sourceUpdatedAt,
    observed_at: reportDate,
    ingested_at: null,
    effective_date: publicationDate,
    effective_date_basis: "publication_date",
    diagnostic: null,
  };
}
