# Evidence: P1 Live Answer Quality Benchmark

## Date

2026-06-22

## Module

P1: Live Answer Quality Benchmark

## What Changed

Added a live vector-only answer benchmark:

- `rag/eval_live_chat.py`
- `rag/tests/test_eval_live_chat.py`
- `rag/retriever/vector_only.py`
- `pnpm rag:eval:live-chat`

The benchmark runs the five golden questions through:

```text
Query Understanding -> Chroma vector retrieval -> citations -> DeepSeek answer generation
```

Mode:

- `vector-only`
- Neo4j unavailable
- Web search unavailable

## Snapshot Artifact

Output file:

- `docs/rag-transformation/evals/live-chat-snapshot-2026-06-22.json`

Summary:

```json
{
  "total": 5,
  "with_citations": 5,
  "without_citations": 0,
  "needs_web_questions": 2
}
```

## Per-Question Findings

### Q1: Recent RAG Trends

Status:

- Answer generated.
- 8 citations.
- Citation dates after recent-filter fix: `2026-06-19`, `2026-06-20`, `2026-06-21`.

Quality note:

- The answer focuses on recent GitHub/RAG signals such as Graphify and related RAG projects.
- This is acceptable for vector-only baseline, but should later be improved with reranking and trend clustering.

### Q2: RAG Evolution And Papers

Status:

- Answer generated.
- 10 citations.
- Correctly states that internal evidence is not enough for a complete academic history.

Quality note:

- This question needs future web search or curated external paper references.
- Current answer should be treated as partial learning-map support, not final research output.

### Q3: Claude Recent Updates

Status:

- Answer generated.
- 8 citations.
- Citation dates after recent-filter fix: `2026-06-19`, `2026-06-20`, `2026-06-21`.

Quality note:

- The answer correctly surfaced Claude Code Artifacts from Product Hunt.
- This is a good vector-only result.

### Q4: GitHub Weekly Topics

Status:

- Answer generated.
- 8 citations.
- Citation dates: `2026-06-19`, `2026-06-20`, `2026-06-21`.
- Sources include `GitHub Search:rag`, `GitHub Search:ai-agent`, and `GitHub Search:llm`.

Quality note:

- Initially returned 0 hits due source metadata mismatch.
- Fixed by adding `source_family=GitHub`.

### Q5: Google OKF / ALM Wiki

Status:

- Answer generated with citations.
- Correctly says no evidence was found for OKF or ALM Wiki.
- Does not fabricate the relationship or performance claims.

Quality note:

- This is the desired safe behavior in vector-only mode.
- A final answer requires external primary-source search later.

## Verification

Focused command:

```bash
.venv/bin/python -m unittest rag.tests.test_eval_live_chat rag.tests.test_chat_service -v
```

Result:

```text
Ran 4 tests

OK
```

Canonical command:

```bash
pnpm rag:check:p0
```

Result:

```text
Ran 58 tests

OK
```

Live benchmark command:

```bash
.venv/bin/python -m rag.eval_live_chat
```

Result:

```json
{
  "output": "docs/rag-transformation/evals/live-chat-snapshot-2026-06-22.json",
  "summary": {
    "total": 5,
    "with_citations": 5,
    "without_citations": 0,
    "needs_web_questions": 2
  }
}
```

## Bugs Found And Fixed During This Module

### Recent Questions Retrieved Old Evidence

Problem:

- Q1 and Q3 initially retrieved May evidence despite asking for recent updates.

Root cause:

- `recent_corpus_first` was only a routing note and did not create a metadata filter.

Fix:

- `recent_corpus_first` now creates a 14-day date `$in` filter anchored to the latest corpus date.

## Residual Risks

- Answers are not yet graded by a human rubric.
- Vector-only mode cannot perform graph reasoning.
- Q2 and Q5 still require future web search or curated external sources.
- Benchmark output is a single current snapshot and should later become dated historical snapshots.

## Next Recommended Module

P1 Agent Control and Safety:

- Add explicit answer policy for `needs_web_search=true`.
- Require answers to label internal-only vs external-needed.
- Add lightweight rubric scoring for citation relevance, refusal quality, and freshness.
