# Decision 0009: Upstream corpus and local index boundary

## Status

Accepted on 2026-08-05.

## Context

The repository retained scheduled workflows copied from AI-TREND-RADAR and also had a local sync script. This made two repositories appear to be content producers, while downloading files did not automatically update Neo4j or ChromaDB. A GitHub-hosted runner also cannot update Conrad's local Docker volumes because each run uses a temporary remote machine.

## Decision

- AI-TREND-RADAR is the canonical producer and publishes auditable reports through GitHub Pages.
- AI-TREND-RADAR-RAG only consumes those public artifacts.
- Cloud automation synchronizes raw corpus files into this repository; it does not build or commit database snapshots.
- Local startup checks the same upstream source and incrementally ingests dates whose content fingerprint has not yet been recorded as successfully indexed. This covers new downloads, fresh clones, and files already updated by Git.
- A failed update preserves the last successful corpus and is visible in system status instead of blocking product use.
- Agent is the primary dashboard action. Briefs remain an internal/API capability but no longer occupy top-level navigation.

## Consequences

This boundary removes duplicate production and keeps raw evidence reviewable in Git. Local indexes remain reproducible and machine-specific. Scheduled GitHub Actions will activate only after the workflow exists on the repository's default branch; development and review remain confined to `claude/rag-transformation-checkpoints` until Conrad explicitly chooses to merge.

## Replaceable implementation choices

GitHub Pages, the 30-day recent-revision recheck window, and the current visual treatment are implementation choices rather than permanent product constraints. The recheck window never caps catch-up: every upstream date newer than the local latest date is synchronized. Future work may change transport, retention, or UI without changing the producer/consumer boundary and the last-known-good failure policy.
