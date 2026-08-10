# AI Trend Radar RAG

This context describes how the product turns retrieved trend material into grounded, auditable answers.

## Language

**Evidence Ledger（证据账本）**:
The request-scoped set of evidence actually returned by tools and eligible to support the final answer. Evidence outside the ledger cannot be presented as a citation for that answer.
_Avoid_: Citation pool, candidate references, retrieved results

**Evidence Record（证据记录）**:
A uniquely identifiable item in the Evidence Ledger that contains enough provenance for a user to inspect its origin and supported content.
_Avoid_: Source item, search hit, chunk

**Displayed Citation（展示引用）**:
A user-facing link or label derived from an Evidence Record that the final answer explicitly uses.
_Avoid_: Suggested source, related reading

**Grounded Claim（有据结论）**:
A claim in the final answer that is supported by at least one identified Evidence Record from the current request's Evidence Ledger.
_Avoid_: Model conclusion, likely fact

**Claim Citation（结论引用）**:
The binding from one core factual or analytical claim to one or more Evidence Record IDs. Headings, transitions, and explicitly labelled suggestions do not require Claim Citations.
_Avoid_: Answer-level sources, sentence-by-sentence footnotes

**Canonical Producer（唯一报告生产者）**:
The upstream `AI-TREND-RADAR` project that fetches public signals and publishes the official report artifacts consumed by this product.
_Avoid_: RAG scheduler, local crawler

**Daily Corpus Report（日语料报告）**:
The upstream daily `ai-topic-radar` report used as the report-level retrieval corpus because it preserves item-level source provenance and daily granularity. It is not itself a raw primary source.
_Avoid_: Raw evidence, primary source, daily rollup

**Rollup Report（趋势汇总报告）**:
A weekly or monthly derivative that selects and synthesizes Daily Corpus Reports for human browsing. It is excluded from vector and graph ingestion so repeated summaries do not distort retrieval.
_Avoid_: Independent evidence, primary corpus, additional daily report

**Corpus Sync（语料同步）**:
The one-way, validated transfer of published report artifacts from the Canonical Producer into this project. It does not fetch source websites or call an LLM.
_Avoid_: News crawl, report generation, upstream ingestion

**Official Channel（官方渠道）**:
A publisher-controlled API, feed, sitemap, or webpage that can provide first-party publication metadata or content. Different channels from the same publisher may complement each other rather than compete as duplicate sources.
_Avoid_: Website scraper, external search result, source URL

**Publication Record（发布记录）**:
A normalized first-party item with canonical URL, title, publication/update time, summary or content, and field-level provenance. It represents one publication even when multiple Official Channels describe it.
_Avoid_: Crawl result, RSS item, sitemap entry

**Content Completeness（内容完整度）**:
The declared quality state of a Publication Record, distinguishing complete content, official-summary-only, metadata-only, and missing-summary records. It is observable data quality, not a hidden implementation fallback.
_Avoid_: Fetch success, valid item, confidence score

**Publication Update（发布更新）**:
A meaningful change to an existing Publication Record after its original publication time. It may re-enter a daily report as an update but must not be represented as a newly published item.
_Avoid_: New article, sitemap lastmod, republished item
