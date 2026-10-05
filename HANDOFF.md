# HANDOFF.md — agent-to-agent continuation guide

> Written for an agent resuming with fresh context on this machine
> (E:python_projects/apps_building). Read [PLAN.md](./PLAN.md) (the spec
> pointer) and the design spec first, then this.

## Current state (2026-10-04)

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
- **CORS fix (commit 47edd56):** VIBE_CORS_ORIGINS env var for configurable
  dev-server origin allowlist (comma-separated).
- **Frontend overhaul (2026-09-30):** Complete frontend redesign with:
  - Expanded design tokens (colors, spacing, typography, motion, z-index)
  - CSS @layer system for predictable cascade
  - New UI primitives: Toast, Loading, ErrorBoundary, ShortcutsHelp,
    CommandPalette
  - New hooks: usePolling, useMediaQuery
  - New utilities: logger
  - Accessibility improvements: focus trap in Modal, visible labels,
    keyboard navigation
  - Feature enhancements: keyboard shortcuts guide, command palette,
    session search, export/import, drag-and-drop file upload, character count
  - Architecture improvements: decoupled stores, memoization, SSE exponential
    backoff, lazy loading
  - Documentation: ARCHITECTURE.md, COMPONENTS.md, DESIGN_SYSTEM.md,
    AGENT_GUIDE.md
  - Verification: 55 frontend tests PASS, typecheck clean, build clean
- **Frontend polish pass (2026-09-30, impeccable review → enhance → polish;
  identity kept — no redesign).** Measured in a live browser, not by eye:
  - **CSS layer inversion fixed.** `components.css` was imported before the
    `@layer reset, base, components, utilities;` statement, so base element
    rules beat every component rule: `.btn-primary` computed to
    `--bg-raised` and the app had **no visible primary action anywhere**.
    The statement now comes first in `global.css`.
  - **`.spinner` had no CSS rule at all** — every loading spinner was
    invisible (border-width 0, animation none). Authored in components.css.
  - **Mobile Code/Preview tabs were dead** (blank screen): the ≤768px block
    never undid the ≤1100px fixed/translated drawer. The ≤768px panel
    switching now resets `position/transform/visibility` and hides the
    inactive panel with a `[data-mobile-tab]`-qualified selector — the
    feature sheets are unlayered, so an equal-specificity rule loses.
  - **Drawers no longer swallow their own toggle** (header `z-index` +
    drawer `top: var(--header-height)`), and **Escape closes them**.
  - Density: session rows 108px → 44px with hover/focus-revealed actions;
    model picker 551px select → 172px, themed popup via `color-scheme`.
  - `usePolling` no longer dies after 3 failures (15s recovery cadence);
    contrast floor raised (`--text-faint` 4.12:1 → 5.1:1, light 2.85:1 →
    4.9:1); first-run `.chat-intro` state authored; fake "Import" control
    removed; Toast/ErrorBoundary/useMediaQuery wired up instead of dead.
  - axe-core: 2 violations found and fixed during the pass (empty `<h1>`
    at ≤430px, missing `main` landmark on mobile code/preview tabs) → **0
    violations** at 390px (chat/code/preview) and 1440px.
  - Verification: 63 frontend tests PASS, typecheck clean, build clean,
    mechanical detector clean. Evidence:
    [.impeccable/captures/2026-09-30-polish-verification.md](./.impeccable/captures/2026-09-30-polish-verification.md).
  - Open (needs a decision, backend line): `GET /sessions/{sid}/files`
    returns 3680 paths, 3667 under `node_modules`
    (`services/vibe/src/vibe/api/routes/sessions.py:77`).
