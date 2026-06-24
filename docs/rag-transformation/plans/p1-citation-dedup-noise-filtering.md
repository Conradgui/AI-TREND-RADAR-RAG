# P1 Citation Deduplication and Noise Filtering Plan

## Module

P1 Citation Deduplication and Noise Filtering

## Why This Module Matters

The retrieval precision benchmark showed that the current system can return valid citations that are still redundant or weakly related to the user question. This creates noisy prompts and can make the final answer look more grounded than it really is.

This module fixes the cheapest obvious problems before introducing heavier reranking.

## Definition Of Done

Product behavior:
- Repeated topic/project citations are reduced.
- For needs-web questions with external evidence, obvious internal noise is removed from the final citation set.

Engineering behavior:
- Citation assembly deduplicates semantically repeated internal chunks.
- Chat response assembly compresses weak internal context after external evidence is available.

Evidence behavior:
- Focused tests prove deduplication and filtering behavior.
- Canonical RAG check passes.
- Hybrid live verification is recorded separately and not claimed unless Docker/Neo4j is available.

Evaluation behavior:
- Existing retrieval precision baseline remains as the before-state.
- A new after-state hybrid snapshot should be generated when Docker Desktop is running.

Non-goals:
- No semantic reranker.
- No LLM-as-judge.
- No vector index rebuild.
- No original AI Trend Radar UI change.

Residual risks:
- The internal noise filter is deterministic and conservative.
- Needs-web filtering currently focuses on obvious distracting internal citations.
- Full relevance ranking still needs a later reranking module.

## Verification Table

1. Add failing tests for repeated citations and needs-web internal noise -> verify RED.
2. Add minimal dedup/filter implementation -> verify focused tests pass.
3. Run related focused suites -> verify citation/chat paths pass.
4. Run canonical check -> verify full deterministic RAG suite passes.
5. Attempt hybrid live after-state snapshot -> if Docker unavailable, record as blocked.
6. Run secret scan -> verify no API key prefixes appear.
