# Evidence: P1 Semantic Contradiction Detection Seed

Date: 2026-06-24

## Scope

Added deterministic seed checks for semantic contradiction risk.

The checks focus on:

- weak or mixed sources requiring uncertainty language;
- forbidden overclaim terms;
- external paper/reference claims requiring external citations or explicit uncertainty.

## Files Added Or Updated

- `rag/eval_semantic_contradiction.py`
- `rag/tests/test_eval_semantic_contradiction.py`
- `docs/rag-transformation/evals/semantic-contradiction-seed-2026-06-24.json`
- `docs/rag-transformation/evals/semantic-contradiction-matrix-2026-06-24.json`
- `docs/rag-transformation/plans/p1-semantic-contradiction-seed.md`
- `rag/eval_claim_level.py`
- `package.json`

## Focused Verification

Command:

```bash
python3 -m unittest rag.tests.test_eval_claim_level rag.tests.test_eval_semantic_contradiction -v
```

Result:

```text
Ran 9 tests in 0.000s
OK
```

## Matrix Verification

Command:

```bash
python3 -m rag.eval_semantic_contradiction --input docs/rag-transformation/evals/hybrid-live-chat-snapshot-2026-06-23-after-filter.json --seed docs/rag-transformation/evals/semantic-contradiction-seed-2026-06-24.json --output docs/rag-transformation/evals/semantic-contradiction-matrix-2026-06-24.json
```

Result:

```json
{
  "total": 3,
  "passed": 3,
  "failed": 0,
  "failure_counts": {}
}
```

## Canonical Verification

Command:

```bash
pnpm rag:check:p0
```

Result:

```text
Ran 156 tests in 0.122s
OK
```

## False-Positive Handling

The first semantic contradiction matrix produced one false positive because the detector did not recognize:

- `无法就此给出明确结论`

as uncertainty language.

The shared uncertainty marker list now includes this and similar conservative expressions.

## Interpretation

The project now has a seed-level guardrail for selected semantic contradiction risks.

This is not full semantic correctness. It is a deterministic safety net for known high-risk patterns.

## Residual Risks

- The detector is marker- and seed-based.
- It cannot catch all hallucinations or subtle logical contradictions.
- Future expansion should add more annotated failure modes and, only if justified, consider an LLM-as-judge or entailment-model layer.
