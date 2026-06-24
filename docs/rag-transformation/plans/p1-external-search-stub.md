# P1 External Search Tool Stub and Citation Schema Plan

Date: 2026-06-22

## Goal

Prepare the project for future web search without enabling real network search yet.

The module defines what external evidence must look like, how unavailable external tools should respond, and how future search results will be evaluated before they are mixed with internal AI Trend Radar corpus evidence.

## Product Meaning

This protects the product from becoming a generic chatbot with loose web snippets.

External search is useful only if the answer can clearly separate:

- internal AI Trend Radar evidence;
- external evidence;
- remaining uncertainty;
- source freshness and citation quality.

## Scope

1. Add an external evidence schema.
   - Required fields: `evidence_type`, `source`, `title`, `url`, `retrieved_at`, `excerpt`.
   - Optional fields: `published_at`, `author`, `source_type`.

2. Add a disabled external tool adapter.
   - `web_search` should return a structured unavailable result.
   - The result should tell the caller that web search is planned but not enabled.

3. Add validation helpers and tests.
   - Good external citations should pass.
   - Missing URL/source/excerpt should fail.
   - Internal citations should not be accepted as external citations.

4. Add a lightweight readiness evaluator.
   - It should confirm the schema exists and disabled tool shape is stable.

## Out of Scope

- Real web search API calls.
- Browser automation.
- Fetching URLs.
- Merging external findings into final answers.
- Changing the original AI Trend Radar UI.

## Validation Table

1. External citation schema tests
   - Verification: valid external citation passes, incomplete or mislabeled citations fail.

2. Disabled web-search tool tests
   - Verification: unavailable result is structured, non-fatal, and explicit.

3. Focused RAG check
   - Verification: `pnpm rag:check:p0` passes.

4. Evidence records
   - Verification: evidence and execution log files exist.
