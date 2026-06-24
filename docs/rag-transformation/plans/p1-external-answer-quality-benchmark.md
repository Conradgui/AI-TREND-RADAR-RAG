# P1 External Evidence Answer Quality Benchmark Plan

Date: 2026-06-22

## Goal

Add a deterministic benchmark for needs-web answers that include external evidence.

## Product Meaning

The system should not be considered better merely because it can call Tavily.

This module checks whether the final answer:

- separates internal corpus evidence from external evidence;
- preserves citations and source quality metadata;
- treats generic or weak external sources with caution;
- records whether external search actually changed answer policy.

## Scope

1. Add an external-answer-quality rubric module.
2. Support the current single external chat smoke artifact.
3. Score source mix, citation fields, answer labels, and uncertainty handling.
4. Add a CLI command and focused tests.
5. Save a benchmark snapshot and evidence record.

## Out of Scope

- LLM-as-judge grading.
- Full factuality verification.
- URL fetch/extract.
- Multi-provider live comparison.

## Definition Of Done

Product behavior:
- Conrad can run one command to see whether an external-evidence answer follows basic evidence-quality rules.

Engineering behavior:
- A deterministic scorer exists and can read `external-chat-smoke-2026-06-22.json`.
- Tests cover passing hybrid evidence, missing citation mix, and weak-source uncertainty handling.

Evidence behavior:
- Benchmark output is saved under `docs/rag-transformation/evals/`.
- Evidence and execution log record results and limitations.

Evaluation behavior:
- Focused tests pass.
- `pnpm rag:check:p0` passes.
