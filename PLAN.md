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

## 3. Milestones

| Milestone | Goal | Status |
|---|---|---|
| M1 — Core loop | Single-session chat → generate → install → build → run → preview → auto-fix. Provider seam live. | **done** 2026-09-29 |
| M2 — Sessions & models | Multi-session management, model picker, provider settings UI. | **done** 2026-09-29 |
| M3 — Polish | Image input, Monaco hand-editing, supply-chain approval, budgets, a11y, tests. | **done** 2026-09-29 |
| M4 — Scale | Docker executor, Postgres, auth, deployment — behind the same interfaces. | pending |
| M5 — Frontend UI/UX overhaul | Design system, shell, honest states, chat, approvals, code, preview. | **done** 2026-09-29 |

## 4. Open items

- App name (working name "vibe").
- M4: Docker executor, Postgres, auth, deployment.
- Playwright console/screenshot capture (removed offline; restore when network returns).
- EventLog SQLite persistence (currently in-memory; spec §7.2 shows SQLite events table).
- Workspace scaffolding (spec §6.2 — Vite+React+TS template on session creation).
