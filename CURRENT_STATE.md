# CURRENT_STATE

<!-- session-maintained snapshot — refreshed at session start; a render script is planned with implementation -->

## Git

- Branch: master
- Latest commit: 47edd56 (fix(cors): make dev-server origin allowlist configurable via VIBE_CORS_ORIGINS)
- Commit history: scaffold 215ca70 → M1 core loop → M2 sessions/models → M3 polish → M5 frontend UI/UX overhaul → CORS fix
- Dirty files: 96 modified, 46 untracked (`git status --porcelain`: 146 entries) — M2/M3/M5 work, the 2026-09-30 frontend polish pass, the 2026-10-04 bridge fixes, the 2026-10-04 P0+P1 structural work, the 2026-10-04 P3 developer-experience work, the 2026-10-05 P2 seams work, and the 2026-10-05 P4 product-gap work (nothing was staged or reverted). The count grew partly because `ruff check --fix` rewrote imports across the backend

## Active jobs

- Backend dev server: **down** — ports 7321 and 7322 do not accept connections
  (re-verified 2026-10-04, after the P3 verification runs).
- Frontend dev server: **down** — port 5173 does not accept connections
  (verified 2026-10-04). Start both with `start.bat`, or run the backend on a
  free port and the frontend with `VITE_API_URL`.
- Live harness port 7399: **down** (verified 2026-10-04).
- Port 8000 is held by a foreign httpd/Apache — never kill it.
- Agent sessions: **25** stored sessions in `C:\Users\AhmadMhmoud\vibe-workspaces`
  (the 2026-10-04 merge); `2943b651ae98` is the E2E workspace

## Tasks

- See [TASKS.md](./TASKS.md) — M1 core loop **done** (E2E PASS 2026-09-29),
  M2 **done** (2026-09-29), M3 **done** (2026-09-29), M5 **done**
  (2026-09-29). Next milestone: **M4 — Scale**.
- M5 delivered: design system + UI primitives, app shell (3-col, Settings
  modal, responsive), honest states (errors/loading/empty/confirms),
  per-session chat store + history endpoint + markdown, rich approval cards
  with always-allow policy, accessible code file list + language detection +
  save indicator, real preview state via preview endpoints + polling,
  favicon/title/theme toggle. 53 frontend tests PASS, typecheck clean,
  build clean, axe-core 0 violations desktop + mobile.
- CORS fix (commit 47edd56): VIBE_CORS_ORIGINS env var for configurable
  dev-server origin allowlist.
