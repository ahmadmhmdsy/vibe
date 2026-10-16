# CURRENT_STATE

<!-- session-maintained snapshot — refreshed at session start; a render script is planned with implementation -->

## Git

- Branch: master
- Latest commit: `0849b14` (P3b — prettier sweep)
- Commit history: `0849b14` → `e6a5c75` (P3a — root pnpm workspace + unified scripts) → `b377020` (bridge fixes, P0–P6, loopback auth) → `47edd56` (CORS) → `635828d` (polish). Earlier: scaffold `215ca70` → M1 → M2 → M3 → M5.
- Dirty files: **191 entries** (104 modified, 86 untracked) re-measured 2026-10-16 after the review remediation; at the M7 close (2026-10-11) it was **189 entries** (103 modified, 85 untracked), measured with `git status --porcelain`; was 188 entries (104 modified, 84 untracked) at 00:20 earlier the same session. It grows with every hardening task — that is expected, nothing has been committed. Earlier snapshot: 89 entries (60 modified, 29 untracked) at 19:31, measured with `git status --porcelain` (49 entries / 35 modified / 14 untracked at 19:00, before this session's own document writes). The number is moving, so it carries two epochs: the [full app review](./docs/reviews/2026-10-11-full-app-review/README.md) found **9** (5 modified / 4 untracked — `TASKS.md`, `CommandPalette.tsx`, `useKeyboardShortcut.ts`, `useMediaQuery.ts`, `usePolling.ts` plus three new test files and `archive/`); the rest arrived with the hardening program's first phases (R0 documents, R1 backend, R4 frontend), which are being executed concurrently. Added this session: `docs/reviews/` and `docs/superpowers/plans/2026-10-11-local-production-hardening.md`. Nothing was staged or reverted.

## Active jobs

- **No dev server is running (re-verified 2026-10-16).** The M7 snapshot recorded a
  `python -m vibe serve` on port 7321 (PID 29948); at this session's re-check,
  `Get-NetTCPConnection -LocalPort 7321,7322,5173,7399 -State Listen` returned **no listener on
  any of the four**. That is also why the seven `tests/test_doctor.py` `port-backend` failures the
  M7 notes describe did not reproduce here — the backend run at review was 463 passed / 1 failed,
  and after the RED-2 fix, **464 passed / 0 failed**. Start a dev pair with `start.bat`, or run the
  backend on a free port and the frontend with `VITE_API_URL`.
- Port 8000 is held by a foreign httpd/Apache — never kill it.
- Agent sessions: **25** stored sessions in `C:\Users\AhmadMhmoud\vibe-workspaces`
  (the 2026-10-04 merge, not re-counted 2026-10-11); `2943b651ae98` is the E2E workspace

## Tasks

- **2026-10-16 review remediation — done (uncommitted).** A read-only verification review of the
  working tree re-ran every gate and fixed six findings (see [TASKS.md](./TASKS.md) § Review
  remediation — 2026-10-16): the prettier drift on 16 files that would have failed the CI frontend
  job (RED-1); `test_install_build_dev_server`, whose scaffold declared a `vite build` script with
  no `vite` dep and no build-script approval (RED-2); two stale code comments (RED-3, RED-4); and
  this snapshot's stale port note (RED-5). One new question is open — RED-6, whether a session
  workspace's `pnpm install` hits `ERR_PNPM_IGNORED_BUILDS` on pnpm 12. Verified after the fixes:
  backend **464 passed** + ruff clean; frontend `tsc` exit 0, eslint 0 errors / 5 warnings,
  `prettier --check` exit 0.
- **M7 — UI/UX overhaul: done (2026-10-11).** Phases A–G landed: a self-hosted IBM Plex type
  system and token layer, a rebuilt app shell (4-track grid, conversation primary, side column at
  `clamp(320px, 34%, 560px)` with Preview/Code tabs and a splitter), an event-sourced agent
  timeline, a grouped session sidebar, a rebuilt preview/code workspace, a composer with a toolbar /
  template library / slash commands, and a rebuilt first-run and settings panel. Verified: axe-core
  **0 violations** at 1440 dark, 1440 light, 1024 and 390; **0 contrast violations**; frontend
  **32 files / 290 tests** green, `tsc` exit 0, eslint 0 errors / 5 pre-existing warnings, build
  595.23 kB / 161.63 kB gzip; backend `ruff` clean. Evidence:
  `artifacts/ui-review/report-m7.json`, `artifacts/ui-review/impeccable-detect-m7.json`
  (`[]`), `artifacts/ui-review/pytest-m7.txt`. Plan:
  [docs/superpowers/plans/2026-10-11-ui-ux-overhaul.md](./docs/superpowers/plans/2026-10-11-ui-ux-overhaul.md);
  review: [docs/reviews/2026-10-11-ui-ux-review/README.md](./docs/reviews/2026-10-11-ui-ux-review/README.md).
  Five decisions are still open for the user — see the M7 section of TASKS.md.
- See [TASKS.md](./TASKS.md) — M1 core loop **done** (E2E PASS 2026-09-29),
  M2 **done** (2026-09-29), M3 **done** (2026-09-29), M5 **done**
  (2026-09-29). M4 — Scale is **deferred** (local-first; the seams are kept).
  Next milestone: **R7** (release verification) of the local-production hardening
  program — **R0 through R6 have landed and R5 is complete** (including T11: the README for a
  local user plus `docs/guides/local-setup.md`); R7's release verification is finishing. Step 6a
  is green now (the workspace-held delete answers 204 + `.trash/<sid>-*` after the BE-20 fix) and
  step 6b proves the 409 `workspace_busy` path; the latest script run is `RESULT: PASS` on
  `summary: 0 FAIL/BLOCKED, 1 SKIPPED`. Step 4 stays SKIPPED with its harness cause proven and fixed
  (a `Start-Process -ArgumentList` header split) but not re-run. R7 also found and fixed **BE-21**
  (an unset `VIBE_LOG_FILE` counted as off, so the documented workspace log file was never
  written; `artifacts/hardening-r7-log-default.txt`) and **BE-22** (a second event-log allocator
  collided on `PRIMARY KEY (session_id, seq)` and turned `POST /messages` into a 500; the insert now
  re-seeds that session's counter under the existing lock and retries -
  `artifacts/hardening-be22-seq-race.txt`). Final quiet-tree gate, 2026-10-11 21:49: backend
  **459 passed, 2 warnings**, ruff clean (`artifacts/hardening-gate-final-backend.txt`); frontend
  **25 files / 158 tests passed**, `tsc` exit 0, eslint 0 errors / 9 warnings, prettier clean,
  build 397.85 kB / 123.33 kB gzip (`artifacts/hardening-gate-final-frontend.txt`);
  `scripts/release-check.ps1` **PASS - 8/8 steps green** (`artifacts/release-check-final.txt`), and the same gate re-run after BE-23 is green at **backend 464 passed / frontend 158 tests** (`artifacts/release-check-post-be23.txt`). The
  M1-M11 browser checks ran for real in prod mode on port 7322
  (`artifacts/hardening-r7-browser-checks.txt`): **1 PASS (M3), 1 FAIL (M6), 2 SKIPPED (M10, M11),
  7 BLOCKED** - every blocked check and M6 itself trace to **BE-23**, found while running M6. It is
  **High** and now fixed: the `OriginGuard` trusted only the dev Vite origin, so in prod mode the served
  UI's own same-origin mutations were refused `origin not allowed` and no session could be created at all;
  the guard now trusts a request that is same-origin with its own `Host` (the allowlist stays for the dev
  split), proved at the ASGI layer (5 new tests; **464 passed**, ruff clean -
  `artifacts/hardening-be23-prod-origin.txt`) and on a real prod server with `VIBE_CORS_ORIGINS` unset
  (same-origin `POST /sessions` 201, foreign Origin 403 -
  `artifacts/hardening-be23-prod-origin-orchestrator.txt`). Both check scripts now require PowerShell 7
  (`#Requires -Version 7.0`, run with `pwsh`), the guide no longer claims the bare module command is
  equivalent to the launchers, and the M1-M11 checks were re-run on the fixed build
  (`artifacts/hardening-r7-browser-recheck.txt`): **7 PASS, 1 FAIL, 2 BLOCKED, 1 SKIPPED** - M6 now passes
  from all three entry points (the shortcut was never broken; the 403 was), M1/M2/M3/M4/M9/M11 pass with
  observed values, M7 and M8 stayed BLOCKED (no approval was ever requested; no throwaway provider) and
  M10 SKIPPED (it needs a source edit). The one FAIL is **FE-16** (Low): a `Jump to latest` control shown
  when the transcript fits its box and cannot scroll - fixed by measuring scrollability instead of trusting
  a flag only `onScroll` updated, with two regression tests.
- **2026-10-11 UI/UX overhaul (M7) — in progress.** Review: 22/40 on the Nielsen heuristics with
  twelve findings (UX-01…UX-12), baseline measured in `artifacts/ui-review/report-01.json`. Plan:
  [docs/superpowers/plans/2026-10-11-ui-ux-overhaul.md](./docs/superpowers/plans/2026-10-11-ui-ux-overhaul.md).
  Three user decisions approved at the gate: keep the identity and rebuild on a real type system; the
  conversation stays primary with the side column at ~34%, resizable, Preview/Code as tabs; and the
  whole interface in scope. **Phases A–E landed and verified**: self-hosted IBM Plex (12 font assets),
  a 4-track shell grid with `[0,0]` overflow at every breakpoint, an event-sourced transcript that
  finally shows tool calls, a sidebar with a roving tabindex, and a workspace whose editor measures
  263×771 where it measured 604×0. Re-measured at 1440×900: columns `260 / 684 / 6 / 490`, tab stops
  before the composer **27** (was ~114), `role="tooltip"` elements **0** (was 79), landmarks all named,
  body font `"IBM Plex Sans Variable"`. Phase G found and fixed two real regressions of my own: the
  desktop `grid-column: 2` pin collapsed the conversation to **0px** wide on every phone, and the first
  probe mis-reported a `visibility: hidden` drawer as visible. **Phase F (composer toolbar, template
  library, slash commands, onboarding and settings) and the final Phase G gates were still running at
  the time of this snapshot.** Frontend gate at that point: `tsc` exit 0, eslint 0 errors / 6 warnings,
  `vitest` 31 files / 265 tests, build 581.62 kB / 157.36 kB gzip (the main chunk fell from 697 kB
  because the transcript no longer pulls in `react-markdown`).
- **2026-10-11 full app review — done.** **48 findings** (24 backend, 16
  frontend, 8 docs/CI/tests; 6 High, 15 Medium, 22 Low, 2 Low/Info, 3 Info;
  41 at the review, plus BE-19 registered by hardening R3-T4 and BE-20, BE-21, BE-22 and BE-23
  found by R7's release verification and its first real browser run, BE-24 by the CLI smoke
  alongside it, and FE-16 by the browser re-check, all fixed in the same phase)
  evidence and re-runnable probes live beside it. The four highest-impact:
  BE-04 (the one-run-per-session guard is not atomic), BE-02 (the allowlist is
  bypassable by an alias specifier), BE-03 (no conversation memory — only the
  newest message reaches the model), BE-01 (`body: dict` turns a typo into a 500).
- **Local production hardening program — approved 2026-10-11.** Plan:
  [docs/superpowers/plans/2026-10-11-local-production-hardening.md](./docs/superpowers/plans/2026-10-11-local-production-hardening.md).
  Phase order R0 (documents) → R1 (concurrency/cancellation) → R2 (validation
  and secrets) → R3 (product completeness) → R4 (frontend trust) → R5 (local
  packaging and operations) → R6 (scalability seams) → R7 (release
  verification). Live status in
  [TASKS.md](./TASKS.md) § Local production hardening — 2026-10-11; decisions
  D1–D6 in [MEMORY.md](./MEMORY.md).
  **Landed so far:** R0, R1, R2, R3, R4, R6 **PASS**, R5 **all but T11**, and
  R7 is running (its acceptance script has already found and fixed BE-20, a `DELETE`
  that answered 500 while a preview held the session workspace). In flight: R5-T11
  (the README) and R7's final acceptance/probe run. **Nothing is committed** — every
  phase's intended commit messages are in its evidence artifact under
  `artifacts/hardening-*.txt`, awaiting an explicit user decision; the running log is
  [artifacts/hardening-progress-log.txt](./artifacts/hardening-progress-log.txt).
  **This round's evidence:** [hardening-r5-lifecycle.txt](./artifacts/hardening-r5-lifecycle.txt)
  (start/stop, production serving, graceful shutdown),
  [hardening-r5-offline.txt](./artifacts/hardening-r5-offline.txt) (registry probe,
  orphan reaping), [hardening-r5-logs-firstrun.txt](./artifacts/hardening-r5-logs-firstrun.txt)
  (rotating log, first-run panel), [hardening-r6-guardrails.txt](./artifacts/hardening-r6-guardrails.txt)
  (L-1/L-2/L-5/L-6/L-8), [hardening-r6-gate-closure.txt](./artifacts/hardening-r6-gate-closure.txt)
  (the exit gate, zero exemptions), [acceptance-local.txt](./artifacts/acceptance-local.txt)
  (the real end-to-end run) and [hardening-r7-delete-busy.txt](./artifacts/hardening-r7-delete-busy.txt)
  (BE-20).
- **Measured suite size, 2026-10-11 20:41 (after R3, R4, R5 and R6):** backend
  **435 passed, 0 xfailed, 2 warnings** + ruff clean
  ([hardening-r6-gate-closure.txt](./artifacts/hardening-r6-gate-closure.txt)); frontend
  **153 tests in 24 files** + typecheck + eslint (0 errors / 9 warnings) + build green
  ([hardening-r5-logs-firstrun.txt](./artifacts/hardening-r5-logs-firstrun.txt)). The 2
  xfails R3 held out were promoted to passing tests when R3 landed — 0 remain. Both counts move
  while R7 lands — re-measure rather than trusting these; the pre-program
  baseline for comparison is
  [baseline-vitest.txt](./docs/reviews/2026-10-11-full-app-review/evidence/baseline-vitest.txt)
  and
  [baseline-pytest.txt](./docs/reviews/2026-10-11-full-app-review/evidence/baseline-pytest.txt).
- M5 delivered: design system + UI primitives, app shell (3-col, Settings
  modal, responsive), honest states (errors/loading/empty/confirms),
  per-session chat store + history endpoint + markdown, rich approval cards
  with always-allow policy, accessible code file list + language detection +
  save indicator, real preview state via preview endpoints + polling,
  favicon/title/theme toggle. 53 frontend tests PASS (count as of 2026-09-29), typecheck clean,
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
  **Resolved 2026-10-05, re-checked 2026-10-11 (R0-T2):** the root-workspace
  restructure landed (P3a) and the prettier sweep landed (P3b); `format:check`
  is green again and stays in the frontend CI job, after R0-T2 re-formatted one
  later untracked test file (`CommandPalette.test.tsx`) by exact path — that is
  review finding DOC-01; the 14 warnings became 9 (P3c).
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
  Validation: 190 backend tests + ruff clean; 86 frontend tests (count as of
  2026-10-05) + eslint (0 errors / 14 warnings) + typecheck; a 5-check live probe over a real socket
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
  source command. Validation: install 364 packages; build PASS; 86 vitest
  (count as of 2026-10-05); typecheck; eslint 0 errors / 14 warnings; 190
  pytest; ruff clean. Evidence:
  [p3a-all.txt](./artifacts/p3a-all.txt).
- 2026-10-05 P3b — the prettier sweep — **done** (the user said "start P3a, P3b
  and P3c"). `pnpm format` reformatted 37 files (595 insertions, 184
  deletions — whitespace/line-width only, no semantic change).
  `format:check` passes and joined the frontend CI job. **Gotcha:** a
  `format:check` run immediately after `--write` in the same script reported
  one file still unformatted; a second check passed — verify with a
  standalone `format:check`. Validation: 86 vitest, typecheck, build, eslint
  0 errors / 14 warnings all still PASS. Evidence:
  [p3b-before.txt](./artifacts/p3b-before.txt),
  [p3b-after.txt](./artifacts/p3b-after.txt),
  [p3b-verify.txt](./artifacts/p3b-verify.txt).
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
  **Resolved by task 16 (2026-10-04), re-verified 2026-10-11:** the shared
  workspace walk returns **10 paths, 0 under `node_modules`** for the E2E
  workspace `2943b651ae98` — evidence
  [probes/file_count_probe.py](./docs/reviews/2026-10-11-full-app-review/probes/file_count_probe.py),
  recorded as [DOC-04](./docs/reviews/2026-10-11-full-app-review/04-docs-and-process.md).

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
  **Corrected 2026-10-11:** the restructure landed (P3a, 2026-10-05), the
  prettier sweep landed (P3b, 2026-10-05), `format:check` **is** in the frontend
  CI job, and the warning count is 9 (P3c), not 14. R0-T2 of the hardening
  program re-formatted one later untracked test file by exact path.

- 2026-10-11 (M7 UI/UX overhaul): keep the visual identity and rebuild the **structure** on a real
  type system — self-hosted IBM Plex Sans/Mono, an 11/12/13/14/16/20/24/28 scale, tracking tokens, and
  a measure; the palette, accent and semantic colours are untouched. The conversation is the primary
  column and the side column is `clamp(320px, 34%, 560px)`, user-resizable, with Preview and Code as
  **tabs**. Scope is the whole interface: timeline, workspace, sidebar, composer, onboarding,
  accessibility and tests. `styles/app.css` was **deleted** and every component rule now lives inside
  `@layer components`, because unlayered CSS beats all layered CSS and one unlayered feature sheet
  silently overrode the whole system. The transcript is **event-sourced**: every SSE event is folded
  into the timeline, tool calls included, where the client previously discarded everything but the
  text. WCAG 2.2 AA is the recorded accessibility target (`apps/vibe/PRODUCT.md`,
  `apps/vibe/DESIGN.md`). Open decisions carried forward: repo-wide `ruff format`, `vibe backup` from
  the launchers, backup retention of 7, deleting the confirmed-dead `lib/markdown.tsx` and its
  `react-markdown` dependency, and whether to add a skip link for the transcript.

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
