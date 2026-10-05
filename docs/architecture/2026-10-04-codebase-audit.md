# Codebase audit — structure, reusability, extensibility

**Date:** 2026-10-04 · **Scope:** the whole repository · **Method:** first-hand read of
every backend module and the frontend tree, plus targeted greps. Every claim below
carries an exact `file:line`; anything I could not reproduce from the code is marked
`UNVERIFIED` or left out.

**Question asked:** make this clean, reusable, easy to edit, and expandable for
later — and report weaknesses, missing implementation, and features to add / remove /
edit. Nothing is treated as sacred.

---

## 1. Verdict

The code is **small and mostly well-factored**: ~1.5k LOC backend, ~3.6k LOC
frontend, a clear `features/<name>/` convention on the frontend, and a genuinely
clean seam list in `api/app.py`. It is not a mess, and it should **not** be
rewritten.

But it is a **prototype wearing production clothes**. Three properties make it
one-time-use today, and they are all fixable without touching the good parts:

1. **State that lives only in RAM** — chat history and provider/session events are
   in-process dictionaries, so a restart silently empties every conversation.
2. **Configuration that is not portable** — `~/vibe-workspaces` is never expanded,
   so real user data sits in a directory literally named `~`, resolved against the
   process's current working directory; the launcher scripts hard-code an absolute
   `E:\python_projects\...` path.
3. **Lifecycle that never ends** — deleting a session leaves its workspace, its
   subprocess, its executor, and its event history alive forever.

Fix those three and the existing structure is a good base to grow on.

| Dimension | Grade | One-line reason |
|---|---|---|
| Feature-level structure | **B+** | consistent `features/` layout, `components/ui` primitives, small modules |
| Backend layering | **C** | HTTP handlers, provider construction and persistence are braided together |
| Data integrity / lifecycle | **D** | in-memory history, orphaned workspaces and processes |
| Portability / reproducibility | **D** | literal `~` data dir, absolute paths in scripts, no version pins, no lockfile policy |
| Developer experience | **D** | zero logging, zero linters, zero CI |
| Extensibility | **C** | adding a provider means editing the API module; no registry, no DI |
| Typing / tests | **A−** | no `any` escapes in the frontend; 77 + 76 tests, real regression coverage |

**Grades are the 2026-10-04 audit snapshot.** After P0+P1+P3 (below) three rows
moved: data integrity / lifecycle **D → B**, portability / reproducibility
**D → C+**, developer experience **D → B**. Backend layering and extensibility are
unchanged — they are P2 work.

### Status — 2026-10-05: P0 + P1 + P2 + P3 + P4 implemented

The user approved P0 and P1 together; P3 followed on the plan's own recommended
order. Everything below was verified against the running application, not just the
test suite.

