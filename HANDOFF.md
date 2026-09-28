# HANDOFF.md — agent-to-agent continuation guide

> Written for an agent resuming with fresh context on this machine
> (E:\python_projects\apps_building). Read [PLAN.md](./PLAN.md) (the spec
> pointer) and the design spec first, then this.

## Current state (2026-09-28)

- Design spec approved and committed.
- Project scaffolded with the nano_SLMs-inspired doc system: CLAUDE.md
  (thin adapter), AGENTS.md (router), SOUL.md (identity), CURRENT_STATE.md
  (snapshot), ENVIRONMENT.md (stable policy), TASKS.md (live list),
  MEMORY.md (decisions + lessons), HANDOFF.md (this guide), rules/
  (conditional policy).
- Implementation **not started**. Design spec approved; implementation plan
  written to docs/superpowers/plans/2026-09-28-m1-core-loop.md (16 tasks,
  backend → frontend → E2E). Next: execute M1.

## Milestones

| Milestone | Goal | Status |
|---|---|---|
| M1 — Core loop | Single-session chat → generate → install → build → run → preview → auto-fix | pending |
| M2 — Sessions & models | Multi-session, model picker, provider settings UI | pending |
| M3 — Polish | Image input, Monaco editing, supply-chain approval, budgets, a11y, tests | pending |
| M4 — Scale | Docker executor, Postgres, auth, deployment | pending |

## Environment

- See [ENVIRONMENT.md](./ENVIRONMENT.md) for stable policy and machine
  profiles (Python 3.13.7, uv 0.11.22, Node 24.18.0, pnpm 12.3.4, Docker
  28.3.2).

## Resume notes

- The design spec is the source truth:
  docs/superpowers/specs/2026-09-28-vibe-coding-app-design.md.
- The document map in AGENTS.md is the index — a doc outside it does not
  exist for the next agent.
- Git: scaffold commit 215ca70 on master; working tree clean.
