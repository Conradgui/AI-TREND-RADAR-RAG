# AI Trend Radar RAG Roadmap

## Product Goal

Build AI Trend Radar RAG into a personal AI research cockpit.

The first useful product is not a public SaaS and not the original AI Trend Radar web Agent button. The first useful product is a reliable local knowledge system that can answer questions from fresh AI Trend Radar corpus, cite evidence, admit when evidence is insufficient, and later support automated trend research workflows.

## Target Architecture

The target architecture is defined in `specs/2026-06-22-target-architecture-spec.md`.

Short version:

1. Data Layer
   - Sync AI Trend Radar public corpus into this project.
2. Index Layer
   - Build vector and graph indexes from citation-ready corpus data.
3. Retrieval Layer
   - Plan queries, apply metadata filters, retrieve from vector/graph stores, and later rerank.
4. Evidence Layer
   - Preserve internal/external citations, source quality, deep fetch records, and uncertainty.
5. Agent Layer
   - Route bounded tools such as corpus search, web search, URL fetch, and comparison.
6. Evaluation Layer
   - Use golden questions, deterministic rubrics, and smoke checks to prevent regressions.
7. Runtime Layer
   - Keep local/server behavior controlled by config, CI, and explicit runtime toggles.
8. Integration Layer
   - After the RAG core and Nexus-like cockpit are mature, reduce deployment friction through a single-repo local demo workspace.

## Status Labels

Use these labels instead of vague "done" language:

- `Planned`: not implemented yet.
- `Implemented`: code or data path exists.
- `Locally Verified`: deterministic local tests or smoke checks passed.
- `Live Smoke Verified`: a low-volume real API/runtime check passed.
- `CI Ready`: deterministic checks are wired into the canonical check command.
- `Production Ready`: deployable with monitoring, failure modes, cost controls, and security review.
- `Not Claimed`: intentionally not represented as complete.

## P0: Fresh Corpus Sync + RAG Grounding

**Goal:** Make AI Trend Radar RAG fresh, runnable, and verifiable.

### Modules

1. Project record folder
   - Meaning: durable documentation for plans, decisions, evidence, and execution logs.
   - Role: keeps multi-step work from drifting.
   - Verification: this folder exists and contains roadmap, plan, decision, and evaluation seed files.

2. Fresh corpus sync
   - Meaning: pull AI Trend Radar Pages artifacts into this RAG project.
   - Role: fixes stale local corpus without requiring every upstream scraping token.
   - Source: `https://conradgui.github.io/AI-TREND-RADAR`.
   - Verification: local `manifest.json` reflects the latest online date, and recent digest files exist locally.

3. Topic pool compatibility
   - Meaning: support the real `topic-pool.json` shape, especially `candidates`.
   - Role: prevents RAG from silently missing structured topic evidence.
   - Verification: tests prove both `candidates` and legacy `topics` shapes load correctly.

4. RAG ingestion grounding
   - Meaning: every markdown chunk and topic candidate carries source metadata.
   - Role: retrieval results can become citations, not anonymous text.
   - Verification: ingested chunks include date, report type, title or topic, source, URL when available, and evidence snippets.

5. Citation path
   - Meaning: `/chat` returns evidence-backed citations instead of an empty list.
   - Role: establishes trust and debuggability.
   - Verification: answerable golden questions return non-empty citations with date, source, title, and excerpt.

6. First golden questions
   - Meaning: the first evaluation set.
   - Role: turns quality discussion from opinion into regression checks.
   - Verification: the five seed questions have expected behavior and are used in a repeatable local evaluation.

## P1: Retrieval Quality + Agent Control

**Goal:** Improve accuracy and control after the P0 baseline is measurable.

### Modules

1. Query understanding
   - Recognize intent, topic, source, and time range.
   - Rewrite vague user questions into retriever-friendly queries.

2. Hybrid retrieval quality
   - Improve vector plus graph retrieval with metadata filters, dynamic top-k, and reranking.
   - Measure retrieval relevance before and after changes.

