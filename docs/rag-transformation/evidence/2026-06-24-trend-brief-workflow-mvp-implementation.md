# Evidence: Trend Brief Workflow MVP Implementation

Date: 2026-06-24

## Scope

Implemented the first deterministic Trend Brief workflow.

This module turns selected local RAG evidence into a Markdown research artifact with:

- executive summary;
- key trend themes;
- evidence table;
- graph relationship summary;
- source quality review;
- uncertainty and missing evidence;
- recommended follow-up actions;
- machine-readable JSON appendix.

## Product Boundary

The MVP is intentionally deterministic and local-first.

It does not call DeepSeek, external search providers, or the original AI Trend Radar UI.

Reason:

- the immediate product goal is an inspectable research artifact;
- the main risk is evidence overclaim, not lack of language fluency;
- LLM-assisted writing can be added later behind an explicit live mode.

## Code Changes

- Added `rag/trend_brief.py`.
  - Builds Markdown trend briefs.
  - Builds machine-readable summaries.
  - Saves brief artifacts to `docs/rag-transformation/briefs/`.
- Added `rag/generate_trend_brief.py`.
  - Provides `python -m rag.generate_trend_brief`.
  - Connects local Hybrid Retriever, Neo4j graph evidence, source review, and answer policy.
- Added tests:
  - `rag/tests/test_trend_brief.py`
  - `rag/tests/test_generate_trend_brief.py`
- Updated `package.json`.
  - Adds `rag:brief:trend`.
  - Adds new tests to `rag:test:p0`.
  - Adds new modules to `rag:check:p0` py_compile.

Quality pass:

- Cleans HTML line-break noise from evidence table cells.
- Groups graph citations under `Graph coverage`.
- Adds an explicit internal-only risk: missing external primary sources.
- Prunes generic report chunks when more specific topic or graph citations exist.
- Aligns CLI citation count with the final filtered Markdown artifact.

## Verification

Focused checks:

```text
python3 -m unittest rag.tests.test_trend_brief -v
```

Result:

```text
Ran 4 tests in 0.001s
OK
```

Focused checks after CLI helper:

```text
python3 -m unittest rag.tests.test_trend_brief rag.tests.test_generate_trend_brief -v
```

Result:

```text
Ran 5 tests in 0.001s
OK
```

Low-cost syntax checks:

```text
jq '.scripts["rag:brief:trend"]' package.json
PYTHONPYCACHEPREFIX=/tmp/ai_trend_rag_pycache python3 -m py_compile rag/trend_brief.py rag/generate_trend_brief.py
```

Result:

```text
"python -m rag.generate_trend_brief"
```

Canonical module gate before quality pass:

```text
pnpm rag:check:p0
```

Result:

```text
Ran 167 tests in 0.422s
OK
```

Canonical module gate after quality pass:

```text
pnpm rag:check:p0
```

Result:

```text
Ran 170 tests in 0.091s
OK
```

## Live Local Artifact Smoke

Command:

```text
.venv/bin/python -m rag.generate_trend_brief --topic RAG --output docs/rag-transformation/briefs/trend-brief-rag-2026-06-24.md
```

Result:

```text
{
  "output": "docs/rag-transformation/briefs/trend-brief-rag-2026-06-24.md",
  "topic": "RAG",
  "citation_count": 5,
  "has_graph_summary": true,
  "policy_mode": "internal_grounded"
}
```

Generated artifact:

- `docs/rag-transformation/briefs/trend-brief-rag-2026-06-24.md`

Artifact appendix summary:

```text
topic: RAG
citation_count: 5
evidence_types: graph 1, internal 4
graph_counts: 18 topics, 14 dates, 4 sources
residual_risks: 2
```

Interpretation:

- Runtime artifact generation is now `Live Smoke Verified`.
- The generated brief is a usable first artifact for product review.
- It is still not proof of semantic correctness or complete external coverage.

## Residual Risks

- Semantic correctness is still not proven by structural tests.
- The deterministic brief may be too terse for final user-facing research output; LLM-assisted summary should be evaluated later only after evidence selection is stable.