- **Structural work — audit P0 + P1: DONE** (2026-10-04). The user asked for a
  clean/reusable/extensible structure plus an honest report of weaknesses; the
  first-hand audit is [docs/architecture/2026-10-04-codebase-audit.md](./docs/architecture/2026-10-04-codebase-audit.md)
  (5 high / 10 medium findings, 15 missing implementations, a hygiene list, a
  target structure, a 5-phase plan). The user then approved **"P0 + P1 together"**.
  - **P0 — portability & safety.** `Settings.__post_init__` now expands and
    resolves the workspace root once, and `from_env` uses
    `os.environ.get(...) or default` so an empty `VIBE_WORKSPACE_DIR` can no
    longer resolve to the process CWD. The literal-`~` data was merged into
    `C:\Users\AhmadMhmoud\vibe-workspaces` (23 dirs / 25 rows, backup
    `sessions.db.bak-20261004-182245`) by `services/vibe/scripts/merge_workspaces.py`
    — **the three original roots are intact and left for the user to delete.**
    `start.bat`/`test.bat` use `%~dp0`; `.gitignore` covers `~/` and
    `artifacts/`; six evidence files moved to `artifacts/`; root clutter
    archived to `archive/scratch/` (archived, not deleted). `Settings.host`
    (`VIBE_HOST`) was added and `__main__.py` rewritten with a `main()` so
    `python -m vibe` honours `VIBE_HOST`/`VIBE_PORT` and no longer builds the
    app at import time.
  - **P1 — lifecycle & integrity.** `EventLog` is sqlite-backed
    (`events.db`, WAL, `PRAGMA user_version`), so chat history survives a
    restart; `SessionStore` gained WAL + a `threading.Lock` +
    `asyncio.to_thread` + migrations. `lifecycle.py` owns the delete cascade:
    abort the run → stop the dev server → drop executor/policy/approvals/events
    → move the workspace to `.trash/` → delete the row **last** (so a failed
    move aborts the delete). The executor drains the dev-server pipe into a ring
    buffer, stops an existing server before starting a new one, and the app
    lifespan reaps idle servers and stops every executor on shutdown.
  - **Deliberate behaviour changes:** history persists across restarts;
    `DELETE` moves the workspace to `.trash/` instead of leaving it;
    dev servers stop on restart and after the idle timeout; `/health` returns
    the resolved paths. `read_console_logs` stays inert on purpose (Vite's
    startup banner would trip the autorun runtime-error check) and now documents
    why.
  - Verification: 98 backend tests, 22/22 live harness checks, 76 frontend
    tests, typecheck, build, plus an end-to-end run proving restart durability
    and the delete cascade against a live server — all PASS. Evidence:
    [artifacts/p0p1-pytest.txt](./artifacts/p0p1-pytest.txt),
    [p0p1-live.txt](./artifacts/p0p1-live.txt),
    [p0p1-e2e.txt](./artifacts/p0p1-e2e.txt),
    [p0p1-vitest.txt](./artifacts/p0p1-vitest.txt),
    [p0p1-typecheck.txt](./artifacts/p0p1-typecheck.txt),
    [p0p1-build.txt](./artifacts/p0p1-build.txt).
  - The audit's **P4 — product gaps: DONE** (2026-10-05), which completes all five
    phases. Titles, pagination, the error taxonomy and the M6 honesty fix are in,
    and the README's false capability claims are corrected. Still
    `NEEDS_USER_DECISION`: a browser driver for real console/screenshot
    capture, and any auth story beyond loopback. See the P4 entry below.
- **Next: M4 — Scale** (Docker executor, Postgres, auth, deployment).

## Milestones

| Milestone | Goal | Status |
|---|---|---|
| M1 — Core loop | Single-session chat → generate → install → build → run → preview → auto-fix | **done** 2026-09-29 (E2E PASS) |
| M2 — Sessions & models | Multi-session, model picker, provider settings UI | **done** 2026-09-29 |
| M3 — Polish | Image input, Monaco editing, supply-chain approval, budgets, a11y, tests | **done** 2026-09-29 |
| M4 — Scale | Docker executor, Postgres, auth, deployment | pending |
| M5 — Frontend UI/UX overhaul | Design system, shell, honest states, chat, approvals, code, preview | **done** 2026-09-29 |
| Frontend overhaul | Complete redesign with tokens, layers, new components, docs | **done** 2026-09-30 |
| Bridge fixes | SSE fan-out + monotonic seq, real Stop/abort, provider PATCH field names, usage by_model, session-id 404s, workspace prune, path encoding, message ids | **done** 2026-10-04 |
| Codebase audit | First-hand audit of structure/reusability/extensibility + a 5-phase plan | **done** 2026-10-04 |
| Audit P0 + P1 | Portability & safety (resolved workspace root, data migration, `%~dp0`, hygiene) + lifecycle & integrity (sqlite events, delete cascade, pipe drain, idle reaper, WAL/lock/to_thread, migrations) | **done** 2026-10-04 |
| Audit P2 — Seams | Container + Depends, provider registry, EventStore protocol, `vibe/services/` | **done** 2026-10-05 |
| Audit P3 — Developer experience | Logging, ruff + eslint + prettier config, `vitest run` default, CI | **done** 2026-10-04 |
| Audit P4 — Product gaps | Auto-titles from the first message, pagination + `X-Total-Count`, a stable error taxonomy, the M6 honesty fix, README corrected | **done** 2026-10-05 |
| Audit P5 — The browser driver | Playwright console capture + screenshots that reach the model; the `ToolResult`→`repr()` defect fixed; the pnpm `--`/Vite-5173 port bug fixed | **done** 2026-10-05 |
| Audit P3a — Root workspace | One root `package.json` + `pnpm-workspace.yaml`; unified scripts for the frontend workspace and the Python backend | **done** 2026-10-05 |
| Audit P6 — Loopback auth | Machine-level deny-by-default + `OriginGuard` (CSRF); the `Authenticator` seam | **done** 2026-10-05 |

