# P1 URL Fetch and Source Deepening Plan

Date: 2026-06-22

## Goal

Add a safe URL fetch and extraction layer for external citations.

## Product Meaning

Search-provider snippets are useful discovery signals, but they are not enough for stronger RAG evidence.

Source deepening means:

- fetch the cited page safely;
- extract title and readable text;
- record failure reasons;
- preserve the original citation trail.

## Scope

1. Add URL safety checks for protocol and private/local network targets.
2. Add lightweight HTML title/text extraction.
3. Add source-deepening helper for external citations.
4. Add focused tests and canonical check coverage.

## Out of Scope

- JavaScript-rendered page extraction.
- Browser automation.
- Paywalled pages.
- Integration into final `/chat` prompt.
- Live broad crawling.

## Definition Of Done

Product behavior:
- The system can safely deepen an external citation without silently trusting provider snippets.

Engineering behavior:
- Safe fetch utility exists.
- HTML extraction exists.
- External citations can receive a `deep_fetch` record.

Evidence behavior:
- Evidence file records security boundaries and limitations.

Evaluation behavior:
- Focused tests pass.
- `pnpm rag:check:p0` passes.
