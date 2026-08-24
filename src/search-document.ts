import { createHash } from "node:crypto";
import {
  buildTemporalMetadata,
  type EffectiveDateBasis,
  type PublicationDateSource,
} from "./temporal-semantics.ts";

export const SEARCH_DOCUMENT_SCHEMA_VERSION = 2 as const;
export const SEARCH_DOCUMENT_ID_SCHEME = "atr-v1" as const;

const TRACKING_PARAMS = new Set(["fbclid", "gclid", "dclid", "msclkid", "mc_cid", "mc_eid", "ref_src"]);
const CREDENTIAL_PARAM_RE =
  /(?:^|[_-])(?:api[_-]?key|access[_-]?token|auth|authorization|credential|password|secret|signature)(?:$|[_-])/i;
const ANCHOR_RE = /^[A-Za-z][A-Za-z0-9:._-]{0,127}$/;

/** Decode the standard entities that may survive upstream article extraction. */
function decodeDisplayText(value: unknown): string {
  return String(value ?? "")
    .replace(/&#(\d+);/g, (_match, digits: string) => String.fromCodePoint(Number(digits)))
    .replace(/&#x([\da-f]+);/gi, (_match, digits: string) =>
      String.fromCodePoint(Number.parseInt(digits, 16)),
    )
    .replace(/&quot;/gi, '"')
    .replace(/&apos;/gi, "'")
    .replace(/&#39;/gi, "'")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&");
}

/** Input boundary for projecting one dated candidate pool into searchable items. */
export interface CandidatePoolInput {
  date: string;
  reportId: string;
  reportType: "daily" | "rollup";
  candidates: unknown[];
}

/** Original upstream editorial fields rendered by the item detail view. */
export interface SearchDocumentDisplayFields {
  recommended_topic: string;
  reason: string;
  angle: string;
  evidence: string[];
}

/** Producer-owned mapping to a stable anchor in a rendered daily report. */
export interface SearchDocumentReportTarget {
  report_id: string;
  anchor_id: string;
}

/** Versioned, publication-safe item shared by static search and future RAG projection. */
export interface SearchDocument {
  schema_version: typeof SEARCH_DOCUMENT_SCHEMA_VERSION;
  id_scheme: typeof SEARCH_DOCUMENT_ID_SCHEME;
  content_id: string;
  daily_item_id: string;
  occurrence_id: string;
  item_anchor: string;
  date: string;
  report_date: string;
  publication_date: string | null;
  publication_date_source: PublicationDateSource;
  source_updated_at: string | null;
  observed_at: string;
  ingested_at: string | null;
  effective_date: string;
  effective_date_basis: EffectiveDateBasis;
  report_id: string;
  report_type: "daily";
  result_type: "item";
  title: string;
  normalized_title: string;
  summary: string;
  source: string;
  category: string;
  score: number;
  action: string;
  display_fields: SearchDocumentDisplayFields;
  tags: string[];
  entities: string[];
  aliases: string[];
  external_url: string | null;
  local_url: string;
  report_target: SearchDocumentReportTarget | null;
  content_fingerprint: string;
  occurrence_fingerprint: string;
  duplicate_count: number;
  identity_quality: "stable" | "degraded";
  legacy_ids: string[];
}

/** Non-sensitive build diagnostic; never includes rejected URL credential values. */
export interface SearchDocumentDiagnostic {
  date: string;
  field: string;
  category: string;
}

/** Search-document output plus the source count needed for coverage auditing. */
export interface SearchDocumentBuildResult {
  sourceCandidateCount: number;
  documents: SearchDocument[];
  diagnostics: SearchDocumentDiagnostic[];
}

type CandidateRecord = Record<string, unknown>;

interface PreparedCandidate {
  candidate: CandidateRecord;
  canonicalUrl: string | null;
  source: string;
  normalizedSource: string;
  title: string;
  normalizedTitle: string;
  upstreamId: string;
  exactKey: string;
  duplicateCount: number;
  baseIdentity: string;
}

/** Normalize identity text without applying semantic aliases or fuzzy correction. */
export function normalizeSearchText(value: unknown): string {
  return String(value ?? "")
    .normalize("NFKC")
    .toLocaleLowerCase("en-US")
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim()
    .replace(/\s+/g, " ");
}

function digest(value: string): string {
  return createHash("sha256").update(value).digest("hex").slice(0, 32);
}

function dailyItemId(date: string, identity: string): string {
  return `ATR-${date.replaceAll("-", "")}-${digest(identity).slice(0, 6).toUpperCase()}`;
}

function legacyOccurrenceId(date: string, reportId: string, candidateIdentity: string): string {
  return digest(`sd-v1|${date}|${reportId}|${candidateIdentity}`);
}

function stableStringify(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(",")}]`;
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    return `{${Object.keys(record)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stableStringify(record[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value) ?? "null";
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function stringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string");
}

function removeCdata(value: string): string {
  const trimmed = value.trim();
  return trimmed.startsWith("<![CDATA[") && trimmed.endsWith("]]>") ? trimmed.slice(9, -3).trim() : trimmed;
}

function hasCredentialParam(params: URLSearchParams): boolean {
  for (const key of params.keys()) {
    if (CREDENTIAL_PARAM_RE.test(key)) return true;
  }
  return false;
}

/** Canonicalize a public HTTP(S) URL and reject credential-bearing inputs. */
export function canonicalizeExternalUrl(raw: unknown): {
  url: string | null;
  error: string | null;
} {
  const cleaned = removeCdata(stringValue(raw));
  if (!cleaned) return { url: null, error: null };

  try {
    const url = new URL(cleaned);
    if (url.protocol !== "http:" && url.protocol !== "https:") {
      return { url: null, error: "invalid_protocol" };
    }
    if (url.username || url.password) {
      return { url: null, error: "credential_in_authority" };
    }
    if (hasCredentialParam(url.searchParams)) {
      return { url: null, error: "credential_in_query" };
    }
    if (url.hash.includes("=")) {
      const fragmentParams = new URLSearchParams(url.hash.slice(1));
      if (hasCredentialParam(fragmentParams)) {
        return { url: null, error: "credential_in_fragment" };
      }
    }

    for (const key of [...url.searchParams.keys()]) {
      if (key.toLowerCase().startsWith("utm_") || TRACKING_PARAMS.has(key.toLowerCase())) {
        url.searchParams.delete(key);
      }
    }
    url.hostname = url.hostname.toLowerCase();
    if (
      (url.protocol === "https:" && url.port === "443") ||
      (url.protocol === "http:" && url.port === "80")
    ) {
      url.port = "";
    }
    return { url: url.toString(), error: null };
  } catch {
    return { url: null, error: "invalid_url" };
  }
}

function upstreamItemId(candidate: CandidateRecord): string {
  for (const key of ["id", "itemId", "item_id", "guid"]) {
    const value = stringValue(candidate[key]).trim();
    if (value) return value;
  }
  return "";
}

function parseReportTarget(candidate: CandidateRecord, reportId: string): SearchDocumentReportTarget | null {
  const raw = candidate.report_target ?? candidate.reportTarget;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const target = raw as Record<string, unknown>;
  const targetReport = stringValue(target.report_id ?? target.reportId);
  const anchorId = stringValue(target.anchor_id ?? target.anchorId);
  if (targetReport !== reportId || !ANCHOR_RE.test(anchorId)) return null;
  return { report_id: targetReport, anchor_id: anchorId };
}

function prepareCandidates(input: CandidatePoolInput): {
  prepared: PreparedCandidate[];
  diagnostics: SearchDocumentDiagnostic[];
} {
  const diagnostics: SearchDocumentDiagnostic[] = [];
  const exactGroups = new Map<string, { candidate: CandidateRecord; count: number }>();

  for (const raw of input.candidates) {
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
      diagnostics.push({ date: input.date, field: "candidate", category: "invalid_record" });
      continue;
    }
    const candidate = raw as CandidateRecord;
    const title = decodeDisplayText(candidate.title ?? candidate.topic).trim();
    if (!title) {
      diagnostics.push({ date: input.date, field: "title", category: "missing_title" });
      continue;
    }
    const exactKey = stableStringify(candidate);
    const existing = exactGroups.get(exactKey);
    if (existing) existing.count += 1;
    else exactGroups.set(exactKey, { candidate, count: 1 });
  }

  const prepared = [...exactGroups.entries()].map(([exactKey, group]) => {
    const candidate = group.candidate;
    const title = decodeDisplayText(candidate.title ?? candidate.topic).trim();
    const source = decodeDisplayText(candidate.source).trim();
    const normalizedSource = normalizeSearchText(source) || "unknown-source";
    const canonical = canonicalizeExternalUrl(candidate.url);
    if (canonical.error) {
      diagnostics.push({ date: input.date, field: "url", category: canonical.error });
    }
    const upstreamId = upstreamItemId(candidate);
    const baseIdentity = upstreamId
      ? `upstream:${normalizedSource}:${upstreamId}`
      : canonical.url
        ? `url:${canonical.url}|source:${normalizedSource}`
        : `fallback:${normalizedSource}|title:${normalizeSearchText(title)}`;
    return {
      candidate,
      canonicalUrl: canonical.url,
      source,
      normalizedSource,
      title,
      normalizedTitle: normalizeSearchText(title),
      upstreamId,
      exactKey,
      duplicateCount: group.count,
      baseIdentity,
    };
  });

  return { prepared, diagnostics };
}

/** Build deterministic daily item documents; ambiguous identities fail closed. */
export function buildSearchDocuments(input: CandidatePoolInput): SearchDocumentBuildResult {
  if (input.reportType !== "daily") {
    return { sourceCandidateCount: 0, documents: [], diagnostics: [] };
  }

  const { prepared, diagnostics } = prepareCandidates(input);
  const titlesByBase = new Map<string, Set<string>>();
  for (const item of prepared) {
    const titles = titlesByBase.get(item.baseIdentity) ?? new Set<string>();
    titles.add(item.normalizedTitle);
    titlesByBase.set(item.baseIdentity, titles);
  }

  const semanticGroups = new Map<string, PreparedCandidate[]>();
  for (const item of prepared) {
    const hasTitleVariants = (titlesByBase.get(item.baseIdentity)?.size ?? 0) > 1;
    const candidateIdentity = hasTitleVariants
      ? `${item.baseIdentity}|title:${item.normalizedTitle}`
      : item.baseIdentity;
    const group = semanticGroups.get(candidateIdentity) ?? [];
    group.push(item);
    semanticGroups.set(candidateIdentity, group);
  }

  const documents = [...semanticGroups.entries()].map(([candidateIdentity, variants]) => {
    if (variants.length !== 1) {
      throw new Error(`Ambiguous candidate identity on ${input.date}: ${digest(candidateIdentity)}`);
    }
    const item = variants[0]!;
    const candidate = item.candidate;
    const hasTitleVariants = (titlesByBase.get(item.baseIdentity)?.size ?? 0) > 1;
    const identityQuality: "stable" | "degraded" =
      !item.upstreamId && (!item.canonicalUrl || hasTitleVariants) ? "degraded" : "stable";
    const occurrenceId = dailyItemId(
      input.date,
      `${SEARCH_DOCUMENT_ID_SCHEME}|${input.date}|${input.reportId}|${candidateIdentity}`,
    );
    const contentId = digest(
      `${SEARCH_DOCUMENT_ID_SCHEME}|content|${
        item.upstreamId
          ? `upstream:${item.normalizedSource}:${item.upstreamId}`
          : (item.canonicalUrl ?? `${item.normalizedSource}|${item.normalizedTitle}`)
      }`,
    );
    const displayFields: SearchDocumentDisplayFields = {
      recommended_topic: decodeDisplayText(candidate.recommendedTopic ?? candidate.recommended_topic),
      reason: decodeDisplayText(candidate.reason),
      angle: decodeDisplayText(candidate.angle),
      evidence: stringArray(candidate.evidence).map(decodeDisplayText),
    };
    const temporal = buildTemporalMetadata(candidate, input.date);
    if (temporal.diagnostic) {
      diagnostics.push({
        date: input.date,
        field: "publication_date",
        category: temporal.diagnostic,
      });
    }
    const contentPayload = {
      title: item.title,
      summary: decodeDisplayText(candidate.summary),
      source: item.source,
      category: stringValue(candidate.category),
      score: typeof candidate.score === "number" ? candidate.score : 0,
      action: stringValue(candidate.action),
      display_fields: displayFields,
      tags: stringArray(candidate.tags),
      entities: stringArray(candidate.entities),
      aliases: stringArray(candidate.aliases),
      external_url: item.canonicalUrl,
      publication_date: temporal.publication_date,
    };
    const contentFingerprint = digest(stableStringify(contentPayload));
    const reportTarget = parseReportTarget(candidate, input.reportId);
    const duplicateCount = item.duplicateCount;

    return {
      schema_version: SEARCH_DOCUMENT_SCHEMA_VERSION,
      id_scheme: SEARCH_DOCUMENT_ID_SCHEME,
      content_id: contentId,
      daily_item_id: occurrenceId,
      occurrence_id: occurrenceId,
      item_anchor: `item-${occurrenceId}`,
      date: input.date,
      report_date: temporal.report_date,
      publication_date: temporal.publication_date,
      publication_date_source: temporal.publication_date_source,
      source_updated_at: temporal.source_updated_at,
      observed_at: temporal.observed_at,
      ingested_at: temporal.ingested_at,
      effective_date: temporal.effective_date,
      effective_date_basis: temporal.effective_date_basis,
      report_id: input.reportId,
      report_type: "daily" as const,
      result_type: "item" as const,
      title: item.title,
      normalized_title: item.normalizedTitle,
      summary: contentPayload.summary,
      source: item.source,
      category: contentPayload.category,
      score: contentPayload.score,
      action: contentPayload.action,
      display_fields: displayFields,
      tags: contentPayload.tags,
      entities: contentPayload.entities,
      aliases: contentPayload.aliases,
      external_url: item.canonicalUrl,
      local_url: `#${input.date}/${input.reportId}/item/${occurrenceId}`,
      report_target: reportTarget,
      content_fingerprint: contentFingerprint,
      occurrence_fingerprint: digest(
        stableStringify({ occurrence_id: occurrenceId, content_fingerprint: contentFingerprint }),
      ),
      duplicate_count: duplicateCount,
      identity_quality: identityQuality,
      legacy_ids: [legacyOccurrenceId(input.date, input.reportId, candidateIdentity)],
    } satisfies SearchDocument;
  });

  documents.sort(
    (a, b) =>
      b.score - a.score ||
      a.normalized_title.localeCompare(b.normalized_title) ||
      a.occurrence_id.localeCompare(b.occurrence_id),
  );

  const ids = new Set<string>();
  for (const document of documents) {
    if (ids.has(document.occurrence_id)) {
      throw new Error(`Search document occurrence_id collision: ${document.occurrence_id}`);
    }
    ids.add(document.occurrence_id);
  }

  return {
    sourceCandidateCount: input.candidates.length,
    documents,
    diagnostics,
  };
}