3. Graph RAG hardening
   - Normalize entities.
   - Add stronger topic/entity/source/date relationships.
   - Track relation evidence and confidence.

4. Agent control
   - Add tool routing, step limits, fallback behavior, and call traces.
   - Keep simple questions cheap and complex questions multi-step.

## P2: Trend Research Workflow

**Goal:** Move from chat answers to repeatable research output.

### Modules

1. Trend brief workflow
   - Input: a topic such as RAG, Claude, GitHub AI tools, or Google knowledge frameworks.
   - Output: timeline, key evidence, source comparison, uncertainty, and recommended next actions.

2. Knowledge artifacts
   - Precompute topic timelines, entity cards, source coverage snapshots, and daily knowledge summaries.
   - Use artifacts to reduce repeated ad hoc retrieval.

3. Observability
   - Log query, retrieval candidates, citations, tool calls, duration, and failure reason.
   - Use logs to improve the evaluation set.

## Stage 2.5: Unified Local Demo Workspace

**Goal:** Reduce two-project deployment friction without prematurely building a full desktop/local software product.

### Product Rationale

Stage 2.5 is the accepted B plan.

The user should experience one local workspace:

- one repo to clone;
- one `.env` to configure;
- one local workflow to prepare data, sync corpus, ingest indexes, and start the dashboard/Agent.

The internal architecture should still preserve boundaries between:

- upstream trend data production;
- corpus sync;
- indexing;
- RAG/Agent analysis;
- dashboard experience.

### Candidate Implementation

Evaluate after Nexus-like iteration:

1. `external/ai-trend-radar` local upstream folder.
2. Git submodule.
3. Git subtree.
4. Extracted package.

Recommended first path:

- start with a simple local upstream folder or equivalent;
- expose one unified local command sequence;
- avoid deep code merge until the workflow proves valuable.

### Non-Goals

- Full desktop app.
- Production scheduler.
- Replacing all GitHub Actions behavior immediately.
- Multi-user SaaS.
- Long-running background app lifecycle management.

## P3 / Future Vision: Unified Local App

**Goal:** Consider a complete local-first software product only after Stage 2.5 and Nexus-like usage prove the need.

### Modules

1. Local data-production replacement
   - Replace GitHub Actions with a local scheduler or app background worker if the unified workflow proves valuable.

2. Local dashboard or desktop shell
   - Move beyond localhost browser only if it materially improves user experience.

3. Team or SaaS expansion
   - Add user accounts, permissions, shared feedback, monitoring, and cost controls only after the personal cockpit is useful.

## Priority Rule

Do not add web search or public UI integration before the internal corpus is fresh, citations work, and the first evaluation set is repeatable. Otherwise the system becomes a generic chatbot with search instead of a grounded AI Trend Radar research product.

## Progress Snapshot

Last updated: 2026-06-24

### Completed

- P0 baseline: `Locally Verified`
- Fresh AI Trend Radar corpus sync: `Locally Verified`
- Topic-pool compatibility: `CI Ready`
- Citation-ready ingestion: `CI Ready`
- Chat citation path: `CI Ready`
- Golden questions: `CI Ready`
- Web-search tool boundary: `Implemented`
- Tavily external search for first needs-web path: `Live Smoke Verified`
- Canonical RAG focused check command: `CI Ready`

### P1 Completed Slices

- Query Understanding
  - Adds deterministic query plans with intent, topics, entities, sources, time window, web-search signal, retrieval query, and top-k.
  - Status: `CI Ready`.
- Hybrid Retrieval Quality Slice 1
  - Passes source/date metadata filters from query plans into vector retrieval.
  - Status: `CI Ready`.
- Query Plan Benchmark
  - Adds `pnpm rag:eval:plans`.
  - Status: `CI Ready`.
- Corpus Availability Benchmark
  - Adds `pnpm rag:eval:corpus`.
  - Current benchmark: Q1/Q2/Q3/Q4 have partial or strong local evidence signals; Q5 only has weak local signal and needs external evidence later.
  - Status: `CI Ready`.
