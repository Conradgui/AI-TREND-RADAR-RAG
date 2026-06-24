# Trend Brief Workflow MVP Spec

Date: 2026-06-24

## 1. Purpose

This spec defines the first product workflow for AI Trend Radar RAG.

The goal is to move from a chat-first RAG demo to a local AI research cockpit that produces a durable, reviewable research artifact.

## 2. Product Job

User job:

> "I want to understand what is happening around one AI topic, why it matters, what evidence supports it, and what I should investigate next."

The first MVP should answer this job with a Markdown trend brief.

## 3. MVP Input

Required:

- `topic`: a short research topic.

Optional:

- `time_window`: default to recent corpus first.
- `include_external_plan`: default true, but do not call external providers unless the workflow is explicitly run in live mode.
- `max_internal_citations`: default 8.
- `max_graph_paths`: default 8.

Recommended first topic:

- `RAG`

Reason:

- strongest current internal evidence;
- graph relationship coverage already verified;
- existing Q1/Q2 claim and retrieval precision checks cover the topic.

## 4. MVP Output

The first output should be a Markdown file under:

```text
docs/rag-transformation/briefs/
```

Suggested filename:

```text
trend-brief-[topic-slug]-[date].md
```

## 5. Output Schema

Each brief must include:

1. Header
   - topic;
   - generated date;
   - corpus latest date;
   - mode: `local-only`, `internal-plus-external-plan`, or `live-external`.

2. Executive Summary
   - 3 to 5 concise bullets.
   - Must distinguish what is supported from what is uncertain.

3. Key Trend Themes
   - grouped themes;
   - each theme must include evidence IDs;
   - avoid one-off items being labeled as trends.

4. Evidence Table
   - date;
   - source;
   - title;
   - evidence type: internal, graph, external;
   - citation ID;
   - excerpt.

5. Graph Relationship Summary
   - entity/topic/date/source coverage;
   - sample graph paths;
   - what graph evidence can and cannot prove.

6. Source Quality Review
   - source roles;
   - primary/supporting/weak signals;
   - source conflicts if present.

7. Uncertainty And Missing Evidence
   - unsupported claims;
   - missing source types;
   - whether external research is needed.

8. Recommended Follow-Up Actions
   - next search queries;
   - URLs or source types to fetch;
   - questions to ask next.

9. Machine-Readable Appendix
   - compact JSON block with topic, citations, graph counts, policy mode, and residual risks.

## 6. Workflow Steps

### Step 1: Plan

Use existing deterministic query understanding.

Do not introduce LangChain or LangGraph for the first MVP.

### Step 2: Retrieve Internal Evidence

Use existing hybrid retriever:

- vector evidence;
- graph citations;
- metadata filters when topic/source/time constraints exist.

### Step 3: Build Graph Summary

Use existing graph relationship service where possible.

For the first MVP, graph output can be structural:

- topic count;
- date count;
- source count;
- sample paths.

### Step 4: Review Sources

Use existing source review logic.

The brief should not present weak or social/generic sources as strong proof.

### Step 5: Draft Brief

First implementation options:

1. Deterministic Markdown assembly.
2. LLM-assisted summary only after evidence is selected and marked.

Recommended first path:

- deterministic Markdown assembly for structure;
- optional LLM summary later, behind a live mode flag.

### Step 6: Save Artifact

Save the Markdown brief to `docs/rag-transformation/briefs/`.

This makes the workflow inspectable and easy to diff.

## 7. Failure Modes

### False Trend

Problem:

- one-off item is labeled as a trend.

Mitigation:

- require repeated dates/sources for strong trend language;
- otherwise label as emerging signal or one-off observation.

### Source Overclaim

Problem:

- Product Hunt heat, GitHub stars, or generic media are treated as proof of adoption or commercial success.

Mitigation:

- source quality review;
- uncertainty section;
- evidence-sufficiency policy.

### Graph Overclaim

Problem:

- graph relationship counts are treated as causal evidence.

Mitigation:

- graph section must state that graph evidence proves coverage/association, not causality or market adoption.

### External Evidence Confusion

Problem:

- internal corpus and external web evidence are blended without labels.

Mitigation:

- evidence table must label evidence type.

### Benchmark Overfitting

Problem:

- workflow is built to satisfy Q6-Q12 instead of user research needs.

Mitigation:

- Q6-Q12 remain review drafts;
- brief workflow is judged by whether the artifact helps Conrad inspect a topic.

## 8. Verification

MVP verification should use three layers:

1. Unit tests
   - brief schema fields;
   - citation table includes required fields;
   - graph summary handles missing paths;
   - uncertainty section appears when evidence is weak.

2. Local structural smoke
   - generate one brief for `RAG`;
   - no external LLM or search required;
   - citations and graph summary present.

3. Optional live mode
   - LLM-assisted executive summary;
   - explicit external data-transfer approval required;
   - not part of deterministic CI.

## 9. Non-Goals

- No UI dashboard yet.
- No original AI Trend Radar UI integration.
- No Stage 2.5 repo unification.
- No LangGraph workflow engine.
- No production scheduler.
- No claim of complete semantic correctness.

## 10. Completion Criteria

The MVP implementation is complete when:

- `RAG` trend brief can be generated locally as Markdown;
- the brief includes all schema sections;
- internal citations are visible and citation-ready;
- graph relationship summary is present;
- uncertainty and missing evidence are explicitly stated;
- focused tests pass;
- evidence and execution log are recorded.
