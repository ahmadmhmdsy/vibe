# TASKS.md — live task list

One row per task; the table is the current truth, rewritten in place as
states change. Statuses: `pending` → `in_progress` → `done`, or
`blocked` (always say what gates it). User-gated tasks do not start
without the user's explicit go. Evidence links make every status
auditable.

Seeded from the approved design spec (2026-09-28). TASKS.md owns live
status; HANDOFF.md owns the narrative.

## Now

| # | Task | Status | Gate / next action | Evidence |
|---|---|---|---|---|
| 1 | User reviews the design spec | `done` | approved 2026-09-28 | docs/superpowers/specs/2026-09-28-vibe-coding-app-design.md |
| 2 | Write the implementation plan (writing-plans skill) | `done` | complete | docs/superpowers/plans/2026-09-28-m1-core-loop.md |
| 3 | M1 backend: FastAPI + LangGraph scaffold, AgentRuntime seam, ToolRegistry | `done` | core loop proven | services/vibe/src/vibe/{api,runtime,tools}/ |
| 4 | M1 backend: LocalSubprocessExecutor, provider seam, EventLog + SessionStore, SSE | `done` | verified in E2E | services/vibe/src/vibe/{providers,events,store}/ |
| 5 | M1 backend: auto-run verify-fix policy | `done` | ran in E2E (build after file change) | services/vibe/src/vibe/autorun/ |
| 5b | M1 backend: wire UsageTracker into runtime + expose /usage endpoint | `done` | records usage_metadata. **Corrected 2026-10-04:** the endpoint was not fully live — `by_model` was hardcoded `[]` and `total_cache_write_tokens` hardcoded 0. Both now aggregate real records | services/vibe/src/vibe/usage/tracker.py; services/vibe/tests/test_bridge_fixes.py |
| 6 | M1 frontend: Vite + React + TS scaffold, feature modules | `done` | all feature modules exist | apps/vibe/src/features/ |
| 7 | M1 frontend: chat, preview, code (Monaco), sessions, settings | `done` | all panels exist | apps/vibe/src/features/ |
| 8 | M1 E2E smoke: prompt → generate → build → run → preview → auto-fix | `done` | PASS 2026-09-29 (longcat only) | E2E run session ae75b0d6738a |
| 13 | CORS fix: configurable VIBE_CORS_ORIGINS | `done` | commit 47edd56 | services/vibe/src/vibe/config.py, api/app.py |
| 14 | Bridge audit: every frontend↔backend API call + the SSE live stream | `done` | all 24 API calls verified live against the running backend; browser E2E confirmed. Root cause of "no agent response": SSEClient.parse required the `data: ` prefix that EventSource.onmessage already strips, so every event was dropped — fixed with a fallback + try/catch, 2 regression tests | apps/vibe/src/lib/sse.ts; apps/vibe/src/lib/__tests__/sse.test.ts |
| 15 | Frontend polish pass (impeccable: review → enhance → polish, identity kept) | `done` | 12 measured defects fixed; 63 tests, typecheck, build PASS; axe-core 0 violations at 390px (chat/code/preview) and 1440px; detector clean | .impeccable/captures/2026-09-30-polish-verification.md |
| 16 | Backend: exclude vendored dirs (node_modules, dist) from GET /sessions/{sid}/files | `done` | resolved 2026-10-04: one shared walk (`vibe/workspace.py`) prunes node_modules/.git/.venv/dist/build/coverage for the HTTP route, the chat file snapshot, and the list_files tool | services/vibe/src/vibe/workspace.py; services/vibe/tests/test_bridge_fixes.py |
| 17 | Bridge fixes: SSE fan-out + monotonic seq, real Stop/abort, provider PATCH field names, usage by_model, session-id 404s, workspace prune, path encoding, message ids | `done` | 2026-10-04: 75 backend + 76 frontend tests, typecheck, build, and a live ASGI/SSE run all PASS | artifacts/pytest-after.txt; artifacts/live-verification.txt; artifacts/vitest-after.txt |
| 18 | Live bridge harness — deterministic runtime over the real ASGI/SSE stack (streaming + abort), no LLM or network needed | `done` | 2026-10-04: reusable; two subscribers verified identical | services/vibe/tests/live/ |
| 19 | Codebase audit — structure, reusability, extensibility (first-hand, every claim carries file:line) | `done` | 2026-10-04: 5 high / 10 medium findings, 15 missing implementations, a hygiene list, a target structure and a 5-phase plan | docs/architecture/2026-10-04-codebase-audit.md |
| 20 | 2026-10-11 full app review + local production hardening program | `done` | review **done** (48 findings; **BE-20**, **BE-21**, **BE-22** and **BE-23** were found by the program's own acceptance run, its re-runs and the first real browser run, **BE-24** by the CLI smoke and **FE-16** by the browser re-check, all fixed in the same phase); program **R0-R6 done**, R7 verified - release-check **8/8 green**, acceptance **RESULT: PASS**, the M1-M11 browser checks run for real and re-run on the fixed build (**7 PASS / 1 FAIL / 2 BLOCKED / 1 SKIPPED**, the FAIL being **FE-16**, now fixed); final orchestrator gate **464 backend / 160 frontend** tests green, ruff, tsc, eslint, prettier and build all clean | docs/reviews/2026-10-11-full-app-review/FINDINGS.md; docs/superpowers/plans/2026-10-11-local-production-hardening.md |
| 21 | UI/UX overhaul — rebuild the interface on a real design system (M7) | `done` | 2026-10-11: Phases A–G complete — axe-core 0 violations at 1440 dark / 1440 light / 1024 / 390, contrast 0 violations, frontend 32 files / 290 tests green, backend `ruff` green; see the M7 section below; the review that scoped it is `docs/reviews/2026-10-11-ui-ux-review/README.md` (Nielsen 22/40, UX-01…UX-12) and the approved plan is `docs/superpowers/plans/2026-10-11-ui-ux-overhaul.md` | docs/superpowers/plans/2026-10-11-ui-ux-overhaul.md |
| 22 | Competitor parity program (M8, C1–C6) | `pending` | **User-gated** — pick a phase to start; research and plan landed 2026-10-16 | docs/superpowers/plans/2026-10-16-competitor-parity.md; docs/research/2026-10-16-competitive-analysis.md |

## Structural work — audit 2026-10-04 (P0+P1+P2+P3+P3a+P4+P5+P6 done)

| Phase | Task | Status | Gate / next action | Evidence |
|---|---|---|---|---|
| P0 | Portability & safety: expanduser the workspace root + migrate the literal `~` data; `%~dp0` in launchers; gitignore the artefact; relocate evidence files; drop root clutter | `done` | 2026-10-04, approved by the user ("P0 + P1 together"). Workspace root now expands+resolves; 23 dirs / 25 rows merged into `~/vibe-workspaces` with a backup; the three original `~` roots are **left in place for the user to delete after verifying**. `Settings.host`/`VIBE_HOST` added and `__main__` wired to Settings | artifacts/p0p1-e2e.txt; services/vibe/scripts/merge_workspaces.py |
| P1 | Lifecycle & integrity: sqlite-backed EventStore; delete cascade (dev server, executor, policy, events, workspace); drain the dev-server pipe; wire or delete the idle timeout; WAL + lock + to_thread; migration table | `done` | 2026-10-04. History survives a real process restart (proven end-to-end); DELETE cascades and moves the workspace to `.trash/`; dev servers stop before restart and are reaped when idle; WAL + `threading.Lock` + `asyncio.to_thread`; `PRAGMA user_version` migrations on both databases | artifacts/p0p1-pytest.txt; artifacts/p0p1-e2e.txt |
| P2 | Seams: Container + Depends; SessionService/MessageService; provider registry; resolve the dead provider trio (Settings.host and __main__-uses-Settings were pulled forward into P0) | `done` | 2026-10-05. Handlers now declare a deps: App parameter and never touch app.state; the container is frozen and swapped whole via dataclasses.replace. The provider trio was **deleted** (dead *and* broken — ChatOpenAI was built with no model=), leaving one registry behind build_llm_factory. Path confinement and the history projection moved into vibe/services/, so both are testable without standing up FastAPI | artifacts/p2-pytest.txt (136 passed); artifacts/p2-ruff.txt; artifacts/p2-live.txt (22 PASS / 0 FAIL); artifacts/p2-vitest.txt; artifacts/p2-typecheck.txt; artifacts/p2-build.txt; artifacts/p2-eslint.txt |
| P3 | Developer experience: logging; ruff + eslint + prettier; `vitest run` default; CI; packageManager pin | `done` | 2026-10-04. H5 closed: `vibe/logging_setup.py` + `getLogger` in app/lifecycle/executor/chat, and the swallowed reaper failure now logs with a traceback. ruff configured; **all 136 findings fixed** (118 auto, 18 by hand) and the suite still passes. eslint flat config + prettier config; `pnpm test` is now `vitest run`; CI added; pnpm pinned | artifacts/p3-ruff.txt; artifacts/p3-pytest.txt; artifacts/p3-eslint.txt; artifacts/p3-logging.txt; artifacts/p3-vitest.txt |
| P3a | Root workspace + unified scripts (one install at the root, `pnpm -r` scripts) | `done` | 2026-10-05, approved by the user ("start P3a, P3b and P3c"). Root `package.json` (private, `packageManager` pin, unified scripts) + root `pnpm-workspace.yaml` (`packages: ["apps/*"]` + the `allowBuilds: esbuild` setting moved up from `apps/vibe/pnpm-workspace.yaml`, which is now gone). One `pnpm install` at the root covers the workspace; `pnpm --filter vibe {dev,build,test,typecheck,lint,format}` all run inside `apps/vibe`, and `pnpm test:backend` / `pnpm lint:backend` reach the Python venv. **Verified:** install 364 packages; build PASS; 86 frontend tests; typecheck; eslint 0 errors / 14 warnings; 190 backend tests; ruff clean. **Gotcha:** the backend scripts need a leading `.\` — pnpm runs them through `cmd`, and a bare `.venv\...` is parsed as the `.` source command | artifacts/p3a-all.txt |
| P3b | Prettier sweep (`pnpm run format`) | `done` | 2026-10-05, approved by the user ("start P3a, P3b and P3c"). `pnpm format` reformatted 37 files (595 insertions, 184 deletions — whitespace/line-width only, no semantic change). `format:check` now passes and was added to the frontend CI job. **Verified:** 86 vitest, typecheck, build, eslint 0 errors / 14 warnings all still PASS. **Re-checked 2026-10-11 (R0-T2):** a later untracked test file (`CommandPalette.test.tsx`, added with P3c) had made `format:check` red again — review finding DOC-01 — so it was re-formatted by exact path; that file now passes `prettier --check` (exit 0) and its 7 tests PASS, and the repo-wide check is re-verified in `artifacts/hardening-r0-docs.txt`. `format:check` may now be kept in CI | artifacts/p3b-before.txt; artifacts/p3b-after.txt; artifacts/p3b-verify.txt; artifacts/hardening-r0-docs.txt |
| P3c | React-hooks triage: 2× `refs` + 3× `set-state-in-effect` | `done` | 2026-10-05. `useMediaQuery` → `useSyncExternalStore` (canonical external-store subscription, no effect); `useKeyboardShortcut` + `usePolling` → the "latest ref" write moved into an effect (no ref write during render); `CommandPalette` → the two reset effects replaced by a render-phase state adjustment (`prevOpen`) + an `onChange` selection reset, so the first paint of an open palette is already clean. 18 new tests (4 + 7 + 7). **Verified:** 104 vitest (was 86), typecheck, build, eslint 0 errors / 9 warnings (was 14 — the 5 P3c findings are gone; the remaining 9 are 8 `exhaustive-deps` + 1 `react-refresh`, out of P3c scope) | artifacts/p3c-eslint-before.txt; artifacts/p3c-eslint-after.txt; artifacts/p3c-vitest.txt; artifacts/p3c-typecheck.txt; artifacts/p3c-build.txt |
| P4 | Product gaps: titles from first message; pagination + `X-Total-Count`; error taxonomy; M6 honesty fix; README corrected | `done` | 2026-10-05. Sessions auto-title from the first user message while the title is still the `Untitled xxxx` placeholder (a manual rename is never clobbered). `GET /sessions/{sid}/messages` returns the latest 200 by default (`limit` 1-1000, `offset` counts back from the newest) and reports the real total in `X-Total-Count` (CORS-exposed); the frontend prepends older pages behind a "Load older messages" button. Every API error answers `{"error": {"code", "message"}}` with a stable machine-readable code. `read_console_logs`/`screenshot` now return `None` ("no driver") rather than `""` ("clean"), so the autorun loop no longer claims a check it cannot make (M6). README's false console-log / screenshot / runtime-error claims corrected, and the port-7321 pinning replaced with the auto-increment reality. **Left open, `NEEDS_USER_DECISION`:** a browser driver for real console/screenshot capture; any auth story beyond loopback. **The browser driver was resolved 2026-10-05 — see P5.** | artifacts/p4-pytest.txt (161 passed); artifacts/p4-ruff.txt; artifacts/p4-live.txt (22 PASS / 0 FAIL); artifacts/p4-live-probe.txt (13 PASS / 0 FAIL); artifacts/p4-vitest.txt (86 passed); artifacts/p4-typecheck.txt; artifacts/p4-build.txt; artifacts/p4-eslint.txt |
| P5 | The browser driver: Playwright console capture + screenshots that reach the model | `done` | 2026-10-05, the user chose "A. Implement Playwright". `vibe/executor/browser.py` owns the Playwright lifecycle (lazy launch, TCP readiness wait, `console`/`pageerror` listeners attached before `goto`, level filtering, real PNG screenshots, idempotent `close()`); every method returns `None` when Playwright or the browser binary is absent. `ToolResult.attachments` + `response_format="content_and_artifact"` carry an image to the model as a content block while keeping base64 out of the SSE stream, and `is_error` now reaches the event stream. **Also found and fixed:** pnpm 12 forwards `--` literally, so Vite ignored `--port` and every session collided on 5173 — the `--` is gone and the dev-server test now asserts something is *listening* on the port. **Left open, `NEEDS_USER_DECISION`:** any auth story beyond loopback (design delivered, awaiting the user's scope call) | artifacts/p5-pytest.txt (177 passed); artifacts/p5-ruff.txt; artifacts/p5-browser.txt |
| P6 | Loopback auth: machine-level deny-by-default + OriginGuard (CSRF) | `done` |
  2026-10-05, the user approved the recommendation (one user, one machine, local now,
  reusable/scalable later). `vibe/auth.py` — `Principal`, `Authenticator` protocol,
  `LoopbackAuthenticator` (accepts `request.client is None` or a host in {`127.0.0.1`,
  `::1`, `localhost`, `testclient`}); `Principal.id` is always `"local"`.
  `require_principal` raises `ApiError(UNAUTHENTICATED)` (401) on `None`, and all seven
  routers are mounted with `dependencies=[Depends(require_principal)]` so the default is
  deny and `/health` stays open. `OriginGuard` refuses state-changing methods whose
  `Origin` is not in `VIBE_CORS_ORIGINS` with `403 forbidden_origin` — a second,
  independent control, because loopback auth cannot catch CSRF (a cross-site POST from
  the user's own browser arrives from `127.0.0.1`). Seam: `Container.build(authenticator=...)`
  + `Settings.auth_mode`/`VIBE_AUTH_MODE`; an unknown mode raises `ValueError` rather than
  downgrading. **Deliberately out of scope:** no token (security theatre, and it breaks
  `start.bat`); no users/ownership — multi-user later means `owner_id` on sessions + an
  ownership check in `require_session` + a filtered `SessionStore.list` |
  artifacts/p6-pytest.txt (190 passed); artifacts/p6-ruff.txt;
  artifacts/p6-vitest.txt (86 passed); artifacts/p6-typecheck.txt;
  artifacts/p6-eslint.txt |

## Later

| # | Task | Status | Gate / next action | Evidence |
|---|---|---|---|---|
| 9 | M2: multi-session management, model picker, provider settings UI | `done` | sessions sidebar (rename/badge/activity), model picker persists to session, provider settings (key status + custom provider CRUD) | apps/vibe/src/features/{sessions,chat,settings}/; services/vibe/src/vibe/providers/custom.py |
| 10 | M3: image input, Monaco hand-editing, supply-chain approval, budgets, a11y, tests | `done` | all M3 features complete + tested | services/vibe/src/vibe/{supply_chain,approvals,usage/,api/routes/approvals.py}; apps/vibe/src/features/{chat,code}/ |
| 11 | M4: Docker executor, Postgres, auth, deployment | `pending` | gated on M3 | — |
| 12 | M5: frontend UI/UX overhaul — design system, shell, states, chat, approvals, code, preview | `done` | all 8 tasks complete; verified in browser (desktop + mobile) | docs/superpowers/plans/2026-09-29-m5-frontend-ui-ux-overhaul.md; commits 504be45..47edd56 |
| 12.1 | Task 1: design tokens, global styles, UI primitives | `done` | 13 tests | apps/vibe/src/styles/, apps/vibe/src/components/ui/ |
| 12.2 | Task 2: app shell — 3-col layout, header, Settings modal, responsive | `done` | 4 tests; browser-verified | apps/vibe/src/App.tsx |
| 12.3 | Task 3: honest states — errors, loading, empty, delete confirms | `done` | error banners, spinners, empty states, ConfirmDialog | apps/vibe/src/lib/api.ts + panels |
| 12.4 | Task 4: chat — per-session store, history, markdown, composer | `done` | messages endpoint + react-markdown. **Corrected 2026-10-04:** the stop button did nothing — it set a store flag no code read and never called the backend. It now POSTs `/sessions/{sid}/abort`, which cancels the run task | apps/vibe/src/features/chat/Composer.tsx; services/vibe/src/vibe/api/routes/chat.py |
| 12.5 | Task 5: approval flow — rich cards | `done` | always-allow localStorage policy; 6 tests | apps/vibe/src/features/chat/ApprovalCard.tsx |
| 12.6 | Task 6: code panel — accessible file list, language detect, save indicator | `done` | aria-pressed file buttons; detectLanguage; Saving/Saved | apps/vibe/src/features/code/ |
| 12.7 | Task 7: preview panel — real backend state | `done` | preview endpoints + polling store; 4 tests | apps/vibe/src/features/preview/ + services/vibe/src/vibe/api/routes/preview.py |
| 12.8 | Task 8: polish pass — favicon, title, theme toggle, verification sweep | `done` | 53 tests, typecheck, build, a11y 0 violations (desktop+mobile) | apps/vibe/index.html, apps/vibe/src/lib/theme.ts |

## Local production hardening — 2026-10-11

Findings register: [docs/reviews/2026-10-11-full-app-review/FINDINGS.md](./docs/reviews/2026-10-11-full-app-review/FINDINGS.md) (42; BE-19 was added during R3).
Approved plan: [docs/superpowers/plans/2026-10-11-local-production-hardening.md](./docs/superpowers/plans/2026-10-11-local-production-hardening.md).
One row per phase; each phase's exit gate is a command whose raw output goes to an evidence artifact.
Per phase: one commit per task, exact paths only, and a `code-review` verdict recorded before the next phase starts.

| Phase | Name | Status | Exit gate / next action | Evidence |
|---|---|---|---|---|
| **R0** | Truth and bookkeeping | `done` | 2026-10-11: `pnpm format:check` **PASS** (exit 0, `All matched files use Prettier code style!`, re-run 19:06 after the concurrent frontend session finished its own formatting; it was `BLOCKED by an external cause` until then); the document audit is clean and every path R0 touched is intended. The tree also carries the concurrent R1/R4 work — 61 dirty entries at 19:06, itemized in the evidence file | artifacts/hardening-r0-docs.txt |
| **R1** | Correctness under concurrency and cancellation | `done` | 2026-10-11: all four tasks landed, each seen to fail first (two concurrent sends both returned 200; a grandchild outlived the timeout; a failed delete left 0 events with the session row still present). Orchestrator gate re-run: `212 passed, 21 xfailed` and `ruff: All checks passed!` | `artifacts/hardening-r1-pytest.txt`; `artifacts/hardening-r1-probe4.txt`; `artifacts/hardening-r1-probe5.txt`; `artifacts/hardening-gate-r0r1r4.txt` |
| **R2** | Validation and secrets | `done` | 2026-10-11: strict-xfail count **21 → 2** (only R3's BE-03/BE-07 remain). Every JSON route takes a declared model; validation is 400 `validation_failed` with a field path; allowlist bypass closed for protocol/path/junk specifiers; provider store locked + atomic + quarantining. Orchestrator gate: `276 passed, 2 xfailed` and `ruff: All checks passed!` | `artifacts/hardening-r2-pytest.txt`; `artifacts/hardening-r2-custom-providers.txt`; `artifacts/hardening-gate-r2-r5t1.txt` |
| **R3** | Product completeness | `done` | 2026-10-11: all eight tasks. BE-03 (conversation replayed, `VIBE_HISTORY_MESSAGES`), BE-08 (auto-fix turns recorded and streamed, Stop reaches the loop), BE-07 (warning formattable), BE-19 (system prompt from code/env + a read-only `GET /settings`), BE-09 (no-dev-server and no-driver told apart), BE-10 (dead branch deleted, session timestamps, generic 500 + error id), BE-11 (`.trash` swept at startup and on delete, default 14 days, 0 disables), BE-12 (event index via migration; deferred, indexed, measured). Orchestrator gate: `397 passed, 0 failed`, `ruff: All checks passed!`, lifespan sweep proven by a real startup. The GUI prompt field is a frontend follow-up | `artifacts/hardening-r3-report.txt`; `artifacts/hardening-r3b-report.txt`; `artifacts/hardening-r3b-pytest.txt`; `artifacts/hardening-r3-live.txt`; `artifacts/hardening-r3-lifespan.txt`; `artifacts/hardening-gate-r3.txt` |
| **R4** | Frontend trust and UX | `done` | 2026-10-11: all fifteen findings fixed, plus a follow-up turn (platform-aware New-session shortcut, root error-boundary test). Orchestrator gate: `vitest 23 files / 138 tests`, `tsc` exit 0, `eslint 0 errors / 9 warnings`, `build` 393.31 kB, `prettier --check .` exit 0. M1-M11 browser checks remain SKIPPED for R7 | `artifacts/hardening-r4-vitest.txt`; `artifacts/hardening-r4-followup.txt`; `artifacts/hardening-r4-lint.txt`; `artifacts/hardening-r4-manual-pending.md`; `artifacts/hardening-gate-r0r1r4.txt` |
| **R5** | Local packaging and operations | `done` | 2026-10-11: T1 doctor, T2 one-command serve, T3 static SPA, T4 first-run, T5 rotating logs, T6 graceful shutdown, T7 backup/repair, T8 offline detection, T9 orphan reap, T10 release + acceptance scripts, T11 README rewrite and `docs/guides/local-setup.md`. Exit gate `scripts/acceptance-local.ps1` steps 1-2 and 5-7 PASS | `artifacts/hardening-r5-doctor.txt`; `artifacts/hardening-r5-lifecycle.txt`; `artifacts/hardening-r5-logs-firstrun.txt`; `artifacts/hardening-r5-offline.txt`; `artifacts/hardening-r5-backup.txt`; `artifacts/acceptance-local.txt` |
| **R6** | Scalability seams | `done` | 2026-10-11: all eight landed - T1 owner column (store v1->v2, events v2->v3), T2 SQL confined to store providers, T3 executor only through its protocol, T4 identity only from `Principal`, T5 `SessionKey` registries, T6 zero environment exemptions, T7 one frontend API base, T8 migrations only through `user_version`. Exit gate `tests/test_seams.py` PASS at `_ENV_EXEMPTIONS = {}` | `artifacts/hardening-r6-guardrails.txt`; `artifacts/hardening-r6-gate-closure.txt` |
| **R7** | Release verification | `done` | 2026-10-11: `scripts/release-check.ps1` **PASS - 8/8 steps green** (`artifacts/release-check-final.txt` at 459, then re-run after BE-23: **`artifacts/release-check-post-be23.txt` - PASS, 8/8 steps green, backend 464 passed / frontend 158 tests** / build clean), acceptance `summary: 0 FAIL/BLOCKED, 1 SKIPPED`, **RESULT: PASS** (`artifacts/acceptance-local.txt`), step 6a green after the BE-20 fix; **BE-21**, **BE-22** and **BE-23** were found here and fixed (BE-22 event-seq race **High**; BE-23 prod OriginGuard **High**, `artifacts/hardening-be23-prod-origin.txt` + `artifacts/hardening-be23-prod-origin-orchestrator.txt`); the M1-M11 browser checks ran for real in prod mode (`artifacts/hardening-r7-browser-checks.txt`: 1 PASS, 1 FAIL, 2 SKIPPED, 7 BLOCKED, all behind BE-23) and re-run on the fixed build (`artifacts/hardening-r7-browser-recheck.txt`: **7 PASS, 1 FAIL, 2 BLOCKED, 1 SKIPPED** - M6 now passes from all three entry points, so the pre-fix failure was the OriginGuard 403 and not the key binding; the one FAIL is **FE-16**, a `Jump to latest` control shown when the transcript cannot scroll, fixed with two regression tests). Check scripts require PowerShell 7 (`#Requires -Version 7.0`, run with `pwsh`). Remaining: three open user decisions (repo-wide `ruff format`, `vibe backup` from the launchers, backup retention of 7), carried forward into the M7 section below. |

### R0 task detail

| Task | Change | Status | Verification | Evidence |
|---|---|---|---|---|
| R0-T1 | Record DOC-07 in the review; update the register and counts | `done` | 41 findings (**not** the plan's 40 — the plan's arithmetic was off by one; noted as a deviation). The live register is **42** after BE-19 was registered by R3-T4. DOC-07 sits before `## TEST-01` to keep the DOC-* findings contiguous, also a noted deviation | docs/reviews/2026-10-11-full-app-review/{FINDINGS.md,04-docs-and-process.md,README.md} |
| R0-T2 | Format the single red file | `done` | `prettier --check` on that path exits 0; `vitest run` on it: **1 file / 7 tests PASS**; the repo-wide `pnpm format:check` then exited 0 as well (re-run 19:06, once the concurrent frontend session stopped mid-writing) | apps/vibe/src/components/ui/__tests__/CommandPalette.test.tsx; artifacts/hardening-r0-docs.txt |
| R0-T3 | Refresh CURRENT_STATE.md | `done` | Git block re-measured (`git status --porcelain`, 49 entries, two epochs); Active-jobs ports re-verified (no listener on 7321/7322/5173/7399); the three conflicting test counts dated; DOC-04 closed; one measured frontend count (104 tests / 18 files) | CURRENT_STATE.md |
| R0-T4 | Correct ENVIRONMENT.md | `done` | the false Playwright row replaced (driver + dep + install step, re-verified 2026-10-11); the CI row labeled `SKIPPED` with the two known first-run failures; the prettier/warning row corrected to 9 (artifact) | ENVIRONMENT.md |
| R0-T5 | Register the two new document kinds | `done` | two document-map rows added and the Architecture-audit row extended; the immutable-review rule written | AGENTS.md; docs/reviews/README.md |
| R0-T6 | TASKS/HANDOFF/PLAN bookkeeping | `done` | the split `## Now` table repaired; this section created; PLAN.md gained M6, M4 moved to `deferred`, and the §4 open items corrected (the workspace-scaffolding item **stays** — verified not implemented: `workspace.py` only enumerates, `ensure_workspace` only mkdirs) | TASKS.md; HANDOFF.md; PLAN.md |
| R0-T7 | MEMORY decisions, lessons, milestones | `done` | user decisions D1–D6 recorded with date and reason; five lessons recorded | MEMORY.md |

### R3 task detail

| Task | Change | Status | Verification | Evidence |
|---|---|---|---|---|
| R3-T1 | Replay the conversation: the route reads the log's transcript through `MessageService.history` and appends this turn; `Settings.history_messages` (default 24, `VIBE_HISTORY_MESSAGES`) caps it | `done` | `tests/test_history.py` un-xfailed plus a new cap case; probe 3 re-run prints the second turn's three messages. Before: every turn carried exactly one message | `artifacts/hardening-r3-report.txt`; `artifacts/hardening-r3-probes.txt` |
| R3-T2 | The auto-fix turn is recorded: new `vibe/services/turns.py` (`TurnRecorder`), `autorun/policy.py` logs the prompt and the answer and publishes tool calls; `AgentContext.is_aborted` lets Stop reach the loop | `done` | three new cases in `tests/test_autorun.py` PASS — logged tool call, logged prompt, assistant text, and a stopped loop that never builds | `artifacts/hardening-r3-report.txt` |
| R3-T3 | One placeholder and one argument in the VIBE_HOST warning | `done` | `tests/test_logging_setup.py` un-xfailed; probe 6 re-run: no formatting errors, warning present | `artifacts/hardening-r3-probes.txt` |
| R3-T4 (backend half) | The system prompt: `vibe/prompts.py` (`DEFAULT_SYSTEM_PROMPT`, `system_prompt_for`), `AgentInput.system`, `build_messages` puts it first, `Settings.system_prompt`/`VIBE_SYSTEM_PROMPT` overrides, chat route and fix loop both send it | `done` | `tests/test_system_prompt.py` **8 passed** (stack named, blank override falls back, system message first, no invented prompt, route wiring, override wins) | `artifacts/hardening-r3-report.txt` |
| R3-T5 | BE-09: the two causes no longer collapse — no dev server names `run_dev_server` (and the executor is never called), a live server with no driver says so | `done` | `tests/test_browser_tools.py` (7 cases, 4 failed first); probe: 0 executor calls with no dev server | `artifacts/hardening-r3b-pytest.txt` |
| R3-T6 | BE-10: unreachable `usage is None` branch deleted; `GET /sessions/{sid}` matches the list shape; unexpected failures send `500 internal` + `error id <8hex>` with the detail logged under the same id | `done` | `tests/test_api_gaps.py` (10 cases, 4 failed first); probe: raw exception text in the body False | `artifacts/hardening-r3b-pytest.txt` |
| R3-T7 | BE-11: `sweep_trash` removes only `<workspace>/.trash` entries matching our own `<12hex>-<date>-<time>` naming and older than `VIBE_TRASH_RETENTION_DAYS` (default 14, 0 disables); wired at startup and after delete | `done` | `tests/test_retention.py` (9 cases, 9 failed first); real startup: a 30-day entry removed and logged with its age, a fresh entry kept, a foreign name kept, retention 0 removed nothing | `artifacts/hardening-r3-lifespan.txt`; `artifacts/hardening-r3b-pytest.txt` |
| R3-T8 | BE-12: `user_version` 1→2 adds `idx_events_session_type_seq`, in place and idempotent; the store protocol was **not** rewritten | `done` | `tests/test_event_store.py` (5 cases, 4 failed first); `EXPLAIN QUERY PLAN` now uses the index; measured on 40k events: session+type median 182.7 µs → 103.4 µs, session-only reads unchanged. Label: deferred, indexed, measured | `artifacts/hardening-r3b-pytest.txt` |
| GUI prompt field | read-only `GET /settings` (`{system_prompt: {configured, effective, default, source}}`) plus a writable `PATCH /settings`; the persistence decision was to store the override in `<workspace>/settings.json` (never the environment, applies without a restart, an empty string clears it) | `done` | `SettingsPanel.tsx` renders the field with a source label, and `SystemPrompt.test.tsx` (5 cases) is green in the 160-test frontend suite | `artifacts/release-check-final-post-m5.txt` |

**R3 notes (from `artifacts/hardening-r3-report.txt`):** the prompt is deliberately not written to the event log (static configuration, not conversation — but two sessions under different `VIBE_SYSTEM_PROMPT` values cannot be told apart from their logs); the history projection replays text only, so prior tool traffic and earlier attachments are not resent; `TurnRecorder` is not yet adopted by the chat route (separate cleanup, as the plan says).

**Orchestrator additions after R3b (single writer, recorded not hidden):** the lifespan one-liner R3b could not reach is now in `api/app.py` (`sweep_trash` inside a `try/except`, so housekeeping can never block startup) and is proven against a real app startup; `tests/test_doctor.py`'s serving test was stale against the deliberate move to `uvicorn.Server` (needed for `/admin/shutdown`) and now asserts host/port through that mechanism instead of the removed `uvicorn.run` call; and the read-only `GET /settings` route was added to the already-mounted providers router, with the 404 "gap" test converted into a read-only guard.

### R5 task detail

| Task | Change | Status | Verification | Evidence |
|---|---|---|---|---|
| R5-T1 | Doctor preflight (`vibe doctor` + `doctor.bat`): ten checks, six blocking, every failure naming its exact remedy | `done` | `tests/test_doctor.py` **32 passed**; real runs exit 0 with 10 PASS, and exit 1 with the remedy printed when a listener holds the port; the contradiction found in the failing run is pinned by two regression tests. SKIPPED: server startup (port held by design) | `artifacts/hardening-r5-doctor.txt` |
| R5-T7 | `vibe backup` / `vibe repair`: timestamped snapshot dirs under `<workspace>/backups` with a manifest, a real restore, `PRAGMA integrity_check`, quarantine of a corrupt provider store, and pruning that only ever matches our own timestamp pattern (default keep 7) | `done` | Real runs in the evidence file: backup 24,654 bytes in 3 files; restore into a fresh workspace read the seeded row back; corrupt `providers.json` quarantined with the original bytes preserved; corrupt `sessions.db` left untouched with exit 1; `--keep 0` refused with exit 2; `python -m vibe --help` lists `{serve,doctor,backup,repair}`; the generated project survived every step | `artifacts/hardening-r5-backup.txt` |
| R6-T3 | Executor stays a protocol (L-3) | `done` | `container.py` named the concrete class six times; now twice (import + one construction) because the field types and the factory signature take `Executor`. Three scanners proven red on a planted offender in a scratch copy of the package and green on the real one; protocol-conformance test asserts a non-empty protocol first | `services/vibe/tests/test_seams.py` |
| R6-T4 | Identity only from the principal (L-4) | `done` | one `"local"` literal left, `auth.LOOPBACK_OWNER_ID`; the scanner finds exactly that one and zero elsewhere, zero allowlist entries | `services/vibe/tests/test_seams.py` |
| R6-T7 | One API base in the frontend (L-7) | `done` | real offender at `features/chat/MessageList.tsx:71` built its own origin; `API_BASE` is now exported from `lib/api.ts` and `SSEClient` defaults to it. Red proof flagged the planted file by name; green 8/8; full frontend suite 23 files / 140 tests, tsc exit 0 | `apps/vibe/src/lib/__tests__/api.test.ts`; `artifacts/hardening-r6-seams.txt` |
| R5-T2 | `stop.bat` + `POST /admin/shutdown`: graceful stop, then proof the port is free | `done` | POST is loopback-only and behind `require_principal`; GET answers 405 (a GET that stops a server is reachable from any page) | `artifacts/hardening-r5-lifecycle.txt` |
| R5-T3 | The built SPA is served by FastAPI in prod mode (`api/static.py`) | `done` | shell + assets from the backend port; a missing build says so instead of 404-ing the app | `artifacts/hardening-r5-lifecycle.txt` |
| R5-T4 | First-run panel: explains the app, opens Settings, fills the composer from an example | `done` | 13 new frontend tests (decision rule, visibility, panel, App integration); fail-first shown; frontend 153 passed, typecheck/lint/build green | `artifacts/hardening-r5-logs-firstrun.txt` |
| R5-T5 | Rotating log file under the workspace (2 MiB x 5), settings redaction, startup banner | `done` | 23 targeted tests; a real process wrote `<workspace>/logs/vibe.log`; redaction falsified by a planted key. Orchestrator then wired `configure_logging(settings=settings)` into `__main__.py`, which is what makes the default file activate | `artifacts/hardening-r5-logs-firstrun.txt` |
| R5-T6 | The dev server is stopped through the app, not by killing a window | `done` | `uvicorn.Server` held explicitly so shutdown is graceful; `tests/test_doctor.py` seam updated | `artifacts/hardening-r5-lifecycle.txt` |
| R5-T8 | Offline truth: an npm-registry probe with a message that says nothing was downloaded | `done` | one TCP connect, cached 300 s ok / 30 s fail; the doctor half is `NEEDS_USER_DECISION` (a new check name would break the pinned check set) | `artifacts/hardening-r5-offline.txt` |
| R5-T9 | Orphaned dev servers from a previous run are reaped at startup | `done` | `maintenance.reap_dev_servers` + the orchestrator's one-line wiring in `api/app.py` and two `tests/test_lifespan.py` tests (reap is called with the workspace; a failing reap cannot stop startup) | `artifacts/hardening-r5-offline.txt`, `artifacts/hardening-r5-lifecycle.txt` |
| R5-T10 | CI is real: `.github/workflows/ci.yml` + `acceptance.yml`, `scripts/release-check.ps1` | `done` | workflows added; `release-check.ps1` run on this checkout | `artifacts/hardening-final-checks.txt` |
| R5-T11 | Document the product for its actual user (AC-12) | `done` | README rewritten (requirements with versions, install, run, first run, troubleshooting by doctor check name, data locations, backup, uninstall, known gaps); `docs/guides/local-setup.md` added (provider keys, first app, offline notes, running the checks, uninstall); `AGENTS.md` document-map row added | `README.md`; `docs/guides/local-setup.md`; `AGENTS.md` |
| R6-T1 | `owner_id` on every persisted row (L-1) | `done` | store v1->v2 and events v2->v3, guarded `ADD COLUMN` + owner-first index, proven against a populated pre-migration DB; `tests/test_migrations.py` (9) | `artifacts/hardening-r6-guardrails.txt` |
| R6-T2 | SQL lives only in the store providers (L-2) | `done` | a statement-shaped scan with a planted offender it must find; zero exemptions | `artifacts/hardening-r6-guardrails.txt` |
| R6-T5 | Registries keyed by (owner, session) (L-5) | `done` | `SessionKey` keys the run registry, container executors/policies and lifecycle teardown; `tests/test_registry_keys.py` (7) | `artifacts/hardening-r6-guardrails.txt` |
| R6-T6 | `config.py` is the only reader of the environment (L-6) | `done` | closed by the orchestrator after R6: `config.local_app_data()`, `doctor` asks it, `logging_setup` no longer reads `VIBE_LOG_FILE`/`VIBE_LOG_LEVEL`; `_ENV_EXEMPTIONS` is empty | `artifacts/hardening-r6-gate-closure.txt` |
| R6-T8 | Migrations are the only schema writer (L-8) | `done` | `PRAGMA user_version` is the only DDL path; scan + planted offender | `artifacts/hardening-r6-guardrails.txt` |

**R0 deviations (all recorded in the evidence file):** the register total is 41, not 40; DOC-07 was inserted before `## TEST-01`; README's status cell — not a new count row — carries the count; ENVIRONMENT.md line 89 and the CURRENT_STATE.md Decisions bullet about prettier/CI were corrected beyond the plan's named edits; PLAN.md's Playwright and EventLog open items were removed as resolved.


## UI/UX overhaul — 2026-10-11 (M7)

Review: [docs/reviews/2026-10-11-ui-ux-review/README.md](./docs/reviews/2026-10-11-ui-ux-review/README.md) — Nielsen heuristic score **22/40**, twelve UX findings (UX-01…UX-12), plus the measured baseline in `artifacts/ui-review/report-01.json`.
Approved plan: [docs/superpowers/plans/2026-10-11-ui-ux-overhaul.md](./docs/superpowers/plans/2026-10-11-ui-ux-overhaul.md).
Product and design record: [apps/vibe/PRODUCT.md](./apps/vibe/PRODUCT.md), [apps/vibe/DESIGN.md](./apps/vibe/DESIGN.md).

Three user decisions taken at the gate (2026-10-11, all recommendations accepted): keep the identity and rebuild the structure on a real type system; the conversation stays primary with the side column at ~34%, resizable, Preview/Code as tabs; and the full scope — timeline, workspace, sidebar, composer, onboarding, accessibility and tests.

| Phase | Name | Status | Exit gate / next action | Evidence |
|---|---|---|---|---|
| **A** | Design system foundation | `done` | Self-hosted IBM Plex Sans/Mono (`fonts.css`, 12 font assets in the build), a real type scale and tracking set, control/touch/splitter/panel tokens, `color-scheme`, reduced-motion; `app.css` deleted in favour of `layout.css` + `primitives.css`; all new rules inside `@layer components` | apps/vibe/src/styles/{fonts,tokens,layout,primitives}.css |
| **B** | App shell and workspace | `done` | 4-track grid (`sidebar │ main │ splitter │ side`), `.app-shell` overflow 0 at every breakpoint, named landmarks, one `h1` (the session title), 79 stray `role="tooltip"` elements down to 0, `Splitter` on the side column, Preview/Code tabs owned by the shell, mobile single-track fix | apps/vibe/src/{App.tsx,app/} |
| **C** | Agent activity timeline (UX-02) | `done` | The transcript folds every SSE event — `tool_call`, `tool_result`, `assistant/error`, `error` — instead of discarding all but the text; `role="log"` with `aria-live="polite"`; fenced-code rendering replaced the markdown pipeline | apps/vibe/src/features/chat/ |
| **D** | Sessions sidebar | `done` | Recency grouping with real headings, roving tabindex (36 action triggers out of the tab order), one labelled row menu, inline rename with focus return, labelled search field, two distinct empty states, a live result count | apps/vibe/src/features/sessions/ |
| **E** | Preview and code workspace | `done` | The `.code-panel` height-0 defect fixed (a `flex-direction: row` with no `display: flex`); both panels on the same `.panel`/`.panel-header`/`.panel-body` contract; header carries the file path or URL, not a duplicate title; polling gated on the active tab | apps/vibe/src/features/{preview,code}/ |
| **F** | Composer and onboarding | `done` | First-run and settings rebuilt on the type scale and primitives (tabbed Providers / System prompt, skeleton → error+retry → content, `focusProviders` opens and focuses the form); composer toolbar (reference a file, prompt templates, model, plan/act), a data-driven 5-entry template library, a caret-aware slash listbox, and the Enter / Shift+Enter / Ctrl+Enter / IME contract. Plan/Act is a client-side prompt prefix and "Reference a file" inserts an editable path placeholder — the backend has no plan/act flag and no upload endpoint, so neither pretends to have one | apps/vibe/src/features/{chat,onboarding,settings}/ |
| **G** | Verification and close-out | `done` | Frontend gate green (`typecheck` exit 0, `lint` 0 errors / 5 pre-existing warnings, `vitest` 32 files / **290 tests**, `build` 595.23 kB / 161.63 kB gzip in 3.08s); backend `ruff` exit 0; **axe-core 0 violations** at 1440 dark, 1440 light, 1024 and 390; geometry re-measured at three viewports; `impeccable detect --json apps/vibe/src` returned `[]`; docs closed out | artifacts/ui-review/{report-m7.json,impeccable-detect-m7.json,pytest-m7.txt} |

**Phase G measured results** (2026-10-11, 1440×900 / 1024×768 / 390×844 — `artifacts/ui-review/report-m7.json`, all four states incl. light): `.app-shell` overflow `[0,0]` and `overflowX 0` at all three widths; desktop columns `260 / 684 / 6 / 490` with the conversation now the widest (was sidebar 260 / main 575 / side 605); **axe-core 0 violations** at 1440 dark, 1440 light, 1024 and 390; contrast violations **0** in every state; tab stops **30 of 36** before the composer at desktop, 31 of 32 at tablet, 27 of 31 at mobile (was ~114); the only visible font families are `IBM Plex Sans Variable` and `IBM Plex Mono`; the heading outline is real (`h1` session title → `h2` Sessions → `h3` recency groups); the sidebar is a right drawer at 1024 (hidden, then `560px` + scrim when toggled) and a left drawer at 390 with a single-track body and a 49px bottom tab bar; `main` measures `390×747` at mobile where it previously measured `0` wide; zero page errors and an empty console.

**Defects found by Phase G and fixed in it:** the `≤768px` grid pinned `.app-main` to a `0px` track, which collapsed the conversation to zero width on every phone (fixed by placing both panels in the single cell); the first three-viewport probe reported `visibility: hidden` elements as visible, so the tablet drawer looked broken when it was not (the probe was fixed, not the CSS); axe-core found three real accessibility defects — `aria-expanded` on the composer textarea (an attribute `textbox` does not support, and HTML-ARIA forbids the `combobox` role that would allow it on a `textarea`, so the open state is now carried by `aria-controls` plus `aria-activedescendant`), a nameless header search trigger once its label collapses to an icon under 900px, and the resize handle sitting outside every landmark (it is now rendered inside the section it resizes); and the visually-hidden file input duplicated the visible "Attach image" button as an invisible tab stop.

**Backend gate:** `ruff check .` exit 0. `pytest` is **7 failed / 457 passed**, all seven in `tests/test_doctor.py` and all caused by `port-backend` reporting unavailable because the running `vibe serve` (PID 29948) holds the port; no backend file was changed by this milestone. Evidence: `artifacts/ui-review/pytest-m7.txt`.

### Open user decisions (carried forward)

| # | Decision | Why it is open |
|---|---|---|
| D1 | Repo-wide `ruff format` (70 of 89 files are unformatted) | A large, review-hostile diff that touches the backend only; needs an explicit go-ahead |
| D2 | Offer `vibe backup` from `doctor.bat` / `start.bat` | A product decision about how much the launchers should do |
| D3 | Default backup retention of 7 | A policy value, not a defect |
| D4 | Delete `apps/vibe/src/lib/markdown.tsx` and the `react-markdown` dependency | Confirmed dead — the file is the only importer of the package and nothing imports the file. Removing a dependency is a deletion, so it is reported rather than done |
| D5 | Add a skip link to the transcript | 15 tool rows are genuine interactive controls, so a long agent run still adds tab stops before the composer; a skip link is the standard remedy but is a visible UI addition |


## Review remediation — 2026-10-16

Read-only verification review of the working tree (commit `0849b14` + the uncommitted
M7 work); every gate was re-run. Security was verified clean and is not listed below
(no shell injection — all subprocesses use `create_subprocess_exec`; no XSS sinks in
`apps/vibe/src`; path confinement resolves before `is_relative_to` in
`tools/files.py:11` and `services/sessions.py:50`; `require_session(deps, sid, owner)`
on every session route; `OriginGuard` + loopback auth). Findings RED-1…RED-5, plus one
more (RED-6) found while fixing RED-2:

| # | Finding | Severity | Status | Fix / evidence |
|---|---|---|---|---|
| RED-1 | `pnpm format:check` red on 16 files; CI frontend job runs it (`.github/workflows/ci.yml:75-76`) | High | `done` | `pnpm format` (`apps/vibe`); standalone `pnpm format:check` → exit 0, "All matched files use Prettier code style!" |
| RED-2 | `tests/test_executor.py::test_install_build_dev_server` fails — the scaffold declares a `vite build` script but never declares `vite`; once declared, pnpm 12 exits 1 with `ERR_PNPM_IGNORED_BUILDS` | Medium | `done` | scaffold now declares `vite: ^6.0.0` **and** a `pnpm-workspace.yaml` with `allowBuilds: esbuild` (a `tmp_path` inherits nothing from the root); `pytest tests/test_executor.py -q` → **7 passed** |
| RED-3 | `features/chat/timeline.ts` comment claimed `next_seq` "peeks ... not a reservation"; it reserves (increments) | Low | `done` | comment corrected: the seq is reserved/advanced from the same counter, only stored events move `lastSeq` |
| RED-4 | `lib/api.ts` comment said `GET /sessions/{id}` lacks timestamps (BE-19 / R3-T6); R3-T6 landed | Low | `done` | comment corrected to state both `GET /sessions` and `GET /sessions/{id}` return timestamps |
| RED-5 | `CURRENT_STATE.md` listed a port-7321 listener (PID 29948) that no longer exists | Low | `done` | snapshot refreshed (Git + Active jobs + this section) |
| RED-6 | (found while fixing RED-2) a **session workspace** declaring a build-script dependency (vite→esbuild) makes `install()` return `is_error=True` on pnpm 12 unless the project approves it; the app wrote no such config into session workspaces | Medium | `done` | executor `install()` now writes a `pnpm-workspace.yaml` (`allowBuilds: esbuild`) into the session workspace, but **only when the project has none of its own**, and appends an allowlist hint to an `ERR_PNPM_IGNORED_BUILDS` failure; `local.py` `SAFE_BUILD_SCRIPTS`. `pytest tests/test_executor.py -q` → **11 passed**, including the integration test with no hand-written approval file (the executor must supply it) |
| — | 5 eslint warnings (3 `exhaustive-deps`, 2 `react-refresh`) | Info | `accepted` | documented triage decision in `apps/vibe/eslint.config.js`; no change |

### Open decisions closed — 2026-10-16

After the commit, the user answered the four decisions carried from the M7 review and the
hardening left-overs. All are implemented in the working tree (uncommitted):

| # | Decision (user chose the recommended option) | Status | What landed |
|---|---|---|---|
| P5 | Auth beyond loopback: shared-secret token | `done` | `Settings.auth_token` (`VIBE_AUTH_TOKEN`) + a fail-closed `__post_init__` guard (a non-loopback `VIBE_HOST` without a token is a startup error); `TokenAuthenticator` in `auth.py` (loopback trusted, remote peers must send `Authorization: Bearer <token>`, constant-time compare); `Container._build_authenticator` selects `"token"` mode |
| R5-T8 | Non-blocking informational `network` doctor check | `done` | `doctor._check_network()` via a `_network_reachable()` seam (so tests stay offline); not in `HARD_CHECKS`; `EXPECTED_CHECKS` updated; new offline test |
| D1 | Repo-wide `ruff format` | `done` | `ruff format .` → 91 files reformatted; `ruff format --check` clean, `ruff check` clean |
| D2 | `vibe backup` from the launchers | `done` | opt-in `start.bat backup` runs `python -m vibe backup --keep 7` after the preflight and aborts the start if the backup fails |
| D3 | Backup retention of 7 | `done` (no-op) | `maintenance.KEEP_DEFAULT = 7` was already the value; nothing to change |
| D4 | Delete dead `lib/markdown.tsx` + `react-markdown` | `done` | file deleted, dependency removed from `apps/vibe/package.json`, lockfile updated (`pnpm install`) |
| D5 | Skip link for the transcript | `done` | skip link added in `ChatPanel.tsx` (targets `#composer-input`), `.skip-link` CSS in `layout.css` |

**Verification (2026-10-16, after the decisions):** backend `pytest -q` → **477 passed** (`0` failed) and `ruff format --check` + `ruff check .` clean; frontend `tsc --noEmit` exit 0, `eslint` 0 errors / 5 warnings, `vitest` **290 passed** (32 files), `prettier --check` exit 0 (frontend verified with D1/D4/D5; the auth/doctor/executor work is backend-only).

Committed as `1deed29` — `feat: M7 UI/UX overhaul, local production hardening, and
review remediation` (223 files) — which lands the whole accumulated worktree, not just
RED-1..RED-5. **Not pushed:** the repo has no `origin` configured. The decisions above
(RED-6, P5, R5-T8, D1–D5) are **implemented and committed** in `eb6bfb7` —
`feat: auth token beyond loopback, executor build-script allowlist, and M7 follow-on
decisions` (103 files: the four decisions plus the `ruff format` whitespace on 91
backend files). Corrected 2026-10-16 after that commit landed; the tree is clean.

## Competitor parity — 2026-10-16 (M8)

Research: [docs/research/2026-10-16-competitive-analysis.md](./docs/research/2026-10-16-competitive-analysis.md)
(what Dyad / Lovable / Bolt / Replit / Cursor / Onlook / bolt.diy ship that we do not).
Plan: [docs/superpowers/plans/2026-10-16-competitor-parity.md](./docs/superpowers/plans/2026-10-16-competitor-parity.md).

**Governing rule (user, 2026-10-16):** never write code for one-time use — this is a
package that expands as we move, so it must stay clean, easy and structured. Every
capability lands as a **seam** (Definition ⊕ Provider ⊳ Consumer), never a one-off
script or a branch in shared code.

**User-gated:** no phase starts without an explicit go. Statuses are `pending` until
then. Each task below is a phase in the plan.

| # | Task (phase) | Seam | Status | Gate / next action | Evidence |
|---|---|---|---|---|---|
| 22.1 | **C1 — Import an existing project** + workspace scaffolding | `ProjectSource` (`ViteReactTsTemplate`, `LocalFolderSource`, `GitRepoSource`) | `pending` | User-gated; also closes the long-open PLAN.md §4 scaffolding item | docs/superpowers/plans/2026-10-16-competitor-parity.md §C1 |
| 22.2 | **C2 — Git integration** | `Vcs` (`GitVcs`) | `pending` | User-gated; local-only, no implicit push | plan §C2 |
| 22.3 | **C3 — Per-step checkpoints / restore-from-chat** | `CheckpointStore` (`LocalFsCheckpointStore`) | `pending` | User-gated; anchored to the event-log `seq` | plan §C3 |
| 22.4 | **C4 — Plan-before-build** | `Planner` node in the runtime graph | `pending` | User-gated; reuses the install-approval pause | plan §C4 |
| 22.5 | **C5 — App persistence + auth for generated apps** | `DataBackend` (`None` default, `LocalSqlite`, `Supabase`) | `pending` | User-gated; **needs a user decision on the default** (local vs Supabase) | plan §C5 |
| 22.6 | **C6 — Quick wins** (local models, MCP, generated-code scan) | `LlmPreset`, `ToolSource`, `CodeScanner` | `pending` | User-gated; independent of the spine | plan §C6 |

**Not in scope (deliberately):** deploy/hosting, real-time collaboration,
multi-tenancy, cloud agents — hosted-product features, not gaps for a single-user
local tool (analysis §5).

**Open questions for the user** (from the plan): the C5 default backend; folder vs git
first (and whether in-place import is required); Git as a panel or a thin action set;
whether MCP is in scope now.



