# P1 Provider Quality Evaluation Plan

Date: 2026-06-23

## Module

P1 Provider Quality Evaluation

## Concept

Provider quality evaluation means measuring whether the system's answer pipeline behaves better after vector, graph, external search, deep fetch, and source review are all available.

This module does not ask another LLM to grade answers. It starts with deterministic checks that are cheap, repeatable, and easy to debug.

## Definition of Done

Product behavior:

- Golden questions produce a quality matrix with pass/fail checks.
- Internal-only questions are expected to have citations and internal grounding.
- Needs-web questions are expected to either use external evidence or explicitly preserve the external-evidence boundary.
- Graph-assisted answers can be measured by graph citation count.
- External answers can be measured by external citation count, source quality, and source review.

Engineering behavior:

- Add provider quality scoring helper.
- Add a CLI script that scores a snapshot.
- Add tests for internal-only, graph-assisted, needs-web, and weak-source cases.
- Wire the script into `package.json` and canonical compile check.

Evidence behavior:

- Save a provider quality matrix under `docs/rag-transformation/evals/`.
- Record remaining gaps instead of claiming production answer quality.

Non-goals:

- Do not add an LLM judge.
- Do not introduce a new framework.
- Do not claim semantic correctness from structural checks alone.

Residual risks:

- Deterministic checks cannot prove answer truthfulness.
- The golden set is still small and should expand.
- Human review is still needed for final answer-quality judgment.
