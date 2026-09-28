# TASKS.md — live task list

One row per task; the table is the current truth, rewritten in place as
states change. Statuses: `pending` → `in_progress` → `done`, or
`blocked` (always say what gates it). User-gated tasks do not start
without the user's explicit go. Evidence links make every status
auditable.

Seeded from the approved design spec (2026-09-28). TASKS.md owns live
status; HANDOFF.md owns the narrative.

## Now

| # | Task | Status | Gate / next action | Evidence |
|---|---|---|---|---|
| 1 | User reviews the design spec | `in_progress` | awaiting user approval | docs/superpowers/specs/2026-09-28-vibe-coding-app-design.md |
| 2 | Write the implementation plan (writing-plans skill) | `pending` | gated on #1 | — |
| 3 | M1 backend: FastAPI + LangGraph scaffold, AgentRuntime seam, ToolRegistry | `pending` | gated on #2 | — |
| 4 | M1 backend: LocalSubprocessExecutor, provider seam, EventLog + SessionStore, SSE | `pending` | gated on #3 | — |
| 5 | M1 backend: auto-run verify-fix policy, usage/cost tracking | `pending` | gated on #4 | — |
| 6 | M1 frontend: Vite + React + TS scaffold, feature modules | `pending` | gated on #2 | — |
| 7 | M1 frontend: chat, preview, code (Monaco), sessions, settings | `pending` | gated on #6 | — |
| 8 | M1 E2E smoke: prompt → generate → build → run → preview → auto-fix | `pending` | gated on #5, #7 | — |

## Later

| # | Task | Status | Gate / next action | Evidence |
|---|---|---|---|---|
| 9 | M2: multi-session management, model picker, provider settings UI | `pending` | gated on M1 | — |
| 10 | M3: image input, Monaco hand-editing, supply-chain approval, budgets, a11y, tests | `pending` | gated on M2 | — |
| 11 | M4: Docker executor, Postgres, auth, deployment | `pending` | gated on M3 | — |