- Runtime Readiness
  - Adds project `.venv`.
  - Installs RAG runtime dependencies.
  - Ingests local corpus into ChromaDB with 1346 chunks.
  - Verifies DeepSeek model access.
  - Adds vector-only chat fallback when Neo4j is unavailable.
  - Verifies `/health` and `/chat` in vector-only mode.
  - Status: vector-only runtime `Live Smoke Verified`; Neo4j graph runtime `Live Smoke Verified`.
- Live Answer Quality Benchmark
  - Adds `pnpm rag:eval:live-chat`.
  - Saves `docs/rag-transformation/evals/live-chat-snapshot-2026-06-22.json`.
  - Runs all five golden questions through vector-only RAG + DeepSeek.
  - Current result: 5/5 questions returned citations; Q5 safely refused unsupported OKF/ALM claims.
  - Status: `Live Smoke Verified`.
- Agent Control and Safety
  - Adds deterministic answer-policy modes: `internal_grounded`, `needs_external_evidence`, and `evidence_insufficient`.
  - Adds user-visible evidence-boundary disclosures to chat answers.
  - Adds `pnpm rag:eval:answer-policy`.
  - Saves `docs/rag-transformation/evals/live-chat-rubric-2026-06-22.json`.
  - Current rubric result: 5/5 live benchmark answers passed answer-policy checks.
  - Status: `CI Ready`.
- Tool Routing Contract
  - Adds deterministic tool-routing modes for `search_corpus`, planned `web_search`, planned `fetch_url`, and planned `compare_internal_and_external`.
  - Adds `query_understanding.tool_routing` to chat responses and live benchmark snapshots.
  - Adds `pnpm rag:eval:tool-routing`.
  - Saves `docs/rag-transformation/evals/live-tool-routing-rubric-2026-06-22.json`.
  - Current rubric result: 5/5 live benchmark rows passed routing-contract checks.
  - Status: `CI Ready`.
- External Search Tool Stub and Citation Schema
  - Adds required external citation fields and schema validation.
  - Adds a disabled `web_search` result shape that is explicit and non-fatal.
  - Adds `pnpm rag:eval:external-evidence`.
  - Saves `docs/rag-transformation/evals/external-evidence-readiness-2026-06-22.json`.
  - Current readiness result: passed.
  - Status: `CI Ready`.
- Search Provider Routing Strategy
  - Adds official-source-informed multi-provider routing strategy.
  - Adds provider profiles for Brave, Tavily, Exa, SerpAPI, and GitHub API.
  - Adds optional provider key config in `.env.example` and `rag/config.py`.
  - Adds `pnpm rag:eval:search-provider-routing`.
  - Saves `docs/rag-transformation/evals/search-provider-routing-2026-06-22.json`.
  - Initial deterministic snapshot: 2 needs-web questions detected, 0 configured external primary providers before local search API keys were added.
  - Status: `CI Ready`.
- Search Provider Adapter Interface
  - Adds provider-agnostic `SearchRequest` and unavailable-result shapes.
  - Adds disabled adapters and registry for known provider profiles.
  - Adds `pnpm rag:eval:search-provider-adapters`.
  - Saves `docs/rag-transformation/evals/search-provider-adapters-2026-06-22.json`.
  - Current readiness result: passed.
  - Status: `CI Ready`.
- First Live Tavily Provider
  - Adds Tavily live adapter behind the provider-agnostic interface.
  - Adds `pnpm rag:eval:tavily-live`.
  - Saves `docs/rag-transformation/evals/tavily-live-smoke-2026-06-22.json`.
  - Current smoke result: Tavily available, 1 external citation returned, 1 credit used.
  - Status: `Live Smoke Verified`.
