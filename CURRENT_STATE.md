# CURRENT_STATE

<!-- session-maintained snapshot — refreshed at session start; a render script is planned with implementation -->

## Git

- Branch: master
- Commit: 215ca70 (scaffold) + M1–M3 commits; M5 commits 504be45..HEAD
  (8 tasks, frontend UI/UX overhaul — done 2026-09-29)
- Dirty files: pre-existing M2/M3 work was committed with its milestones;
  M5 work is fully committed.

## Active jobs

- Backend dev server: not started (port 8000 held by foreign httpd/Apache —
  use VIBE_PORT=8001)
- Frontend dev server: not started (use VITE_API_URL=http://localhost:8001
  with the backend on 8001; dev server on 5173 for CORS)
- Agent sessions: none

## Tasks

- See [TASKS.md](./TASKS.md) — M1 core loop **done** (E2E PASS 2026-09-29),
  M2 **done** (2026-09-29), M3 **done** (2026-09-29), M5 **done**
  (2026-09-29). Next milestone: **M4 — Scale**.
  M5 delivered: design system + UI primitives, app shell (3-col, Settings
  modal, responsive), honest states (errors/loading/empty/confirms),
  per-session chat store + history endpoint + markdown, rich approval cards
  with always-allow policy, accessible code file list + language detection +
  save indicator, real preview state via preview endpoints + polling,
  favicon/title/theme toggle. 53 frontend tests PASS, typecheck clean,
  build clean, axe-core 0 violations desktop + mobile.

## Decisions

- 2026-09-28: server-side sandbox, local-first, core-loop MVP, full tool
  suite, provider-agnostic + OpenCode Go, LangGraph + local subprocess,
  usage/cost tracking. See [PLAN.md](./PLAN.md) and the design spec.
- 2026-09-29 (M5): dark-first IDE aesthetic; Settings as modal (Cmd+,);
  react-markdown for LLM output (hand-rolled HTML is an XSS risk);
  per-session chat store keyed by sid (global store bled messages across
  sessions); approval always-allow policy stored in localStorage.

## Environment

- See [ENVIRONMENT.md](./ENVIRONMENT.md) for stable policy and machine
  profiles.