## Environment

- See [ENVIRONMENT.md](./ENVIRONMENT.md) for stable policy and machine
  profiles (Python 3.13.7, uv 0.11.22, Node 24.18.0, pnpm 12.3.4, Docker
  28.3.2).
- **Port 8000 is held by a foreign `httpd` (Apache)** — do not kill it.
  Run the backend on another port: `VIBE_PORT=7321` (Settings.from_env
  honors it) and start the frontend with
  `VITE_API_URL=http://localhost:7321`. CORS allows the origins in
  VIBE_CORS_ORIGINS (default: http://localhost:5173,http://127.0.0.1:5173).

## Resume notes

- The design spec is the source truth:
  docs/superpowers/specs/2026-09-28-vibe-coding-app-design.md.
- The document map in AGENTS.md is the index — a doc outside it does not
  exist for the next agent.
- Git: scaffold commit 215ca70 on master; M5 commits 504be45..47edd56 on top.
- 2026-09-28 incident: "New session" click did nothing — start.bat set
  `VITE_API_URL` with a trailing space (batch `set X=y &&` gotcha), so all
  API fetches failed URL parsing. Fixed start.bat (removed the space);
  verified end-to-end in the browser (click New → session appears). See
  MEMORY.md Lessons. The 404 in the console was the browser's favicon
  request to the Vite dev server — benign.
- 2026-09-30 incident: user reported "typed in the chat input, got no
  response from the agent". Bridge audit (all 24 frontend API calls + the SSE
  stream, verified live against the running backend + in a real browser):
  the backend was healthy — every endpoint answered, the agent ran, and the
  reply was persisted. The break was in the frontend SSE client:
  `SSEClient.parse` matched `data: (.+)\n\n`, but
  `EventSource.onmessage` delivers `msg.data` with the `data: ` prefix
  and trailing blank line already stripped — so parse matched nothing,
  returned null, and every event (text_chunk, turn_complete) was silently
  dropped. The send POST succeeded, so no error ever surfaced. Fix: fall
  back to the raw string when the frame regex misses + try/catch around
  JSON.parse; 2 regression tests (parse with the onmessage shape, and the
  full connect→onmessage→onEvent wiring). Verified live in the browser:
  assistant reply renders as it streams. See MEMORY.md Lessons.
  **Least steps if it ever recurs:** (1) GET /sessions/{sid}/messages —
  reply present ⇒ backend healthy, break is the frontend SSE path;
  (2) console shows no error — the drop is silent by design;
  (3) fix SSEClient.parse (apps/vibe/src/lib/sse.ts) to accept the
  onmessage shape: 'const json = match ? match[1] : raw;' + try/catch;
  (4) cd apps/vibe && pnpm vitest run src/lib/__tests__/sse.test.ts;
  (5) browser-check: send a message, assert a .message-assistant
  node with the reply appears.
