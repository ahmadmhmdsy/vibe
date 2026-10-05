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

## Structural work — audit 2026-10-04 (P0+P1+P2+P3+P4+P5 done)

| Phase | Task | Status | Gate / next action | Evidence |
|---|---|---|---|---|
| P0 | Portability & safety: expanduser the workspace root + migrate the literal `~` data; `%~dp0` in launchers; gitignore the artefact; relocate evidence files; drop root clutter | `done` | 2026-10-04, approved by the user ("P0 + P1 together"). Workspace root now expands+resolves; 23 dirs / 25 rows merged into `~/vibe-workspaces` with a backup; the three original `~` roots are **left in place for the user to delete after verifying**. `Settings.host`/`VIBE_HOST` added and `__main__` wired to Settings | artifacts/p0p1-e2e.txt; services/vibe/scripts/merge_workspaces.py |
| P1 | Lifecycle & integrity: sqlite-backed EventStore; delete cascade (dev server, executor, policy, events, workspace); drain the dev-server pipe; wire or delete the idle timeout; WAL + lock + to_thread; migration table | `done` | 2026-10-04. History survives a real process restart (proven end-to-end); DELETE cascades and moves the workspace to `.trash/`; dev servers stop before restart and are reaped when idle; WAL + `threading.Lock` + `asyncio.to_thread`; `PRAGMA user_version` migrations on both databases | artifacts/p0p1-pytest.txt; artifacts/p0p1-e2e.txt |
| P2 | Seams: Container + Depends; SessionService/MessageService; provider registry; resolve the dead provider trio (Settings.host and __main__-uses-Settings were pulled forward into P0) | `done` | 2026-10-05. Handlers now declare a deps: App parameter and never touch app.state; the container is frozen and swapped whole via dataclasses.replace. The provider trio was **deleted** (dead *and* broken — ChatOpenAI was built with no model=), leaving one registry behind build_llm_factory. Path confinement and the history projection moved into vibe/services/, so both are testable without standing up FastAPI | artifacts/p2-pytest.txt (136 passed); artifacts/p2-ruff.txt; artifacts/p2-live.txt (22 PASS / 0 FAIL); artifacts/p2-vitest.txt; artifacts/p2-typecheck.txt; artifacts/p2-build.txt; artifacts/p2-eslint.txt |
| P3 | Developer experience: logging; ruff + eslint + prettier; `vitest run` default; CI; packageManager pin | `done` | 2026-10-04. H5 closed: `vibe/logging_setup.py` + `getLogger` in app/lifecycle/executor/chat, and the swallowed reaper failure now logs with a traceback. ruff configured; **all 136 findings fixed** (118 auto, 18 by hand) and the suite still passes. eslint flat config + prettier config; `pnpm test` is now `vitest run`; CI added; pnpm pinned | artifacts/p3-ruff.txt; artifacts/p3-pytest.txt; artifacts/p3-eslint.txt; artifacts/p3-logging.txt; artifacts/p3-vitest.txt |
| P3a | Root workspace + unified scripts (one install at the root, `pnpm -r` scripts) | `pending` | **NEEDS_USER_DECISION** — a root `package.json` + `pnpm-workspace.yaml` changes how pnpm resolves for `apps/vibe` and can break a working install, so it was not done unasked. Note: `apps/vibe/pnpm-workspace.yaml` is *not* a stray workspace file — it is pnpm 12's settings file (`allowBuilds`) | docs/architecture/2026-10-04-codebase-audit.md §8 |
| P3b | Prettier sweep (`pnpm run format`) | `pending` | **NEEDS_USER_DECISION** — `prettier --check` reports 37 files, all currently holding uncommitted user work. Run it *after* committing, not before. `format:check` is deliberately kept out of CI until then | artifacts/p3-prettier-check.txt |
| P3c | React-hooks triage: 2× `refs` + 5× `set-state-in-effect` | `pending` | real findings, kept at `warn` so CI is green. Each needs a behaviour-affecting refactor (`useSyncExternalStore`, render-phase state reset, `useEffectEvent`) with its own tests — not a lint-cleanup commit. Locations in apps/vibe/eslint.config.js | apps/vibe/eslint.config.js; artifacts/p3-eslint.txt |
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
