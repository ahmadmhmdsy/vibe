# PLAN.md — Vibe Coding App

Status: **Approved design spec** (2026-09-28). The authoritative spec is
[docs/superpowers/specs/2026-09-28-vibe-coding-app-design.md](./docs/superpowers/specs/2026-09-28-vibe-coding-app-design.md).

## 1. Product

A local-first vibe-coding IDE. The user describes an app idea in chat; an agent
builds it as a multi-file React (Vite + TypeScript) project, installs dependencies,
builds, runs, and previews it — with an auto-run verify-fix loop that catches and
fixes build/runtime errors.

## 2. Architecture (summary)

deepseek-harness-inspired **capability seams** — every swappable part has a
Definition (interface), Provider (implementation), and Consumer:

| Seam | Providers |
|---|---|
| LLM | OpenAI, Anthropic, OpenCode Go, custom OpenAI/Anthropic-compatible |
| Agent runtime | LangGraph adapter (swappable) |
| Executor | Local subprocess (today), Docker (M4) |
| Tools | file/build/run/screenshot registry |
| Sessions | SQLite (today), Postgres (M4) |
| Events | SQLite-backed log + SSE |

Two rules: **model-visible means logged** (the EventLog is the source of truth);
**narrow interfaces, no reaching across seams**.

"Ready to run on one local machine" is defined by the 12 acceptance criteria
(AC-1…AC-12) in
[docs/superpowers/plans/2026-10-11-local-production-hardening.md](./docs/superpowers/plans/2026-10-11-local-production-hardening.md) §1.

## 3. Milestones

| Milestone | Goal | Status |
|---|---|---|
| M1 — Core loop | Single-session chat → generate → install → build → run → preview → auto-fix. Provider seam live. | **done** 2026-09-29 |
| M2 — Sessions & models | Multi-session management, model picker, provider settings UI. | **done** 2026-09-29 |
| M3 — Polish | Image input, Monaco hand-editing, supply-chain approval, budgets, a11y, tests. | **done** 2026-09-29 |
| M4 — Scale | Docker executor, Postgres, auth, deployment — behind the same interfaces. | **deferred** — local-first; seams kept (see M6 and §2 of the hardening plan) |
| M5 — Frontend UI/UX overhaul | Design system, shell, honest states, chat, approvals, code, preview. | **done** 2026-09-29 |
| M6 — Local production readiness | One-command local install and run, production serving mode, first-run guidance, retention and recovery, honest states. | **pending** — [plan](./docs/superpowers/plans/2026-10-11-local-production-hardening.md) |

## 4. Open items

- App name (working name "vibe").
- M4: Docker executor, Postgres, auth, deployment — deferred to the scale path
  (seams kept; see M6).
- Workspace scaffolding (spec §6.2 — Vite+React+TS template on session creation).
  Verified **not implemented** 2026-10-11: `services/vibe/src/vibe/workspace.py`
  only enumerates files, and `SessionService.ensure_workspace`
  (`services/vibe/src/vibe/services/sessions.py:35-39`) only creates the directory.

Resolved and removed from this list 2026-10-11:

- Playwright console/screenshot capture — **done** (P5, 2026-10-05;
  `executor/browser.py`). ENVIRONMENT.md's old "REMOVED from deps" row was the
  false claim recorded as DOC-07 in the
  [2026-10-11 review](./docs/reviews/2026-10-11-full-app-review/04-docs-and-process.md).
- EventLog SQLite persistence — **done** (P1, 2026-10-04; the log has been
  SQLite-backed since, so spec §7.2 is satisfied — see TASKS.md P1).
