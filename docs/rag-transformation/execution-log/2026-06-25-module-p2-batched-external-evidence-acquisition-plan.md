# Execution Log: P2 Batched External Evidence Acquisition

Date: 2026-06-25

## Module

P2 Batched External Evidence Acquisition

## Definition Of Done

Product behavior:

- The next external evidence acquisition is visible as a planned batch before any API call.
- The accepted batch can be executed once and reviewed as a separate artifact.

Engineering behavior:

- A deterministic planner maps source relevance gaps to source types, queries, routes, and budget.
- A batch executor uses the existing search provider registry and respects the budget.

Evidence behavior:

- A JSON batch plan artifact records claim gaps, provider routes, and execution status.
- A JSON live batch result artifact records provider attempts and citations.

Evaluation behavior:

- Focused planner/executor tests and canonical P0 checks pass.

Non-goals:

- Do not add providers or credentials.
- Do not modify original AI Trend Radar UI.

Residual risks:

- Queries may need refinement before final brief integration.
- Generic citations must be treated as background, not as primary support.

## Architecture Boundary Gate

Layer:

- Evidence
- Evaluation
- Research Artifact

Inputs:

- source relevance matrix;
- provider routing policy.

Outputs:

- batched evidence acquisition plan.

Data boundary:

- live external data fetched only through the batch executor.

Evidence boundary:

- adds a planning boundary before external evidence acquisition and records live results separately.

Reuse/new module decision:

- add `rag/evidence_batch_plan.py`;
- add `rag/eval_batched_evidence_acquisition.py`;
- reuse `build_search_provider_route`.
- reuse `SearchProviderRegistry`.

Future integration impact:

- Stage 2.5/local app can present planned external searches before executing them.

Official component check:

- no dependency added.

## Actions

- Added batch evidence planner.
- Added batch executor.
- Added CLI for plan-only or live-batch mode.
- Added focused tests.
- Added batch plan artifact and live result artifact.
- Added P0 coverage.
- Executed one live batch through configured providers.

## Verification

- Focused tests: 5 passed.
- Live batch: 4 external API calls, 9 citations, 2 / 2 gaps with citations.
- Source quality: 4 academic, 1 official, 1 developer, 3 generic.
- Provider issue recorded: one Exa request returned `exa_network_error`; Tavily fallback returned citations.
- Canonical P0: 188 tests passed; py_compile passed.
- External API calls: 4.

## Change Inventory

Code changed:

- `rag/evidence_batch_plan.py`
- `rag/eval_batched_evidence_acquisition.py`
- `package.json`

Tests changed:

- `rag/tests/test_evidence_batch_plan.py`

Docs/specs/plans changed:

- `docs/rag-transformation/plans/p2-batched-external-evidence-acquisition-plan.md`

Artifacts/evals/evidence generated:

- `docs/rag-transformation/evals/batched-evidence-acquisition-plan-2026-06-25.json`
- `docs/rag-transformation/evals/batched-evidence-acquisition-result-2026-06-25.json`
- `docs/rag-transformation/evidence/2026-06-25-batched-external-evidence-acquisition-plan.md`
- `docs/rag-transformation/execution-log/2026-06-25-module-p2-batched-external-evidence-acquisition-plan.md`

Historical dirty files:

- none.

Local-only ignored files:

- `.env`
- `.venv/`
- Python cache directories
- `rag/data/chroma/`

## Next-Step Bias

Next bottleneck: evidence integration.

The next module should integrate the returned academic/official/developer citations into the trend brief path and keep generic citations as background unless they directly support a claim.

## Checkpoint

- Branch: `codex/rag-transformation-checkpoints`
- Commit: `6eb9e80`
- Message: `checkpoint(rag): batched external evidence acquisition - live batch verified`
- Push status: pending.
