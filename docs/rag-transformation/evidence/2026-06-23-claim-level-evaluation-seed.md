# Evidence: P1 Claim-Level Evaluation Seed

Date: 2026-06-23

## Scope

Added a deterministic claim-level evaluation seed and evaluator for selected golden questions.

This module checks whether answers:

- support required high-level claims with the expected evidence type;
- avoid unsupported overclaims;
- mark uncertainty when evidence is insufficient.

## Files Added Or Updated

- `rag/eval_claim_level.py`
- `rag/tests/test_eval_claim_level.py`
- `docs/rag-transformation/evals/claim-level-seed-2026-06-23.json`
- `docs/rag-transformation/evals/claim-level-matrix-2026-06-23.json`
- `docs/rag-transformation/plans/p1-claim-level-evaluation-seed.md`
- `package.json`

## Focused Verification

Command:

```bash
python3 -m unittest rag.tests.test_eval_claim_level -v
```

Result:

```text
Ran 5 tests in 0.000s
OK
```

Covered behaviors:

- `should_support` passes with required terms and citations.
- `should_support` fails when required external citations are missing.
- `should_avoid` fails on forbidden overclaim phrases.
- `should_mark_uncertain` passes with uncertainty language.
- summary counts failures.

## Snapshot Evaluation

Command:

```bash
python3 -m rag.eval_claim_level --input docs/rag-transformation/evals/hybrid-live-chat-snapshot-2026-06-23.json --seed docs/rag-transformation/evals/claim-level-seed-2026-06-23.json --output docs/rag-transformation/evals/claim-level-matrix-2026-06-23.json
```

Result:

```json
{
  "total": 8,
  "passed": 8,
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
Ran 136 tests in 0.067s
OK
```

## Quality Notes

One initial seed rule produced a false positive because it treated mention of "user preference efficiency" as an overclaim even when the answer was denying that evidence existed. The rule was narrowed to forbid only assertive overclaim phrases such as "already proven" and "significant improvement".

This was a useful example of why evaluation seeds must be reviewed as product artifacts, not treated as objective truth.

## Residual Risks

- Deterministic text checks can miss paraphrased overclaims.
- The seed only covers Q1, Q2, and Q5.
- Passing the claim matrix does not prove full semantic correctness.
- Conrad should later review whether these claims represent the intended product-quality bar.