- 2026-10-04 bridge-fix session: a third-party review of the
  frontend↔backend seam was checked claim-by-claim against the code, then all
  findings (plus defects the review missed) were fixed. What actually changed:
  `EventBus` now fans out to one queue **per subscriber** instead of a single
  shared queue per session; ephemeral frames (`text_chunk`, `turn_complete`)
  take a real monotonic seq from `EventLog.next_seq` while staying out of the
  log; the SSE route subscribes **before** replaying and skips live events the
  replay already sent; the client only advances `lastSeq` on a strictly
  greater seq; Stop is a real `asyncio.Task` cancel via
  `POST /sessions/{sid}/abort`; provider `PATCH` accepts camelCase **and**
  snake_case (a snake_case-only filter silently dropped every field the UI
  sent while returning 200); `/usage` returns a real `by_model` breakdown
  and cache-write tokens (both were stubbed); unknown session ids are 404
  except idempotent `DELETE`; one shared workspace walk prunes
  `node_modules`/dist/.venv for the HTTP route, the chat file snapshot, and
  the `list_files` tool; file paths are per-segment URL-encoded; chat
  messages carry stable ids and each turn streams into its own message.
  Validation: 75 backend tests, 76 frontend tests, typecheck, build, and a
  **live** ASGI/SSE run (two subscribers + a real abort) — all PASS. Evidence:
  artifacts/pytest-after.txt, artifacts/live-verification.txt,
  artifacts/vitest-after.txt, artifacts/typecheck.txt, artifacts/build.txt.
  The live harness is reusable and needs no LLM:
  services/vibe/tests/live/{server,live}.py.
  Deliberate behavior changes to know about: a second concurrent
  `POST /messages` on a live session returns 409; SSE dedupes by seq; a
  non-integer `after_seq` is 400 (was 500); unknown ids 404 (was empty 200).
  Known limitation: on a failed send the composer still restores the text
  *and* history now records `assistant/error`, so the failure is visible
  twice, and the in-memory transcript keeps the user message until a reload.
- 2026-10-04 structural audit (first-hand; every claim carries file:line):
  docs/architecture/2026-10-04-codebase-audit.md. Headline: the code is small and
  well-factored, but it is a prototype wearing production clothes, and three things
  make it one-time-use — (1) chat history lives only in RAM (`events.py:24`,
  derived at `messages.py:25`), so a restart empties every conversation while the
  session list survives; (2) `VIBE_WORKSPACE_DIR=~/vibe-workspaces` is never
  expanded (`config.py:53`), so real data — 18 sessions, `sessions.db`,
  `providers.json` — sits in a literal `services/vibe/~/vibe-workspaces/`
  resolved against the process CWD, and a clone or a different launch directory
  silently presents an empty install; (3) deleting a session orphans its
  workspace, executor, dev server and events (`store.py:67`, `sessions.py:88`).
  Also found: three provider modules that no production code instantiates
  (`providers/{openai_chat,anthropic,openai_responses}.py` — only a test imports
  `providers/base.py`) while `api/app.py:22-70` builds LangChain models inline;
  zero logging in the backend; no linter, formatter or CI anywhere; a dev-server
  spawn that never drains its stdout pipe and overwrites its handle
  (`executor/local.py:50-56`); two documented env knobs that do nothing
  (`VIBE_DEV_SERVER_IDLE_TIMEOUT_MIN` parsed but never consumed,
  `VIBE_HOST` not even a Settings field) and `__main__.py:8` hard-coding
  host+port so `python -m vibe` ignores `VIBE_PORT`; stubbed console-log and
  screenshot reads that make the autorun runtime-error loop inert and make
  `README.md:12-13` false; and absolute `E:\python_projects\...` paths baked
  into `start.bat`/`test.bat`. Phased plan (P0 portability, P1 lifecycle,
  P2 seams, P3 DX, P4 product gaps) is in §8. **Superseded 2026-10-04:** the user
  approved "P0 + P1 together" and both are done — see the Current state entry
  above and the status block in the audit. P3 and P2 are done too (below). P4
  is still open.
- 2026-10-04 P0+P1 session — things worth knowing before you touch this area:
  (1) the workspace root is resolved **once** in `Settings.__post_init__`; never
  build a workspace path anywhere else. (2) `C:\Users\AhmadMhmoud\vibe-workspaces`
  is the live root (25 sessions, `sessions.db`, `events.db`); the three old
  literal-`~` roots are **still on disk and must be deleted by the user**, not by
  an agent. (3) `DELETE /sessions/{sid}` now moves the workspace to
  `<workspace_dir>/.trash/<sid>-<stamp>/` and deletes the row last — the order is
  load-bearing on Windows (open handles block a directory rename), so do not
  "tidy" it. (4) `events.db` is why chat history survives a restart; if a
  conversation looks empty, check the SSE route's `after_seq` before suspecting
  the store. (5) `read_console_logs` returning `""` is deliberate — see its
  docstring before "fixing" it. (6) To test an infinite SSE endpoint, drive the
  route function directly (as `test_sse.py` does); `TestClient.stream` hangs.
  Verification: `artifacts/p0p1-{pytest,live,e2e,vitest,typecheck,build}.*`.
