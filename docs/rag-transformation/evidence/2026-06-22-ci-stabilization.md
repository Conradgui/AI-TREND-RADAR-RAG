# Evidence: CI Stabilization

## Date

2026-06-22

## Module

Post-P0 / CI Stabilization

## What Changed

Added a canonical RAG P0 check command and wired it into GitHub Actions CI.

Files:

- `package.json`
- `.github/workflows/ci.yml`

## Canonical RAG Command

Command:

```bash
pnpm rag:check:p0
```

Result:

```text
Ran 33 tests in 0.024s

OK
```

The command also syntax-checks:

- `rag/citations.py`
- `rag/chat_service.py`
- `rag/eval_golden.py`
- `rag/server.py`

## CI Workflow Change

`.github/workflows/ci.yml` now:

- sets up Node 22
- sets up Python 3.11
- installs pnpm dependencies
- runs existing Node checks
- runs `pnpm rag:check:p0`

## Local Node Test Note

Command:

```bash
pnpm test
```

Result:

```text
sh: vitest: command not found
```

Interpretation:

Local Node dependencies are not installed in this workspace. This does not prove CI failure because the CI workflow runs `pnpm install --frozen-lockfile` before `pnpm test`. I did not run `pnpm install` locally because it is a larger dependency installation.

## What This Does Not Cover

- Live Neo4j/ChromaDB/LLM runtime.
- Scheduled digest workflows that require secrets.
- Full pytest suite across old pytest-style tests.
- Original AI Trend Radar UI integration.

## Reviewer Gate

Reviewer verdict: `Pass With Follow-ups`.

No P0 blocking issues were found.

P1 follow-ups:

- `py_compile` does not validate runtime dependency installation or service startup.
- `rag:test:p0` uses an explicit module list; future P0 test modules must be added to the command or the command should later be made discoverable.
- A future timeout can be added to the RAG CI step if the suite grows or accidentally starts network/service calls.
