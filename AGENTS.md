# AGENTS.md — agent guide & document map

Any agent working in this repo works on the **Vibe Coding App** — a local-first
vibe-coding IDE where a user describes an app idea in chat and an agent builds it
as a multi-file React project. The repo hosts the React + TypeScript frontend under
`apps/vibe/` and the Python backend under `services/vibe/`; agent skills remain
under `.agents/skills/`.

[CLAUDE.md](./CLAUDE.md) is the **operating system** — read it first. This
file is the **repo supplement**: it maps every durable document to its job and
fixes the repo-specific conventions CLAUDE.md points here for.

## 1) Document map — one authoritative home per concern

| Concern | File | Read it when | Update it when |
|---|---|---|---|
| Operating rules | [CLAUDE.md](./CLAUDE.md) | every session | only for deliberate OS changes (rare) |
| Plan (the spec) | [PLAN.md](./PLAN.md) | before any feature/architecture work | only for user-approved spec changes |
| State (where we are) | [HANDOFF.md](./HANDOFF.md) | at session start | as milestones/incidents land — snapshot style, newest entries win |
| Tasks (what is next) | [TASKS.md](./TASKS.md) | at session start | whenever a task starts/finishes/gets gated |
| Memory (lessons & decisions) | [MEMORY.md](./MEMORY.md) | before touching anything non-obvious | every hard-won gotcha or user decision, immediately |
| Environment (what we run on) | [ENVIRONMENT.md](./ENVIRONMENT.md) | before running anything | after any tooling/version/disk change |
| Usage (humans) | [README.md](./README.md) | for command syntax | when commands or usage change |
| Design spec | [docs/superpowers/specs/2026-09-28-vibe-coding-app-design.md](./docs/superpowers/specs/2026-09-28-vibe-coding-app-design.md) | before any implementation work | only for user-approved spec changes |

A doc listed above that does not exist yet must be **created the moment its
concern becomes real** — the map is the index; a doc outside the map does not
exist for the next agent. When creating one, keep this table in sync.

Mnemonic:

    PLAN = what to build      HANDOFF = where we are      TASKS = what is next
    MEMORY = what we learned  ENVIRONMENT = what we run on

## 2) Repository layout

```
apps_building/
├─ AGENTS.md · CLAUDE.md            (this file + the OS; durable project docs at root)
├─ .agents/skills/                  installed agent skills (react-doctor · a11y-audit · etc.)
├─ apps/vibe/                       Vibe Coding App frontend (Vite + React + TypeScript)
│  ├─ src/                          app source: features/ · app/ · lib/ · components/
│  ├─ public/                       static assets served as-is
│  └─ index.html / vite.config.ts / tsconfig.json / package.json
├─ services/vibe/                   Vibe Coding App backend (FastAPI + LangGraph)
│  ├─ src/                          agent runtime, tools, providers, executor, sessions
│  └─ pyproject.toml / uv.lock
└─ docs/                            project documents + design spec
```

Update this layout section as real directories appear — stale entries are worse
than missing entries.

## 3) Commands

Fill in as the project is scaffolded (from `package.json` and `pyproject.toml`). Expected defaults:

```
<pkg-manager> install       # install deps (use the lockfile manager — never mix)
<pkg-manager> run dev       # dev server
<pkg-manager> run build     # production build (typecheck + bundle)
<pkg-manager> run lint      # eslint
<pkg-manager> run typecheck # tsc --noEmit (add this script if missing)
uv run pytest              # backend unit tests (once configured)
```

Rules:

- Never install, delete, or upgrade anything during inspection — installs happen only as part of a task that needs them.
- Report exactly which commands ran and their PASS/FAIL status; label unavailable checks SKIPPED with the reason.

## 4) Environment constraints (hard facts)

1. **Windows host.** Use native paths and, for shell work, PowerShell.
2. **Two package managers, one per ecosystem.** pnpm for the frontend (apps/vibe), uv for the Python backend (services/vibe). Never mix.
3. **Client secrets are public.** Everything bundled into the frontend (including `VITE_*` env vars) is readable by anyone — keep secrets server-side. LLM API keys live in the backend config only.
4. Node version must match `package.json` engines / `.nvmrc` once present; Python must match `pyproject.toml` requires-python. Do not upgrade runtimes unrequested.
5. Skills live in `.agents/skills/` — load a skill before acting on work that matches it (React code quality → react-doctor; animation → gsap-react; Clerk auth → clerk-react-patterns).

## 5) Git rules (summary)

- Standard flow: inspect status → preserve uncommitted user work → small, clean commits with clear messages.
- Never commit: `node_modules/`, `dist/`, real `.env`, OS/editor junk, generated workspaces.
- No force-push, no history rewrites, no branch deletion without explicit authorization.

## 6) Conventions

- Validation labels PASS / FAIL / SKIPPED / BLOCKED; honest reporting over optimistic claims (CLAUDE.md §10, §16).
- Task statuses `pending` / `in_progress` / `blocked` / `done` in the tasks doc; user-gated items say so explicitly.
- Keep dates machine-verifiable (git log) rather than vague.
- Component conventions (once code exists): function components + hooks, typed props, co-located styles, no new class components.

## 7) Keeping the map honest

- New durable knowledge → the memory doc. New work → the tasks doc. A new *kind* of document must be added to the map in §1 — the map is the index.
- HANDOFF and TASKS may describe the same next step: TASKS owns the live status, HANDOFF owns the narrative and evidence.
