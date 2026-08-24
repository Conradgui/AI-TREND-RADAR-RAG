import { describe, expect, it } from "vitest";
import {
  buildSearchDocuments,
  canonicalizeExternalUrl,
  type CandidatePoolInput,
} from "../search-document.ts";

const baseCandidate = {
  title: "Apple Is Getting This Wrong",
  summary: "Original upstream summary.",
  recommendedTopic: "Apple 为什么值得关注？",
  url: "https://openai.com/index/apple/?utm_source=rss",
  source: "OpenAI",
  category: "标杆企业动向",
  score: 98,
  action: "深挖",
  angle: "从竞争格局切入",
  reason: "官方一手信号",
  evidence: ["来源：OpenAI"],
  tags: ["openai"],
};

function pool(candidates: unknown[], overrides: Partial<CandidatePoolInput> = {}): CandidatePoolInput {
  return {
    date: "2026-08-05",
    reportId: "ai-topic-radar",
    reportType: "daily",
    candidates,
    ...overrides,
  };
}

describe("buildSearchDocuments", () => {
  it("builds one detail-ready document from the real candidates shape", () => {
    const result = buildSearchDocuments(pool([baseCandidate]));

    expect(result.sourceCandidateCount).toBe(1);
    expect(result.documents).toHaveLength(1);
    expect(result.documents[0]).toMatchObject({
      schema_version: 2,
      id_scheme: "atr-v1",
      date: "2026-08-05",
      report_date: "2026-08-05",
      publication_date: null,
      publication_date_source: "unknown",
      source_updated_at: null,
      observed_at: "2026-08-05",
      ingested_at: null,
      effective_date: "2026-08-05",
      effective_date_basis: "report_date_fallback",
      report_id: "ai-topic-radar",
      title: baseCandidate.title,
      summary: baseCandidate.summary,
      external_url: "https://openai.com/index/apple/",
      duplicate_count: 1,
      report_target: null,
      display_fields: {
        recommended_topic: baseCandidate.recommendedTopic,
        reason: baseCandidate.reason,
        angle: baseCandidate.angle,
        evidence: baseCandidate.evidence,
      },
    });
    expect(result.documents[0]?.local_url).toMatch(
      /^#2026-08-05\/ai-topic-radar\/item\/ATR-20260805-[A-F0-9]{6}$/,
    );
    expect(result.documents[0]?.daily_item_id).toBe(result.documents[0]?.occurrence_id);
    expect(result.documents[0]?.legacy_ids).toEqual([expect.stringMatching(/^[a-f0-9]{32}$/)]);
  });

  it("preserves a structured upstream publication date without changing report identity", () => {
    const document = buildSearchDocuments(pool([{ ...baseCandidate, publishedAt: "2022-02-11T09:30:00Z" }]))
      .documents[0]!;

    expect(document.report_date).toBe("2026-08-05");
    expect(document.publication_date).toBe("2022-02-11");
    expect(document.publication_date_source).toBe("upstream_declared");
    expect(document.effective_date).toBe("2022-02-11");
    expect(document.effective_date_basis).toBe("publication_date");
    expect(document.occurrence_id).toMatch(/^ATR-20260805-/);
  });

  it("keeps a source update date separate from publication semantics", () => {
    const document = buildSearchDocuments(
      pool([{ ...baseCandidate, sourceUpdatedAt: "2026-08-04T10:00:00Z" }]),
    ).documents[0]!;

    expect(document.publication_date).toBeNull();
    expect(document.source_updated_at).toBe("2026-08-04");
    expect(document.effective_date).toBe("2026-08-05");
    expect(document.effective_date_basis).toBe("report_date_fallback");
  });

  it("keeps a valid historical evidence date unverified instead of promoting it to publication", () => {
    const result = buildSearchDocuments(
      pool([{ ...baseCandidate, evidence: ["来源：OpenAI", "发布时间：2024-07-25"] }]),
    );
    const document = result.documents[0]!;

    expect(document.publication_date).toBeNull();
    expect(document.publication_date_source).toBe("unknown");
    expect(document.effective_date).toBe("2026-08-05");
    expect(result.diagnostics).toContainEqual({
      date: "2026-08-05",
      field: "publication_date",
      category: "unverified_legacy_date",
    });
  });

  it("recovers an update-only legacy source date only as source_updated_at", () => {
    const document = buildSearchDocuments(
      pool([{ ...baseCandidate, source: "GitHub Search:rag", evidence: ["发布时间：2024-07-25"] }]),
    ).documents[0]!;

    expect(document.publication_date).toBeNull();
    expect(document.source_updated_at).toBe("2024-07-25");
    expect(document.effective_date_basis).toBe("report_date_fallback");
  });

  it("recovers a legacy publication-event date through the audited adapter contract", () => {
    const document = buildSearchDocuments(
      pool([{ ...baseCandidate, source: "Hacker News", evidence: ["发布时间：2026-08-11"] }]),
    ).documents[0]!;

    expect(document.publication_date).toBe("2026-08-11");
    expect(document.publication_date_source).toBe("legacy_adapter_contract");
    expect(document.source_updated_at).toBeNull();
    expect(document.effective_date).toBe("2026-08-11");
    expect(document.effective_date_basis).toBe("publication_date");
  });

  it("does not promote a legacy official-site sitemap date to publication", () => {
    const document = buildSearchDocuments(
      pool([{ ...baseCandidate, source: "OpenAI", evidence: ["发布时间：2026-08-11"] }]),
    ).documents[0]!;

    expect(document.publication_date).toBeNull();
    expect(document.publication_date_source).toBe("unknown");
    expect(document.source_updated_at).toBeNull();
  });

  it("does not promote legacy Chinese-adapter fallback dates to publication", () => {
    const document = buildSearchDocuments(
      pool([{ ...baseCandidate, source: "掘金", evidence: ["发布时间：2026-08-12"] }]),
    ).documents[0]!;

    expect(document.publication_date).toBeNull();
    expect(document.publication_date_source).toBe("unknown");
  });

  it("rejects malformed publication dates instead of silently treating them as recent", () => {
    const result = buildSearchDocuments(pool([{ ...baseCandidate, evidence: ["发布时间：+058576-06"] }]));
    const document = result.documents[0]!;

    expect(document.publication_date).toBeNull();
    expect(document.publication_date_source).toBe("unknown");
    expect(document.effective_date).toBe("2026-08-05");
    expect(result.diagnostics).toContainEqual({
      date: "2026-08-05",
      field: "publication_date",
      category: "invalid_legacy_evidence",
    });
  });

  it("does not infer a publication date from prose in a summary", () => {
    const document = buildSearchDocuments(
      pool([{ ...baseCandidate, summary: "Originally published on November 29, 2023." }]),
    ).documents[0]!;

    expect(document.publication_date).toBeNull();
    expect(document.effective_date_basis).toBe("report_date_fallback");
  });

  it("decodes upstream HTML entities before publishing searchable display text", () => {
    const result = buildSearchDocuments(
      pool([
        {
          ...baseCandidate,
          title: "Learning more about Claude&#x27;s mathematical capabilities",
          summary: "Claude &amp; mathematics",
          recommendedTopic: "Why Claude&#x27;s result matters",
        },
      ]),
    );

    expect(result.documents[0]?.title).toBe("Learning more about Claude's mathematical capabilities");
    expect(result.documents[0]?.summary).toBe("Claude & mathematics");
    expect(result.documents[0]?.display_fields.recommended_topic).toBe("Why Claude's result matters");
  });

  it("does not change occurrence identity when a mutable summary is repaired", () => {
    const first = buildSearchDocuments(pool([baseCandidate])).documents[0]!;
    const repaired = buildSearchDocuments(pool([{ ...baseCandidate, summary: "Repaired upstream summary." }]))
      .documents[0]!;

    expect(repaired.occurrence_id).toBe(first.occurrence_id);
    expect(repaired.content_fingerprint).not.toBe(first.content_fingerprint);
  });

  it("links repeated observations through stable content identity while preserving each report occurrence", () => {
    const first = buildSearchDocuments(pool([baseCandidate])).documents[0]!;
    const nextDay = buildSearchDocuments(pool([baseCandidate], { date: "2026-08-06" })).documents[0]!;

    expect(nextDay.content_id).toBe(first.content_id);
    expect(nextDay.occurrence_id).not.toBe(first.occurrence_id);
    expect(first.observed_at).toBe("2026-08-05");
    expect(nextDay.observed_at).toBe("2026-08-06");
  });

  it("keeps ids deterministic when candidate order changes", () => {
    const second = {
      ...baseCandidate,
      title: "Introducing The OpenAI Economic Research Exchange",
      url: "https://openai.com/index/economic-research-exchange/",
    };
    const forward = buildSearchDocuments(pool([baseCandidate, second])).documents;
    const reversed = buildSearchDocuments(pool([second, baseCandidate])).documents;

    expect(reversed.map((item) => item.occurrence_id).sort()).toEqual(
      forward.map((item) => item.occurrence_id).sort(),
    );
  });

  it("distinguishes same-url same-source variants without using summary", () => {
    const result = buildSearchDocuments(
      pool([
        baseCandidate,
        { ...baseCandidate, title: "Apple lawsuit document analysis", summary: "Another summary" },
      ]),
    );

    expect(result.documents).toHaveLength(2);
    expect(new Set(result.documents.map((item) => item.occurrence_id)).size).toBe(2);
    expect(result.documents.every((item) => item.identity_quality === "degraded")).toBe(true);
  });

  it("aggregates exact duplicates and makes the audit equation explicit", () => {
    const result = buildSearchDocuments(pool([baseCandidate, { ...baseCandidate }]));

    expect(result.documents).toHaveLength(1);
    expect(result.documents[0]?.duplicate_count).toBe(2);
    expect(result.documents.reduce((sum, item) => sum + item.duplicate_count, 0)).toBe(
      result.sourceCandidateCount,
    );
  });

  it("fails instead of silently merging non-identical candidates with one stable identity", () => {
    expect(() =>
      buildSearchDocuments(
        pool([baseCandidate, { ...baseCandidate, summary: "A different candidate record" }]),
      ),
    ).toThrow(/Ambiguous candidate identity/);
  });

  it("counts and diagnoses malformed source candidates instead of hiding a coverage gap", () => {
    const result = buildSearchDocuments(pool([{ source: "Missing title" }]));

    expect(result.sourceCandidateCount).toBe(1);
    expect(result.documents).toEqual([]);
    expect(result.diagnostics).toContainEqual({
      date: "2026-08-05",
      field: "title",
      category: "missing_title",
    });
  });

  it("does not create retrieval documents for browse-only rollups", () => {
    const result = buildSearchDocuments(
      pool([baseCandidate], { reportId: "ai-weekly", reportType: "rollup" }),
    );

    expect(result.documents).toEqual([]);
    expect(result.sourceCandidateCount).toBe(0);
  });

  it("only exposes producer-supplied report targets with a valid stable anchor", () => {
    const valid = buildSearchDocuments(
      pool([
        { ...baseCandidate, report_target: { report_id: "ai-topic-radar", anchor_id: "entry-openai-1" } },
      ]),
    ).documents[0]!;
    const guessed = buildSearchDocuments(
      pool([
        { ...baseCandidate, report_target: { report_id: "ai-topic-radar", anchor_id: "../title-match" } },
      ]),
    ).documents[0]!;

    expect(valid.report_target).toEqual({
      report_id: "ai-topic-radar",
      anchor_id: "entry-openai-1",
    });
    expect(guessed.report_target).toBeNull();
  });
});

describe("canonicalizeExternalUrl", () => {
  it("removes CDATA and tracking parameters while preserving identity parameters", () => {
    expect(
      canonicalizeExternalUrl("<![CDATA[https://example.com/post?id=42&utm_campaign=daily#section-2]]>"),
    ).toEqual({
      url: "https://example.com/post?id=42#section-2",
      error: null,
    });
  });

  it("rejects credentials in authority, query, or fragment without echoing their values", () => {
    for (const unsafe of [
      "https://user:secret@example.com/post",
      "https://example.com/post?api_key=secret-value",
      "https://example.com/post#access_token=secret-value",
    ]) {
      const result = canonicalizeExternalUrl(unsafe);
      expect(result.url).toBeNull();
      expect(result.error).toMatch(/credential/);
      expect(result.error).not.toContain("secret-value");
    }
  });
});