- 2026-10-04 P0+P1 structural work (the user approved both phases together,
  from the audit's §8 plan). **P0 — portability & safety:** `Settings` now
  expands and resolves the workspace root once, so `VIBE_WORKSPACE_DIR=~/...`
  no longer creates a literal `~` directory; the three stray roots were merged
  into `C:\Users\AhmadMhmoud\vibe-workspaces` (23 dirs / 25 rows, backup
  `sessions.db.bak-20261004-182245`) by `services/vibe/scripts/merge_workspaces.py`
  — the originals are **left in place for you to delete after verifying**;
  `start.bat`/`test.bat` use `%~dp0`; `.gitignore` covers `~/` and `artifacts/`;
  evidence moved to `artifacts/` and root clutter archived to `archive/scratch/`.
  **P1 — lifecycle & integrity:** `EventLog` is sqlite-backed so chat history
  survives a restart; `SessionLifecycle.delete` cascades (abort run → stop dev
  server → drop executor/policy/approvals/events → move the workspace to
  `.trash/` → delete the row last); the dev-server pipe is drained, an existing
  server is stopped before a new one starts, idle servers are reaped after
  `VIBE_DEV_SERVER_IDLE_TIMEOUT_MIN`, and shutdown stops every executor; both
  databases use WAL + `synchronous=NORMAL` + `busy_timeout`, a `threading.Lock`
  and `asyncio.to_thread`, with `PRAGMA user_version` migrations. `Settings.host`
  (`VIBE_HOST`) was added and `__main__.py` now uses `settings.host`/`.port` via
  a `main()`, so `python -m vibe` honours `VIBE_PORT` and no longer builds the
  app at import time. Validation: 98 backend tests, 22/22 live harness checks,
  76 frontend tests, typecheck, build, plus an end-to-end restart-durability and
  delete-cascade run against a live server — all PASS. Evidence:
  [p0p1-pytest.txt](./artifacts/p0p1-pytest.txt),
  [p0p1-live.txt](./artifacts/p0p1-live.txt),
  [p0p1-e2e.txt](./artifacts/p0p1-e2e.txt),
  [p0p1-vitest.txt](./artifacts/p0p1-vitest.txt),
  [p0p1-typecheck.txt](./artifacts/p0p1-typecheck.txt),
  [p0p1-build.txt](./artifacts/p0p1-build.txt).
  The audit's order is now complete: P3, P2 and P4 all followed — see the
  entries below. Nothing in the plan is outstanding.
- 2026-10-04 P3 developer experience — **done**. (1) **Logging**, the last
  silent subsystem: `vibe/logging_setup.py` puts one stderr handler on the
  `vibe` logger (`propagate=False`, idempotent, `VIBE_LOG_LEVEL`, default
  INFO, unknown level names fall back rather than raise). Library modules only
  call `getLogger(__name__)`; `__main__` configures, and `create_app`
  configures only if nobody has — `start.bat` mounts the app through
  `uvicorn --factory`, which never runs `__main__`. The idle-reaper's bare
  `except Exception: pass` now logs a warning with a traceback.
  (2) **ruff 0.16.10** (dev extra) over E/F/W/I/UP/B/C4/SIM/RUF: **136 findings
  fixed**, 118 automatically and 18 by hand — the hand-fixed ones were real
  (`B904` `raise` losing its cause, `B905` `zip` without `strict`, an
  `F841` dead assignment, `SIM105`, 9 `E701` one-liners).
  (3) **eslint 10 flat config + prettier config**: 23 baseline problems → **0
  errors, 14 warnings**. (4) `pnpm test` is now `vitest run`; `test:watch`
  added; `packageManager` pinned to `pnpm@12.3.4`. (5) **CI**:
  `.github/workflows/ci.yml` runs backend (ruff + pytest) and frontend
  (eslint + tsc + vitest + build) on `windows-latest`.
  Validation: 107 backend tests + ruff clean; 76 frontend tests + eslint
  (0 errors) + typecheck + build; the live ASGI/SSE harness PASS; `test.bat`
  green end to end. Evidence:
  [p3-pytest.txt](./artifacts/p3-pytest.txt),
  [p3-ruff.txt](./artifacts/p3-ruff.txt),
  [p3-logging.txt](./artifacts/p3-logging.txt),
  [p3-live.txt](./artifacts/p3-live.txt),
  [p3-eslint.txt](./artifacts/p3-eslint.txt),
  [p3-vitest.txt](./artifacts/p3-vitest.txt),
  [p3-test-bat.txt](./artifacts/p3-test-bat.txt).
  **Left open on purpose (needs your call):** the root-workspace restructure
  (a root `package.json` changes pnpm resolution for `apps/vibe`), the
  prettier sweep (`prettier --check` reports **37 files**, all currently
  uncommitted work), and the 14 eslint warnings — 2 `react-hooks/refs` +
  5 `react-hooks/set-state-in-effect` are genuine findings kept at `warn`
  with the reason written into `apps/vibe/eslint.config.js`.
- 2026-10-05 P2 seams — **done**. (1) **Container + Depends:** `vibe/container.py` holds one frozen `Container` with `Container.build(settings, **overrides)`; `create_app(settings, *, container=None)` builds or accepts one and assigns it to `app.state.container` (the only `app.state` write left). Routes declare `deps: App` (`App = Annotated[Container, Depends(get_container)]`), so a route's needs are in its signature; `app.state.container` stays reassignable so a test swaps a seam whole via `dataclasses.replace` (`tests/conftest.py` `swap()`). (2) **Provider registry:** `providers/registry.py` — `build_llm_factory(settings, custom_store)` returns the one `LlmFactory`; the three provider classes were **deleted** (dead — only a test imported them — and broken: `ChatOpenAI` built with no `model=`, and `openai_responses.py` claiming `/v1/responses` while building `ChatOpenAI`). (3) **EventStore protocol:** `vibe/events.py` declares the capability; `runtime/base.py`, `usage/tracker.py` and `api/app.py` are typed against it, and `tests/test_events.py` proves a fake store can stand in. (4) **`vibe/services/`:** `SessionService` (CRUD + workspace path confinement) and `MessageService` (history projection) — both were inline in the route handlers, so neither was testable without a FastAPI app. Validation: 136 backend tests + ruff clean; 76 frontend tests + eslint (0 errors / 14 warnings) + typecheck + build; the live ASGI/SSE harness 22 PASS / 0 FAIL. Evidence: [p2-pytest.txt](./artifacts/p2-pytest.txt), [p2-ruff.txt](./artifacts/p2-ruff.txt), [p2-live.txt](./artifacts/p2-live.txt), [p2-vitest.txt](./artifacts/p2-vitest.txt), [p2-typecheck.txt](./artifacts/p2-typecheck.txt), [p2-build.txt](./artifacts/p2-build.txt), [p2-eslint.txt](./artifacts/p2-eslint.txt). **Behaviour changes:** routes no longer read `app.state`; the container is frozen and swapped whole; `require_session` takes the container, not the request; `send_message`/`abort_run` lost their unused `request` parameter; path confinement and the history projection moved into `vibe/services/`. **Heads-up:** `require_session` is a **reconstruction** — an agent error destroyed the user's uncommitted version mid-refactor and it was not in git (HEAD has a 0-byte `deps.py`); it was rebuilt from its 14 call sites and is not byte-identical to the lost original.
- 2026-10-05 P4 product gaps — **done**, which completes all five phases of the
  audit's plan. (1) **Titles from the first message:** `store.title_from_text` +
  `SessionStore.retitle_from_message` + `SessionService.retitle_from_message`, called
  from `POST /messages` after the user message is appended; it only fires while the
  title is still the `Untitled xxxx` placeholder, so a manual rename is never
  clobbered. (2) **Pagination:** `MessageService.page` returns a frozen
  `MessagePage`; `GET /sessions/{sid}/messages` takes `limit` (1-1000, default 200)
  and `offset` (counts back from the newest) and reports the real total in
  `X-Total-Count` (CORS-exposed). The frontend prepends older pages behind a
  "Load older messages" button, and the auto-scroll effect is keyed on the last
  message so loading older history does not yank the view down. (3) **Error
  taxonomy:** `vibe/api/errors.py` — `ErrorCode` (StrEnum) + `ApiError(code,
  message, *, status=None)` with a default-status map; four handlers give every
  error the same `{"error": {"code", "message"}}` body, and the frontend surfaces
  the code. (4) **M6 honesty fix:** `read_console_logs`/`screenshot` return `None`
  ("no driver"), never `""` ("clean"); `AutoRunPolicy` treats `None` as *nothing was
  read*, and the agent-facing tools say "unavailable: this build has no browser
  driver installed". (5) **README corrected:** the false console-log / screenshot /
  runtime-error claims are gone, replaced by a **Known gaps** section that also
  records the unauthenticated-by-design decision; the port-7321 pinning now matches
  what `start.bat` actually does. **Bug found and fixed:** `req<void>` called
  `resp.json()` on a 204 with an empty body, so `api.deleteSession` always threw a
  `SyntaxError` after the server had deleted — and the sidebar never refreshed.
  Fixed with `readBody()`. Validation: 161 backend tests + ruff clean; 86 frontend
  tests + eslint (0 errors / 14 warnings) + typecheck + build; the live ASGI/SSE
  harness 22 PASS / 0 FAIL; a 13-check live probe over the new behaviours 13 PASS /
  0 FAIL. Evidence: [p4-pytest.txt](./artifacts/p4-pytest.txt),
  [p4-ruff.txt](./artifacts/p4-ruff.txt), [p4-live.txt](./artifacts/p4-live.txt),
  [p4-live-probe.txt](./artifacts/p4-live-probe.txt),
  [p4-vitest.txt](./artifacts/p4-vitest.txt),
  [p4-typecheck.txt](./artifacts/p4-typecheck.txt),
  [p4-build.txt](./artifacts/p4-build.txt),
  [p4-eslint.txt](./artifacts/p4-eslint.txt).
  **Left open, `NEEDS_USER_DECISION`:** a browser driver for real console/screenshot
  capture, and any auth story beyond loopback. **Both resolved 2026-10-05 — see P5.**
- 2026-10-05 P5 — the browser driver — **done** (the user chose "A. Implement
  Playwright"). (1) **`vibe/executor/browser.py`** owns the Playwright lifecycle:
  lazy launch, a TCP readiness wait before every capture, `console`/`pageerror`
  listeners attached *before* `page.goto`, level filtering (`error` default,
  `warning`, `all`), real PNG screenshots, idempotent `close()`. Every method
  returns `None` when Playwright or the browser binary is missing, so a machine
  without a browser still runs. `VIBE_BROWSER_HEADLESS=0` opens a visible window.
  (2) **The `ToolResult` → `repr()` defect, which affected every tool call, is
  fixed.** A dataclass returned from a LangChain tool was stringified into
  `ToolMessage.content`, so the model read `"ToolResult(content='...', ...)"`
  instead of the answer. Fixed with `response_format="content_and_artifact"`
  plus a list of content blocks; `is_error` now reaches the event stream, and the
  SSE payload joins only `type=="text"` blocks so no base64 reaches the browser.
  (3) **A real bug found while verifying: pnpm 12 forwards `--` literally.**
  `pnpm run dev -- --port 57180` reached Vite as `vite "--" "--port" "57180"`,
  Vite ignored `--port` after a bare `--` and **fell back to 5173** — every session
  collided on the default port and `dev_server_url` named a port nothing listened
  on. The `--` is gone, and the dev-server test now asserts something is
  *listening* on `handle.port`, not merely that the port is positive.
  Validation: 177 backend tests + ruff clean; 86 frontend tests + eslint
  (0 errors / 14 warnings) + typecheck + build. Evidence:
  [p5-pytest.txt](./artifacts/p5-pytest.txt),
  [p5-ruff.txt](./artifacts/p5-ruff.txt),
  [p5-browser.txt](./artifacts/p5-browser.txt).
  **Left open, `NEEDS_USER_DECISION`:** any auth story beyond loopback — the design
  is delivered and explained; implementation awaits the user's scope call.
- 2026-10-05 P6 — loopback auth — **done** (the user approved the recommendation:
  one user, one machine, local now, reusable/scalable later). (1) **`vibe/auth.py`**:
  `Principal`, an `Authenticator` protocol, and `LoopbackAuthenticator`, which accepts
  a request only when `request.client` is unset (in-process ASGI) or its host is
  `127.0.0.1`, `::1`, `localhost`, or `testclient` (the Starlette `TestClient` marker).
  It authenticates the *machine*, not a user — `Principal.id` is always `"local"`.
  (2) **Router-level deny-by-default:** `require_principal` raises
  `ApiError(UNAUTHENTICATED)` (401) when the authenticator returns `None`, and all
  seven routers are mounted with `dependencies=[Depends(require_principal)]`, so a
  route added tomorrow is protected without remembering to ask. `/health` stays open.
  (3) **`OriginGuard` — a second, independent control,** because loopback auth cannot
  catch CSRF: a cross-site POST from the user's own browser arrives from `127.0.0.1`.
  The guard refuses state-changing methods whose `Origin` is not in
  `VIBE_CORS_ORIGINS` with `403 forbidden_origin`; a missing `Origin` is allowed and
  GET is not checked. (4) **The seam:** `Container.build(authenticator=...)` +
  `Settings.auth_mode` / `VIBE_AUTH_MODE`; an unknown mode raises `ValueError` rather
  than falling back to loopback. **Deliberately out of scope:** no token (an
  auto-generated token in the frontend bundle is security theatre and breaks
  `start.bat`); no users/ownership — multi-user later means `owner_id` on sessions +
  an ownership check in `require_session` + a filtered `SessionStore.list`.
  Validation: 190 backend tests + ruff clean; 86 frontend tests + eslint
  (0 errors / 14 warnings) + typecheck; a 5-check live probe over a real socket
  (health open, local GET 200, allowed Origin 201, no Origin 201, foreign Origin
  403) 5 PASS / 0 FAIL. Evidence: [p6-pytest.txt](./artifacts/p6-pytest.txt),
  [p6-ruff.txt](./artifacts/p6-ruff.txt), [p6-vitest.txt](./artifacts/p6-vitest.txt),
  [p6-typecheck.txt](./artifacts/p6-typecheck.txt),
  [p6-eslint.txt](./artifacts/p6-eslint.txt).
- 2026-10-05 P3a — root workspace + unified scripts — **done** (the user said
  "start P3a, P3b and P3c"). A root `package.json` (private, `packageManager`
  pin, unified scripts) and a root `pnpm-workspace.yaml`
  (`packages: ["apps/*"]`) own the install; the `allowBuilds: esbuild` setting
  moved up from `apps/vibe/pnpm-workspace.yaml`, which is gone. One
  `pnpm install` at the root covers the workspace;
  `pnpm --filter vibe {dev,build,test,typecheck,lint,format}` run inside
  `apps/vibe`, and `pnpm test:backend` / `pnpm lint:backend` reach the Python
  venv. **Gotcha:** pnpm runs scripts through `cmd`, so the backend scripts need
  a leading `.\` — a bare `.venv\Scripts\python.exe` is parsed as the `.`
  source command. Validation: install 364 packages; build PASS; 86 vitest;
  typecheck; eslint 0 errors / 14 warnings; 190 pytest; ruff clean. Evidence:
  [p3a-all.txt](./artifacts/p3a-all.txt).
- 2026-10-04 bridge fixes (a third-party frontend↔backend review, verified  claim-by-claim, then every finding plus the defects the review missed):
  EventBus fans out one queue per subscriber; ephemeral stream frames take a
  real monotonic seq without entering the log; the SSE route subscribes before
  replaying and dedupes by seq; the client never moves `lastSeq` backwards;
  Stop is a real run-task cancel via `POST /sessions/{sid}/abort`; provider
  `PATCH` accepts camelCase and snake_case and 400s on an empty update;
  `/usage` aggregates a real `by_model` breakdown and cache-write tokens;
  unknown session ids are 404 (DELETE stays idempotent); one shared workspace
  walk prunes vendored dirs everywhere; file paths are URL-encoded per
  segment; chat messages carry stable ids and each turn streams into its own
  message. Validation: 75 backend tests, 76 frontend tests, typecheck, build,
  and a live ASGI/SSE run (two subscribers + a real abort) — all PASS.
  Evidence: [pytest-after.txt](./artifacts/pytest-after.txt),
  [live-verification.txt](./artifacts/live-verification.txt),
  [vitest-after.txt](./artifacts/vitest-after.txt),
  [typecheck.txt](./artifacts/typecheck.txt),
  [build.txt](./artifacts/build.txt).
- 2026-09-30 frontend polish pass (impeccable review → enhance → polish;
  identity kept): CSS layer inversion fixed (the app had no visible primary
  action), invisible `.spinner` authored, dead mobile Code/Preview tabs
  repaired, drawers no longer cover their own toggle (+ Escape to close),
  session rows 108px → 44px, polling survives backend restarts, contrast
  floor raised, first-run chat state authored, fake Import control removed,
  Toast/ErrorBoundary/useMediaQuery wired up. 63 frontend tests PASS,
  typecheck clean, build clean, axe-core 0 violations at 390px
  (chat/code/preview) and 1440px, mechanical detector clean. Evidence:
  [.impeccable/captures/2026-09-30-polish-verification.md](./.impeccable/captures/2026-09-30-polish-verification.md).
  Open finding for a backend decision: `GET /sessions/{sid}/files` returns
  3680 paths (3667 under `node_modules`).

## Decisions

- 2026-09-28: server-side sandbox, local-first, core-loop MVP, full tool
  suite, provider-agnostic + OpenCode Go, LangGraph + local subprocess,
  usage/cost tracking. See [PLAN.md](./PLAN.md) and the design spec.
- 2026-09-29 (M5): dark-first IDE aesthetic; Settings as modal (Cmd+,);
  react-markdown for LLM output (hand-rolled HTML is an XSS risk);
  per-session chat store keyed by sid (global store bled messages across
  sessions); approval always-allow policy stored in localStorage.
- 2026-09-29 (CORS): VIBE_CORS_ORIGINS env var for configurable CORS
  allowlist (comma-separated origins).
- 2026-10-04 (P0/P1): deleting a session **moves its workspace to
  `<workspace_dir>/.trash/`** rather than destroying it, and the row is deleted
  last so a failed move aborts the delete; the workspace root is resolved once in
  `Settings` and is the single source of truth (exposed by `/health`); the idle
  dev-server timeout is wired to a real 60 s reaper rather than being deleted;
  `read_console_logs` deliberately stays inert (Vite's startup banner would make
  the autorun runtime-error check fire on a healthy app) and now says so in its
  docstring — capturing the real browser console needs a driver (P4).
  **Corrected 2026-10-05 (P4):** it returns `None`, not `""` — "no driver", not
  "clean" — so the loop can tell "nothing to check" apart from "no errors".- 2026-10-04: one agent run per session (a concurrent send is 409); Stop
  cancels the run's `asyncio.Task` rather than setting a UI flag; unknown
  session id is 404 everywhere except `DELETE`; the bus mirrors the log so a
  second tab sees the whole transcript.
- 2026-10-04 (P3): configuring logging is the **entry point's** job — library
  modules only call `getLogger(__name__)`, with `create_app` the single
  exception (it configures only if no handler exists, so `uvicorn --factory`
  is not silent). Lint **warnings** are permitted but must be triaged in the
  config with the reason written there, never silently ignored. prettier is
  configured but **not applied** and `format:check` stays out of CI until the
  sweep is committed. The root-workspace restructure is deferred to the user
  because it changes pnpm resolution for a working install.

## Environment

- See [ENVIRONMENT.md](./ENVIRONMENT.md) for stable policy and machine
  profiles.
- **Correction (2026-10-04):** PyPI is **reachable**. ENVIRONMENT.md and
  HANDOFF.md both claimed it was not and that `uv run` hangs; `uv add
  --optional dev ruff` and `uv run --with pyyaml` both resolved and
  downloaded. The `--offline` flags those docs recommended are no longer
  needed. npm registry reachable (unchanged).
- GitHub Actions has never been executed for this repo — the CI workflow is
  **unverified** until a run appears.
