# P1 Agent Control and Safety Plan

Date: 2026-06-22

## Goal

Make the RAG agent controlled enough to be useful before adding web search or UI integration.

This module does not try to make the agent more autonomous. It makes the agent more honest: every answer should expose whether it is grounded only in the internal AI Trend Radar corpus, whether external evidence is still required, and whether the current evidence is insufficient.

## Product Meaning

For Conrad, this module turns the system from "a chatbot that sounds confident" into "a research assistant with evidence boundaries."

In real AI product work, this matters because users need to know what the system actually checked. A RAG answer without a stated evidence boundary can look professional while quietly mixing retrieved facts, model memory, and guesses.

## Scope

1. Add a deterministic answer policy layer.
   - Input: query plan and citations.
   - Output: answer mode, evidence boundary, external-search requirement, and user-facing disclosure.

2. Inject answer policy into chat prompts.
   - The LLM should receive clear instructions for internal-only and needs-web questions.
   - Needs-web questions must not pretend that external evidence was checked.

3. Apply a deterministic safety disclosure to final answers.
   - Even if the LLM forgets, the returned answer still labels the evidence boundary.

4. Add a lightweight answer-policy rubric evaluator.
   - It should score live benchmark snapshots without calling an LLM.
   - It should catch missing citations, missing evidence-boundary labels, and weak needs-web handling.

## Out of Scope

- Real web search function calling.
- Original AI Trend Radar UI Agent integration.
- Neo4j graph-runtime verification, because local Docker/Neo4j is still unavailable.
- Full semantic answer grading by another LLM.

## Validation Table

1. Answer policy unit tests
   - Verification: internal-only, needs-web, and no-citation cases return expected policy modes.

2. Chat service tests
   - Verification: policy instructions are passed to the agent and final answers include a deterministic evidence-boundary disclosure.

3. Rubric evaluator tests
   - Verification: a good needs-web row passes and a missing-disclosure row fails.

4. Focused RAG check
   - Verification: `pnpm rag:check:p0` passes.

## Stage Gate

Pass this module only if:

- The system can label evidence boundaries without relying on the LLM.
- Needs-web questions are clearly marked as needing external evidence.
- Existing P0/P1 focused tests still pass.
- Evidence and execution logs are saved.