- External Source Quality Controls and Excerpt Policy
  - Adds source quality classes and quality scores for external citations.
  - Replaces fixed 600-character excerpt truncation with source-aware excerpt limits.
  - Adds official-source domain policy for Tavily Google/OKF lookups.
  - Current smoke result: Tavily returned one `cloud.google.com` official citation, 1 credit used.
  - Status: `CI Ready`; Tavily official-source smoke `Live Smoke Verified`.
- External Evidence Merge Into Chat
  - Calls external search for `needs-web` chat questions when a configured provider exists.
  - Separates internal corpus citations from external web citations in the prompt.
  - Uses concise task-specific external search queries instead of sending the full user question to the search API.
  - Updates answer policy to `internal_and_external_grounded` when external citations are actually retrieved.
  - Adds `pnpm rag:eval:external-chat-smoke`.
  - Current smoke result: 12 citations total, 10 internal citations, 2 external citations, answer policy `internal_and_external_grounded`.
  - Status: `Live Smoke Verified`.
- External Evidence Answer Quality Benchmark
  - Adds deterministic quality scoring for answers that use external evidence.
  - Checks internal/external citation mix, answer labels, required citation fields, external-search trace, and weak-source uncertainty language.
  - Adds `pnpm rag:eval:external-answer-quality`.
  - Current rubric result: 1/1 external-chat smoke row passed, 0 failures.
  - Status: `CI Ready`.
- URL Fetch and Source Deepening Foundation
  - Adds safe URL fetch and lightweight HTML extraction.
  - Blocks non-HTTP schemes and private/local network targets.
  - Adds `deep_fetch` records for external citations that need deeper verification.
  - Current focused result: URL fetch tests passed and canonical RAG check includes the safety boundary.
  - Status: `CI Ready`.
- Deep Fetch Integration Policy
  - Adds bounded deep-fetch target selection for external citations.
  - Prioritizes official/academic/developer sources, then weak sources that need verification.
  - Adds optional `external_deep_fetcher` integration in chat.
  - Adds `query_understanding.deep_fetch` trace and prompt-level deep-fetch excerpts.
  - Current focused result: 113 tests passed.
  - Status: `CI Ready`; live runtime default `Not Claimed`.
- Live Deep Fetch Smoke and Runtime Toggle
  - Adds explicit `RAG_ENABLE_DEEP_FETCH` runtime flag.
  - Passes the live URL fetcher to chat only when the flag is explicitly enabled.
  - Exposes `deep_fetch_enabled` in `/health`.
  - Adds `pnpm rag:eval:deep-fetch-url-live`.
  - Updates URL fetch safety for managed-proxy DNS environments while still rejecting direct private/local/proxy IP access.
  - Current focused result: 118 tests passed.
  - Current live URL smoke result: Google Cloud official OKF page fetched successfully with status 200 and 3000-character extracted excerpt.
  - Current chat-level smoke result after provider expansion: OKF/ALM path used Brave fallback, returned 2 external citations, and triggered deep fetch for 2 URLs.
  - Status: runtime toggle `CI Ready`; live URL deep fetch `Live Smoke Verified`; end-to-end fallback plus deep-fetch `Live Smoke Verified`; perfect fetch success for every selected URL `Not Claimed`.
- Live Provider Adapter Expansion
  - Adds live Brave Search adapter for broad/recent web search.
  - Adds live Exa adapter for research and technical-article search.
  - Adds live GitHub repository search adapter for GitHub-specific questions.
  - Adds `pnpm rag:eval:search-provider-live`.
  - Current live smoke result: Brave, Exa, and GitHub all available and returned at least one citation.
  - Current focused result: 122 tests passed.
  - Status: adapters `CI Ready`; Brave/Exa/GitHub live smoke `Live Smoke Verified`; claim-level semantic conflict handling `Not Claimed`.
- Source Conflict Handling
  - Adds deterministic source review for external citations.
  - Assigns source roles: primary evidence, supporting context, weak context.
  - Adds source review instructions to the chat prompt.
  - Adds `query_understanding.source_review` trace.
  - Current focused result: 126 tests passed.
  - Status: minimal source role handling `CI Ready`; semantic contradiction detection `Not Claimed`.
