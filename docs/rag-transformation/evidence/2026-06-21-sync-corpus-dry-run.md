# Evidence: Fresh Corpus Sync Dry Run

## Date

2026-06-21

## Module

P0 / Module 1: Fresh Corpus Sync Design

## What Was Verified

The local sync script can:

- Build a sync plan from the upstream AI Trend Radar Pages `manifest.json`.
- Reach the public AI Trend Radar Pages corpus.
- Fetch the latest manifest, search index, report markdown, and topic pool paths in dry-run mode.

## Commands

```bash
python3 -m unittest rag.tests.test_sync_corpus -v
```

Result:

```text
test_build_sync_plan_includes_manifest_search_index_reports_and_topic_pools ... ok
test_normalize_base_url_removes_trailing_slash ... ok
test_sync_corpus_writes_files_from_fetcher ... ok

Ran 3 tests in 0.004s

OK
```

```bash
python3 -m rag.sync_corpus --days 1 --dry-run
```

Result:

```text
[sync] downloaded=4 failed=0
```

## Interpretation

The sync script is ready for a small real sync. The next recommended action is to sync only the latest few days first, verify local files and manifest freshness, then expand the sync window.