- 2026-10-04 P3 session (developer experience). What changed:
  (1) **Logging — the last silent subsystem.** New
  `vibe/logging_setup.py`: one stderr `StreamHandler` on the `vibe` logger,
  `propagate=False`, idempotent, level from `VIBE_LOG_LEVEL` (default INFO,
  unknown names fall back instead of raising). Library modules only call
  `getLogger(__name__)`; `__main__` configures. `create_app` configures too,
  but **only if nobody has** — `start.bat` mounts the app through
  `uvicorn --factory`, which never runs `__main__`. The reaper's bare
  `except Exception: pass` now logs a warning with `exc_info`.
  (2) **ruff** (0.16.10, dev extra) with E/F/W/I/UP/B/C4/SIM/RUF; **136
  findings fixed**, 118 auto and 18 by hand — the hand-fixed ones were real:
  `B904` bare `raise` in an `except` (lost the cause), `SIM105`, `B905`
  `zip` without `strict`, an `F841` dead assignment, and 9 `E701` one-liners.
  (3) **eslint 10 flat config** + **prettier 3.9.9** config; 23 baseline
  problems reduced to 0 errors / 14 warnings. (4) `pnpm test` is now
  `vitest run`; `test:watch` added; `packageManager` pinned to pnpm 12.3.4.
  (5) `.github/workflows/ci.yml` — backend (ruff+pytest) and frontend
  (eslint+tsc+vitest+build) on windows-latest.
  **Things worth knowing before you touch this area:** the 14 remaining
  eslint warnings are NOT noise and NOT fixed on purpose — 2
  `react-hooks/refs` and 5 `react-hooks/set-state-in-effect` are real
  React-Compiler-era findings that need behaviour-affecting refactors
  (`useSyncExternalStore` for `useMediaQuery` is the clean one); they are
  downgraded to `warn` in `apps/vibe/eslint.config.js` with the reason
  written there. `prettier --check` reports **37 files** and was deliberately
  NOT applied — the tree is full of uncommitted work and reformatting it
  would bury it; run `pnpm run format` only after a commit, and that is why
  `format:check` is not in CI. The **root-workspace restructure** is also
  still open on purpose: adding a root `package.json` changes pnpm
  resolution for `apps/vibe` and can break a working install, so it needs
  the user's call. Note `apps/vibe/pnpm-workspace.yaml` is pnpm 12's
  *settings* file (`allowBuilds`), not a stray workspace definition.
  Validation: backend 107 pytest + ruff clean; frontend 76 vitest + eslint
  (0 errors) + typecheck + build; live ASGI/SSE harness PASS; `test.bat`
  green end to end. Evidence:
  `artifacts/p3-{pytest,ruff,live,logging,eslint,vitest,typecheck,build,test-bat,prettier-check}.txt`.