| Finding | Status | What changed |
|---|---|---|
| H1 history is memory-only | **Fixed** | `events.py` is sqlite-backed (`events(session_id, seq, type, payload)`, WAL); proven across a real process restart — `artifacts/p0p1-e2e.txt` §B |
| H2 literal `~` workspace root | **Fixed** | `Settings.__post_init__` expands and resolves; `from_env` no longer turns an empty value into the CWD; data migrated by `scripts/merge_workspaces.py` (23 dirs / 25 rows, backup kept, originals left for the user) |
| H3 deleting a session orphans its state | **Fixed** | `lifecycle.py` — abort run, stop dev server, drop executor/policy/approvals/events, move the workspace to `.trash/`, delete the row last |
| H4 provider layer is dead code | **Fixed (P2)** | the three provider classes were dead *and* broken — `ChatOpenAI(api_key=..., base_url=..., streaming=True)` with no `model=`, and `openai_responses.py` claimed `/v1/responses` while building `ChatOpenAI`. **Deleted**, leaving one registry behind `build_llm_factory`. Deletion is git-recoverable |
| H5 no backend logging | **Fixed (P3)** | `vibe/logging_setup.py` — one stderr handler on the `vibe` logger, `propagate=False`, idempotent, level from `VIBE_LOG_LEVEL` (default INFO, unknown names fall back). `getLogger` in `app`/`lifecycle`/`executor`/`chat`; the reaper's `except: pass` now logs with `exc_info`; `create_app` configures only if nobody has, so `uvicorn --factory` is not silent. Proof: `artifacts/p3-logging.txt` |
| M1 blocking sqlite on the event loop | **Fixed** | WAL + `synchronous=NORMAL` + `busy_timeout`, a `threading.Lock`, and `asyncio.to_thread` on both stores |
| M2 composition root is a service locator | **Fixed (P2)** | `container.py` — one frozen `Container` dataclass built before anything derives from it, injected with `Depends`. Handlers declare `deps: App` and never touch `app.state`; `app.state.container` stays reassignable so a test can still swap a seam whole via `dataclasses.replace` |
| M3 launchers hard-code an absolute path | **Fixed** | `start.bat`/`test.bat` use `%~dp0` |
| M4 two config knobs do nothing | **Fixed** | `Settings.host` added and read from `VIBE_HOST`; `__main__.py` now uses `settings.host`/`settings.port` via a `main()`; the idle timeout drives a real reaper |
| M5 dev-server deadlock and leaks | **Fixed** | stdout is drained into a ring buffer; an existing server is stopped before a new one starts; a 60 s reaper stops idle servers; the lifespan stops every executor on shutdown |
| M6 autorun runtime-error half is inert | **Fixed (P4), then implemented (P5)** | P4 made the stub honest: `read_console_logs`/`screenshot` return `None` — "no driver", not "clean" — and `AutoRunPolicy` treats `None` as *nothing was read*. **P5 then supplied the driver the honesty was reserving a place for:** `vibe/executor/browser.py` drives Playwright, so the loop now reacts to *runtime* errors and blank pages, not only build failures. Every capture still degrades to `None` when Playwright or the browser binary is absent |
| M9 no database migration path | **Fixed** | `PRAGMA user_version` + a `_migrate()` on both databases |
| M10 nothing enforces style | **Fixed (P3)** | ruff 0.16.10 (E/F/W/I/UP/B/C4/SIM/RUF) — **136 findings fixed**, 118 auto / 18 by hand; eslint 10 flat config + prettier config, 23 baseline problems → 0 errors / 14 triaged warnings; `pnpm test` is now `vitest run`; `packageManager` pinned; `.github/workflows/ci.yml` (never executed — unverified) |

Deliberate behaviour changes, so nothing surprises you later:

- Chat history now **persists across restarts** (`events.db` next to `sessions.db`).
- `DELETE /sessions/{sid}` now **moves the workspace to `<workspace_dir>/.trash/`**
  instead of leaving it in place. Nothing is destroyed, but the directory does move.
- Dev servers are stopped when the backend restarts, and after
  `VIBE_DEV_SERVER_IDLE_TIMEOUT_MIN` (0 or negative disables the reaper).
- `/health` returns the resolved `workspace_dir` and both database paths.
- The backend now **logs to stderr** on the `vibe` logger at `VIBE_LOG_LEVEL`
  (default INFO) — previously every subsystem was silent.
- `pnpm test` now means **`vitest run`** (one shot, exits). Watch mode moved to
  `pnpm run test:watch`. `test.bat` was updated in the same change.
- **P4:** sessions are auto-titled from the first user message, but only while the
  title is still the `Untitled xxxx` placeholder — a manual rename is never clobbered.
- **P4:** `GET /sessions/{sid}/messages` returns the latest 200 by default
  (`limit` 1–1000, `offset` counts back from the newest) and reports the real total
  in `X-Total-Count`, which CORS exposes. The frontend prepends older pages behind a
  "Load older messages" button.
- **P4:** every API error answers `{"error": {"code", "message"}}` with a stable
  machine-readable code (`session_not_found`, `not_found`, `run_in_progress`,
  `conflict`, `validation_failed`, `provider_not_configured`, `internal`); the
  frontend surfaces the code instead of a generic message.
