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
The human-readable daily `ai-topic-radar` report projected from Daily Signal Observations. It can be browsed and deep-linked, but the rendered report is neither raw primary evidence nor the canonical retrieval corpus.
_Avoid_: Raw evidence, primary source, report-level retrieval corpus, daily rollup

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

**Daily Item ID（日条目编号）**:
A user-visible, immutable identity assigned when one information item is admitted to a specific daily report, and the sole public identity propagated by downstream search, retrieval, citation, and navigation. Its date denotes the report admission date rather than the source publication date; re-running that daily pipeline preserves the same identity, while a meaningful Publication Update admitted on a later date receives a new Daily Item ID linked to the same publication.
_Avoid_: Row number, score ID, citation index, content fingerprint

**Daily Signal Observation（日信号观测）**:
A dated, independently identified record of a publication, project, product, or event admitted to a daily report. A later observation may describe the same underlying subject when its content or trend signals change materially.
_Avoid_: Duplicate article, daily copy, raw metric

**Longitudinal Trend（纵向趋势）**:
The time-ordered change of one underlying subject across multiple Daily Signal Observations.
_Avoid_: Repeated result, duplicate history

**Cross-sectional Trend（横向趋势）**:
A pattern supported by multiple distinct observations connected through shared topics, entities, sources, or events.
_Avoid_: Similar titles, same category, semantic cluster

**Hot Trend（热门趋势）**:
A recent Cross-sectional Trend supported primarily by repeated structural signals across distinct events or sources. A single major official announcement may be retained as a trend candidate, but does not by itself prove a repeated trend.
_Avoid_: Top-scored article, recent article list, repeated items from one publisher

**Worth-watching Open-source Project（值得关注的开源项目）**:
An open-source project whose frozen corpus evidence directly establishes relevance to the requested technology type. Relevance is judged before adoption signals; speculative novelty or future potential is not part of the first evaluation contract.
_Avoid_: Search-keyword hit, popular but unrelated repository, unverified product

**Inferred Relationship（推断关系）**:
A candidate connection derived from semantic or model-based analysis whose confidence and derivation remain explicit. It is not treated as a factual graph relationship until supported by verifiable evidence.
_Avoid_: Fact edge, confirmed relationship, graph truth

**Material Signal Change（实质信号变化）**:
A source-aware content or metric change significant enough to justify a new Daily Signal Observation. Its meaning is defined by the source's observable signals rather than one global percentage threshold.
_Avoid_: Any change, score fluctuation, daily duplicate

**Query Frame（问题框架）**:
A request-scoped interpretation of the user's task, subject, time expectation, evidence need, and ambiguity. It may contain more than one task signal and is never stored as a property of a corpus item.
_Avoid_: Keyword intent, permanent query label, routing guess

**Evidence Candidate（候选证据）**:
A corpus or external record admitted for request-scoped relevance evaluation but not yet eligible to support the answer. Becoming a candidate does not make it an Evidence Record in the Evidence Ledger.
_Avoid_: Citation, answer evidence, search result

**Relevance Tier（相关性层级）**:
The request-scoped role assigned to an Evidence Candidate after judging how directly it answers the current Query Frame: Primary, Supplementary, Background, Unverified, or Excluded.
_Avoid_: Global importance class, source rank, fixed news tier

**Primary Evidence（主答案证据）**:
Evidence that directly answers the current Query Frame and is eligible to determine the main answer.
_Avoid_: Top-scored item, newest item, generally important news

**Supplementary Evidence（补充证据）**:
Evidence that is relevant but not direct or central enough to determine the main answer; it may qualify implications, adjacent developments, or secondary changes.
_Avoid_: Weak primary evidence, filler result

**Background Evidence（背景证据）**:
Older or contextual evidence that helps explain the current answer but must not be presented as a current development or primary finding.
_Avoid_: Recent update, main result, historical noise

**Dynamic Importance（动态重要性）**:
The request-scoped judgment of an item's impact breadth, impact depth, actor prominence, novelty, and public significance after its Relevance Tier is known. It is not a permanent corpus label.
_Avoid_: Global important-news flag, upstream score, popularity alone

**Query-relative Freshness（问题相关新鲜度）**:
How well an item's event or publication time satisfies the Query Frame's time expectation. It matters strongly for current-news tasks and may matter little for explanatory or historical tasks.
_Avoid_: Latest-first ordering, report date alone, universal recency boost

**Evidence Quality（证据质量）**:
The request-scoped fitness of evidence based on provenance, completeness, corroboration, and claim support. It is distinct from source popularity and from whether an item is relevant.
_Avoid_: Authority score alone, field completeness alone, relevance score

**Intent Signal（意图信号）**:
An independently retained clue about what the user wants, such as recency, comparison, verification, navigation, or relationship analysis. Multiple Intent Signals may coexist and do not overwrite one another.
_Avoid_: Final route, keyword intent, single intent label

**Task Route（任务路线）**:
The request-scoped primary user task selected from the stable product task families, with optional supporting routes for compound questions. It determines the evidence view and answer contract without replacing the original query.
_Avoid_: Intent Signal, tool choice, prompt name

**Trend Discovery（动态与趋势发现）**:
The Task Route for questions asking what recently happened or what deserves attention. It returns a news-ranked list or a trend cluster, but does not by itself explain how a structure evolved.
_Avoid_: Timeline, relationship analysis, any query containing the word trend

**Temporal Relation Exploration（时间与关系探索）**:
The Task Route for questions asking how something evolved, how entities or events relate, or what longitudinal or cross-sectional structure exists. Its answer mode must be timeline, relation, longitudinal trend, or cross-sectional trend.
_Avoid_: Recent-news list, important-update ranking, co-occurrence presented as causality

**Route Contract（路由合同）**:
The versioned request-scoped agreement that binds the original query, Intent Signals, Task Route, rewrite policy, evidence requirements, answer-construction contract, output contract, and budget profile. Generative routes use a Prompt Contract; deterministic navigation uses an Answer Builder Contract.
_Avoid_: Rewritten query, QueryPlan string, routing log

**Query Variant（检索变体）**:
A retrieval-oriented expression derived from the original query for one search channel while preserving exact user constraints. It is not a replacement for the user's question or a new statement of intent.
_Avoid_: Polished question, final prompt, inferred answer

**Prompt Package（提示包）**:
The task-specific, evidence-bounded input compiled for answer generation from one Route Contract and one Evidence Bundle. It carries an output contract and may not alter the route or evidence tiers.
_Avoid_: System prompt string, user query, retrieval query

**Answer Envelope（回答信封）**:
The validated machine-readable answer object whose claims, evidence references, limitations, and route-specific fields satisfy the current output contract. It is the source for presentation but is not itself the user interface.
_Avoid_: Raw model JSON, Markdown answer, chat message

**Answer Renderer（回答渲染器）**:
The deterministic transformation from an Answer Envelope into a user-facing presentation such as Markdown or UI cards without changing claims, evidence tiers, ordering, or links.
_Avoid_: Answer generator, prompt template, model formatter
