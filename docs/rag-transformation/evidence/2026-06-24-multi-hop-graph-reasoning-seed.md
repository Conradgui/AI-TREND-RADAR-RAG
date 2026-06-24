# Evidence: P1 Multi-Hop Graph Reasoning Seed

Date: 2026-06-24

## Scope

Added a deterministic graph reasoning seed and evaluator.

This module checks whether the Neo4j graph can support seeded multi-hop relationship questions:

- Entity -> Topic
- Topic -> DailyDigest date
- Topic -> Source
- repeated entity/topic appearances across dates

## Files Added Or Updated

- `rag/eval_graph_reasoning.py`
- `rag/tests/test_eval_graph_reasoning.py`
- `docs/rag-transformation/evals/graph-reasoning-seed-2026-06-24.json`
- `docs/rag-transformation/evals/graph-reasoning-matrix-2026-06-24.json`
- `docs/rag-transformation/plans/p1-multi-hop-graph-reasoning-seed.md`
- `package.json`

## Focused Verification

Command:

```bash
python3 -m unittest rag.tests.test_eval_graph_reasoning -v
```

Result:

```text
Ran 3 tests in 0.004s
OK
```

## Live Graph Matrix

Command:

```bash
.venv/bin/python -m rag.eval_graph_reasoning --seed docs/rag-transformation/evals/graph-reasoning-seed-2026-06-24.json --output docs/rag-transformation/evals/graph-reasoning-matrix-2026-06-24.json
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

Seed results:

- `rag`: 18 topics, 14 dates, 4 sources.
- `openai`: 29 topics, 8 dates, 3 sources.
- `ai-agent`: 16 topics, 14 dates, 2 sources.

## Canonical Verification

Command:

```bash
pnpm rag:check:p0
```

Result:

```text
Ran 146 tests in 0.068s
OK
```

## Interpretation

The graph has enough relationship coverage to support multi-hop graph reasoning seeds.

This does not yet prove the chat Agent can plan and execute graph-specific reasoning steps. It proves the data layer and relationship paths are present.

## Residual Risks

- Current chat flow still primarily uses hybrid retrieval, not explicit graph question planning.
- The graph reasoning seed is small and should expand to company, source, and date comparison tasks.
- Some entities are broad tags; entity normalization still needs later refinement.
