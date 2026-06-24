# Evidence: Trend Brief Product Review And Live External Mode

Date: 2026-06-24

## Product Review

Reviewed:

- `docs/rag-transformation/briefs/trend-brief-rag-2026-06-24.md`

Observed artifact properties:

```text
sections: 8
citation_count: 5
evidence_types: graph 1, internal 4
graph_counts: 18 topics, 14 dates, 4 sources
policy_mode: internal_grounded
source_review_status: internal_only
```

Strengths:

- brief has the required sections;
- graph evidence is present;
- graph overclaim guardrail is present;
- internal-only limitation is explicit;
- source evidence is inspectable through citation IDs.

Weaknesses:

- no external primary source citations;
- no current live web evidence;
- semantic quality still requires human review;
- deterministic wording is structurally clear but not yet a polished research memo.

Product decision:

- Do not add LLM-assisted summary yet.
- Add explicit live external evidence mode first.

Reason:

- The artifact's main gap is evidence coverage, not prose quality.
- LLM polishing would make an internal-only artifact more fluent without fixing source completeness.

## Code Changes

- Updated `rag/generate_trend_brief.py`.
  - Adds `--mode local-only|live-external`.
  - Adds `--max-external-citations`.
  - Adds provider-routed external search request construction.
  - Adds external citation count and search trace to CLI summary.
  - Keeps default mode `local-only`.
- Updated `rag/tests/test_generate_trend_brief.py`.
  - Verifies local-only emits no external requests.
  - Verifies live-external uses provider routing.
  - Verifies generation summary includes external counts and trace.
- Updated `rag/trend_brief.py` and `rag/tests/test_trend_brief.py`.
  - Filters irrelevant external citations for RAG briefs.
  - Uses external URLs as citation IDs.
  - Uses `retrieved_at` as the external citation date in evidence tables.
  - Cleans HTML entities in evidence excerpts.

## Verification

Focused tests:

```text
python3 -m unittest rag.tests.test_generate_trend_brief rag.tests.test_trend_brief -v
```

Result:

```text
Ran 10 tests in 0.001s
OK
```

Canonical P0 before live-smoke quality fix:

```text
pnpm rag:check:p0
```

Result:

```text
Ran 172 tests in 0.123s
OK
```

Canonical P0 after live-smoke quality fix:

```text
pnpm rag:check:p0
```

Result:

```text
Ran 174 tests in 0.109s
OK
```

## Live Verification

Command:

```text
.venv/bin/python -m rag.generate_trend_brief --topic RAG --mode live-external --output docs/rag-transformation/briefs/trend-brief-rag-live-external-2026-06-24.md
```

Result:

```text
{
  "output": "docs/rag-transformation/briefs/trend-brief-rag-live-external-2026-06-24.md",
  "topic": "RAG",
  "citation_count": 8,
  "external_citation_count": 3,
  "has_graph_summary": true,
  "mode": "live-external",
  "policy_mode": "internal_and_external_grounded"
}
```

Artifact quality check:

- final artifact has 8 citations;
- evidence types: 4 internal, 1 graph, 3 external;
- irrelevant NASA/Nature provider results are filtered from the Markdown artifact;
- external citation IDs are URLs;
- HTML entities are cleaned in evidence excerpts;
- source review status remains `weak_only`.

Interpretation:

- live-external runtime path is `Live Smoke Verified`;
- source quality is still weak;
- next improvement should target provider/query strategy or source deepening, not prose polishing.

## Residual Risks

- External providers returned weak/generic sources in this smoke.
- Source conflict handling exists but generated artifact quality still needs live review.
- Deep fetch is not enabled in this module.
