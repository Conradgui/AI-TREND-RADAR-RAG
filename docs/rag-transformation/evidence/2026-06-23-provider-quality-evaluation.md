# Evidence: P1 Provider Quality Evaluation

Date: 2026-06-23

## What Changed

- Added deterministic provider quality matrix scoring in `rag/eval_provider_quality.py`.
- Added `pnpm rag:eval:provider-quality`.
- Added hybrid live chat benchmark in `rag/eval_hybrid_live_chat.py`.
- Added `pnpm rag:eval:hybrid-live-chat`.
- Added tests for provider quality scoring.

## Validation

Focused tests:

```text
python3 -m unittest rag.tests.test_eval_provider_quality -v
Ran 4 tests
OK
```

Hybrid live chat benchmark:

```text
.venv/bin/python -m rag.eval_hybrid_live_chat
total: 5
with_citations: 5
with_graph_citations: 5
with_external_citations: 2
needs_web_questions: 2
```

Provider quality matrix:

```text
python3 -m rag.eval_provider_quality --input docs/rag-transformation/evals/hybrid-live-chat-snapshot-2026-06-23.json --output docs/rag-transformation/evals/provider-quality-matrix-2026-06-23.json
total: 5
passed: 5
failed: 0
with_graph_citations: 5
with_external_citations: 2
failure_counts: {}
```

Canonical check:

```text
pnpm rag:check:p0
Ran 131 tests
OK
```

## Outputs

- `docs/rag-transformation/evals/hybrid-live-chat-snapshot-2026-06-23.json`
- `docs/rag-transformation/evals/provider-quality-matrix-2026-06-23.json`

## Product Interpretation

This is the first unified quality matrix across the golden question set after vector, graph, external search, provider routing, and source review are available.

Current result:

- all 5 golden questions returned citations;
- all 5 had graph citations;
- both needs-web questions had external citations;
- structural quality checks passed for all 5 rows.

This does not prove the answers are semantically perfect. It proves the answer pipeline is structurally behaving according to the current product contract.

## Residual Risks

- The golden set has only 5 questions.
- The rubric is structural and deterministic, not a semantic truth judge.
- Human review is still required to decide whether answer content is good enough for demos/interviews/product use.
- Future benchmark should add latency, cost, retrieval precision, and claim-level factual checks.
