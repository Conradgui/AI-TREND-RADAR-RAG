# Execution Log: P2 Trend Brief Live External Mode

Date: 2026-06-24

## Loop

### Orient

Reviewed the generated local-only RAG brief.

Finding:

- structure is useful;
- source boundary is clear;
- the main gap is lack of external primary evidence.

### Decide

Decision:

- Add explicit `--mode live-external`.
- Keep default mode `local-only`.
- Do not add LLM-assisted writing yet.

### Implement

Changed:

- `rag/generate_trend_brief.py`
- `rag/trend_brief.py`
- `rag/tests/test_generate_trend_brief.py`
- `rag/tests/test_trend_brief.py`

Behavior:

- `local-only` produces no external requests.
- `live-external` builds provider-routed external requests from configured providers.
- CLI summary reports `external_citation_count`, `mode`, and `external_search`.
- Irrelevant external results are filtered for RAG briefs.
- External URL is used as the citation ID.
- HTML entities are cleaned in evidence excerpts.

### Verify

Focused tests:

```text
python3 -m unittest rag.tests.test_generate_trend_brief rag.tests.test_trend_brief -v
```

Result:

```text
Ran 10 tests in 0.001s
OK
```

Canonical P0:

```text
pnpm rag:check:p0
```

Result:

```text
Ran 174 tests in 0.109s
OK
```

### Live Smoke

Command:

```text
.venv/bin/python -m rag.generate_trend_brief --topic RAG --mode live-external --output docs/rag-transformation/briefs/trend-brief-rag-live-external-2026-06-24.md
```

Result:

```text
citation_count: 8
external_citation_count: 3
has_graph_summary: true
policy_mode: internal_and_external_grounded
```

Product review:

- live path works;
- final artifact filters irrelevant NASA/Nature results;
- external sources remain weak/generic;
- next gate should improve source quality or use deep fetch, not LLM prose.