- Graph Runtime Hardening Slice 1
  - Makes graph retrieval results citation-ready.
  - Adds graph metadata fields needed by citation building: date, source, title, URL, citation ID, excerpt, category, score.
  - Starts Neo4j through Docker Compose after Docker Desktop became available.
  - Ingests 14 digest dates into Neo4j and ChromaDB.
  - Current graph counts: 279 Topic nodes, 268 Entity nodes, 945 MENTIONS relationships, 812 APPEARED_ON relationships.
  - Adds `pnpm rag:eval:graph-runtime-live`.
  - Current live graph smoke result: 8 citations returned, including 4 graph citations.
  - Current focused result: 127 tests passed.
  - Status: graph citation-ready retrieval `CI Ready`; Neo4j live runtime `Live Smoke Verified`; vector plus graph runtime `Live Smoke Verified`; multi-hop graph reasoning `Not Claimed`.
- Provider Quality Evaluation
  - Adds deterministic provider quality matrix scoring.
  - Adds hybrid live chat benchmark across all five golden questions.
  - Measures citation coverage, graph citation coverage, external citation coverage, answer-policy mode, source review, and search trace.
  - Current hybrid benchmark result: 5/5 questions returned citations, 5/5 had graph citations, 2/2 needs-web questions had external citations.
  - Current provider quality matrix: 5 passed, 0 failed.
  - Current focused result: 131 tests passed.
  - Status: quality matrix `CI Ready`; hybrid live snapshot `Live Smoke Verified`; semantic correctness `Not Claimed`.
- Claim-Level Evaluation Seed
  - Adds deterministic claim-level seed checks for selected golden questions.
  - Checks required support, required citation types, forbidden overclaims, and uncertainty language.
  - Current seed covers Q1, Q2, and Q5.
  - Current claim matrix: 8 passed, 0 failed.
  - Current focused result: 136 tests passed.
  - Status: seed evaluator `CI Ready`; current hybrid snapshot claim seed `Locally Verified`; full semantic correctness `Not Claimed`.
- Retrieval Precision / Reranking Seed
  - Adds deterministic retrieval precision scoring for selected golden questions.
  - Classifies citations as relevant, redundant, distracting, or weak.
  - Current focused result: 140 tests passed.
  - Initial retrieval precision matrix: 0/3 passed; Q1/Q2 failed on redundancy, Q5 failed on weak/distracting citations.
  - After citation deduplication and noise filtering, retrieval precision matrix improved to 3/3 passed.
  - Status: evaluator `CI Ready`; after-filter benchmark `Locally Verified`; semantic reranking still `Not Claimed`.
- Citation Deduplication and Noise Filtering
  - Adds semantic citation deduplication by title/source/URL.
  - Adds conservative needs-web internal noise filtering after external evidence is available.
  - Adds official-source fallback continuation when the first provider returns only generic citations.
  - Current focused result: 143 tests passed.
  - Current after-filter retrieval precision matrix: 3 passed, 0 failed; citation count reduced from 32 to 13, distracting citations reduced from 3 to 0.
  - Current after-filter provider quality matrix: 5 passed, 0 failed.
  - Current after-filter claim matrix: 8 passed, 0 failed.
  - Official-source fallback live result: Tavily generic result fell through to Brave, which returned `cloud.google.com` official evidence for Q5.
  - Status: dedup/noise filtering `Live Smoke Verified`; official-source fallback `Live Smoke Verified`.
- Multi-Hop Graph Reasoning Seed
  - Adds deterministic graph reasoning seed for entity/topic/date/source relationship coverage.
  - Current live graph matrix: 3 passed, 0 failed.
  - Seed results: `rag` has 18 topics / 14 dates / 4 sources; `openai` has 29 topics / 8 dates / 3 sources; `ai-agent` has 16 topics / 14 dates / 2 sources.
  - Current focused result: 146 tests passed.
  - Status: graph relationship coverage `Live Smoke Verified`.
