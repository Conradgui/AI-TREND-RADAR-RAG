# Plan: P2 Trend Brief Batch Evidence Integration

Date: 2026-06-25

## Goal

Integrate batched external evidence into the Trend Brief workflow without making the Agent or retrieval runtime depend on a narrow search sample.

## Scope

In scope:

- add dual search strategy modes;
- set production provider result count to 8;
- set exploration provider result count to 15;
- allow exploration mode to pool all task-suitable configured providers;
- select high-quality batch citations before adding them to a Trend Brief;
- write batch evidence trace into the Trend Brief appendix.

Out of scope:

- original AI Trend Radar UI;
- LLM reranking;
- new search providers;
- replacing the existing provider adapters;
- changing graph/vector retrieval internals.

## Architecture Boundary Gate

Layer:

- Evidence
- Research Artifact
- Evaluation

Inputs:

- source relevance matrix;
- configured search provider registry;
- batched evidence result artifacts;
- existing Trend Brief generator.

Outputs:

- `docs/rag-transformation/evals/batched-evidence-acquisition-production-2026-06-25.json`
- `docs/rag-transformation/evals/batched-evidence-acquisition-exploration-2026-06-25.json`
- `docs/rag-transformation/briefs/trend-brief-rag-production-batch-evidence-2026-06-25.md`
- `docs/rag-transformation/briefs/trend-brief-rag-exploration-batch-evidence-2026-06-25.md`

Data boundary:

- external data is fetched only through the existing provider registry.
- raw candidate pools stay in JSON eval artifacts.
- Trend Brief receives selected citations, not the whole candidate pool.

Evidence boundary:

- generic/social sources remain background candidates by default.
- academic/official/developer sources are eligible for Trend Brief selection.

Reuse/new module decision:

- add `rag/batch_evidence.py` as a thin selector.
- reuse `SearchProviderRegistry`, `select_brief_citations`, source quality, and source relevance logic.

Future integration impact:

- local app can expose two buttons later: production search and exploration search.
- Agent runtime can keep production mode while benchmark/research workflows use exploration mode.

Official component check:

- no new dependency needed.

## Definition Of Done

Product behavior:

- production mode is no longer starved by 3-result provider calls.
- exploration mode can build a larger evidence pool for evaluation and research.
- Trend Brief shows which batch artifact it consumed and how many candidates were filtered out.

Engineering behavior:

- batch planning accepts `strategy_mode`.
- batch execution respects per-call result budgets.
- Trend Brief generation accepts an optional batch evidence artifact.
- default behavior remains backward compatible when no batch artifact is passed.

Evidence behavior:

- production live batch returns at least one citation per claim gap.
- exploration live batch creates a larger candidate pool.
- generated briefs remain artifact-consistent.

Evaluation behavior:

- focused tests cover dual-mode planning, batch selection, and Trend Brief summary/appendix.
- canonical P0 check passes before checkpoint.

Residual risks:

- deterministic source relevance is still coarse and may label official/developer definition pages as weak context.
- exploration mode increases candidate noise, so raw pools must not be injected directly into user-facing answers.
