# Vibe Coding App

A local-first vibe-coding IDE. Describe an app idea in chat; an agent builds it as a
multi-file React (Vite + TypeScript) project, installs dependencies, builds, runs,
and previews it — with an auto-run verify-fix loop that catches and fixes
build/runtime errors.

## Features (designed — see the spec for status)

- **Chat panel** — conversation history, model picker, text input (image input post-MVP).
- **Multi-session** — create, rename, delete, resume sessions; each with its own workspace.
- **Live preview** — the generated app runs in an iframe; the agent can read console
  logs and take screenshots to verify its work.
- **Auto-run** — after each turn the app is built and run; build/runtime errors are
  fed back to the agent, which fixes them (up to a capped number of iterations).
- **Code view** — Monaco editor over the generated project (read-only for MVP).
- **Providers** — OpenAI, Anthropic, OpenCode Go, and custom OpenAI/Anthropic-compatible
  endpoints; per-model protocol routing; usage + cost tracking per step/turn/session.

## Layout

- `apps/vibe` — React + TypeScript frontend (Vite)
- `services/vibe` — Python backend (FastAPI + LangGraph)
- `docs/` — project documents and the design spec
- `.agents/skills/` — installed agent skills

## Run

Frontend and backend commands will be documented here once the implementation lands.
Until then, the design spec is the source of truth:
[docs/superpowers/specs/2026-09-28-vibe-coding-app-design.md](./docs/superpowers/specs/2026-09-28-vibe-coding-app-design.md).

## Project documents

- [PLAN.md](./PLAN.md) — approved product and architecture specification.
- [HANDOFF.md](./HANDOFF.md) — latest implementation state and evidence.
- [TASKS.md](./TASKS.md) — live task statuses and gated follow-ups.
- [MEMORY.md](./MEMORY.md) — durable decisions and gotchas.
- [ENVIRONMENT.md](./ENVIRONMENT.md) — toolchain and environment facts.
