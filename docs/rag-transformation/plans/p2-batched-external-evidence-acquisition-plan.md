# Plan: P2 Batched External Evidence Acquisition Plan

Date: 2026-06-25

## Goal

Plan and execute the next external evidence acquisition as one explicit batch when live evidence improves quality or efficiency.

## Scope

In scope:

- convert the source relevance matrix into claim gaps;
- assign needed source types;
- choose provider routes from existing routing policy;
- set a call budget;
- save a batch plan artifact;
- execute the planned batch once through configured providers;
- save a live batch result artifact.

Out of scope:

- no provider adapter changes;
- no new API keys;
- no LLM semantic judging;
- no original AI Trend Radar UI work.

## Architecture Boundary Gate

Layer:

- Evidence
- Evaluation
- Research Artifact

Inputs:

- `docs/rag-transformation/evals/trend-brief-source-relevance-2026-06-25.json`
- provider routing policy in `rag/search_provider_routing.py`

Outputs:

- `docs/rag-transformation/evals/batched-evidence-acquisition-plan-2026-06-25.json`
- `docs/rag-transformation/evals/batched-evidence-acquisition-result-2026-06-25.json`

Data boundary:

- external citations are fetched only by the explicit batch executor.

Evidence boundary:

- keeps a request-before-execution plan boundary and stores live batch results separately.

Reuse/new module decision:

- add a small local planner in `rag/evidence_batch_plan.py`.
- reuse existing provider routing.

Future integration impact:

- the local app can later display planned evidence batches before running them.

Official component check:

- no dependency needed.

## Definition Of Done

Product behavior:

- Before live external search, the system can show what it intends to fetch, why, from which provider, and under what budget.
- After execution, the system can show which providers were called, which calls failed, and which citations were returned.

Engineering behavior:

- A deterministic function builds a no-network batch plan from a source relevance matrix.
- A batch executor uses the existing provider registry and respects the module call budget.
- P0 checks include the planner.

Evidence behavior:

- The saved batch plan records claim gaps, source types, routes, and budget.
- The saved live result records external API calls, provider attempts, returned citations, and source quality.

Evaluation behavior:

- focused planner tests pass.
- canonical P0 check passes.

Residual risks:

- The generated queries are deterministic heuristics and should be refined in the next integration module if they return too much generic context.
- One provider failure should be treated as provider/data quality evidence unless repeated across modules.
