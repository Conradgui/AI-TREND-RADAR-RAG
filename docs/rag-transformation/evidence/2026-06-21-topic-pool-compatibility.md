# Evidence: Topic Pool Compatibility

## Date

2026-06-21

## Module

P0 / Module 2: Topic Pool Compatibility

## What Was Verified

The ingestion layer now normalizes topic pools into a canonical `{"candidates": [...]}` shape.

It supports:

- Current upstream shape: `candidates`
- Legacy shape: `topics`
- Missing or malformed topic pools
- Date normalization on each candidate

## Real Corpus Shape

Command:

```bash
node -e "const fs=require('fs'); const p=JSON.parse(fs.readFileSync('digests/2026-06-21/topic-pool.json','utf8')); console.log(JSON.stringify({keys:Object.keys(p), candidates:Array.isArray(p.candidates) ? p.candidates.length : null, topics:Array.isArray(p.topics) ? p.topics.length : null}, null, 2));"
```

Result:

```json
{
  "keys": [
    "generatedAt",
    "date",
    "candidates",
    "sourceStatuses",
    "notices",
    "warnings"
  ],
  "candidates": 52,
  "topics": null
}
```

## Test Verification

Command:

```bash
python3 -m unittest rag.tests.test_ingest -v
```

Result:

```text
Ran 10 tests in 0.001s

OK
```

Command:

```bash
python3 -m unittest rag.tests.test_sync_corpus -v
```

Result:

```text
Ran 3 tests in 0.012s

OK
```

## Related Reliability Fixes

Two import-time issues were exposed while making this testable:

- `python-dotenv` is now optional for importing `rag.config`.
- Neo4j and ChromaDB imports are delayed until `run_ingestion()` is actually executed.

This keeps pure unit tests runnable without installing the full RAG service stack.

## Residual Risk

Some older tests in the repository still use pytest-style functions and are not discovered by `unittest`. That should be handled in the GitHub Action stabilization module rather than hidden inside topic-pool compatibility work.
