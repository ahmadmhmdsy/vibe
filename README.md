# Vibe Coding App

A local-first vibe-coding IDE. Describe an app idea in chat; an agent builds it as a
multi-file React (Vite + TypeScript) project, installs dependencies, builds, runs,
and previews it — with an auto-run verify-fix loop that catches and fixes build
errors.

## Features

- **Chat panel** — conversation history with markdown rendering, model picker, text input with image attachment, streaming responses with stop button.
- **Multi-session** — create, rename, delete, resume sessions; each with its own workspace.
- **Live preview** — the generated app runs in an iframe; its dev server is started on demand and stopped again when the session goes idle.
- **Auto-run** — after each turn the app is built and run; build errors are fed back to the agent, which fixes them (up to a capped number of iterations).
- **Code view** — Monaco editor over the generated project with file tree, language detection, and hand-editing support.
- **Providers** — OpenAI, Anthropic, OpenCode Go, and custom OpenAI/Anthropic-compatible endpoints; per-model protocol routing; usage + cost tracking per step/turn/session.
- **Supply-chain approval** — agent requests approval before installing packages outside the allowlist; always-allow policy available.
- **Settings** — provider management (built-in + custom), API key configuration (server-side only).

## Layout

- `apps/vibe` — React + TypeScript frontend (Vite)
- `services/vibe` — Python backend (FastAPI + LangGraph)
- `docs/` — project documents and the design spec
- `.agents/skills/` — installed agent skills

## Run

### Backend (FastAPI + LangGraph)

```powershell
cd services\vibe
.venv\Scripts\python.exe -m uvicorn vibe.api.app:create_app --factory --port 7321
```

### Frontend (Vite + React)

```powershell
cd apps\vibe
set VITE_API_URL=http://localhost:7321&& pnpm run dev
```

### Or use the launcher

Double-click `start.bat` to start both servers in separate windows.

`start.bat` checks whether 7321 is free and walks upwards until it finds one
that is, then hands that port to the frontend as `VITE_API_URL` — so the numbers
above are defaults, not a fixed contract. The backend reads `VIBE_HOST` and
`VIBE_PORT`; the frontend reads `VITE_API_URL`. See `.env.example`.

## Develop

Run everything at once with `test.bat` (backend then frontend), or one half
at a time:

| What | Where | Command |
|---|---|---|
| Backend tests | `services\vibe` | `.venv\Scripts\python.exe -m pytest -q` |
| Backend lint | `services\vibe` | `.venv\Scripts\python.exe -m ruff check .` |
| Frontend tests | `apps\vibe` | `pnpm test` |
| Frontend watch tests | `apps\vibe` | `pnpm run test:watch` |
| Frontend lint | `apps\vibe` | `pnpm run lint` |
| Typecheck | `apps\vibe` | `pnpm run typecheck` |
| Format | `apps\vibe` | `pnpm run format` |

The repo is a pnpm workspace: `pnpm install` at the root covers
`apps/vibe`, and the root `package.json` exposes the same commands —
`pnpm test`, `pnpm typecheck`, `pnpm lint`, `pnpm build`, `pnpm dev` — plus
`pnpm test:backend` / `pnpm lint:backend` for the Python side.

`pnpm test` is `vitest run` — a single pass that exits. Do not write
`pnpm test -- --run`: pnpm forwards the `--` and the extra flag reaches
vitest.

The backend logs to stderr through `vibe.logging_setup`; set
`VIBE_LOG_LEVEL=DEBUG` for more. The same file owns the format, so a record
is never printed twice.

CI runs the backend and frontend jobs on every push and pull request — see
`.github/workflows/ci.yml`. `prettier --check` is deliberately not part of
it yet: the tree is not prettier-formatted, and applying it is a separate
reviewable change.

## Known gaps

Current limits, stated plainly. None of them hides behind a feature claim.

- **The agent can see the browser, but only where a browser is installed.**
  `vibe/executor/browser.py` drives Playwright: `read_console_logs` returns real
  console output (errors by default; `level="warning"` or `"all"` for more) and
  `screenshot` returns a real PNG that reaches the model as an image. Every
  method degrades to `None` when Playwright or the browser binary is missing,
  so a machine without a browser still runs — it just cannot see the app.
  Install both: `uv add playwright`, then `playwright install chromium`.
  `VIBE_BROWSER_HEADLESS=0` opens a visible window, which is the easiest way
  to watch the agent work.
- **The API authenticates the machine, not a user.** Every router is mounted
  behind `LoopbackAuthenticator`, which accepts a request only when it arrives
  from `127.0.0.1`, `::1`, `localhost`, or an in-process caller, and answers
  anything else with `401 unauthenticated`. A second, independent control —
  `OriginGuard` — refuses state-changing requests whose `Origin` is not in
  `VIBE_CORS_ORIGINS` with `403 forbidden_origin`. Both are needed: loopback auth
  cannot catch CSRF, because a cross-site POST from your own browser arrives
  from `127.0.0.1` and therefore looks local. `/health` stays open.
  There are no users, passwords, or tokens: `Principal.id` is always `"local"`.
  The seam is `vibe/auth.py` (an `Authenticator` protocol plus
  `Container.build(authenticator=...)`); a future token authenticator plugs in
  there, and multi-user later means an `owner_id` on sessions plus an ownership
  check in `require_session`.
- **A stored API key cannot be cleared from the UI.** Replace or remove the entry
  in `providers.json` in the workspace directory instead.

## Project documents

- [PLAN.md](./PLAN.md) — approved product and architecture specification.
- [HANDOFF.md](./HANDOFF.md) — latest implementation state and evidence.
- [TASKS.md](./TASKS.md) — live task statuses and gated follow-ups.
- [MEMORY.md](./MEMORY.md) — durable decisions and gotchas.
- [ENVIRONMENT.md](./ENVIRONMENT.md) — toolchain and environment facts.
- [docs/architecture/2026-10-04-codebase-audit.md](./docs/architecture/2026-10-04-codebase-audit.md) — structural audit and the phased plan it drove.