- Graph Question Planner
  - Adds deterministic graph relationship question detection.
  - Adds service-layer graph evidence retrieval and graph citation formatting.
  - Adds `pnpm rag:eval:graph-question-planner-live`.
  - Current live graph planner smoke: passed with RAG evidence across 18 topics, 14 dates, and 4 sources.
  - Current focused result: 152 tests passed.
  - Status: planner/service layer `Live Smoke Verified`; dedicated chat UI mode `Not Claimed`.
- Semantic Contradiction Detection Seed
  - Adds deterministic contradiction-risk checks for weak/mixed evidence overclaiming, forbidden strong claims, and external-paper claims without external citations.
  - Adds `pnpm rag:eval:semantic-contradiction`.
  - Current semantic contradiction matrix: 3 passed, 0 failed.
  - Current focused result: 156 tests passed.
  - Status: seed-level semantic guardrail `CI Ready`; full semantic correctness `Not Claimed`.
- Evaluation Set Expansion Draft
  - Expands golden questions from 5 to 12.
  - Adds AI Agent graph coverage, AI coding tools, Product Hunt discovery, OpenAI synthesis, repeated cross-source themes, evidence sufficiency, and source-signal comparison.
  - Keeps all 12 questions marked `needs_conrad_review`.
  - Adds query understanding for OpenAI, AI Agent, Product Hunt, AI coding, and evidence sufficiency.
  - Adds mixed-source filtering for GitHub plus Product Hunt.
  - Adds answer-policy mode `evidence_sufficiency_review`.
  - Current readiness summary: 9 internal-only, 2 needs-web, 1 insufficient.
  - Current focused result: 161 tests passed.
  - Status: expanded evaluation asset `CI Ready`; Q6-Q12 product labels `Needs Conrad Review`.
- Loop V2 And Q12 Structural Benchmark
  - Adds Loop V2 governance: script-first evidence collection, draft-test classification, verification budget ladder, and product-before-test rule.
  - Adds local-only 12-question structural benchmark.
  - Current local structural benchmark: 12/12 with citations, 12/12 with graph citations, 1 evidence-sufficiency review mode.
  - DeepSeek 12-question live benchmark: user-approved but blocked by execution policy in this environment.
  - Current focused/canonical result: 162 tests passed.
  - Status: loop governance `CI Ready`; local structural benchmark `Live Smoke Verified`; DeepSeek live benchmark `Blocked`.
- Product Architecture And Quality Strategy Review
  - Re-centers the project on the local AI research cockpit rather than benchmark tuning.
  - Maps each core module to role, maturity, failure mode, and next strategy.
  - Recommends moving next to a Trend Brief Workflow MVP.
  - Status: strategy review `Completed`; implementation `Not Claimed`.
- Trend Brief Workflow MVP Spec
  - Defines Markdown-first trend brief workflow.
  - Output includes executive summary, trend themes, evidence table, graph relationship summary, source review, uncertainty, follow-up actions, and machine-readable appendix.
  - Recommends first topic `RAG`.
  - Status: spec `Completed`.
- Trend Brief Workflow MVP Implementation
  - Adds deterministic Markdown brief assembly.
  - Adds `python -m rag.generate_trend_brief`.
  - Adds `pnpm rag:brief:trend`.
  - Reuses query understanding, hybrid retrieval, graph reasoning, source review, and answer policy.
  - Adds brief quality controls for noisy excerpts, graph theme labeling, internal-only risk language, and low-specificity report chunk pruning.
  - Current canonical result: 170 tests passed.
  - Local artifact smoke generated `docs/rag-transformation/briefs/trend-brief-rag-2026-06-24.md` with 5 citations, graph summary, and `internal_grounded` policy mode.
  - Status: deterministic workflow `CI Ready`; first real brief artifact `Live Smoke Verified`.
