# Evidence: P1 URL Fetch and Source Deepening

Date: 2026-06-22

## What Changed

Added a safe URL fetch and lightweight extraction layer for external citations.

The system can now:

- reject unsupported URL schemes;
- reject private or local network targets;
- fetch HTTP/HTTPS pages through an injectable transport;
- extract HTML title and readable text;
- attach a `deep_fetch` record to external citations that need deeper verification.

## Files Added

- `rag/url_fetch.py`
- `rag/tests/test_url_fetch.py`
- `docs/rag-transformation/plans/p1-url-fetch-source-deepening.md`

## Files Updated

- `package.json`
- `docs/rag-transformation/roadmap.md`

## Security Boundary

This module intentionally starts with a conservative fetch policy.

It blocks:

- non-HTTP/HTTPS schemes;
- missing hostnames;
- localhost, loopback, private, link-local, multicast, reserved, or unspecified IP addresses.

Why this matters:

- URL fetch in an agent can become an SSRF risk if it can access local or internal network resources.
- The first version must be safe before it is connected to automatic chat behavior.

## Validation

### TDD Red Check

Command:

```bash
python3 -m unittest rag.tests.test_url_fetch -v
```

Initial result:

- Failed with `ModuleNotFoundError` because `rag.url_fetch` did not exist yet.

### Focused Tests

Command:

```bash
python3 -m unittest rag.tests.test_url_fetch -v
```

Result:

- 4 tests passed.

### Full Focused RAG Check

Command:

```bash
pnpm rag:check:p0
```

Result:

- 109 tests passed.
- Python compile check passed.

## Product Interpretation

This is the foundation for moving from "provider snippet evidence" toward "source-inspected evidence."

It is not yet wired into `/chat`. That is intentional:

- first build and test the safe fetch boundary;
- then integrate it into external evidence flow;
- then decide when live fetching is worth the latency and cost.

## Remaining Risk

- No JavaScript-rendered page extraction.
- No redirect-chain safety audit beyond the initial hostname check.
- No full-page semantic chunking.
- Not yet integrated into answer generation.
- Live fetching may add latency and should be gated by source quality and budget policy.