- 2026-10-05 P2 session (seams). What changed:
  (1) **Container + Depends.** New `vibe/container.py`: one frozen `Container` dataclass with `Container.build(settings, **overrides)`. `create_app(settings, *, container=None)` builds it (or takes a pre-built one) and assigns it to `app.state.container` — the only `app.state` write left. Routes declare `deps: App` where `App = Annotated[Container, Depends(get_container)]`, so what a route needs is in its signature. `app.state.container` stays reassignable, so a test swaps a seam whole with `dataclasses.replace` (`tests/conftest.py`: `swap()`).
  (2) **Provider registry.** `providers/registry.py` — `build_llm_factory(settings, custom_store)` returns the one `LlmFactory`. The three provider classes were **deleted**: they were dead (only `tests/test_providers.py` touched them) and broken (`ChatOpenAI(api_key=..., base_url=..., streaming=True)` with no `model=`; `openai_responses.py` claimed `/v1/responses` while building `ChatOpenAI`). Deletion is git-recoverable.
  (3) **EventStore protocol.** `vibe/events.py` declares the capability (`next_seq`/`append`/`get`/`last_seq`/`clear`/`close`); `runtime/base.py`, `usage/tracker.py` and `api/app.py` are typed against it rather than against `EventLog`. `tests/test_events.py` proves a fake store can stand in.
  (4) **`vibe/services/`.** `SessionService` (create/list/rename/set_model/delete + workspace path confinement) and `MessageService` (history projection). Path confinement and the `_MESSAGE_TYPES` projection used to live in the route handlers, so neither was testable without a FastAPI app. `tests/test_services.py` covers both, including symlink escape.
  **Things worth knowing before you touch this area:** (1) `Container.build` applies overrides *before* deriving anything, and rejects unknown names — a typo in an override raises `TypeError` rather than silently leaving the real seam in place. (2) The container is frozen; assign to a field and you get `FrozenInstanceError`. Swap the container, never a field. (3) `require_session` in `api/deps.py` takes the container, not the request — it is a pure function of the session store. (4) `Container.build` mkdirs the workspace root because `SessionStore` opens sqlite there eagerly. (5) **`require_session` is a reconstruction.** An agent error destroyed the user's uncommitted version mid-refactor and it was not in git (HEAD has a 0-byte `deps.py`); it was rebuilt from its 14 call sites and is not byte-identical to the lost original. (6) `ChatEvent`/`ChatRequest` in `models.py` are now referenced only by tests.
  Validation: backend 136 pytest + ruff clean; frontend 76 vitest + eslint (0 errors / 14 warnings) + typecheck + build; live ASGI/SSE harness 22 PASS / 0 FAIL. Evidence: `artifacts/p2-{pytest,ruff,live,vitest,typecheck,build,eslint}.txt`.