- Trend Brief Product Review And Live External Mode
  - Reviews the generated RAG brief as a product artifact.
  - Finds the main gap is missing external primary evidence, not prose quality.
  - Adds explicit `--mode live-external` while keeping default `local-only`.
  - Adds provider-routed external search request construction and external search trace in CLI summary.
  - Adds RAG-specific external result filtering, external URL citation IDs, and HTML entity cleanup.
  - Current canonical result: 174 tests passed.
  - Runtime smoke generated `docs/rag-transformation/briefs/trend-brief-rag-live-external-2026-06-24.md` with 8 citations: 4 internal, 1 graph, 3 external.
  - Source quality remained `weak_only`.
  - Status: live external mode `Live Smoke Verified`; source quality improvement `Planned`.
- Trend Brief External Source Quality Upgrade
  - Expands deterministic source-quality classification for authoritative technical/vendor documentation sources.
  - Adds `artifact_quality_status` to CLI summary and Markdown appendix.
  - Adds deterministic artifact consistency inspection for Evidence Table vs Machine-Readable Appendix.
  - Adds RAG-specific external query terms for arXiv/benchmark/evaluation/Graph RAG/Agentic RAG discovery.
  - Current focused result: 23 focused tests passed.
  - Current canonical result: 177 tests passed.
  - Live external artifact generated `docs/rag-transformation/briefs/trend-brief-rag-source-quality-2026-06-25.md` with 8 citations: 4 internal, 1 graph, 3 external.
  - Source review improved from `weak_only` to `mixed_quality`.
  - Artifact quality status: `research_quality_verified`.
  - Artifact consistency: passed; Evidence Table and appendix both report 8 citations with 3 external, 1 graph, and 4 internal.
  - Status: source quality gate `Live Smoke Verified`; semantic source relevance still needs review.

### Current Gate

Current module: P2 Trend Brief Source Relevance And Claim Review.

Next bottleneck: evidence relevance.

Decision rule:

- Use the current RAG core to produce a durable research artifact.
- Start with Markdown/file output, not UI, unless Conrad explicitly changes priority.
- Keep the MVP focused on one workflow: topic -> evidence -> graph summary -> source review -> uncertainty -> follow-up actions.
- Treat `research_quality_verified` as a source-quality gate, not proof that every selected external source is semantically ideal.
- Review whether selected external sources support the specific Trend Brief claims, not only whether the domains are authoritative.
- Include a checkpoint change inventory at P2 module close.

Completed:

- Python RAG dependencies installed in `.venv`.
- ChromaDB package/runtime verified.
- DeepSeek test API key verified.
- Vector-only `/chat` verified.
- Tavily external search verified.
- Needs-web `/chat` can merge external citations.
- External evidence answer quality benchmark verified.
- Safe URL fetch and source-deepening foundation verified.
- Deep fetch integration policy verified.
- Deep fetch runtime toggle verified.
- Live URL deep fetch against a Google Cloud official page verified.
- Brave, Exa, and GitHub live provider adapters verified.
- Provider fallback from Tavily to Brave verified.
- Minimal source role handling verified.
- Graph retrieval can now produce citation-ready metadata.
- Neo4j live runtime verified through Docker Compose.
- Provider quality matrix verified over the five golden questions.
- Claim-level seed evaluation verified for selected Q1/Q2/Q5 claims.
- Retrieval precision benchmark verified and exposed current citation redundancy/noise.
- Citation deduplication and deterministic needs-web noise filtering are implemented and covered by tests.
- After-filter retrieval precision benchmark improved from 0/3 to 3/3 on the generated live snapshot.
- Official-source fallback is live verified for Q5 with Brave returning Google Cloud official evidence.
- Multi-hop graph relationship seed is live verified for `rag`, `openai`, and `ai-agent`.
- Graph question planner can detect a seeded RAG relationship question and retrieve graph-derived service-layer evidence from Neo4j.
- Semantic contradiction seed matrix passes on the current after-filter hybrid snapshot.
- Golden-question evaluation asset now has 12 questions with all review flags preserved.
- Local-only 12-question structural benchmark passes for retrieval/citation/policy wiring.
- Product architecture review recommends moving to Trend Brief Workflow MVP instead of more benchmark tuning.
- Trend Brief Workflow MVP is specified as Markdown-first.
- Trend Brief deterministic generator is implemented and covered by P0 checks.
- First RAG Trend Brief artifact is generated and ready for product review.
- Trend Brief live external mode is implemented behind an explicit CLI flag.
- Trend Brief live external runtime path is verified with filtered external citations.
- Trend Brief external source quality gate is live-smoke verified with `mixed_quality`, `research_quality_verified`, and artifact consistency passed.

