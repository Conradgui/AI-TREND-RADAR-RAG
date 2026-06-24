# Evidence: Loop V2 And Q12 Structural Benchmark

Date: 2026-06-24

## Scope

Updated the execution loop to V2 and verified the expanded 12-question benchmark through a local-only structural path.

## User Decisions Recorded

- Q6-Q12 remain accepted as draft golden questions.
- DeepSeek live benchmark is acceptable to Conrad, including the data-transfer risk.
- Development should return to product architecture and quality strategy instead of overfitting the draft test set.
- Local-only structural benchmark should be retained.
- Development dependencies may be installed automatically when needed, with preference for project-local and trusted sources.

## Loop V2 Changes

Added:

- Product-before-test rule.
- Draft-test classification rule.
- Token/runtime budget rule.
- Verification budget ladder:
  - schema;
  - focused;
  - canonical;
  - local structural;
  - live external.

## Local Structural Benchmark

Command:

```bash
.venv/bin/python -m rag.eval_hybrid_structural_chat --output docs/rag-transformation/evals/hybrid-structural-chat-snapshot-2026-06-24-q12.json
```

Result:

```json
{
  "total": 12,
  "with_citations": 12,
  "with_graph_citations": 12,
  "with_external_citations": 0,
  "needs_web_questions": 2,
  "evidence_sufficiency_review": 1,
  "answer_policy_modes": {
    "evidence_sufficiency_review": 1,
    "internal_grounded": 9,
    "needs_external_evidence": 2
  }
}
```

## DeepSeek Live Benchmark

Status: blocked by execution policy.

The benchmark was attempted after Conrad explicitly accepted the risk, but the environment rejected the command because it would transfer retrieved local evidence snippets and questions to DeepSeek/search providers.

This benchmark is not claimed as completed.

## Canonical Verification

Command:

```bash
pnpm rag:check:p0
```

Result:

```text
Ran 162 tests in 0.109s
OK
```

## Secret Scan

Command:

```bash
rg -n '[redacted known secret fragments]' --glob '!node_modules/**' --glob '!.git/**' .
```

Result: no output.

## Interpretation

The local RAG structure is stable across the expanded 12-question set.

This proves retrieval/citation/policy wiring, not final answer quality.

The next useful work should focus on product architecture and quality strategy before further benchmark tuning.
