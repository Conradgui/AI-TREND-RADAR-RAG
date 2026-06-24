# Plan: P2 Trend Brief External Source Quality Upgrade

Date: 2026-06-25

## Goal

Improve the Trend Brief live-external workflow from "external citations exist" toward "external evidence quality is explicit and auditable."

## Scope

In scope:

- improve deterministic source-quality classification for authoritative technical/vendor documentation sources;
- expose artifact quality status in the Trend Brief machine-readable appendix and CLI summary;
- add a deterministic artifact consistency inspector for evidence table and appendix counts;
- update tests, evidence, execution log, roadmap, and architecture status;
- checkpoint changes to `codex/rag-transformation-checkpoints`.

Out of scope:

- original AI Trend Radar UI;
- new search providers;
- LangChain or LangGraph;
- LLM prose generation;
- broad semantic ranking.

## Architecture Boundary Gate

Layer:

- Evidence
- Evaluation
- Research Artifact

Inputs:

- normalized external citations;
- source-quality classification;
- Trend Brief Markdown artifact;
- CLI generation summary.

Outputs:

- improved source-quality labels;
- artifact-quality status;
- artifact consistency report.

Data boundary:

- no new corpus boundary.

Evidence boundary:

- strengthens the distinction between weak external citations and research-quality evidence.

Reuse/new module decision:

- reuse `external_source_quality`, `source_review`, and `trend_brief` instead of adding a separate QA framework.

Future integration impact:

- improves Stage 2.5/local app readiness by making artifact quality machine-checkable.

Official component check:

- no new dependency required.

## Definition Of Done

Product behavior:

- Trend Brief can explain whether external evidence is runtime-only, supporting, or research-quality.

Engineering behavior:

- Source classification recognizes authoritative technical/vendor documentation as higher quality than generic pages.
- CLI summary and appendix include evidence type counts and artifact quality status.
- Artifact consistency can be checked deterministically.

Evidence behavior:

- Evidence records whether the module improved the prior `weak_only` bottleneck structurally.

Evaluation behavior:

- focused tests cover source classification, source review, Trend Brief summary, consistency inspection, and generation summary.
- canonical P0 check passes before checkpoint.

Non-goals:

- Do not claim full semantic correctness.
- Do not claim live research-quality verification unless live artifact evidence supports it.

Residual risks:

- Domain-based source quality can still misclassify edge cases.
- Live provider results can vary by date, query, quota, and ranking.