### Verified Runtime Claims

- Live vector-only `/chat` end-to-end path is verified.
- ChromaDB is populated and tested with 1346 chunks.
- Agentic tool routing has deterministic contract coverage.
- Tavily live external search is implemented and smoke-tested.
- External source-quality ranking and official-domain filtering are implemented for Tavily.
- External evidence can be merged into final `/chat` answers for needs-web questions.
- After-filter hybrid `/chat` snapshot returned citations for 5/5 questions, graph citations for 4/5 questions, and external citations for both needs-web questions.
- External evidence answer-quality benchmark is implemented.
- Safe URL fetch and basic HTML extraction are implemented.
- Deep fetch can be injected into chat and shown in the prompt.
- Live deep fetch is default-off and runtime-gated.
- Official-source URL deep fetch is live-smoke verified.
- Brave, Exa, GitHub, and Tavily can all produce normalized external citations.
- Provider fallback can recover when Tavily returns zero citations.
- Chat responses now include source review guidance and trace.
- Graph retrieval metadata is citation-ready in deterministic tests.
- Local Neo4j graph ingestion and hybrid retrieval are live-smoke verified.
- Hybrid live chat benchmark has graph citations for all five golden questions and external citations for both needs-web questions.
- Claim-level deterministic checks can catch missing support, missing external citations, forbidden overclaims, and missing uncertainty language.
- Retrieval precision evaluator can classify citations as relevant, redundant, distracting, or weak.
- Citation assembly can deduplicate repeated title/source/URL evidence.
- Chat assembly can remove obvious internal noise after external evidence is available for needs-web questions.
- Graph question planner can produce citation-ready relationship evidence for seeded entity/topic/date/source questions.
- Semantic contradiction evaluator can catch selected weak-evidence overclaim and missing-external-citation patterns.
- Query planning supports Product Hunt, OpenAI, AI Agent, AI coding tools, evidence sufficiency, and mixed GitHub/Product Hunt filters.
- Loop V2 is now documented as the operating rule for balancing efficiency and quality.
- Trend Brief deterministic assembly is covered by P0 tests and py_compile.
- Trend Brief artifact generation for `RAG` is live-smoke verified locally.
- Trend Brief live external mode request planning is covered by P0 tests.
- Trend Brief live external mode is live-smoke verified.

### Still Not Claimed

- SerpAPI live adapter is not implemented yet.
- Live URL fetch is not enabled by default in the server by design.
- Full claim-level source conflict resolution is not implemented yet.
- Semantic reranking is not implemented yet.
- Semantic answer correctness is not proven by the current structural quality matrix.
- Full semantic contradiction detection is not implemented yet; only a seed-level guardrail exists.
- DeepSeek expanded 12-question live benchmark is not run because this execution environment blocks the external data transfer.
- Trend Brief semantic quality as a research artifact has not been manually reviewed yet.
- Trend Brief semantic source relevance as a research artifact has not been manually or rubric-reviewed yet.
- LangGraph-style stateful agent workflow is not implemented yet.
- Dedicated chat UI graph-reasoning mode is not implemented yet.
- Stage 2.5 single-repo local demo workspace is accepted as direction but not implemented yet.
- Production deployment, monitoring, cost controls, and UI integration are not implemented yet.
- Original AI Trend Radar UI integration remains out of scope until this RAG project core is mature.
