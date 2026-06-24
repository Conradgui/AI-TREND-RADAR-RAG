# Evidence: Trend Brief Workflow MVP Spec

Date: 2026-06-24

## Scope

Created the first product workflow spec for AI Trend Radar RAG.

The workflow turns a topic into a Markdown trend brief containing:

- executive summary;
- key trend themes;
- evidence table;
- graph relationship summary;
- source quality review;
- uncertainty and missing evidence;
- recommended follow-up actions;
- machine-readable appendix.

## Product Decision

Recommended first topic:

- `RAG`

Recommended first output:

- Markdown file under `docs/rag-transformation/briefs/`

Reason:

- avoids UI distraction;
- uses the strongest current evidence area;
- creates an inspectable artifact before building a cockpit interface.

## Reused Modules

- query understanding;
- hybrid retriever;
- graph reasoning service;
- citation helpers;
- source review;
- answer policy.

## Verification

Used low-cost checks only because this module is a spec, not code:

- searched existing workflow references with `rg`;
- verified roadmap/spec current gate strings;
- ran secret scan.

## Residual Risks

- Trend Brief Workflow is specified but not implemented.
- Conrad should confirm the first topic and Markdown-first output before implementation.
- LLM-assisted summary should remain optional/live-gated.
