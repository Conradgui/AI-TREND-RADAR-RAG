# Evidence: P1 External Source Quality Controls and Excerpt Policy

Date: 2026-06-22

## What Changed

Replaced the temporary fixed 600-character external excerpt cap with source-aware quality controls.

The system now classifies external sources and applies different excerpt policies:

- `official`: up to 1400 characters
- `academic`: up to 1600 characters
- `developer`: up to 1200 characters
- `trusted_media`: up to 900 characters
- `generic`: up to 800 characters
- `social`: up to 500 characters

It also adds quality metadata to external citations:

- `source_quality`
- `quality_score`
- `needs_deep_fetch`
- `quality_notes`

## Files Added

- `rag/external_source_quality.py`
- `rag/tests/test_external_source_quality.py`
- `docs/rag-transformation/plans/p1-external-source-quality-controls.md`

## Files Updated

- `rag/search_provider_adapters.py`
- `rag/tests/test_search_provider_adapters.py`
- `rag/eval_tavily_live.py`
- `package.json`
- `docs/rag-transformation/evals/tavily-live-smoke-2026-06-22.json`
- `docs/rag-transformation/roadmap.md`

## Why Fixed 600 Characters Was Not Enough

The fixed cap was a useful emergency safety valve after a Tavily smoke test returned a very noisy LinkedIn page.

But it was too blunt as a long-term policy:

- it could remove useful context from official or academic sources;
- it treated primary and social sources the same way;
- it did not tell downstream answer generation whether a source was trustworthy or needed deeper verification.

The new policy keeps more context for higher-quality sources and less for noisy/social sources.

## Validation

### Source Quality Tests

Command:

```bash
python3 -m unittest rag.tests.test_external_source_quality rag.tests.test_search_provider_adapters -v
```

Result:

- 12 tests passed.

### Full Focused RAG Check

Command:

```bash
pnpm rag:check:p0
```

Result:

- 100 tests passed.
- Python compile check passed.

### Tavily Live Smoke

Command:

```bash
.venv/bin/python -m rag.eval_tavily_live --query "Google OKF Open Knowledge Format"
```

Result:

```json
{
  "available": true,
  "citation_count": 1,
  "raw_results_count": 1,
  "errors": [],
  "usage": {
    "credits": 1
  }
}
```

Sanity check:

- Source: `cloud.google.com`
- Source quality: `official`
- Quality score: `0.95`
- Needs deep fetch: `false`
- Excerpt length: `1400`

## Product Interpretation

This module upgrades external search from "can find pages" to "can prefer better evidence."

For Q5-style official-source questions, social reposts should not be treated as final evidence. They may help discovery, but official domains should be preferred when available.

## Remaining Risk

- This is still rule-based quality scoring.
- URL fetch/extract is not implemented.
- External citations are not yet merged into final chat answers.
- Brave, Exa, SerpAPI, and GitHub live adapters remain unimplemented.
