# P1 External Evidence Merge Into Chat Plan

Date: 2026-06-22

## Goal

Merge live Tavily external citations into `/chat` answers for `needs-web` questions.

## Product Meaning

The system should no longer stop at "this needs external evidence" when a configured provider can retrieve citation-ready external evidence.

For Q2/Q5-style questions, the answer should separate:

- internal AI Trend Radar corpus evidence;
- external evidence;
- remaining uncertainty.

## Scope

1. Add external search execution for `needs-web` query plans.
2. Merge internal and external citations into the prompt.
3. Update answer policy when external evidence is actually used.
4. Expose external search status in `query_understanding`.
5. Wire the FastAPI server to provide a search registry when provider keys exist.

## Out of Scope

- Brave/Exa/SerpAPI/GitHub live clients.
- Multi-provider fanout.
- URL fetch/extract.
- Full source conflict resolution.

## Validation

1. Unit tests prove needs-web chat calls external search when registry is provided.
2. Unit tests prove answer policy changes from "needs external evidence" to "internal + external grounded" when external citations exist.
3. Focused RAG check passes.
4. A low-volume live smoke can run one Q5-style query end to end.