- 2026-10-05 P4 session (product gaps — the audit's final phase). What changed:
  (1) **Session titles from the first message.** `store.title_from_text` +
  `SessionStore.retitle_from_message` + `SessionService.retitle_from_message`;
  `POST /messages` calls it after appending the user message. It only fires while
  the title is still the `Untitled xxxx` placeholder, so a manual rename is never
  clobbered and a blank message cannot blank the title.
  (2) **Pagination.** `MessageService.page` returns a frozen `MessagePage` ("messages", "total", "offset", "limit", "has_more");
  `history` is a thin wrapper over it. `GET /sessions/{sid}/messages` takes `limit`
  (1-1000, default 200) and `offset` (counts back from the newest) and reports the real total in
  `X-Total-Count`, which CORS now exposes. The frontend reads the total, offers a
  "Load older messages" button and prepends older pages — and the auto-scroll effect is
  keyed on the *last* message rather than the list length, so loading older history no
  longer yanks the view to the bottom.
  (3) **Error taxonomy.** New `vibe/api/errors.py`: `ErrorCode` (StrEnum) +
  `ApiError(code, message, *, status=None)` with a default-status map, so a call site
  states only the code. Four exception handlers on the app give every error the same
  `{"error": {"code", "message"}}` body. Every `raise HTTPException(...)` / `raise ValueError(...)` site in the
  routes now raises `ApiError`. The frontend's `ApiError` carries `code` and surfaces it.
  (4) **M6 — the autorun loop no longer lies about what it checks.**
  `read_console_logs`/`screenshot` return `None` ("no driver"), never `""` ("clean");
  `AutoRunPolicy` treats `None` as *nothing was read*; the agent-facing tools answer
  "unavailable: this build has no browser driver installed" instead of reporting an empty console.
  (5) **README corrected.** The claims that the agent "can read console logs and take
  screenshots" and that "build/runtime errors are fed back" were false — only build errors
  are. A **Known gaps** section now states that plainly, records the
  unauthenticated-by-design decision, and notes that a stored API key cannot be
  cleared from the UI. The port-7321 pinning was replaced with what `start.bat`
  actually does (auto-increments, then hands the port to `VITE_API_URL`).
  **Bug found and fixed along the way:** `req<void>` called `resp.json()` on a 204
  with an empty body, so `api.deleteSession`/`api.deleteProvider` always threw a
  `SyntaxError` *after* the server had done the delete — and because
  `features/sessions/store.ts` has no try/catch around it, deleting a session never
  refreshed the sidebar. Fixed with `readBody()`, which returns `undefined` for 204/205.
  **Things worth knowing:** (1) `events.py:47` was audited and is **not** a defect —
  `sse.ts` already sends `after_seq` and only advances on a strictly newer seq, so
  the replay is already incremental; only `messages.py` needed pagination.
  (2) A query-constraint violation is **422**, not 400 — FastAPI's default. The code
  is `validation_failed` either way. (3) `DELETE` returning 204 means a client must
  branch on status before parsing a body.
  Validation: backend 161 pytest + ruff clean; frontend 86 vitest + eslint
  (0 errors / 14 warnings) + typecheck + build; live ASGI/SSE harness 22 PASS /
  0 FAIL; a 13-check live probe over the new behaviours (error shape, auto-titling,
  pagination, `X-Total-Count`) 13 PASS / 0 FAIL. Evidence:
  `artifacts/p4-{pytest,ruff,live,live-probe,vitest,typecheck,build,eslint}.txt`.
- 2026-10-05 P5 session (the browser driver — the user chose "A. Implement
  Playwright"). What changed:
  (1) **`vibe/executor/browser.py`** owns the Playwright lifecycle: lazy launch,
    a TCP readiness wait before every capture, `console`/`pageerror` listeners
    attached *before* `page.goto`, level filtering (`error` default, `warning`,
    `all`), real PNG screenshots, and an idempotent `close()`. Every method
    returns `None` when Playwright or the browser binary is missing, so a
    machine without a browser still runs — it just cannot see the app.
    `VIBE_BROWSER_HEADLESS=0` opens a visible window.
  (2) **The `ToolResult` → `repr()` defect, which affected every tool call.** A
    dataclass returned from a LangChain tool is stringified into
    `ToolMessage.content`, so the model was reading
    `"ToolResult(content='...', name='...', ...)"` instead of the answer.
    Fixed with `response_format="content_and_artifact"` plus a list of content
    blocks: text for the answer, `image_url` for attachments. The tuple's second
    element lands in `ToolMessage.artifact`, a channel the model never sees — so
    `is_error` now propagates to the event stream too, and the SSE payload joins
    only `type=="text"` blocks so no base64 reaches the browser.
  (3) **A real bug found while verifying: pnpm 12 forwards `--` literally.**
    `pnpm run dev -- --port 57180` reached Vite as `vite "--" "--port" "57180"`,
    Vite did not recognise `--port` after a bare `--`, and **fell back to 5173** —
    so every session collided on the default port and `dev_server_url` named a
    port nothing was listening on. The `--` is gone. The dev-server test now
    asserts something is *listening* on `handle.port`, not merely that the port
    is positive — that assertion is what lets this class of bug through.
  **Things worth knowing:** (1) `playwright install chromium` is required after
  `uv add playwright`; CI gained a step for it. (2) The scaffolded test project
  in `test_executor.py` declares no `vite` dependency, so `install([])` succeeds
  offline and the test cannot prove a real install works — it is guarded by a
  `pnpm ping` network check instead. (3) The idle reaper stops dev servers but
  deliberately does **not** close browsers; a browser is closed on session delete
  and on app shutdown. (4) Verified against a deterministic `http.server` rather
  than a scaffolded Vite project, because the scaffold cannot install its own
  dependencies in this environment.
  Validation: backend 177 pytest + ruff clean; frontend 86 vitest + eslint
  (0 errors / 14 warnings) + typecheck + build. Evidence:
  `artifacts/p5-{pytest,ruff,browser}.txt`.
- 2026-10-05 P6 session (loopback auth — the user approved the recommendation:
  single-user, single-machine, local now, reusable later). What changed:
  (1) **`vibe/auth.py`** — `Principal` (frozen dataclass), an `Authenticator`
      protocol, and `LoopbackAuthenticator`, which accepts a request only when
      `request.client` is unset (in-process ASGI) or its host is `127.0.0.1`,
      `::1`, `localhost`, or `testclient` (the Starlette `TestClient` marker).
      It authenticates the *machine*, not a user: `Principal.id` is always
      `"local"`.
  (2) **Router-level deny-by-default.** `require_principal` in `api/deps.py`
      calls the authenticator and raises `ApiError(UNAUTHENTICATED)` on `None`.
      All seven routers are mounted with `dependencies=[Depends(require_principal)]`,
      so a route added tomorrow is protected without remembering to ask.
      `/health` stays open — it is a direct `@app.get`, not part of a router.
  (3) **`OriginGuard` — a second, independent control.** Loopback auth cannot
      catch CSRF, because a cross-site POST from the user's own browser arrives
      from `127.0.0.1`. The guard refuses state-changing methods whose `Origin`
      is not in `VIBE_CORS_ORIGINS` with `403 forbidden_origin`. A missing
      `Origin` is allowed (loopback auth already gated it); GET is not checked.
  (4) **The seam.** `Container.build(authenticator=...)` and
      `Settings.auth_mode` / `VIBE_AUTH_MODE`. An unknown mode raises `ValueError`
      rather than falling back to loopback — a typo that silently downgraded to
      the permissive option would be a vulnerability with a green suite.
  **Deliberately out of scope, with rationale:** no token (an auto-generated
  token injected into the frontend bundle is security theatre and breaks
  `start.bat`); no users or ownership — multi-user later means an `owner_id` on
  sessions plus an ownership check in `require_session` and a filtered
  `SessionStore.list`. The `Authenticator` protocol is the drop-in point.
  **Things worth knowing:** (1) `TestClient` reports `client.host == "testclient"`,
  so the allowlist must include it or every existing test starts failing with a
  401. (2) `TestClient(app, client=("10.0.0.1", 1234))` simulates a non-loopback
  peer, which is how the refusal is tested. (3) The guard is added *before*
  `CORSMiddleware` so the browser still sees CORS headers on a 403.
  Validation: backend 190 pytest + ruff clean; frontend 86 vitest + eslint
  (0 errors / 14 warnings) + typecheck; a 5-check live probe over a real socket
  (health open, local GET 200, allowed Origin 201, no Origin 201, foreign
  Origin 403) 5 PASS / 0 FAIL. Evidence:
  `artifacts/p6-{pytest,ruff,vitest,typecheck,eslint}.txt`.
- 2026-10-05 P3a session (root workspace + unified scripts — the user said
  "start P3a, P3b and P3c"). A root `package.json` (private, `packageManager`
  pin, unified scripts) and a root `pnpm-workspace.yaml`
  (`packages: ["apps/*"]`) now own the install; the `allowBuilds: esbuild`
  setting moved up from `apps/vibe/pnpm-workspace.yaml`, which is gone (two
  workspace roots would fight). One `pnpm install` at the root covers the
  workspace, and `pnpm --filter vibe {dev,build,test,typecheck,lint,format}`
  run inside `apps/vibe` while `pnpm test:backend` / `pnpm lint:backend`
  reach the Python venv. **Gotcha:** pnpm runs scripts through `cmd`, so the
  backend scripts need a leading `.\` — a bare `.venv\Scripts\python.exe` is
  parsed as the `.` source command and fails with "'.venv' is not
  recognized". **Verified:** install 364 packages; build PASS; 86 vitest;
  typecheck; eslint 0 errors / 14 warnings; 190 pytest; ruff clean. Evidence:
  `artifacts/p3a-all.txt`.
- M5 gotchas: (1) zustand v5 selectors that return fresh references
  (`?? []`) loop forever — use `useShallow`; (2) the edit tool rejects
  import-line changes — rewrite whole files instead; (3) vite's watcher
  crashes (EBUSY) when the write tool's temp files land inside the watched
  dir — keep scripts outside apps/vibe and restart vite after writes;
  (4) PowerShell eats `@e3` refs (splatting) — quote them or use CSS
  selectors; agent-browser relaunches its browser per pwsh call, so chain
  open+act+snapshot in one script.
- Frontend overhaul gotchas: (1) Windows file locking can cause EIO errors
  when writing files — use PowerShell Set-Content as fallback; (2) CSS @layer
  order matters — reset → base → components → utilities; (3) React.memo with
  forwardRef requires careful prop typing; (4) lazy loading with Suspense
  needs proper fallback UI.
- Backend tests: `cd services/vibe && .venv/Scripts/python.exe -m pytest -q`.
  `uv run pytest` works again now that PyPI is reachable (2026-10-04), but
  the venv path is faster and needs no resolution step.
- Frontend tests: `cd apps/vibe && pnpm test`. As of 2026-10-04 `pnpm test`
  IS `vitest run` — a single pass that exits. Watch mode is
  `pnpm run test:watch`. Never write `pnpm test -- --run`: pnpm 12 forwards
  the `--` and the extra flag reaches vitest.
- Lint: backend `.venv/Scripts/python.exe -m ruff check .`; frontend
  `pnpm run lint`. Errors must be zero before calling anything done.
- Frontend docs: See `docs/frontend/` for ARCHITECTURE.md, COMPONENTS.md,
  DESIGN_SYSTEM.md, and AGENT_GUIDE.md.
