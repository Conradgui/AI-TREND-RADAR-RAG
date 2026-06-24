# Plan: P2 Trend Brief Source Relevance And Claim Review

Date: 2026-06-25

## Goal

Add a deterministic review layer that checks whether Trend Brief external sources actually support the brief topic and claims, not only whether the source domains are high quality.

## Scope

In scope:

- classify external citations as `direct_support`, `partial_support`, `weak_context`, or `irrelevant_context`;
- inspect an existing Trend Brief Markdown artifact without making new external API calls;
- expose source relevance in the Trend Brief appendix and CLI summary;
- update tests, evidence, execution log, roadmap, and architecture status;
- checkpoint to `codex/rag-transformation-checkpoints`.

Out of scope:

- no new external search requests in this module;
- no new search provider;
- no LLM-based semantic judge;
- no original AI Trend Radar UI work.

## External API Budget Strategy

This module uses the existing live artifact:

```text
docs/rag-transformation/briefs/trend-brief-rag-source-quality-2026-06-25.md
```

No external search API should be called unless the local relevance review proves the current artifact is insufficient and a follow-up module is created.

If a follow-up requires external APIs, batch first:

1. list all needed claims;
2. list needed source types;
3. choose providers and budget;
4. run one planned batch;
5. save all raw/normalized evidence.

## Architecture Boundary Gate

Layer:

- Evidence
- Evaluation
- Research Artifact

Inputs:

- external citation title, URL, excerpt, and source quality;
- Trend Brief Markdown evidence table;
- Source Quality Review section.

Outputs:

- source relevance labels;
- source relevance counts;
- artifact-level source relevance status.

Data boundary:

- no new corpus or external data boundary.

Evidence boundary:

- adds claim-support relevance on top of source-domain quality.

Reuse/new module decision:

- add a small deterministic source relevance module instead of a broad evaluation framework.

Future integration impact:

- local UI can later surface both source quality and claim relevance.

Official component check:

- no dependency required.

## Definition Of Done

Product behavior:

- A Trend Brief can say whether external sources directly support, partially support, weakly contextualize, or fail to support the topic.

Engineering behavior:

- Source relevance can be computed from citations and from saved Markdown artifacts.
- CLI summary and appendix can carry source relevance status.

Evidence behavior:

- Evidence records the relevance matrix for the existing live artifact.

Evaluation behavior:

- focused tests cover citation relevance, artifact inspection, appendix output, and CLI summary.
- canonical P0 check passes before checkpoint.

Non-goals:

- Do not claim full semantic correctness.
- Do not call external search APIs.

Residual risks:

- Deterministic keyword relevance is weaker than human or LLM semantic review.
- Claim-level support is still coarse and topic-specific.
