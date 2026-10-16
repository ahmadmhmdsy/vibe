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
| M4 — Scale | Docker executor, Postgres, auth, deployment | **deferred** — local-first; the seams are kept (see M6) |
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
| Audit P3b — Prettier sweep | 37 files reformatted (whitespace only); `format:check` added to the frontend CI job | **done** 2026-10-05 |
| Audit P6 — Loopback auth | Machine-level deny-by-default + `OriginGuard` (CSRF); the `Authenticator` seam | **done** 2026-10-05 |
| Full app review | Independent review of backend, frontend, and docs/CI/tests: 48 findings, raw evidence, re-runnable probes | **done** 2026-10-11 — `docs/reviews/2026-10-11-full-app-review/FINDINGS.md` |
| Hardening R0 — Truth and bookkeeping | Every planning/task/memory/snapshot document matches the tree; the one red check goes green | **done** 2026-10-11 — `artifacts/hardening-r0-docs.txt` |
| Hardening R1 — Correctness under concurrency and cancellation | Atomic run claim, whole-process-tree kill on timeout and abort, session-delete ordering; probes 4, 5 and 7 promoted to permanent tests | **done** 2026-10-11 — `artifacts/hardening-r1-pytest.txt` |
| Hardening R2 — Validation and secrets | Typed request bodies (400 `validation_failed`), allowlist specifier bypass closed, durable locked provider store | **done** 2026-10-11 — `artifacts/hardening-r2-pytest.txt` |
| Hardening R3 — Product completeness | Conversation history, auto-fix turns logged and streamed, the formattable VIBE_HOST warning, a configurable system prompt with a read-only settings route, honest browser-driver messages, session timestamps and a generic 500 + error id, `.trash` retention, and a measured event-log index | **done** 2026-10-11 — `artifacts/hardening-r3b-report.txt` |
| Hardening R4 — Frontend trust and UX | Swallowed errors surfaced everywhere (SSE status, per-file read, failed actions), root error boundary, platform-aware shortcuts | **done** 2026-10-11 — `artifacts/hardening-r4-followup.txt` |
| Hardening R5-T1 — Preflight doctor | `python -m vibe doctor` and `doctor.bat`: ten checks, six blocking, every failure naming its exact remedy | **done** 2026-10-11 — `artifacts/hardening-r5-doctor.txt` |
| Hardening R5-T7 — Backup and repair | `vibe backup` / `vibe repair`: timestamped snapshots with a manifest, real restore, integrity check, quarantine of a corrupt store, pruned only by our own timestamp pattern | **done** 2026-10-11 — `artifacts/hardening-r5-backup.txt` |
| M6 — Local production readiness | One-command local install and run, production serving mode, first-run guidance, retention and recovery, honest states | **in progress** — hardening program R0–R7; plan `docs/superpowers/plans/2026-10-11-local-production-hardening.md` |
| M8 — Competitor parity & expansion | Import a project, Git, checkpoints, plan-before-build, generated-app persistence, quick wins (local models, MCP, code scan) — each as a seam | **in progress** 2026-10-16 — user-gated; plan `docs/superpowers/plans/2026-10-16-competitor-parity.md`, research `docs/research/2026-10-16-competitive-analysis.md`. **C1 backend landed**: `vibe/projects.py` (seam + `EmptyWorkspaceSource`/`ViteReactTsTemplate`/`LocalFolderSource`/`GitRepoSource`), store schema v3 (`workspace_path`), lifecycle refuses to trash an in-place import, `POST /sessions` takes a `source`. **C1 UI landed**: `NewSessionDialog` (kind chooser + folder path / repo URL) wired through `createSession(model, source)`. Remaining: `AI_RULES.md` for imports, `describe()` in the composer |
| Hardening R5 — packaging, lifecycle, offline truth (T2, T3, T6, T8, T9) | `start.bat`/`stop.bat` around one port and one window; the built SPA served by FastAPI in prod mode; a graceful `POST /admin/shutdown` behind the loopback principal; an npm-registry probe whose message says nothing was downloaded; dev servers left by a previous run reaped at startup | **done** 2026-10-11 — T5/T4's agent: `artifacts/hardening-r5-lifecycle.txt`, `artifacts/hardening-r5-offline.txt` |
| Hardening R5-T4/T5 — a first run that explains itself, and a log you can send | A first-run panel that opens Settings and can fill the composer; a rotating log under the workspace (2 MiB x 5) with settings redaction and a startup banner, activated at the real entry point | **done** 2026-10-11 — 13 new frontend tests (153 passed) and 23 log tests; `artifacts/hardening-r5-logs-firstrun.txt` |
| Hardening R6 — scalability seams | All eight guardrails (L-1..L-8): `owner_id` on every persisted row with additive, idempotent migrations; SQL only in the store providers; registries keyed by (owner, session); `config.py` the only environment reader; migrations the only schema writer | **done** 2026-10-11 — 433 passed after R6, and the L-6 gate closed by the orchestrator with `_ENV_EXEMPTIONS` empty; `artifacts/hardening-r6-guardrails.txt`, `artifacts/hardening-r6-gate-closure.txt` |
| Hardening R7 — acceptance run | `scripts/acceptance-local.ps1` steps 1-7 against a temp workspace with the user's own provider; found BE-20 (`DELETE` answered 500 while a preview held the workspace) and the fix landed with regression tests | **in progress** 2026-10-11 — the real e2e built an 11-file app and served its preview; the script's own run 9 (21:38:04) is `RESULT: PASS` on 0 FAIL/BLOCKED with step 6a and 6b green; found **BE-21** while looking for the traceback of an unexplained 500 (the log file did not exist), fixed with a regression test; `artifacts/acceptance-local.txt`, `artifacts/hardening-r7-delete-busy.txt`, `artifacts/hardening-r7-log-default.txt` |

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
- 2026-10-05 P3b session (the prettier sweep — the user said "start P3a, P3b
  and P3c"). `pnpm format` reformatted 37 files: 595 insertions, 184
  deletions, all whitespace/line-width (no semantic change). `format:check`
  now passes and was added to the frontend CI job, so a drift fails CI
  instead of accumulating. **Gotcha:** a `format:check` run immediately after
  `--write` in the same script reported one file still unformatted; a second
  check passed. Prettier's write and check disagree across a process boundary
  here — verify with a standalone `format:check`, not back-to-back in one
  script. **Verified:** 86 vitest, typecheck, build, eslint 0 errors / 14
  warnings all still PASS. Evidence: `artifacts/p3b-before.txt`,
  `artifacts/p3b-after.txt`, `artifacts/p3b-verify.txt`.
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
- 2026-10-16 competitive research + parity plan. A net search against the closest
  competitors (Dyad is the direct peer — same local-first pitch, and currently
  *ahead* of us; plus bolt.diy, Onlook, Lovable, Bolt, Replit, Cursor) is captured
  in `docs/research/2026-10-16-competitive-analysis.md`, with our moat (the
  append-only event log as source of truth, the install approval gate, fully-local
  no-account) and the 14 gaps they ship that we do not. The follow-on plan
  `docs/superpowers/plans/2026-10-16-competitor-parity.md` (milestone **M8**) turns
  the top five into phases C1–C6, each as a **seam** (Definition/Provider/Consumer).
  **User-gated and not started.** The user's governing constraint: never write code
  for one-time use — this is a package that expands, so it stays clean/easy/structured.
  Registered as `docs/research/` in the AGENTS.md document map.

## Review and hardening program (2026-10-11)

**The review.** A full, first-hand review of the app — backend, frontend, and
docs/CI/tests — landed as `docs/reviews/2026-10-11-full-app-review/` (register
`FINDINGS.md`, detail in `01`–`04`, `probes/`, `evidence/`). It recorded **41
findings** (18 backend, 15 frontend, 8 docs/CI/tests; 4 High, 12 Medium, 20 Low,
2 Low/Info, 3 Info) and changed no application code. Every finding carries a
file:line anchor and a reproduction, and the two probes are re-runnable against
temporary directories only. The four High findings are the ones to read first:
**BE-04** (the one-run-per-session guard is not atomic — two sends both run),
**BE-02** (the supply-chain allowlist is bypassed by an alias specifier such as
`react@npm:evil-package`), **BE-03** (no conversation memory: only the newest
message reaches the model), **BE-01** (`body: dict` turns a malformed request
into a 500 instead of a 4xx).

**The plan.** `docs/superpowers/plans/2026-10-11-local-production-hardening.md`
is the approved program: R0 truth and bookkeeping → R1 concurrency and
cancellation → R2 validation and secrets → R3 product completeness → R4
frontend trust → R5 local packaging and operations → R6 scalability seams →
R7 release verification. Its goal is the one the user stated: fully runnable on
this machine, with no remote service and no payment, but with the capability
seams kept so scaling later does not mean re-architecting. §15's decisions were
answered by the user and are recorded in MEMORY.md: **D1** one loopback port
with `start.bat dev` retained; **D2** a minimal configurable system prompt
(implemented in R3-T4); **D3** the document-map and PLAN.md changes; **D4** no
Playwright download is needed — the browser tooling is already installed; **D5**
all eight R6 guardrails; **D6** subagent-driven execution with the documents
updated as each phase lands.

**R0, executed.** Seven tasks, all landed 2026-10-11; evidence in
`artifacts/hardening-r0-docs.txt` and the R0 task table in `TASKS.md`.

- **R0-T1** added DOC-07 (ENVIRONMENT.md claimed Playwright capture was removed;
  the driver and the `playwright>=1.63.0` dependency are both present) and
  corrected the register counts. The total was **41** at R0 (BE-19, registered by R3-T4, makes the live register 42), not the plan's 40 — the
  plan's own §16 says 41 (39 review findings plus BE-19 and DOC-07).
- **R0-T2** re-formatted `apps/vibe/src/components/ui/__tests__/CommandPalette.test.tsx`
  by exact path — the one file that made `format:check` red (DOC-01). That file
  now passes `prettier --check` and its 7 tests pass. For roughly twenty minutes
  the repo-wide check was `BLOCKED by an external cause`: a concurrent session was
  mid-write in other frontend files, and R0 must not reformat files it does not
  own. It was re-run at 19:06 and now exits 0 with *All matched files use Prettier
  code style!*
- **R0-T3** refreshed `CURRENT_STATE.md`: the Git block (HEAD `0849b14`, and the
  dirty count at two epochs because it moved 9 → 49 → 61 while R1/R4 landed), the
  Active-jobs block (no listener on 7321, 7322, 5173 or 7399 at 19:00 and 19:06),
  the three conflicting frontend test counts (now dated), DOC-04 (the 3680-path
  finding is fixed — the shared walk returns 10 paths with 0 under `node_modules`),
  and one measured suite size (frontend 104 tests in 18 files; backend 190 passed,
  both cited to the review's baseline evidence).
- **R0-T4** corrected `ENVIRONMENT.md`: the Playwright row is now accurate and
  names the `playwright install chromium` step, the CI row is labeled `SKIPPED`
  (never assumed green) with the two known first-run failures, and the stale
  prettier/warning line now reads 9 warnings with its artifact.
- **R0-T5** registered two new document kinds in `AGENTS.md` (Code review →
  `docs/reviews/README.md`; Implementation plans → `docs/superpowers/plans/`),
  extended the Architecture-audit row, and created `docs/reviews/README.md` with
  the immutability rule: a review is superseded, never rewritten.
- **R0-T6** repaired the `## Now` table in `TASKS.md` (a blank line had split it),
  added the review row and this program's R0–R7 section with per-task rows,
  updated the P3b row, added **M6** to `PLAN.md`, moved M4 to `deferred`, and
  corrected §4's open items — the workspace-scaffolding item **stays**, because
  `workspace.py` only enumerates files and `ensure_workspace` only creates the
  directory, so the Vite+React+TS scaffold from spec §6.2 is genuinely missing.
- **R0-T7** recorded the decisions and seven lessons in `MEMORY.md` (the five
  proven failure mechanisms BE-04/BE-05/BE-02/BE-07/BE-01, plus the parallel-gate
  and verify-before-you-plan lessons), and added dated corrections to two older
  rows rather than editing them silently.

**Deliberately not done in R0.** No git history operation of any kind — the
delegating agent forbade `add`/`commit`/`stash`/`checkout`/`reset`, so the ten
intended commit messages are collected in `artifacts/hardening-r0-docs.txt` for a
later, user-controlled commit. No application code was touched: nothing under
`services/vibe/src/**`, and nothing under `apps/vibe/src/**` except the single
formatting target. The backend pytest suite was not run (a concurrent session owns
it); its count is cited from the review's baseline evidence instead.

**R1, executed.** Four tasks, all landed 2026-10-11 (`artifacts/hardening-r1-pytest.txt`).
Each was made to fail first: two concurrent `POST /messages` both returned 200 before
`RunRegistry.try_start` replaced check-then-act; a grandchild process outlived the
1 s timeout before `_kill_tree`; a delete that failed mid-way left zero events with
the session row still present before the lifecycle order was fixed. Probes 4, 5 and 7
are now permanent tests, and **the probe itself is not the proof** — probe 5 only
checked a direct child, so BE-05's evidence is the promoted grandchild test.

**R1 also corrected four errors in the R2 spec before R2 could follow them**, and the
plan now carries them with the reason. The important one: `is_allowlisted`'s
`any(ch in name for ch in "/\\ \t\n")` guard rejects **every scoped package** (`@types/react`
contains a `/`), so it would have denied the same task's allowlist. Also: `react@^19
nope` needed a junk-specifier check, R2-T1 had to change the **existing** handler from
422 to 400 rather than add a second one, and the probe was weaker than its test.

**R4, executed.** All fifteen frontend findings plus a follow-up turn
(`artifacts/hardening-r4-followup.txt`): a removed `.catch(() => [])` that turned a
failed file read into an empty file, an SSE client that now reports
`idle|open|reconnecting|lost` and can `retry()` from `lastSeq`, per-file error state
in the code panel, scroll pinning with a "Jump to latest" escape, a root error
boundary (tested), per-platform shortcut labels, and a model picker that no longer
splits a provider id on `/`. Eleven manual browser checks (M1–M11) are **SKIPPED** and
carried into R7 rather than claimed.

**R2, executed.** Four tasks (`artifacts/hardening-r2-pytest.txt`). Every JSON route now
takes a declared model in the new `api/schemas.py`, and validation failures are
**400 `validation_failed`** with a field path — FastAPI's 422 is no longer part of the
contract (no frontend code referenced 422; checked). The allowlist bypass is closed for
protocol- and path-style specifiers and for junk ranges, and the provider store is now
written under a lock via `os.replace` with corrupt-file quarantine. The headline
measurement is the strict-xfail count: **21 → 2**, the two survivors being R3's
held-out BE-03 and BE-07. Three tests were **adapted, not weakened**, because the
422→400 unification changed their subject (recorded in the evidence file).

**R5-T1, executed.** `services/vibe/src/vibe/doctor.py` + `doctor.bat` + a `doctor`
subcommand (`artifacts/hardening-r5-doctor.txt`). Ten checks, six of them blocking;
chromium and a missing provider key warn instead of blocking. The team's most useful
find came from running the doctor in its **failing** state: it printed "1 blocking
problem(s)" and "all checks passed" on adjacent lines, a contradiction invisible to
any all-green test. Fixed, and pinned by two regression tests. `VIBE_HOST=::1` was
also being bind-tested as IPv4 and reported as a phantom busy port.

**R3-T1–T4, executed.** `artifacts/hardening-r3-report.txt`, suite `304 passed, 0 xfailed`, ruff
clean. The two remaining strict xfails were the phase's own tripwire and they are gone:
BE-03 (the route replays the log's transcript through `MessageService.history`, capped by
`VIBE_HISTORY_MESSAGES`, default 24) and BE-07 (one placeholder, one argument). BE-08 is
the one worth reading: the auto-fix loop used to consume the runtime's events and discard
them, so a fix turn's tool calls never reached the log or the stream. `TurnRecorder` now
records and publishes them, logs the prompt it sends as a user event — because the model
sees it and "model-visible means logged" admits no exception for a loop the user cannot
see — and the loop checks `ctx.is_aborted` before every iteration, so Stop now stops the
fix work too. BE-19 (the system prompt) landed as the backend half: `vibe/prompts.py`
holds `DEFAULT_SYSTEM_PROMPT` and `system_prompt_for()`, `AgentInput.system` carries it,
`build_messages` puts it first, and `Settings.system_prompt` (`VIBE_SYSTEM_PROMPT`)
overrides it. Two limits are recorded rather than papered over: the prompt is **not**
written to the event log, so two sessions under different prompts are indistinguishable
from their logs, and the GUI field the user also asked for is still open. (The field was delivered
later in R3 - `GET`/`PATCH /settings` and the `SettingsPanel` input - so only the log gap remains.) BE-19 was
registered in the review; the register now reads 42 findings.

**R5-T7, executed.** `artifacts/hardening-r5-backup.txt`. Backups are timestamped
directories with a manifest, pruned only by matching our own timestamp pattern, and
`--keep 0` is refused with exit 2 rather than pruning the backup just taken. Repair
quarantines a corrupt provider store with its bytes preserved and **leaves an unreadable
database untouched with exit 1** — it never deletes user data to look healthy. The seeded
generated project survived every step.

**R3-T5–T8, executed.** `artifacts/hardening-r3b-report.txt`. All four failed first and pass
now: the browser tools tell "no dev server" from "no browser driver" instead of sending a
user with a dead server to install Playwright; the dead `usage is None` branch is gone,
`GET /sessions/{sid}` finally matches the list shape, and an unexpected failure returns
`500 internal` with a short `error id` while the detail is logged under that same id;
`.trash` is swept by matching only our own `<12hex>-<date>-<time>` naming, so a mistaken
delete stays recoverable for the retention window (default 14 days, `0` disables); and the
event log gained `idx_events_session_type_seq` through the in-place migration — measured
182.7 µs → 103.4 µs median on 40k events, with the honest note that session-only reads are
unchanged, so the store-level split stays deferred. The live SSE gate
(`artifacts/hardening-r3-live.txt`) is real uvicorn, real routes, a real open SSE
connection and a **scripted** model — labelled as such.

**Then three things were left for the orchestrator, and all three are done and recorded.**
The lifespan wiring R3b could not reach is in `api/app.py` inside a `try/except` so
housekeeping can never block startup, proven against a real app startup
(`artifacts/hardening-r3-lifespan.txt`: a 30-day entry reaped and logged with its age, a
fresh entry kept, a foreign name kept, retention 0 removing nothing). `tests/test_doctor.py`
had gone stale against the deliberate move to `uvicorn.Server` (which `/admin/shutdown`
requires) and now asserts host and port through that mechanism. And BE-19's GUI half got its
missing read surface: a read-only `GET /settings` returning
`{system_prompt: {configured, effective, default, source}}`; a *writable* field still needs a
persistence decision, because a write endpoint without a settings file would lie.

**Next.** R5-T11 (the README a real user follows), then R7 closes: re-run
`scripts/acceptance-local.ps1` with the script's own cleanup respected and record the honest
label per criterion, re-run the review probes, and write the final state into
`CURRENT_STATE.md`/`TASKS.md`/`HANDOFF.md`. The GUI system-prompt field (BE-19) and the
doctor's network check (R5-T8) remain `NEEDS_USER_DECISION`. Nothing has been committed:
every phase's intended commit messages are collected in its evidence artifact, awaiting an
explicit user decision.

**R5 and R6, executed (the long tail).** Everything from R5-T2 to R6-T8 landed in one workstream.
R5: `start.bat`/`stop.bat`/`doctor.bat` as thin wrappers over `python -m vibe <serve|doctor|backup|repair>`,
production mode serving the built SPA and the API on one loopback port, a first-run panel, a rotating
log file (2 MiB x 5), a graceful shutdown that reports `exited=True`, offline detection through a
cached reachability probe (300 s ok / 30 s fail), orphaned dev-server reaping, and the two check
scripts. R6: all eight guardrails, each one first proven able to fail against a planted offender - the
owner column (store v1->v2, events v2->v3), SQL confined to store providers, the executor reached only
through its protocol, identity read only from `Principal`, registries keyed by
`SessionKey(owner_id, session_id)`, config as the only environment reader, one frontend API base, and
DDL only through `PRAGMA user_version`. The R6 exit gate is closed at `_ENV_EXEMPTIONS = {}`:
logging and the doctor were made to read `LOCALAPPDATA` through `config.local_app_data()` rather than
being granted an exemption, because an allowlist with two entries is not a seam.

**BE-19 finished, GUI half included.** `docs/guides/local-setup.md` documents the precedence the GUI
now honours: `VIBE_SYSTEM_PROMPT` > `<workspace>\settings.json` > built-in default. The workspace-scoped
file is written atomically, an unreadable one is quarantined as Ssettings.json.corrupt-<ts>S and
reported as "no override", a blank value clears the key rather than storing an empty instruction set,
and the panel disables its textarea and says why when the environment is in charge. Saving takes effect
on the next turn - no restart. Evidence `artifacts/hardening-be19-gui.txt`; the two test adaptations
(a 405-for-both-verbs assertion replaced by PUT-405 plus two PATCH tests) are strictly more coverage.

**BE-20, and the honest shape of it.** The acceptance run found what no unit test had: `DELETE`s over a
workspace a live process still held answered a generic 500 and hid the fact that the session survived.
The cause was the move raising with no retry and no name; the fix was a bounded retry, a named
`workspace_busy` error and a 409 that leaves the row and `.trash` untouched
(`artifacts/hardening-r7-delete-busy.txt`, register row BE-20). The first fix was **incomplete**, and the
re-run said so: step 6a still failed because a stopping Vite dev server needs longer than the ~1 s retry
window (5 x 0.2 s) to release its handles, while step 6b proved the locked path correct. That second
mechanism is the one worth carrying forward - a bounded retry must be sized against the thing it waits
for, not chosen for looking short.

**Measured at the final quiet tree.** Backend **459 passed, 2 warnings**, ruff `All checks passed!`
(`artifacts/hardening-gate-final-backend.txt`); frontend **25 files / 158 tests passed**, `tsc` exit 0,
eslint **0 errors / 9 warnings**, prettier clean, vite build 397.85 kB (123.33 kB gzip)
(`artifacts/hardening-gate-final-frontend.txt`); `scripts/release-check.ps1`
**PASS - 8 steps green** (`artifacts/release-check.txt`).

**R7's acceptance run.** Step 6a of `scripts/acceptance-local.ps1` is green now (the BE-20 follow-up below explains why it took two tries); step 4 is legitimately SKIPPED -
the model finished before any abort landed, and the in-flight path is covered by
`tests/test_run_registry.py`; that is a skip with a named substitute, not a pass. Steps 1, 2, 3, 5, 6b
and 7 PASS, so the app was observed building a real app from an empty workspace, serving it, surviving a
restart with its transcript, refusing to half-delete a locked workspace, and rendering the first-run
panel with no provider configured.

**Nothing is committed.** Every phase's intended messages are collected in its evidence artifact,
awaiting an explicit user decision.
**BE-20's follow-up, and a corrected diagnosis.** The first fix left step 6a red, and I read that as a
too-short retry window (~1 s) against a stopping dev server. The measurement refuted it: the holder was
the app's own orphaned `node/vite`, still listening 15+ minutes after the stop that should have ended
it. `stop_dev_server()` terminated the pnpm *shim* (cmd.exe), `wait()` returned immediately, and the
`except TimeoutError` branch that called `_kill_tree` never ran - so no window length could have
succeeded, and a widened window would have turned a reproducible failure into an intermittent one.
The fix kills the tree while the shim is still alive and forgets the pidfile only after the tree is
gone; the delete window went to 5.0 s because a real 4-process vite tree needed 1.255 s to disappear,
past the old 1.0 s. Acceptance now reads `summary: 0 FAIL/BLOCKED, 1 SKIPPED` and `RESULT: PASS`
(`artifacts/acceptance-local.txt` line 284; step 6a `PASS DELETE -> 204` with the trash entry, the 404
and zero rows). Backend **456 passed**, ruff clean.

**One more finding, fixed rather than documented away.** The check script declared `#Requires -Version 5.1`
and the README/guide invited `powershell -File`, but under Windows PowerShell 5.1 the run failed before
step 6a: `ConvertFrom-Json` does not unroll a top-level JSON array through the pipeline, so
`@($body | ConvertFrom-Json)` nested it and the provider id became the whole id array joined by spaces
(`model.provider_id: Input should be a valid string`). A `Get-JsonList` helper now enumerates the items
and all five list parses (catalog, files, messages before/after, catalog again) go through it, and the
re-run cleared step 6a. It then stopped in step 6, where the script hands a multi-line program to
`python -c` and 5.1 quotes a native argument differently, and step 7 saw one configured provider in the
instance that is meant to have none. Support for 5.1 was never going to be verifiable in this session,
so both check scripts now declare `#Requires -Version 7.0` and stop on the first line naming the version
they need; section 9 of the guide gives the `pwsh -File` invocation. The app itself has no PowerShell
dependency - `start.bat`, `stop.bat`, `doctor.bat` and `test.bat` are cmd wrappers. Evidence: the 5.1
re-run and the pwsh 7 run appended to `artifacts/acceptance-local.txt`.

**The M1-M11 browser checks ran for real, and the first honest look at prod mode found a blocker.**
An isolated instance (`VIBE_MODE=prod`, port 7322, a temp workspace) served the app to
`agent-browser`, and eleven manual checks were attempted rather than reasoned about: **1 PASS, 1 FAIL,
2 SKIPPED, 7 BLOCKED** (`artifacts/hardening-r7-browser-checks.txt`, six screenshots). M3 (a reload
keeps the theme) passed as a real observation - eval before and after a toggle, then after a hard
reload. M10 and M11 were SKIPPED for stated reasons: provoking a crash needs an app-source edit this
run was forbidden to make, and the empty state has no transcript, so the transcript's role and
announcement shape is not established. Everything else stopped at the same step: **no session could be
created from the browser**. The cause, found while running M6, is a production-readiness defect now
registered as **BE-23**: `OriginGuard` was installed with `DEFAULT_CORS_ORIGINS` (the dev Vite origins),
but in `VIBE_MODE=prod` the SPA is served by the app itself, so the page's own `Origin` was never
allowlisted and every mutating request was refused `origin not allowed`. The fix trusts a request that
is same-origin with its own `Host` and keeps the allowlist for the dev cross-origin case; the browser
checks are re-run afterwards, because M6's other symptom - the advertised `Ctrl Alt N` shortcut - must
be judged on the fixed build and not on a refused request. Neither green suite could have caught BE-23:
pytest sends no `Origin` unless a test asks for one, and `Invoke-WebRequest` never sends one.

**BE-23 fixed, and the fix proved twice.** `OriginGuard` now trusts a request that is same-origin with
its own `Host` (`_same_origin` in `api/app.py`: parsed rather than prefix-matched, scheme taken from the
ASGI scope, default ports applied, hostname compared case-insensitively) while the allowlist stays for the
dev cross-origin split. Five tests in `services/vibe/tests/test_auth.py` fail on the old guard (2 failed /
3 passed, the three refusals pinning unchanged behavior) and pass on the new one; the suite is **464
passed**, ruff clean (`artifacts/hardening-be23-prod-origin.txt`). Independently, I started the real server
with `VIBE_MODE=prod` on port 7333 and `VIBE_CORS_ORIGINS` deliberately unset: `GET /` 200 text/html, a
same-origin `POST /providers` 201, a same-origin `POST /sessions` **201**, a foreign Origin **403
forbidden_origin**, a request with no Origin 201, and the port free afterwards
(`artifacts/hardening-be23-prod-origin-orchestrator.txt`). The release gate re-run on that tree is
**PASS - 8/8 steps green**, backend **464 passed**, frontend 25 files / 158 tests, build clean
(`artifacts/release-check-post-be23.txt`). Two smaller traps found in the same sweep are closed too:
section 6 of the guide no longer claims the bare `python -m vibe serve` is equivalent to the launchers
(it defaults to dev mode and answers JSON at `/`), and `custom_provider_probe.py` - which crashed before
printing - now records that `/catalog` survives a model without an `id`, that the POST is refused, and
that a corrupt `providers.json` and an empty `apiKey` both behave (`artifacts/hardening-final-probes.txt`).

**The M1-M11 browser checks were re-run on the fixed build, and the last open R7 criterion is closed.**
`artifacts/hardening-r7-browser-recheck.txt`: **7 PASS, 1 FAIL, 2 BLOCKED, 1 SKIPPED**, with 23
`browser-check-recheck-*.png` screenshots. M6 - the check that failed before - passes from all three
entry points (`Ctrl+Alt+N` created one session, the palette entry that advertises the shortcut took the
count 1 -> 2, the empty-state button took it 0 -> 1), so the binding was never broken and the earlier
failure was the OriginGuard 403. M1 proves the stream reconnects at `after_seq=43` rather than replaying;
M2 proves Monaco follows the app theme (`rgb(30,30,30)` -> `rgb(255,255,254)`); M3 re-confirms theme
persistence across a hard reload; M4 shows no preview leak into a new session (the switch-back direction
is not established); M9 counts the polling freeze while hidden (14 -> 14 -> 35); M11 finds exactly one
`[role=log]` with the status regions outside it. M7 and M8 stayed BLOCKED (no approval was ever requested,
and no throwaway provider was created) and M10 SKIPPED (provoking a crash needs a source edit a
verification run must not make). The one FAIL is **FE-16** (Low), fixed the same day: `Jump to latest` was
offered when the transcript fitted its box and could not scroll, because visibility was gated on a flag
only `onScroll` updated - `MessageList.tsx` now measures scrollability (and re-measures from a
`ResizeObserver`), with two regression tests in `MessageList.test.tsx`. The gate re-run on that final tree
is **PASS - 8/8 steps green**, backend **464 passed**, frontend **160 passed**, build clean
(`artifacts/release-check-final-post-m5.txt`).

## UI/UX overhaul (2026-10-11, M7)

The full-app review that closed the hardening program scored the interface **22/40** on the Nielsen
heuristics and produced twelve UX findings (UX-01…UX-12) with a measured baseline in
`artifacts/ui-review/report-01.json`. The user's verdict on the app was blunt and correct: it worked,
and the UI/UX was "terrible and lacking in all aspects". This section is that rebuild.

**What was actually wrong (measured, not felt).** At 1440×900 the side column was **605px** and the
conversation **575px** — the transcript was the narrower of the two. Preview and Code were stacked
50/50 in that column with no tabs and no splitter, and `.code-panel` had a `flex-direction: row`
with no `display: flex`, so the Monaco editor measured **604×0**. `.app-shell` scrolled 930px inside
a 900px viewport. 79 elements carried `role="tooltip"` with no `aria-hidden` and no
`aria-describedby`. The document had exactly **one** heading, and it said "vibe" — not the session.
`aside` and `main` were unnamed landmarks. The body font was `-apple-system` and `document.fonts`
was empty, so the design had no typeface of its own. The chat transcript rendered user and assistant
text only: `tool_call`, `tool_result` and `error` were published by the backend and thrown away by
the client, so a long agent run looked like nothing was happening.

**The three decisions the user approved at the gate** (all three recommendations, 2026-10-11): keep the
identity and rebuild the structure on a real type system; the conversation stays primary with the side
column at ~34%, resizable, Preview and Code as tabs; and the whole interface is in scope — timeline,
workspace, sidebar, composer, onboarding, accessibility and tests.

**What landed.**

- **A — design system foundation.** Self-hosted IBM Plex Sans and IBM Plex Mono (12 font assets in the
  build, nothing fetched at runtime), a real type scale (11/12/13/14/16/20/24/28), tracking tokens, a
  measure, control and touch-target sizes, `color-scheme` and `accent-color`, and a reduced-motion
  block that zeroes durations. `styles/app.css` was **deleted**: every component rule now lives in
  `@layer components`.
- **B — the shell.** A four-track grid (`sidebar │ main │ splitter │ side`) with explicit
  `grid-column` on each panel, so hiding the splitter cannot shift a column. All the collapse rules are
  scoped to `min-width: 1101px` so a desktop collapse cannot hide a drawer after a resize. `AppHeader`
  carries the session title as the page's only `h1`, a search trigger with its keyboard chord, and the
  column toggles. `SidePanelHost` owns the Preview/Code tab strip. Tab stops before the composer went
  from ~114 to **27**.
- **C — the timeline.** The transcript folds *every* SSE event: tool calls become expandable rows with
  a summary, errors become real items, and the region is a `role="log"` with `aria-live="polite"`.
  Fenced-code rendering replaced the markdown pipeline (which is why the main chunk fell from 697 kB to
  **581 kB**).
- **D — the sidebar.** Recency grouping with real headings, a roving tabindex that keeps 36 row-action
  triggers out of the tab order, one labelled menu per row, inline rename with focus return, a labelled
  search field, two distinct empty states, and a live result count.
- **E — the workspace.** Both panels rebuilt on one `.panel` / `.panel-header` / `.panel-body`
  contract; the editor now measures **263×771** where it measured 604×0; each header carries the file
  path or the preview URL instead of a duplicated title; polling is gated on the active tab.
- **F — composer and onboarding.** In progress at the time of writing.
- **G — verification.** See below.

**Phase G found two real regressions and they were mine.** The first three-viewport probe reported the
tablet drawer as an overlapping 560px panel and the phone as unusable; the second reading showed the
drawer was correctly `visibility: hidden` and the probe was wrong (it tested the bounding rect only).
But the mobile bug was real: the desktop `grid-column: 2` pin survived into the `≤768px` query, where
the grid has **one** track, so `.app-main` measured **0×747** on every phone. Both panels are now
placed in the single cell at that breakpoint, and `main` measures `390×747`.

**Final measured state (1440×900 / 1024×768 / 390×844).** `.app-shell` overflow `[0,0]` and
`overflowX 0` at all three; desktop columns `260 / 684 / 6 / 490` with the conversation now the
widest; landmarks `HEADER, ASIDE[Sessions], NAV[Sessions], MAIN[Conversation],
SECTION[Preview and code], NAV[Panels]`; `role="tooltip"` elements `0`; body font
`"IBM Plex Sans Variable"` with 9 faces loaded; 30 of 36 tab stops before the composer at desktop
(27 of 31 at mobile). At 1024 the side
column is a right drawer that opens to 560px over a scrim; at 390 the body is a single track with a
49px bottom tab bar and one panel at a time.

**Gates (final, after Phases F and G).** `typecheck` exit 0; `lint` 0 errors (5 pre-existing
warnings); `vitest` 32 files / 290 tests; `build` 595.23 kB / 161.63 kB gzip in 3.08s. Backend
`ruff check .` exit 0; `pytest` 7 failed / 457 passed, all seven in `tests/test_doctor.py` and all
one cause — `port-backend` reports unavailable because the running server holds it. axe-core
**0 violations** at 1440 dark, 1440 light, 1024 and 390, and 0 contrast violations in each.

**New tests added by this work:** `components/ui/__tests__/primitives.test.tsx` (36) pinning the
roving tabindex, the ARIA tabs wiring, the separator's keyboard contract, the tree's structure and
navigation, and the `hidden`-panel accessibility behaviour; `components/ui/__tests__/Menu.test.tsx`
(6); three timeline tests for the mid-stream error branch; and the feature suites rewritten by the
timeline, sidebar, workspace, onboarding and composer work.

**Known limits.** 15 tool rows are genuine interactive controls, so a long agent run still adds tab
stops ahead of the composer — a skip link is the standard remedy and is an open decision (D5).
`.menu-popup` has no portal, so a row menu near the bottom edge can be clipped by its scroller
(pre-existing). `lib/markdown.tsx` and the `react-markdown` dependency are confirmed dead and are
left in place as an open decision (D4).

**Phases F and G, executed and closed.** Phase F finished in two parallel subagents — one on the
composer, one on onboarding and settings — and Phase G then verified the whole thing.

The composer gained a toolbar (reference a file, prompt templates, model, plan/act), a five-entry
template library, a caret-aware slash listbox, and the Enter / Shift+Enter / Ctrl+Enter contract with
an `isComposing` guard. Two honesty decisions matter more than the features: the backend has no
plan/act flag, so **Plan is a client-side prompt prefix** applied to the outgoing text only (a failed
send restores the user's original draft, not the prefixed copy); and there is no upload endpoint, so
**"Reference a file" inserts an editable path placeholder** rather than pretending to attach
anything. Templates append to a non-empty draft instead of replacing it, so a template can never
destroy typed work. The `ModelPicker` was removed from the chat header because it now lives in the
toolbar — two copies meant two `id="model-select"` and two "Model" labels.

First-run and settings were rebuilt on the type scale and primitives: the empty state now says what
the app is, why it is unusable yet and what to do, with one primary action and four real example
prompts (none of them auto-send); settings is a tabbed Providers / System prompt panel with a
skeleton → error+retry → content path, per-row masked key inputs, a toast on success and an inline
`role="alert"` on failure. Built-in provider rows are deliberately **not** typeable, because the
backend has no GUI write path for env keys — the field would be a lie.

Phase G then found four accessibility defects that the overhaul itself had introduced, all four now
fixed: `aria-expanded` on the composer textarea (unsupported on `textbox`, and HTML-ARIA forbids the
`combobox` role that would legalise it on a `textarea`, so the open state is carried by
`aria-controls` + `aria-activedescendant`); a nameless header search trigger once its label
collapses to an icon under 900px; the resize handle sitting outside every landmark, which fails axe's
`region` rule (it now renders inside the section it resizes, pulled back over the empty grid track so
nothing moved); and a visually-hidden file input that was a second, invisible "Attach image" tab stop
beside the visible button. A sixth, smaller one: the root `<html>` still computed to the UA serif
because only `body` carried `--font-ui`.

`impeccable detect --json apps/vibe/src` returns `[]`. Five decisions remain for the user (D1–D5 in
TASKS.md). Evidence: `artifacts/ui-review/report-m7.json`,
`artifacts/ui-review/impeccable-detect-m7.json`, `artifacts/ui-review/pytest-m7.txt`.

