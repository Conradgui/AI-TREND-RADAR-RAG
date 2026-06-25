# Evidence: P2 Trend Brief Batch Evidence Integration

Date: 2026-06-25

## Module

P2 Trend Brief Batch Evidence Integration

## Purpose

Increase evidence pool quality during testing while keeping production mode controlled, then integrate selected batch citations into Trend Brief artifacts.

## Search Strategy Decision

Two modes are now explicit:

- `production`
  - routed providers;
  - max total provider calls: 4;
  - max results per provider call: 8;
  - used for routine Agent or brief generation.
- `exploration`
  - all task-suitable configured providers;
  - max total provider calls: 8;
  - max results per provider call: 15;
  - used for testing, benchmark, and evidence pool expansion.

Rationale:

- the old 3-result setting made the evidence pool too narrow;
- exploration should spend external API quota when it improves quality and reduces repeated Codex/model work;
- production still needs bounded latency and noise.

## Live Evidence

Production batch:

```text
docs/rag-transformation/evals/batched-evidence-acquisition-production-2026-06-25.json
```

Result:

- external API calls: 4
- returned citations: 32
- claim gaps with citations: 2 / 2
- source quality: 8 academic, 2 official, 8 developer, 14 generic

Exploration batch:

```text
docs/rag-transformation/evals/batched-evidence-acquisition-exploration-2026-06-25.json
```

Result:

- external API calls: 6
- returned citations: 75
- claim gaps with citations: 2 / 2
- source quality: 19 academic, 6 official, 6 developer, 42 generic, 2 social

## Generated Briefs

Production batch evidence brief:

```text
docs/rag-transformation/briefs/trend-brief-rag-production-batch-evidence-2026-06-25.md
```

Result:

- citation count: 9
- external citations: 4
- evidence types: 4 external, 1 graph, 4 internal
- artifact quality: `research_quality_verified`
- source relevance: 3 direct support, 1 weak context
- batch candidates: 32
- selected batch citations: 4

Exploration batch evidence brief:

```text
docs/rag-transformation/briefs/trend-brief-rag-exploration-batch-evidence-2026-06-25.md
```

Result:

- citation count: 9
- external citations: 4
- evidence types: 4 external, 1 graph, 4 internal
- artifact quality: `research_quality_verified`
- source relevance: 2 direct support, 2 weak context
- batch candidates: 75
- selected batch citations: 4

## Interpretation

- Exploration mode successfully creates a much larger evidence pool.
- Production mode now returns enough evidence for meaningful filtering without using all providers.
- The selected Trend Brief citations are intentionally capped at 4 external citations to keep the artifact readable.
- Generic and social candidates remain available in the raw artifact but are not automatically inserted into the brief.

## Verification

Focused:

```text
python3 -m unittest rag.tests.test_trend_brief rag.tests.test_batch_evidence rag.tests.test_generate_trend_brief rag.tests.test_evidence_batch_plan -v
```

Result:

- 21 tests passed.

Canonical:

```text
pnpm rag:check:p0
```

Result:

- 191 tests passed.
- py_compile passed.

## Residual Risks

- Deterministic selection currently balances source diversity and source quality; it does not yet use LLM semantic reranking.
- Official/developer definition pages can be useful context but may still be weak support for benchmark/evaluation claims.
- Exploration raw pools are noisy by design and must stay behind a filtering layer.
