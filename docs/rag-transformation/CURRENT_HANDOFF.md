# Current Cross-Device Handoff

Updated: 2026-07-12

## Purpose

This is the current-state entry point for a new device or AI coding assistant. It is a concise orientation layer, not a replacement for the roadmap, plans, evidence, execution logs, or the raw Codex-session archive.

## Exact Repository State

- Repository: `Conradgui/AI-TREND-RADAR-RAG`
- Active branch: `codex/claude-audit-remediation`
- Current remote-backed commit: `f41f1d0 fix(rag): restore agent search citation contracts`
- Relationship: this branch is based on the preserved Claude snapshot and is **not merged into `main`**.
- Starting on device B: clone the repository, fetch all refs, then check out `codex/claude-audit-remediation`. Do not begin from `main` or from the old `claude/rag-transformation-checkpoints` branch.

Before editing on device B, run:

```bash
git status -sb
git log --decorate --oneline -8
```

The expected HEAD is `f41f1d0` or a later deliberate commit on the same branch.

## Product Direction And Boundaries

AI Trend Radar RAG is becoming a **local AI research cockpit**. It consumes the AI Trend Radar corpus, provides grounded retrieval/Agent answers, preserves evidence and citations, and produces Trend Brief artifacts.

The current product boundaries remain intentional:

1. Keep AI Trend Radar (data production) and AI Trend Radar RAG (knowledge application) as separate projects for now.
2. Do not build a generic chatbot, public SaaS, desktop app, or premature two-repository merge.
3. Stage 2.4 must reuse the existing AI Trend Radar `index.html` as its local cockpit shell; report reading is the default surface, while Agent, Briefs, and System are integrated capabilities.
4. Preserve static GitHub Pages behavior while improving the local FastAPI experience.
5. A citation must describe evidence actually used by the answer. A cached search result must not be presented as a newly executed search.

## What Happened Most Recently

### Preserved snapshot audit

The Claude snapshot on `claude/rag-transformation-checkpoints` was treated as a preserved input, not as proof of runtime readiness. A deterministic rerun exposed 5 failures and 2 errors in shared Agent/search paths. The intake record is:

- `docs/rag-transformation/execution-log/2026-07-11-claude-snapshot-intake.md`

### P0 Agent, search, and citation remediation

Commit `f41f1d0` repaired one limited shared-path slice:

- unified direct-LLM and LangGraph-compatible Agent invocation around `ainvoke(payload, config=None)`;
- applied recent-news freshness constraints only to `recent_web`, not paper or official-source discovery;
- restored citation refinement after external evidence merge;
- scoped search-cache keys by question and task/provider route;
- represented a cache hit as `reused_cached_result`, rather than a fresh external search;
- refreshed time-sensitive test fixtures without changing the production ten-day freshness rule.

Verification already recorded:

- focused chat-service/provider-adapter tests: 22 passed;
- canonical check: `pnpm rag:check:p0` — 193 passed;
- `git diff --check` — passed.

Important limitation: no live provider/search request, Docker startup, or local dashboard `/chat` smoke was performed. This work is **Locally Verified for the deterministic P0 contracts**, but Stage 2.4 is **not yet locally runtime verified**.

The associated records are:

- `docs/rag-transformation/plans/2026-07-11-p0-agent-search-citation-remediation.md`
- `docs/rag-transformation/evidence/2026-07-11-p0-agent-search-citation-remediation.md`
- `docs/rag-transformation/execution-log/2026-07-11-p0-agent-search-citation-remediation.md`

Note: the final execution log originally said the GitHub push was blocked. That was true at the time of writing; the commit was successfully pushed on 2026-07-12. The current Git state above is authoritative for remote backup status.

## Next Gate (Do Not Skip)

The immediate bottleneck is **Stage 2.4 local runtime acceptance**, not a Stage 2.5/2.6/2.7 feature expansion.

1. Read the current local-runtime and Docker-isolation plan before starting services.
2. Review the existing `.env` configuration without committing or exposing secrets.
3. Obtain Conrad's confirmation before starting Docker or making live provider/search calls.
4. Run a minimal local dashboard and `/chat` smoke; save evidence that distinguishes runtime success from research-quality evidence.
5. Only then decide whether the next bottleneck is UI flow, Agent ability, evidence selection, or runtime reliability.

Do not claim a production-ready dashboard, live provider compatibility, semantic answer quality, or Stage 2.4 completion from the deterministic suite alone.

## Required Read Order

1. `AGENTS.md`
2. This file: `docs/rag-transformation/CURRENT_HANDOFF.md`
3. `docs/rag-transformation/AI_HANDOFF.md`
4. `docs/rag-transformation/roadmap.md`
5. `docs/rag-transformation/specs/2026-06-22-target-architecture-spec.md`
6. `docs/rag-transformation/specs/2026-06-22-execution-loop-spec.md`
7. `docs/rag-transformation/specs/2026-06-21-quality-governance-spec.md`
8. The latest P0 remediation plan/evidence/execution log listed above.

## Local Codex Archive

The device-migration archive keeps project-related raw Codex session records and their referenced attachments as a recoverable audit trail. It is intentionally separate from the Git repository because it can contain private conversation context and machine-local file references.

Raw session records are not an import contract for the Codex desktop UI and should not be treated as the active project specification. Use this handoff plus the durable repository records for active work; consult the archive only when historical detail is needed.