- **P4:** `DELETE` endpoints resolve instead of throwing — `req<void>` was calling
  `resp.json()` on a 204 with an empty body, so `api.deleteSession` always threw a
  `SyntaxError` and the sidebar never refreshed.

### What P3 deliberately did *not* do

Two items were left open because doing them unasked would have been the wrong
call, not because they were missed. (The third — the root workspace — was
approved and done 2026-10-05 as P3a.)

| Item | Why it was left |
|---|---|
| ~~Root workspace + unified scripts~~ | **Done 2026-10-05 (P3a).** A root `package.json` + `pnpm-workspace.yaml` now own the install; the `allowBuilds: esbuild` setting moved up from `apps/vibe/pnpm-workspace.yaml`, which is gone. Verified: install 364 packages, build, 86 vitest, typecheck, eslint 0 errors / 14 warnings, 190 pytest, ruff clean. |
| `prettier --write` | `prettier --check` reports **37 files**, every one of them currently holding uncommitted user work. Reformatting now would bury that work in a noise diff. `format:check` is therefore kept out of CI until the sweep is committed. |
| 3 × `react-hooks/set-state-in-effect` + 2 × `react-hooks/refs` | Genuine findings, but each needs a behaviour-affecting refactor (`useSyncExternalStore`, render-phase state reset, `useEffectEvent`) with its own tests — not a lint-cleanup commit. Kept at `warn` with the reason written into `apps/vibe/eslint.config.js`. |


---

## 2. High severity — fix before building anything else

### H1. Chat history is memory-only, so every restart wipes every conversation
`EventLog` stores events in a plain dict: `services/vibe/src/vibe/events.py:24`
(`self._events: dict[str, list[Event]] = {}`), created fresh in
`services/vibe/src/vibe/api/app.py:94`. The message endpoint *derives* history from
it — `services/vibe/src/vibe/api/routes/messages.py:25`. Session rows persist in
sqlite, so after a restart the sidebar still lists every session and each one opens
**empty**. The same dict is never evicted on delete, so it grows for the life of the
process.

*Smallest fix:* give `EventLog` a sqlite-backed implementation behind the existing
method surface (`append`/`get`/`last_seq`), table `events(session_id, seq, type,
payload)`, and evict on session delete.

### H2. `VIBE_WORKSPACE_DIR=~/vibe-workspaces` is never expanded — real data lives in a literal `~` directory
`services/vibe/src/vibe/config.py:53` builds `Path(os.environ.get("VIBE_WORKSPACE_DIR", ...))`
with no `expanduser()`. `.env` and `.env.example` both ship
`VIBE_WORKSPACE_DIR=~/vibe-workspaces`. The dataclass default
(`config.py:40`) correctly uses `Path.home()` — only the env path is broken.

Observed on disk: `services/vibe/~/vibe-workspaces/` containing **18 session
directories, `sessions.db`, and `providers.json`**, plus a second `./~/vibe-workspaces`
at the repository root. Because `app.py:93` puts `sessions.db` *inside* the
workspace root, the path is resolved relative to the process CWD: start the server
from the repository root instead of `services/vibe` and the app comes up with an
**empty session list and no configured providers**, while the old data sits
unreachable next door.

