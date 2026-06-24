# Evidence: P2 Trend Brief External Source Quality Upgrade

Date: 2026-06-25

## Module

P2 Trend Brief External Source Quality Upgrade

## Purpose

Move Trend Brief live-external mode beyond "has external citations" by making source quality and artifact consistency explicit.

## What Changed

Code changed:

- `rag/external_source_quality.py`
  - adds authoritative technical/vendor documentation domains to developer-quality classification.
- `rag/source_review.py`
  - adds `artifact_quality_status` and deterministic runtime-vs-research-quality classification.
- `rag/trend_brief.py`
  - adds `source_quality_counts` and `artifact_quality_status` to the appendix.
  - adds `inspect_trend_brief_artifact` for evidence table vs appendix consistency.
- `rag/generate_trend_brief.py`
  - adds evidence type counts, source review status, artifact quality status, and artifact consistency to CLI summary.
  - expands RAG live-external query terms toward arXiv, benchmark, evaluation, Graph RAG, and Agentic RAG.

Tests changed:

- `rag/tests/test_external_source_quality.py`
- `rag/tests/test_source_review.py`
- `rag/tests/test_trend_brief.py`
- `rag/tests/test_generate_trend_brief.py`

Docs/artifacts changed:

- `docs/rag-transformation/plans/p2-trend-brief-external-source-quality-upgrade.md`
- `docs/rag-transformation/briefs/trend-brief-rag-source-quality-2026-06-25.md`
- roadmap and architecture status documents.

## Verification

Focused:

```text
python3 -m unittest rag.tests.test_external_source_quality rag.tests.test_source_review rag.tests.test_trend_brief rag.tests.test_generate_trend_brief -v
```

Result:

- 23 tests passed.

Canonical:

```text
pnpm rag:check:p0
```

Result:

- 177 tests passed.
- `py_compile` passed.

Live artifact smoke:

```text
.venv/bin/python -m rag.generate_trend_brief --topic RAG --mode live-external --output docs/rag-transformation/briefs/trend-brief-rag-source-quality-2026-06-25.md
```

Result:

- output: `docs/rag-transformation/briefs/trend-brief-rag-source-quality-2026-06-25.md`
- citation count: 8
- evidence type counts: 3 external, 1 graph, 4 internal
- source review status: `mixed_quality`
- artifact quality status: `research_quality_verified`
- artifact consistency: passed

Artifact consistency inspection:

- evidence table count: 8
- appendix citation count: 8
- evidence table types: 3 external, 1 graph, 4 internal
- appendix evidence types: 3 external, 1 graph, 4 internal

## Artifact First Review

The new artifact includes:

- one academic primary external source from `arxiv.org`;
- two weak/generic external sources;
- graph and internal evidence preserved;
- matching CLI/appendix/evidence-table counts.

This is a real improvement over the prior `weak_only` brief, but it is not a final semantic-quality claim.

## Next-Step Bias

Next bottleneck: evidence relevance.

The next module should review whether high-quality sources directly support the specific claims in the brief, not only whether the source domain is strong.

## Residual Risks

- Domain-based classification can still overrate sources whose content is only tangentially relevant.
- Live search results can change over time and may vary by provider ranking.
- Semantic correctness still needs claim-level review.
