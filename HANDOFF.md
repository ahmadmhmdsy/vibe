# HANDOFF.md — agent-to-agent continuation guide

> Written for an agent resuming with fresh context on this machine
> (E:python_projectsapps_building). Read [PLAN.md](./PLAN.md) (the spec
> pointer) and the design spec first, then this.

## Current state (2026-09-29)

- Design spec approved and committed.
- Project scaffolded with the nano_SLMs-inspired doc system: CLAUDE.md
  (thin adapter), AGENTS.md (router), SOUL.md (identity), CURRENT_STATE.md
  (snapshot), ENVIRONMENT.md (stable policy), TASKS.md (live list),
  MEMORY.md (decisions + lessons), HANDOFF.md (this guide), rules/
  (conditional policy).
- **M1 core loop: PROVEN.** Full E2E verified 2026-09-29 using only
  `opencode-go/longcat-2.5-preview-free`: prompt → LLM tool calls → files
  generated → `pnpm run build` → dev server → app served (HTTP 200). Backend
  pytest 38/38 PASS. See MEMORY.md for the StructuredTool single-input-tool
  fix that unblocked the tool loop.
- **M1 gap (closed):** UsageTracker is now wired into the runtime
  (langgraph.py records usage_metadata per call) and exposed at
  GET /sessions/{sid}/usage. Budget enforced in the auto-run policy.
- **M2 — Sessions & models: DONE** (2026-09-29). Sessions sidebar (rename,
  model badge, last activity), model picker persists to session, provider
  settings (masked key status + custom provider CRUD, keys server-side only).
- **M3 — Polish: DONE** (2026-09-29). All six sub-features complete + tested:
  - a11y audit (WCAG 2.2 A/AA): keyboard-accessible session items, contrast
    fixes (≥4.5:1), form labels, redundant-role cleanup.
  - Supply-chain approval: allowlist (React/Vite/UI libs) + approval chat
    event with approve/deny; non-allowlisted installs pause for approval.
  - Token budgets: UsageTracker wired + per-session budget enforced in the
    auto-run loop; /usage endpoint + frontend UsageBadge.
  - Image input: attach reference designs (multimodal message); verified
    live (LLM described the attached image).
  - Monaco hand-editing: editable editor + file-sync endpoints
    (GET/PUT /sessions/{sid}/files); agent reads hand-edited files.
  - Full test coverage: backend 47 PASS, frontend 12 PASS, typecheck clean.
- **M5 — Frontend UI/UX overhaul: DONE** (2026-09-29). All 8 tasks from the
  critique snapshot executed sequentially, TDD, one commit per task:
  - Design system (tokens/global/components CSS) + UI primitives (Button,
    IconButton, Modal, ConfirmDialog, Spinner, EmptyState, ErrorBanner,
    Tooltip) — 13 tests.
  - App shell: 3-column layout, header with brand + theme toggle + Settings
    modal (Cmd+,), responsive breakpoints (1100px overlay, 768px drawer +
    tabs) — 4 tests.
  - Honest states: ApiError with status, error banners with retry, loading
    spinners, empty states, delete confirmation dialogs.
  - Chat: per-session store (messagesBySession — no more cross-session
    bleed), message history endpoint (GET /sessions/{sid}/messages from the
    EventLog), react-markdown rendering with copyable code blocks, auto-scroll,
    stop button.
  - Approvals: rich ApprovalCard with package chips, always-allow
    localStorage policy (auto-approves covered packages) — 6 tests.
  - Code panel: file list as aria-pressed buttons, detectLanguage for Monaco,
    Saving/Saved indicator.
  - Preview: real backend state via GET/POST /sessions/{sid}/preview[/run|
    /stop] + 2s polling store — 4 tests.
  - Polish: favicon.svg, title "vibe — local vibe-coding IDE", theme
    bootstrap script (no FOUC), header theme toggle.
  - Verification: 53 frontend tests PASS, typecheck clean, build clean,
    axe-core 0 violations on desktop (1440px) and mobile (390px).
- **Next: M4 — Scale** (Docker executor, Postgres, auth, deployment).

## Milestones

| Milestone | Goal | Status |
|---|---|---|
| M1 — Core loop | Single-session chat → generate → install → build → run → preview → auto-fix | **done** 2026-09-29 (E2E PASS) |
| M2 — Sessions & models | Multi-session, model picker, provider settings UI | **done** 2026-09-29 |
| M3 — Polish | Image input, Monaco editing, supply-chain approval, budgets, a11y, tests | **done** 2026-09-29 |
| M4 — Scale | Docker executor, Postgres, auth, deployment | pending |
| M5 — Frontend UI/UX overhaul | Design system, shell, honest states, chat, approvals, code, preview | **done** 2026-09-29 |

## Environment

- See [ENVIRONMENT.md](./ENVIRONMENT.md) for stable policy and machine
  profiles (Python 3.13.7, uv 0.11.22, Node 24.18.0, pnpm 12.3.4, Docker
  28.3.2).
- **Port 8000 is held by a foreign `httpd` (Apache)** — do not kill it.
  Run the backend on another port: `VIBE_PORT=8001` (Settings.from_env
  honors it) and start the frontend with
  `VITE_API_URL=http://localhost:8001`. CORS allows 5173/5174? — no: only
  `http://localhost:5173` and `http://127.0.0.1:5173`, so use port 5173
  for the dev server.

## Resume notes

- The design spec is the source truth:
  docs/superpowers/specs/2026-09-28-vibe-coding-app-design.md.
- The document map in AGENTS.md is the index — a doc outside it does not
  exist for the next agent.
- Git: scaffold commit 215ca70 on master; M5 commits 504be45..HEAD on top.
- 2026-09-28 incident: "New session" click did nothing — start.bat set
  `VITE_API_URL` with a trailing space (batch `set X=y &&` gotcha), so all
  API fetches failed URL parsing. Fixed start.bat (removed the space);
  verified end-to-end in the browser (click New → session appears). See
  MEMORY.md Lessons. The 404 in the console was the browser's favicon
  request to the Vite dev server — benign.
- M5 gotchas: (1) zustand v5 selectors that return fresh references
  (`?? []`) loop forever — use `useShallow`; (2) the edit tool rejects
  import-line changes — rewrite whole files instead; (3) vite's watcher
  crashes (EBUSY) when the write tool's temp files land inside the watched
  dir — keep scripts outside apps/vibe and restart vite after writes;
  (4) PowerShell eats `@e3` refs (splatting) — quote them or use CSS
  selectors; agent-browser relaunches its browser per pwsh call, so chain
  open+act+snapshot in one script.
