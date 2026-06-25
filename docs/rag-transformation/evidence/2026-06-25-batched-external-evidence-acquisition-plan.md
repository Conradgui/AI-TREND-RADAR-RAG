# Evidence: P2 Batched External Evidence Acquisition

Date: 2026-06-25

## Module

P2 Batched External Evidence Acquisition

## Purpose

Prevent small repeated external search calls by creating a request-before-execution plan, then running the accepted evidence batch once.

## External API Budget Strategy

External search API calls in this module: 4.

This module first created a plan:

```text
docs/rag-transformation/evals/batched-evidence-acquisition-plan-2026-06-25.json
```

Then executed the plan once:

```text
docs/rag-transformation/evals/batched-evidence-acquisition-result-2026-06-25.json
```

## Planned Batch

Input artifact:

```text
docs/rag-transformation/briefs/trend-brief-rag-source-quality-2026-06-25.md
```

Input relevance matrix:

```text
docs/rag-transformation/evals/trend-brief-source-relevance-2026-06-25.json
```

Claim gaps:

- `en-wikipedia-org-primary-confirmation`
  - current issue: weak definition/background context
  - needed source type: primary or authoritative technical reference
  - planned query: `retrieval augmented generation authoritative technical documentation definition`
  - route: Exa -> Tavily -> Brave
- `www-braintrust-dev-claim-corroboration`
  - current issue: partial support for evaluation/tooling claim
  - needed source type: primary benchmark or vendor docs
  - planned query: `retrieval augmented generation RAG evaluation benchmark graph agentic hybrid retrieval`
  - route: Exa -> Tavily -> SerpAPI

Budget:

- max total calls: 4
- planned calls: 4
- execute now: true
- execution status: `executed`

## Live Batch Result

Summary:

- external API calls: 4
- returned citations: 9
- claim gaps covered by citations: 2 / 2

Provider attempts:

- `en-wikipedia-org-primary-confirmation`
  - Exa: unavailable, `exa_network_error`
  - Tavily: available, 3 citations
- `www-braintrust-dev-claim-corroboration`
  - Exa: available, 3 citations
  - Tavily: available, 3 citations

Source quality:

- academic: 4
- official: 1
- developer: 1
- generic: 3

Interpretation:

- This is not a weak-only evidence batch.
- The generic citations should not be blindly inserted into the final brief.
- The next module should integrate the academic/official/developer citations first, then decide whether generic citations are useful as background only.

## Verification

Focused:

```text
python3 -m unittest rag.tests.test_evidence_batch_plan -v
```

Result:

- 5 tests passed.

Canonical:

```text
pnpm rag:check:p0
```

Result:

- 188 tests passed.
- py_compile passed.

## Residual Risks

- Planned queries are deterministic and can still return generic context.
- The Exa network error on one request is recorded as a provider/data issue, not a shared-path bug.
- This module improves evidence availability but does not yet rewrite the trend brief.