*Smallest fix:* `Path(value).expanduser()`, resolve to an absolute path once in
`Settings`, and log the resolved value at startup. Then migrate the existing data
(explicitly, with the user's approval — do not delete anything).

### H3. Deleting a session orphans everything it owned
`services/vibe/src/vibe/store.py:67-69` deletes one sqlite row;
`services/vibe/src/vibe/api/routes/sessions.py:85-88` calls it and nothing else. Not
cleaned up: the workspace directory, the `LocalSubprocessExecutor` and any running
dev server (`app.py:108`), the autorun policy (`app.py:109`), the event log
(`events.py:24`), the approval store, and the usage records. Deleting a session with
a live dev server leaves the `pnpm dev` process running and its port bound.

*Smallest fix:* one `SessionLifecycle.delete(sid)` that stops the dev server,
drops the executor and policy, evicts events/approvals/usage, deletes the row, and
optionally moves the workspace to a trash directory rather than `rmtree`.

### H4. The provider layer is dead code, and the live one is 50 lines inside the API module
`providers/base.py:6` defines `LlmProvider`, implemented by
`providers/openai_chat.py:7`, `providers/anthropic.py:7`,
`providers/openai_responses.py:7`. **No production code instantiates any of them** —
the only importer is `services/vibe/tests/test_providers.py:3`. Instead,
`services/vibe/src/vibe/api/app.py:22-70` builds LangChain chat models inline, with
provider ids, base URLs and headers hard-coded in the web layer
(`app.py:53` — `https://opencode.ai/zen/go/v1`), and its own docstring admits the
provider classes are bypassed.

Consequence: adding or changing a provider means editing the API module, and the
tested abstraction is not the executed one.

*Smallest fix:* a `providers/registry.py` mapping provider id → a small factory,
with each provider in its own module. Then **either** wire the existing classes into
it **or** delete them — but not both halves of a seam.

### H5. There is no logging in the backend at all
A grep for `import logging` / `logger` across `services/vibe/src/vibe` returns **zero
matches**. Failures surface only as HTTP responses; a crashed background turn, a
provider 401, or a dev server that dies are invisible. The frontend has
`apps/vibe/src/lib/logger.ts`; the backend has nothing.

*Smallest fix:* `logging.getLogger(__name__)` per module, one `configure_logging()`
in the composition root, and a request id middleware.

---

## 3. Medium severity

### M1. Blocking sqlite calls run on the event loop, on an unsynchronised connection
`store.py:19` opens `sqlite3.connect(..., check_same_thread=False)` with no lock,
and every method is `async def` while doing blocking I/O (`store.py:35-69`). Two
concurrent requests can interleave on one connection, and a slow disk stalls the
whole server. No WAL mode.

*Fix:* `await asyncio.to_thread(...)` behind a lock, or a small connection-per-call
pool, plus `PRAGMA journal_mode=WAL`.

### M2. The composition root is a service locator
`api/app.py:86-145` assigns 13 attributes to `app.state` and attaches two closures
(`get_executor`, `get_autorun`). Every route reaches through
`request.app.state.<thing>`, so nothing declares its dependencies and tests must
build a whole app to test a handler.

*Fix:* one frozen `Container` dataclass built in `create_app`, injected with
`Depends`. Keeps FastAPI idiomatic while making dependencies explicit.

### M3. Launcher scripts hard-code this machine's absolute path
`start.bat:14`, `start.bat:17`, `test.bat:7`, `test.bat:18` all contain
`E:\python_projects\apps_building`. A clone anywhere else cannot start.

*Fix:* `%~dp0`-relative paths (or replace both scripts with `package.json` scripts
plus a `Makefile`/`justfile`).

### M4. Two documented configuration knobs do nothing
- `VIBE_DEV_SERVER_IDLE_TIMEOUT_MIN` is parsed at `config.py:56` and stored at
  `config.py:43`, and **read nowhere else** — the idle dev-server reaper it
  configures does not exist.
- `VIBE_HOST` appears in `.env` and `.env.example` but is **not a field on
  `Settings` at all**; `__main__.py:8` hard-codes `host="127.0.0.1"`.

Worse, `__main__.py:8` also hard-codes `port=7321`, so `python -m vibe` **ignores
`VIBE_PORT`** — only the `start.bat` uvicorn invocation honours it.

*Fix:* add `host` to `Settings`, use `settings.host`/`settings.port` in
`__main__.py`, and either implement the idle reaper or delete the knob.

### M5. The dev-server path can deadlock and leaks processes
`executor/local.py:50-56` spawns `pnpm run dev` with `stdout=PIPE` and **never
drains the pipe**; a long-running dev server that fills the OS pipe buffer blocks
forever. `self._dev_server` is overwritten on the next call (`local.py:55`) without
stopping the previous one, so each `start_dev_server()` leaks a process.

*Fix:* drain stdout into a ring buffer task, stop any existing server before
starting a new one, and register an `atexit`/`shutdown` hook.

### M6. The autorun self-repair loop is inert
`autorun/policy.py:35` reads console logs to detect runtime errors, but
`executor/local.py:67-69` is a stub returning `""`, so the branch never fires and
`policy.py:40` always concludes "clean". `local.py:71-73` (`screenshot`) is also a
stub. The build-error half works; the runtime-error half has never run.

*Fix:* either implement console capture or delete the branch so the loop is honest
about what it checks.

### M7. Frontend components own their own data fetching
Every panel calls `api.*` directly inside effects and handlers and re-implements
loading/error state: `features/settings/SettingsPanel.tsx:33,55,62,83`,
`features/sessions/SessionsPanel.tsx:39,67`, `features/chat/ModelPicker.tsx:16,25,44`,
`features/chat/UsageBadge.tsx:13`, `features/chat/MessageList.tsx:32,96,100`,
`features/chat/Composer.tsx:83,97`. `usePolling` exists but covers only two call
sites. Swapping the transport or adding caching means touching every panel.

*Fix:* a thin `useResource`/`useAsync` hook returning `{data, error, loading, reload}`,
or adopt TanStack Query. Keep `lib/api.ts` as the single transport.

### M8. Two competing CSS strategies
`apps/vibe/src/styles/global.css` uses `@layer`, while the feature sheets
(`features/chat/chat.css`, `code/code.css`, `preview/preview.css`,
`sessions/sessions.css`, `settings/settings.css`) are unlayered and therefore win
regardless of specificity. This already caused a real cascade bug (recorded in
`MEMORY.md:43`), and `styles/components.css` is a 438-line catch-all.

*Fix:* pick one — put every sheet in the same `@layer` order, or drop `@layer` and
use a documented specificity convention. Split `components.css` by primitive.

### M9. No migration path for the database
`store.py:23-33` is a single `CREATE TABLE IF NOT EXISTS`. There is no
`user_version`/`schema_migrations` table, so the first column you add to
`sessions` has no supported upgrade route on an existing install.

### M10. Nothing enforces code style or runs checks automatically
No `ruff.toml`, `eslint.config.js`, `.prettierrc`, `.github/`, `Makefile`,
`Dockerfile` or compose file exists anywhere in the repository (verified by
enumeration). Tests are only run when a human remembers to run `test.bat`.

---

## 4. Missing implementation (promised or implied, not present)

| # | Missing | Evidence |
|---|---|---|
| 1 | Conversation persistence | `events.py:24`, `messages.py:25` (see H1) |
| 2 | Dev-server idle reaping | knob parsed `config.py:56`, consumed nowhere |
| 3 | Runtime-error detection / console logs | stub `executor/local.py:67-69` |
| 4 | Screenshot capability | stub `executor/local.py:71-73` |
| 5 | Session cleanup cascade | `store.py:67`, `sessions.py:88` (see H3) |
| 6 | Pagination | `messages.py:17` and `events.py:47` return everything |
| 7 | Auth / access control | no middleware in `api/app.py:73-85`; fine for loopback-only, but undocumented as a decision |
| 8 | Readiness / version endpoint | `api/app.py:147-149` returns only `{"status":"ok"}` |
| 9 | Session titles from the first message | `store.py:38` leaves `Untitled {sid[:4]}` forever |
| 10 | Provider registry | see H4 |
| 11 | Structured error taxonomy | routes raise ad-hoc `HTTPException`s; no error codes the frontend can branch on |
| 12 | Multi-session concurrency tests | `RunRegistry` is per-session; no test drives two sessions at once |
| 13 | Console-log reading | **`README.md:12` promises it**; `executor/local.py:67-69` returns `""` |
| 14 | Screenshots | **`README.md:12` promises it**; `executor/local.py:71-73` returns `b""` |
| 15 | Runtime-error feedback in the fix loop | **`README.md:13` promises it**; `autorun/policy.py:35-40` can never fire |

### Documentation that contradicts the code
`README.md` is the human entry point, so its claims are promises:

- `README.md:12` — "the agent can read console logs and take screenshots to verify
  its work" → both are stubs (`executor/local.py:67-73`).
- `README.md:13` — "build/**runtime** errors are fed back to the agent" → only the
  build half works; the runtime half depends on the stub above.
- `README.md:26-40` documents manual startup but never mentions how to run the
  test suites, and `README.md:32,39` pin port 7321 in prose while `start.bat:11`
  auto-increments it.

Either implement the stubs or correct the README. Leaving a false capability claim
in the front door is worse than a missing feature.

---

## 5. Hygiene — remove or relocate

| Path | Why |
|---|---|
| `debug_frontend.js` | scratch debugger at the repo root, no importer |
| `e2e-test.ps1`, `e2e-test-fixed.ps1`, `e2e-test-final.ps1`, `e2e-test-eval.ps1` | four generations of the same throwaway script |
| `vibe-working.png` | a screenshot used to prove something once |
| `test.bat` | duplicates `pnpm test` + `pytest`; kept, and now path-relative via `%~dp0` (**P0**) |
| `./~` and `services/vibe/~/vibe-workspaces/` | the H2 artefact — **contains real user data; migrated, never deleted.** Its contents were merged into `~/vibe-workspaces` by `services/vibe/scripts/merge_workspaces.py` (23 dirs / 25 rows, backup `sessions.db.bak-20261004-182245`). The three original roots are **left in place for the user to delete after verifying** (**P0**) |
| `debug_frontend.js`, `e2e-test*.ps1`, `vibe-working.png` | **Done 2026-10-04 (P0): archived to `archive/scratch/`, not deleted** |
| `apps/vibe/build.txt`, `typecheck.txt`, `vitest-after.txt`, `vitest-baseline.txt`, `services/vibe/pytest-after.txt`, `live-verification.txt` | validation evidence scattered across two packages — move under one ignored `artifacts/` directory. **Done 2026-10-04 (P0): all six now in `artifacts/`.** |
| `apps/vibe/pnpm-workspace.yaml` | holds `allowBuilds: esbuild`, a workspace-root concern, inside an app dir with no root `package.json` |
| `pydantic` in `services/vibe/pyproject.toml:5-13` | declared, never imported |
| `apps/vibe/.impeccable/live/server.json` | tool state committed into the app tree |

---

## 6. What is genuinely good — do not churn it

- The **frontend feature layout** (`features/<name>/{Component.tsx,store.ts,<name>.css,__tests__/}`)
  is consistent and scales; keep it.
- `lib/api.ts` is a real single transport boundary, and the SSE client is a separate
  concern — that split is right.
- **Typing discipline**: a grep for `any`/`as any`/`@ts-ignore` across
  `apps/vibe/src` returns nothing outside tests.
- The **test suites are meaningful**, not decorative: the recent bridge fixes are
  covered by regression tests that fail against the old code.
- `workspace.py`, `runs.py`, `events.py` are small, single-purpose modules with
  docstrings — the model to follow for new backend code.
- The supply-chain path is genuinely wired end to end
  (`tools/executor_tools.py:5` → `supply_chain.py:39` → `approvals.py:25`), not a stub.

---

## 7. Proposed target structure (incremental, not a rewrite)

```
services/vibe/src/vibe/
  config.py            # Settings: expanduser, host, validation, one resolved root
  container.py         # NEW  frozen Container dataclass — replaces app.state.*
  logging_setup.py     # NEW  configure_logging()
  domain/              # NEW  pure logic; no FastAPI, no sqlite, no subprocess
    models.py
    sessions.py        # SessionService: create/rename/model/delete + lifecycle
    messages.py        # history projection from the event store
  infra/               # NEW  adapters, each behind a small protocol
    store_sqlite.py    # migrations + WAL + lock + to_thread
    event_store.py     # protocol + sqlite implementation (replaces the dict)
    workspace.py
    executor/local.py
    providers/         # registry.py + one module per provider
  api/                 # thin: validate -> call service -> serialise
    deps.py  routes/
  runtime/  tools/  usage/  approvals.py  supply_chain.py
```

**Honest trade-off:** the `domain/` + `infra/` split is more ceremony than 1.5k LOC
strictly needs. It earns its keep only because you plan to expand. If you would
rather stay flat, the minimum viable version of this is: `container.py`, a
`services/` module holding session/message logic, and an `EventStore` protocol —
that alone removes the three worst couplings.

Repository level:

```
package.json + pnpm-workspace.yaml   # one workspace root, unified scripts
artifacts/                           # all validation evidence, gitignored
docs/architecture/                   # this audit and future design notes
.github/workflows/ci.yml             # pytest + vitest + ruff + eslint
ruff.toml  eslint.config.js  .prettierrc
```

---

## 8. Phased plan

| Phase | Work | Risk | Why this order |
|---|---|---|---|
| **P0 — Portability & safety** ✅ **done 2026-10-04** | `expanduser` + resolve + log the workspace root; migrate existing data with approval; `%~dp0` in scripts; `.gitignore` the `~` artefact and `artifacts/`; move evidence files; delete root clutter | low | stops data from being lost or created in the wrong place before anything else moves |
| **P1 — Lifecycle & integrity** ✅ **done 2026-10-04** | sqlite-backed `EventStore`; delete cascade (dev server, executor, policy, events, workspace); drain the dev-server pipe + stop-before-restart; wire or delete the idle timeout; WAL + lock + `to_thread`; migration table | medium | these are the actual data-loss and leak bugs |
| **P2 — Seams** ✅ **done 2026-10-05** | `Container` + `Depends`; extract `SessionService`/`MessageService`; provider registry; resolve the dead provider trio; `Settings.host`; `__main__` uses Settings | medium | makes "add a provider / add an endpoint" a local change. **Done:** `container.py` + `api/deps.py` (handlers declare `deps: App`); `vibe/services/` holds path confinement and the history projection; `providers/registry.py` replaces the deleted trio. Proof: `artifacts/p2-pytest.txt` (136 passed), `artifacts/p2-ruff.txt`, `artifacts/p2-live.txt` (22 PASS / 0 FAIL), `artifacts/p2-vitest.txt`, `artifacts/p2-typecheck.txt`, `artifacts/p2-build.txt`, `artifacts/p2-eslint.txt` |
| **P3 — Developer experience** ✅ **done 2026-10-04** | logging; ruff + eslint + prettier; `vitest run` as the default script; CI; `packageManager` pin. **Split out and left open:** root workspace + unified scripts (needs the user's call), the prettier sweep (37 uncommitted files), 7 triaged React-hooks warnings | low | cheap, and it protects every later phase |
| **P3a — Root workspace** ✅ **done 2026-10-05** | the user said "start P3a, P3b and P3c". A root `package.json` (private, `packageManager` pin, unified scripts) + a root `pnpm-workspace.yaml` (`packages: ["apps/*"]`); the `allowBuilds: esbuild` setting moved up from `apps/vibe/pnpm-workspace.yaml`, which is gone. Verified: install 364 packages, build, 86 vitest, typecheck, eslint 0 errors / 14 warnings, 190 pytest, ruff clean | low | one install at the root covers the workspace |
| **P4 — Product gaps** ✅ **done 2026-10-05** | session titles from the first message; pagination + `X-Total-Count`; error taxonomy; the M6 honesty fix; README corrected. **Left open:** console-log capture + screenshots (needs a browser driver — `NEEDS_USER_DECISION`), auth beyond loopback (`NEEDS_USER_DECISION`) | medium | features, not structure — decide after P0–P3 |

| **P5 — The browser driver** ✅ **done 2026-10-05** | the user chose "A. Implement Playwright" for the M6 gap. `vibe/executor/browser.py` (Playwright lifecycle, console capture with level filtering, screenshots, TCP readiness wait, idempotent close); `ToolResult.attachments` + `response_format="content_and_artifact"` so an image reaches the model as a content block while staying out of the SSE stream; `is_error` now propagates to the event stream. **Also found and fixed:** pnpm 12 forwards `--` literally, so Vite ignored `--port` and every session collided on 5173. **Left open:** auth beyond loopback (`NEEDS_USER_DECISION` — design delivered, awaiting the user's scope call) | medium | the last audit phase; closes the loop P4 opened |
| **P6 — Loopback auth** ✅ **done 2026-10-05** | the user approved the
  recommendation: one user, one machine, local now, reusable/scalable later.
  `vibe/auth.py` (`Principal`, `Authenticator` protocol, `LoopbackAuthenticator`);
  `require_principal` mounted as a router-level dependency on all seven routers
  (deny-by-default, `/health` open); `OriginGuard` — a second, independent control
  against CSRF, which loopback auth cannot catch; `Container.build(authenticator=...)`
  + `Settings.auth_mode`/`VIBE_AUTH_MODE` as the seam, with an unknown mode raising
  rather than downgrading. **Left open by design:** no token (security theatre, and it
  breaks `start.bat`); no users/ownership — multi-user later means `owner_id` on
  sessions + an ownership check in `require_session` + a filtered `SessionStore.list` |
  low | closes the last audit phase; the seam is the drop-in point for a future token
  authenticator |

Suggested: **P0 + P1 together** (they are the "don't lose data" pair), then **P3**
(it is cheap and pays for itself), then P2, then P4.

**P0 and P1 were approved and completed together on 2026-10-04.** Verification:
`artifacts/p0p1-pytest.txt` (98 passed), `artifacts/p0p1-live.txt` (22 PASS / 0 FAIL),
`artifacts/p0p1-e2e.txt` (restart durability + delete cascade against a running
server), `artifacts/p0p1-vitest.txt` (76 passed), `artifacts/p0p1-typecheck.txt`,
`artifacts/p0p1-build.txt`.

**P3 followed on 2026-10-04** (the order this plan itself recommends). Verification:
`artifacts/p3-pytest.txt` (107 passed), `artifacts/p3-ruff.txt` (clean),
`artifacts/p3-logging.txt` (the live server's stderr — `vibe ready: workspace=...`,
`run started for session ...`, `run aborted ...`), `artifacts/p3-live.txt` (the live
ASGI/SSE harness, PASS), `artifacts/p3-eslint.txt` (0 errors / 14 warnings),
`artifacts/p3-vitest.txt` (76 passed), `artifacts/p3-typecheck.txt`,
`artifacts/p3-build.txt`, `artifacts/p3-test-bat.txt` (`test.bat` green end to end),
`artifacts/p3-prettier-check.txt` (the 38-file sweep that was deliberately not run).

**P2 — Seams followed on 2026-10-05**, completing the structural half of
the plan. Verification: `artifacts/p2-pytest.txt` (136 passed),
`artifacts/p2-ruff.txt` (clean), `artifacts/p2-live.txt` (the live ASGI/SSE
harness, 22 PASS / 0 FAIL), `artifacts/p2-vitest.txt` (76 passed),
`artifacts/p2-typecheck.txt`, `artifacts/p2-build.txt`, `artifacts/p2-eslint.txt` (0 errors /
14 warnings).

**P4 — Product gaps followed on 2026-10-05**, completing the plan. Verification:
`artifacts/p4-pytest.txt` (161 passed), `artifacts/p4-ruff.txt` (clean),
`artifacts/p4-live.txt` (the live ASGI/SSE harness, 22 PASS / 0 FAIL),
`artifacts/p4-live-probe.txt` (13 PASS / 0 FAIL — error shape, auto-titling,
pagination, `X-Total-Count`), `artifacts/p4-vitest.txt` (86 passed),
`artifacts/p4-typecheck.txt`, `artifacts/p4-build.txt`, `artifacts/p4-eslint.txt`
 (0 errors / 14 warnings).

All five phases of the plan are now complete. Two items remain
`NEEDS_USER_DECISION` and are recorded as such rather than guessed at: a browser
driver for console/screenshot capture, and any auth story beyond loopback.
