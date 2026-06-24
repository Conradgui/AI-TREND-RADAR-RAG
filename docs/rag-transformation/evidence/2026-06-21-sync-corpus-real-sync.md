# Evidence: Fresh Corpus Sync Real Sync

## Date

2026-06-21

## Module

P0 / Module 1: Fresh Corpus Sync

## Scope

Synced the latest 3 days from AI Trend Radar Pages into the local RAG project.

## Command

```bash
python3 -m rag.sync_corpus --days 3
```

Result:

```text
[sync] downloaded=8 failed=0
```

## Local Manifest Verification

Command:

```bash
node -e "const fs=require('fs'); const m=JSON.parse(fs.readFileSync('manifest.json','utf8')); console.log(JSON.stringify({generated:m.generated, latest:m.dates?.[0]?.date, count:m.dates?.length}, null, 2));"
```

Result:

```json
{
  "generated": "2026-06-21T05:07:03.937Z",
  "latest": "2026-06-21",
  "count": 33
}
```

## Files Confirmed

The sync added or updated:

- `manifest.json`
- `digests/search-index.json`
- `digests/2026-06-21/ai-topic-radar.md`
- `digests/2026-06-21/topic-pool.json`
- `digests/2026-06-20/ai-topic-radar.md`
- `digests/2026-06-20/topic-pool.json`
- `digests/2026-06-19/ai-topic-radar.md`
- `digests/2026-06-19/topic-pool.json`

## Test Verification

Command:

```bash
python3 -m unittest rag.tests.test_sync_corpus -v
```

Result:

```text
Ran 3 tests in 0.003s

OK
```

## Interpretation

The local RAG project now has a fresh public corpus through 2026-06-21. This is enough to start validating ingestion compatibility with the real `topic-pool.json` structure.
