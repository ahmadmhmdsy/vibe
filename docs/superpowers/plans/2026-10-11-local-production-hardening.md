# Local Production Hardening — Program Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan phase-by-phase. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Execution status (2026-10-11).** R0 through R7 have all been executed. The live status and the
> per-task evidence live in [TASKS.md](../../../TASKS.md), the running narrative in
> [HANDOFF.md](../../../HANDOFF.md), the session snapshot in [CURRENT_STATE.md](../../../CURRENT_STATE.md),
> and the round-by-round record in `artifacts/hardening-progress-log.txt`. The checkboxes below are the
> authoring checklist: they are kept current for R7 (the phase verified last), while the R0-R6 step boxes
> were left as written when those phases landed - their completion is recorded in TASKS.md and the
> progress log rather than by retro-ticking this file. When the two disagree, the running documents win.

**Goal:** Fix all 39 findings from the 2026-10-11 full-app review and turn vibe into a
single-machine, install-and-run product — no remote services, no accounts, no payments —
while keeping every seam that a later scale-out would need, so that scaling is a new
Provider rather than a rewrite.

**Architecture:** The fixes are sequenced so that each phase leaves the app in a working,
testable state: truth first (docs/state), then correctness under concurrency and
cancellation, then validation and secrets, then product completeness, then frontend trust,
then local packaging and operations, then the cheap scalability seams. All backend fixes
stay behind the existing Definition/Provider/Consumer seams; all frontend fixes stay inside
the existing feature modules. The single architectural addition is a **production serving
mode** (FastAPI serves the built SPA on one loopback port) alongside the existing
dev-server mode.

**Tech Stack:** Python 3.13 + FastAPI 0.141.1 + Pydantic 2.13.5 + LangGraph 1.2.12 +
SQLite; React 19 + TypeScript 5.6 + Vite 6 on the frontend; uv and pnpm as the only
package managers; pytest + vitest for tests; Windows-first host with portable code.

**Spec:** [docs/reviews/2026-10-11-full-app-review/FINDINGS.md](../../reviews/2026-10-11-full-app-review/FINDINGS.md)
(the 39 findings, with per-finding detail in that directory) and
[docs/superpowers/specs/2026-09-28-vibe-coding-app-design.md](../specs/2026-09-28-vibe-coding-app-design.md)
(the product spec). This plan argues from both; executors read the finding detail before
touching the file it names.

## Global Constraints

Copied verbatim from the review and from repository policy. Every task's requirements
implicitly include this section.

- **Host:** Windows (workspace `E:\python_projects\apps_building`); code must stay portable
  (no Windows-only APIs in the app path, no shell=True string assembly).
- **Runtimes:** Python `>=3.13` (`services/vibe/pyproject.toml`), Node v24.18.0,
  pnpm `12.3.4`, uv 0.11.22. Never mix package managers; never a bare `python` or `pip`;
  always `services/vibe/.venv/Scripts/python.exe`.
- **Lint:** ruff, `line-length = 120`, select `E,F,W,I,UP,B,C4,SIM,RUF`, `E501`/tests
  ignores as configured. Frontend: eslint 10 flat config (0 errors) + prettier 3.9.9.
- **No new runtime dependencies** without an explicit user decision. Every fix below is
  implementable with the current dependency set; the two places that tempted a dependency
  (log rotation, atomic file replace) use the standard library (`logging.handlers`,
  `os.replace`).
- **Loopback only:** `VIBE_HOST` defaults to `127.0.0.1`; no telemetry, no remote calls
  except the LLM endpoint the user configures; no payment code, now or in this plan.
- **Secrets stay server-side:** keys live in `.env` / `providers.json` only; never in the
  React bundle, never in a commit, never in a log line.
- **Worktree safety:** never reset/stash/clean; preserve every pre-existing dirty and
  untracked path; stage exact paths only.
- **Evidence:** every claimed result cites an exact relative artifact path under
  `artifacts/` (gitignored) for command output, or the committed review `evidence/` for
  review-time capture. Labels are exactly `PASS` / `FAIL` / `SKIPPED` / `BLOCKED` /
  `NEEDS_USER_DECISION`.
- **Probe isolation:** probe and test fixtures write to temporary directories only; the
  real workspace (`~/vibe-workspaces`, 25 stored sessions) is never mutated by a test.
- **Commit style:** one commit per task, exact paths, conventional message
  (`fix(chat): make the one-run-per-session guard atomic`).

---

## 0. How to use this plan (scope check)

This program spans seven independent subsystems, so by the writing-plans scope rule it is
an **umbrella plan**: it fixes the phase order, the traceability from finding to task, and
the acceptance criteria, and it specifies Phase R0 and the production workstream (R5) in
full because those are the user's explicit first asks. Every other phase gets its own
bite-sized TDD plan — written immediately before that phase executes, in the exact
task/step format of this skill — so an executor never reads more than one phase at a time.

| Phase plan file (created when the phase starts) | Phase |
|---|---|
| `docs/superpowers/plans/2026-10-11-r1-concurrency-and-cancellation.md` | R1 |
| `docs/superpowers/plans/2026-10-11-r2-validation-and-secrets.md` | R2 |
| `docs/superpowers/plans/2026-10-11-r3-product-completeness.md` | R3 |
| `docs/superpowers/plans/2026-10-11-r4-frontend-trust.md` | R4 |
| `docs/superpowers/plans/2026-10-11-r5-local-packaging-and-ops.md` | R5 |
| `docs/superpowers/plans/2026-10-11-r6-scalability-seams.md` | R6 |

Phase R0 is specified in §5 of this file and is executable as written.

---

## 1. What "production-ready, local-only" means (acceptance criteria)

The word "production" is doing unusual work here: this app is a single-user tool that runs
on the user's own machine. It is production-ready when a person who has never seen the
repository can install it, use it, break it, recover from it, and uninstall it without
reading source code. Each criterion is verifiable by a human in one sitting.

| ID | Acceptance criterion | Verified by |
|---|---|---|
| AC-1 | One command starts the whole product; missing prerequisites produce a readable message naming what to install, not a stack trace | `start.bat` on a clean checkout; R5-T2 |
| AC-2 | The app opens in a browser on a single loopback port with no Vite dev server running | `scripts/acceptance-local.ps1` step 1 |
| AC-3 | With no API key configured, the UI explains exactly how to add one and links to the right panel | First-run walkthrough; R5-T4 |
| AC-4 | The full loop works end to end: create session → prompt → files generated → install → build → preview → auto-fix → stop → delete | `scripts/acceptance-local.ps1` step 3 |
| AC-5 | No user-reachable input produces a 500; malformed bodies answer 4xx with the uniform error envelope | `tests/test_api_validation.py` (promoted from probe 1) |
| AC-6 | Every failure the backend knows about reaches the UI as a visible, actionable message (no silent empty states) | R4-T1..T3 |
| AC-7 | Stopping a run actually stops it; a timed-out command is dead; a deleted session leaves no running process | `tests/test_run_registry.py`, `tests/test_executor_timeout.py`, `scripts/acceptance-local.ps1` step 4 |
| AC-8 | Restart keeps chat history and usage; a corrupt state file degrades to an empty store instead of bricking the app; delete is recoverable from `.trash/` | `tests/test_durability.py`; R2-T2 |
| AC-9 | Long use does not grow storage or processes without bound: event log retention, `.trash` retention, idle dev-server reaping, orphan-run recovery | `tests/test_retention.py`; R5-T9 |
| AC-10 | Backend checks green: pytest, ruff; frontend checks green: vitest, typecheck, eslint, `format:check`, build | `artifacts/hardening-final-checks.txt` |
| AC-11 | A crash leaves a log file on disk that names the failing request/step | `artifacts/hardening-logfile.txt`; R5-T5 |
| AC-12 | Every document tells the truth about the current tree (no stale commit, count, or "passing" claim) | `artifacts/hardening-doc-audit.txt`; R0 |

Explicit non-goals: multi-user tenancy, remote deployment, cloud storage, payments,
telemetry, mobile. §11 records where each would attach when it becomes real.

---

## 2. Scalability guardrails (build the seam, not the feature)

The user's constraint is "local now, scalable later without re-architecting". The failure
mode to avoid is not *missing* scale code — it is baking single-user assumptions into
places that a later change cannot reach without a rewrite. These guardrails are cheap now
and expensive later; R6 implements them.

| ID | Guardrail | Why it is cheap now | What it costs later if skipped |
|---|---|---|---|
| L-1 | Every persisted row carries `owner_id` defaulting to `"local"` | one additive column + `PRAGMA user_version` migration | rewriting every query and every index under load |
| L-2 | All SQL lives inside the store providers (`EventStore`, `SessionStore`); consumers see protocols only | the seams already exist; this is an audit + one test that greps for stray SQL | extracting SQL from route handlers and services under time pressure |
| L-3 | `Executor` stays a protocol; Docker is a second provider, never a branch | already true; R6 adds the isolation assertion test | `if docker:` spreading through the runtime |
| L-4 | Identity is read only from `Principal`; `LoopbackAuthenticator` stays the only implementation | already true post-audit; R6 forbids new `"local"` literals outside the authenticator | hardcoded `"local"` in 30 places |
| L-5 | Every in-process registry is keyed by `(owner_id, session_id)`, never by bare `sid` | two classes (`RunRegistry`, `PreviewManager`) + their tests | two users colliding on a session id in one process |
| L-6 | Config is read from `Settings` only; no `os.environ` read outside `config.py` | R6 adds the grep test | a hidden env var that a hosted deploy cannot set |
| L-7 | Frontend calls one base from `lib/api.ts`; no `localhost` literal in components | R6 adds the grep test | every component needs editing for a different host |
| L-8 | Schema changes go through the existing `user_version` migration runner, idempotently | the runner exists | manual ALTER scripts, no rollback |

Not building, and why: multi-tenant auth (no second user exists; the `Authenticator` seam
is the insertion point), Postgres (SQLite is correct for one machine; the `EventStore`
protocol is the insertion point), Docker executor (the host is the user's machine and
generated code is meant to run there; `Executor` is the insertion point), cloud storage or
sync, payments, telemetry. Each is one paragraph in the design spec's M4, unchanged.

## 3. Phase map and sequence

Each phase ends in a state a reviewer can accept or reject independently, and each phase's
exit gate is a command whose output goes to an evidence artifact.

| Phase | Name | Goal | Findings covered | Exit gate |
|---|---|---|---|---|
| **R0** | Truth and bookkeeping | Every planning, task, memory, and snapshot document matches the tree; the one red check goes green | DOC-01, DOC-02, DOC-03, DOC-04, DOC-05, DOC-06, DOC-07 | `pnpm format:check` PASS; doc audit script clean; `artifacts/hardening-r0-docs.txt` |
| **R1** | Correctness under concurrency and cancellation | A second send cannot run two turns; a stopped or timed-out command is dead; a failed delete cannot destroy a transcript | BE-04, BE-05, BE-06, BE-12 (retention half) | `artifacts/hardening-r1-*.txt`; probe 4, 5, 7 promoted to permanent tests |
| **R2** | Validation and secrets | No user-reachable input answers 500; the install allowlist cannot be bypassed; a bad state file cannot brick the app | BE-01, BE-02, BE-14, BE-15, BE-16 | `artifacts/hardening-r2-*.txt`; probes 1, 2 and custom-probe 1-3 promoted |
| **R3** | Product completeness | The agent remembers the conversation; fix turns are visible; every honest degradation reaches the UI; the API gap list is closed | BE-03, BE-07, BE-08, BE-09, BE-10, BE-11, BE-13, BE-17, BE-18 | `artifacts/hardening-r3-*.txt`; probe 3, 6 promoted; new history test |
| **R4** | Frontend trust and UX | Every backend failure is visible; streaming never dies silently; the panels stop lying | FE-01 – FE-15 | `artifacts/hardening-r4-*.txt`; new component tests |
| **R5** | Local packaging and operations | One-command install and run, production serving mode, first-run guidance, log file, retention, recovery, uninstall | AC-1 – AC-3, AC-9, AC-11; new tasks R5-T1..T10 | `scripts/acceptance-local.ps1` step 1-2, 5-7 PASS |
| **R6** | Scalability seams | The eight guardrails in §2 become enforced invariants with tests | L-1 – L-8 | `artifacts/hardening-r6-*.txt`; guardrail grep tests |
| **R7** | Release verification | The full acceptance run on a clean checkout, labeled honestly | AC-1 – AC-12 | `artifacts/hardening-final-*.txt`; release checklist signed |

Ordering is not negotiable for R0 → R1 → R2 (truth, then data safety, then input safety).
R3 and R4 may swap. R5 depends on R1 and R2 landing first: packaging a product whose
cancellation is broken ships the bug to a user who cannot read the log. R6 is last because
its value is architectural and its risk is touching everything.

---

## 4. Conventions every phase follows

**Branch and commits.** Work stays on `master` in the existing worktree (no new branch, no
worktree, because the dirty worktree must be preserved). One commit per task, exact paths
only, conventional message. Never stage `archive/`, `artifacts/`, or `docs/reviews/`
wholesale — stage the file the task produced.

**Test-first.** Every fix starts with a failing test that reproduces the finding, run to
confirm it fails for the stated reason, then the minimal fix, then the test passes, then
the full suite. The probes in `docs/reviews/2026-10-11-full-app-review/probes/` are the
reproduction scripts; each promoted probe becomes a permanent test under
`services/vibe/tests/` so the defect cannot return.

**Evidence.** After each phase: the phase's commands and their raw output to
`artifacts/hardening-r<N>-<topic>.txt`, linked from TASKS.md and CURRENT_STATE.md.

**Promotion rule for probes.** A probe that writes only to `tempfile` directories can be
promoted as-is. A probe that touches the real workspace cannot; R1-T4 adds the
`tmp_path`-based variant instead.

**Review gate.** After each phase, run the `code-review` skill against the phase diff and
record the verdict in the phase evidence file before starting the next phase.

---

## 5. Phase R0 — Truth and bookkeeping (executable now)

R0 exists because of a specific property of this repository: its documents are load-bearing.
The router tells every future agent where truth lives, and the snapshot is what a fresh
session believes. A stale snapshot is therefore a real defect, and the review found seven
of them. R0 fixes the documents *before* code changes them, so that the plan, the task
list, and the memory ledger describe the work rather than lagging it.

R0 changes no application behavior. It is safe to execute in one sitting.

### R0-T1: Correct the review register for a finding the review itself missed

**Finding added while planning this plan: DOC-07.**

**Files:**
- Modify: `docs/reviews/2026-10-11-full-app-review/04-docs-and-process.md` (append DOC-07)
- Modify: `docs/reviews/2026-10-11-full-app-review/FINDINGS.md` (add the row)
- Modify: `docs/reviews/2026-10-11-full-app-review/README.md` (finding count)

**What is wrong:** `ENVIRONMENT.md`'s capability table says
"Playwright browser capture — REMOVED from deps (offline, not cached). Post-M1 refinement —
restore when network returns." That is false on the current tree in two independent ways:
`services/vibe/src/vibe/executor/browser.py` is a real Playwright driver (P5, 2026-10-05,
recorded in MEMORY.md), and `services/vibe/pyproject.toml` declares `playwright>=1.63.0`
as a runtime dependency. A reader deciding whether the browser checks can work is misled.

**Steps:**
- [ ] Confirm the claim before writing it:
  `services\vibe\.venv\Scripts\python.exe -c "import playwright, importlib.metadata as m; print(m.version('playwright'))"`
  Expected: a version number, not ImportError.
- [ ] Confirm the driver is real: `grep -n "playwright" services/vibe/src/vibe/executor/browser.py`
  Expected: an import and a `chromium`/`launch` usage.
- [ ] Append a DOC-07 section to `04-docs-and-process.md` with the two file:line facts and
  severity **Low** (documentation only; the code is correct).
- [ ] Add the DOC-07 row to `FINDINGS.md` in the docs table.
- [ ] Update the counts line in `FINDINGS.md` and the README status row: docs/CI/tests
  becomes 1 Medium, 6 Low, 1 Info, and the total becomes 40 findings.
- [ ] Commit: `docs(review): record DOC-07, the stale Playwright capability claim`

### R0-T2: Make `format:check` green (DOC-01) and stop the docs lying about it

**Files:**
- Reformat: `apps/vibe/src/components/ui/__tests__/CommandPalette.test.tsx` (the only failing file)
- Modify: `TASKS.md` (P3b row), `CURRENT_STATE.md` (P3 entry)

**Critical:** do **not** run `pnpm format` (that would rewrite the whole tree, including
uncommitted user work — the exact reason MEMORY.md records the sweep as deferred). Format
the single file by exact path.

**Steps:**
- [ ] Show the failure and its exact scope:
  `cd apps/vibe; pnpm exec prettier --check src/components/ui/__tests__/CommandPalette.test.tsx`
  Expected: FAIL.
- [ ] Format only that file:
  `cd apps/vibe; pnpm exec prettier --write src/components/ui/__tests__/CommandPalette.test.tsx`
- [ ] Re-run the full check: `pnpm format:check` → Expected: PASS, all files.
- [ ] Re-run the test that file belongs to: `pnpm exec vitest run src/components/ui/__tests__/CommandPalette.test.tsx` → Expected: PASS.
- [ ] Update the P3b row in `TASKS.md` and the P3 entry in `CURRENT_STATE.md`: the prettier
  sweep is complete, `format:check` passes, and `format:check` may now be kept in CI.
- [ ] Commit: `style(vibe): format CommandPalette test; format:check is green`

### R0-T3: Refresh `CURRENT_STATE.md` (DOC-02, DOC-03, DOC-04)

**Files:** Modify `CURRENT_STATE.md`

This is the file's own contract ("refreshed at session start"), and it is wrong in three
independent ways. Replace, do not append a correction — a snapshot holds current values.

- [ ] **Git section:** branch `master`; latest commit `0849b14` ("P3b — prettier sweep");
  history `0849b14 → e6a5c75 → b377020 → 47edd56 → 635828d`; dirty files **9**
  (`git status --porcelain` → 5 modified, 4 untracked) plus the new `docs/reviews/` and
  `docs/superpowers/plans/` trees this session added. Record the command, not just the
  number: `git status --porcelain | wc -l` ran to get it.
- [ ] **Tasks section:** add the review outcome — 40 findings across
  `docs/reviews/2026-10-11-full-app-review/`; the hardening program and its phase order;
  next milestone is **R0**, not M4.
- [ ] **DOC-03:** remove the three conflicting test counts from the M5/P6/P3a entries or
  suffix each with its date, and state the current measured count once, in the Tasks
  section, with its evidence path (`docs/reviews/2026-10-11-full-app-review/evidence/baseline-vitest.txt`).
- [ ] **DOC-04:** delete the closing "Open finding … 3680 paths (3667 under node_modules)"
  from the M5 entry and replace it with: resolved by task 16; the shared walk returns 10
  paths with 0 under `node_modules` for the E2E workspace
  (`docs/reviews/2026-10-11-full-app-review/evidence/`, produced by `probes/file_count_probe.py`).
- [ ] **Active jobs:** re-verify the ports rather than copying the old text — the recorded
  values are from 2026-10-04. Run the check and record what it actually returns:
  `Get-NetTCPConnection -LocalPort 7321,7322,5173,7399 -ErrorAction SilentlyContinue`.
- [ ] Refresh the "last verified" dates on every line touched.
- [ ] Commit: `docs(state): refresh CURRENT_STATE for the review and hardening program`

### R0-T4: Correct `ENVIRONMENT.md` and record the CI reality (DOC-05, DOC-07)

**Files:** Modify `ENVIRONMENT.md`

- [ ] Capability table: replace the Playwright "REMOVED from deps" row with its true state —
  driver implemented (`executor/browser.py`), `playwright>=1.63.0` a runtime dependency, and
  the browser binary installed with `playwright install chromium` (note that a fresh clone
  needs that step; R5-T1 puts it in the setup path).
- [ ] Network section: keep "GitHub Actions … never been executed" and add that as of
  2026-10-11 the workflow would additionally have failed at the frontend Format step
  (DOC-01), now fixed by R0-T2 — so its first real run is still unverified and must be
  labeled `SKIPPED`, not assumed green.
- [ ] Note the pnpm workspace move that DOC-05 records: install is owned by the root
  workspace, so CI's `cache-dependency-path: apps/vibe/pnpm-lock.yaml` keys on a lockfile
  pnpm does not use for a workspace install (fix tracked as R5-T10).
- [ ] Commit: `docs(env): correct the Playwright capability row and the CI cache note`

### R0-T5: Register the new durable knowledge kinds (DOC-06)

**Files:** Modify `AGENTS.md` (document map only)

**This is a stable-policy edit and is therefore `NEEDS_USER_DECISION`.** The review
recommends it and R0 executes it only with the user's go, because AGENTS.md says a new
durable kind must land in the map and also that policy changes are never a drive-by.

Two rows, no other change:

| Concern | File | Read it when | Update it when |
|---|---|---|---|
| Code review | `docs/reviews/README.md` | before fixing a known defect | a finding is fixed or a newer review supersedes it |
| Implementation plans | `docs/superpowers/plans/` | before executing a phase | a plan is written or a phase lands |

- [ ] Create `docs/reviews/README.md` — a three-line index listing
  `2026-10-11-full-app-review/` and the rule that reviews are dated and immutable (a fixed
  review is superseded, never rewritten, so the register stays auditable).
- [ ] Add the two rows to the document map.
- [ ] Also update the "Architecture audit" row's "Update it when" cell to mention the review
  as the newer superseding artifact for structure findings.
- [ ] Commit: `docs(agents): register code reviews and implementation plans in the map`

### R0-T6: Add the program to `TASKS.md` and `HANDOFF.md`

**Files:** Modify `TASKS.md`, `HANDOFF.md`, `PLAN.md`

- [ ] `TASKS.md` — fix the pre-existing broken table: the `## Now` table has a blank line
  before its `| 15 |` row, which splits it into two tables and leaves the second headerless.
  Delete the blank line. (Found by reading lines 27–28 of the file.)
- [ ] `TASKS.md` — add a row to `## Now`: the 2026-10-11 review, `done`, evidence
  `docs/reviews/2026-10-11-full-app-review/FINDINGS.md`, and the hardening program, next
  action R0.
- [ ] `TASKS.md` — add a section `## Local production hardening — 2026-10-11` with one row
  per phase (R0–R7), each `pending` with its gate and evidence path column, mirroring §3.
  Every subsequent phase updates its own row in place.
- [ ] `HANDOFF.md` — append a dated narrative section `## Review and hardening program
  (2026-10-11)`: what was reviewed, the finding counts by severity, the four highest-impact
  findings, the phase order, and the exact next action. HANDOFF owns narrative; it must not
  duplicate the register, so it links it.
- [ ] `PLAN.md` — this is a user-approved spec change, so execute it only with the user's go
  (it is bundled into the same decision as R0-T5):
  - add `M6 — Local production readiness | One-command local install and run, production
    serving mode, first-run guidance, retention and recovery, honest states | pending`
    with the plan path as its reference;
  - change M4's status from plain `pending` to `deferred — local-first; seams kept
    (see M6 and §2 of the hardening plan)`;
  - correct §4 Open items: "EventLog SQLite persistence (currently in-memory)" is **false**
    — the log has been SQLite-backed since P1 (2026-10-04). Remove it, and remove
    "Workspace scaffolding … Vite+React+TS template on session creation" if it is
    implemented; verify with `services/vibe/src/vibe/workspace.py` before deleting.
  - add one line under §2 pointing at the hardening plan for the local-production
    acceptance criteria.
- [ ] Commit: `docs(plan): add M6 and register the hardening program`


### R0-T7: Record what this program learned and decided (MEMORY.md)

**Files:** Modify `MEMORY.md`

The user named memory explicitly, and this program produces both things MEMORY exists for: a
decision that must not be re-litigated, and a mechanism that a future agent will otherwise
re-commit. Two ledgers, appended in their existing formats.

- [ ] **Decisions ledger** — one entry per answered item in `15`, each naming the decision, the
      date, and the reason. Write the two R0 cannot proceed without now: **D3** (reviews and
      plans are registered document kinds) and **D1** (browser on a single loopback port, dev
      mode retained). Add the rest as they are answered — never pre-fill a decision the user has
      not made.
- [ ] **Lessons ledger** — the five mechanisms the review proved, each as
      cause → consequence → rule, because each one is a trap a fresh agent will fall into:
      - a route-level "is it running?" check separated from the claim by an `await` is not a
        guard (BE-04) → claim the slot synchronously;
      - `pnpm` and `npm` are shims, so killing the launched process leaves the real work alive
        (BE-05) → kill the process tree, and never treat a timeout as harmless;
      - a name allowlist plus `split("@")[0]` is bypassable through an alias or a protocol
        specifier (BE-02) → decide on the whole specifier, never the name alone;
      - a `logger` call whose placeholders do not match its arguments is silent (BE-07) → turn
        `logging.raiseExceptions` on in tests so the next mismatch fails the suite;
      - a `body: dict` route turns a user's typo into a 500 (BE-01) → validate at the edge.
- [ ] **Milestones** — one line per completed phase under the existing milestone section, with
      its exit-gate artifact path, so "where are we" is answerable from MEMORY alone.
- [ ] Keep each lesson to one clause per arrow and cite the finding id: the register holds the
      detail, and MEMORY must not become a second review.
- [ ] Commit: `docs(memory): record the hardening decisions and the five proven failure mechanisms`

**R0 exit gate:** `pnpm format:check` PASS; `git status --porcelain` shows only the intended
files changed; `artifacts/hardening-r0-docs.txt` contains the before/after of every command
in R0-T2, the re-verified ports from R0-T3, and the `MEMORY.md` diff from R0-T7.


---

## 6. Phase R1 — Correctness under concurrency and cancellation

Three findings share one property: each leaves the user's machine in a state they cannot
see or undo — a duplicated run, a live orphan process, a destroyed transcript. They ship
before anything cosmetic.

### R1-T1: Make the one-run-per-session guard atomic (BE-04)

**Files:**
- Modify: `services/vibe/src/vibe/runs.py` (add `try_start`)
- Modify: `services/vibe/src/vibe/api/routes/chat.py:34-36` (claim) and `:85` (remove the late claim)
- Test: `services/vibe/tests/test_run_registry.py`

**Root cause, exactly:** `chat.py:34` checks `runs.is_running(sid)` and `:85` claims
`runs.start(sid)`. Between them are six `await` points (`require_session`,
`ensure_workspace`, `event_log.append`, `retitle_from_message`, `event_bus.publish`,
`_snapshot_files`). Two requests on the same event loop both pass line 34, then both reach
line 85 — confirmed by probe 4, which got 200 from both concurrent sends and saw
`runtime.run` called twice.

**Interfaces:**
- Produces: `RunRegistry.try_start(session_id: str) -> RunHandle | None` — synchronous, so
  the check and the claim cannot interleave.

- [ ] **Step 1: Write the failing test**

```python
# services/vibe/tests/test_run_registry.py
import asyncio

from vibe.runs import RunRegistry


def test_try_start_claims_once():
    reg = RunRegistry()
    first = reg.try_start("s1")
    assert first is not None
    assert reg.try_start("s1") is None


def test_try_start_allows_a_new_run_after_finish():
    reg = RunRegistry()
    first = reg.try_start("s1")
    reg.finish("s1", first)
    assert reg.try_start("s1") is not None


def test_concurrent_try_start_has_one_winner():
    reg = RunRegistry()

    async def race():
        return await asyncio.gather(*[asyncio.to_thread(reg.try_start, "s1") for _ in range(8)])

    winners = [h for h in asyncio.run(race()) if h is not None]
    assert len(winners) == 1
```

- [ ] **Step 2: Run it and watch it fail**

Run: `services/vibe/.venv/Scripts/python.exe -m pytest tests/test_run_registry.py -v`
Expected: FAIL — `AttributeError: 'RunRegistry' object has no attribute 'try_start'`

- [ ] **Step 3: Add the atomic claim**

```python
    def try_start(self, session_id: str) -> RunHandle | None:
        """Claim the session's run slot, or None if one is already held.

        Synchronous on purpose: there is no await between the presence check and
        the insert, so two tasks on one event loop cannot both win. Checking
        is_running in the route and calling start fifty lines later is what let
        two concurrent sends run the agent twice.
        """
        if session_id in self._runs:
            return None
        handle = RunHandle(session_id=session_id)
        self._runs[session_id] = handle
        return handle
```

Note the deliberate difference from `is_running`: presence, not `not aborted`. An aborted
handle that has not finished yet still owns the slot, because its task may still be writing
events. Releasing on abort would reopen the interleaving window.

- [ ] **Step 4: Move the claim to the top of the route and wrap the body**

In `send_message`, replace the guard at `:34-36` with an early claim and delete
`handle = runs.start(sid)` at `:85`. The whole body from `ensure_workspace` to the final
`return` goes inside one `try/finally` whose `finally` is the existing release:

```python
    handle = runs.try_start(sid)
    if handle is None:
        raise ApiError(ErrorCode.RUN_IN_PROGRESS, "a run is already in progress for this session")
    try:
        ...                       # everything currently at lines 38-155
    finally:
        if handle.task is not None and not handle.task.done():
            handle.task.cancel()
        runs.finish(sid, handle)
```

This matters beyond the race: today a failure between line 34 and line 85 (a bad body, a
missing workspace) leaves a claimed handle behind and wedges the session forever. The single
`finally` releases on every path. Validate the body *before* claiming (R2-T1 moves it into a
Pydantic model), so a malformed request never claims a slot at all.

- [ ] **Step 5: Test the route, not just the registry**

```python
async def test_two_concurrent_sends_run_the_agent_once(client, counting_runtime, session_id):
    first, second = await asyncio.gather(
        client.post(f"/sessions/{session_id}/messages", json={"content": "a"}),
        client.post(f"/sessions/{session_id}/messages", json={"content": "b"}),
    )
    assert sorted([first.status_code, second.status_code]) == [200, 409]
    assert counting_runtime.calls == 1
    assert second.json()["error"]["code"] == "run_in_progress"
```

- [ ] **Step 6: Run the suite**

Run: `services/vibe/.venv/Scripts/python.exe -m pytest -q` → Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add services/vibe/src/vibe/runs.py services/vibe/src/vibe/api/routes/chat.py services/vibe/tests/test_run_registry.py
git commit -m "fix(chat): claim the run slot atomically so two sends cannot both run"
```

### R1-T2: Kill the process tree on timeout and on stop (BE-05)

**Files:**
- Modify: `services/vibe/src/vibe/executor/local.py` (`_run` timeout path, `stop_dev_server`)
- Test: `services/vibe/tests/test_executor_timeout.py`

**Root cause:** `_run` line 60 catches `TimeoutError` and returns a `ToolResult` without ever
touching `proc`. `proc.communicate()` is cancelled, the `pnpm install`/`build` process keeps
running, and nothing holds a reference to it — probe 5 confirmed the child survived. The
dev-server path (`stop_dev_server`) has the opposite, correct instinct (`terminate` then
`kill`), but kills only the shim: `pnpm` is a `.cmd` wrapper, so the real `node` child is a
grandchild that survives.

- [ ] **Step 1: Write the failing test**

```python
# services/vibe/tests/test_executor_timeout.py
import sys, time

import pytest

from vibe.executor.local import LocalSubprocessExecutor


@pytest.mark.asyncio
async def test_timeout_leaves_no_live_process(tmp_path):
    marker = tmp_path / "still-alive"
    # The parent spawns a grandchild that writes the marker after the parent is
    # gone, so killing only the parent leaves the marker behind.
    inner = f"import time,pathlib;time.sleep(3);pathlib.Path(r'{marker}').write_text('alive')"
    script = f"import subprocess,time;subprocess.Popen([{sys.executable!r},'-c',{inner!r}]);time.sleep(30)"
    ex = LocalSubprocessExecutor(tmp_path, timeout=1)
    result = await ex._run([sys.executable, "-c", script])
    assert result.is_error and result.content == "timeout"
    time.sleep(4)
    assert not marker.exists(), "the grandchild outlived the timeout"
```

- [ ] **Step 2: Run it and watch it fail**

Run: `services/vibe/.venv/Scripts/python.exe -m pytest tests/test_executor_timeout.py -v`
Expected: FAIL — the marker exists, i.e. the grandchild is alive.

- [ ] **Step 3: Add a tree kill**

```python
    async def _kill_tree(self, proc: asyncio.subprocess.Process) -> None:
        """Kill a process and its descendants.

        pnpm is a shim that spawns node, so killing the shim leaves the real work
        running -- the leak behind both the timeout and a dev server that keeps
        its port. taskkill /T walks the tree on Windows; POSIX gets the process
        group created by start_new_session.
        """
        if proc.returncode is not None:
            return
        if os.name == "nt":
            killer = await asyncio.create_subprocess_exec(
                "taskkill", "/F", "/T", "/PID", str(proc.pid),
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            )
            await killer.wait()
        else:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except TimeoutError:
            proc.kill()
```

- [ ] **Step 4: Wire it in**

- In `_run`, add `start_new_session=True` to `create_subprocess_exec` (ignored on Windows,
  required for `killpg` on POSIX), and on the `TimeoutError` branch call
  `await self._kill_tree(proc)` **before** returning the timeout result.
- In `stop_dev_server`, replace the `terminate()`/`wait_for`/`kill()` block with: try
  `proc.terminate()` and `wait_for(proc.wait(), 5)`; on timeout call `await self._kill_tree(proc)`.
- Add `import signal` to the imports.

- [ ] **Step 5: Run the tests and the suite**

Run: `services/vibe/.venv/Scripts/python.exe -m pytest tests/test_executor_timeout.py -q` → PASS
Run: `services/vibe/.venv/Scripts/python.exe -m pytest -q` → PASS

- [ ] **Step 6: Commit**

```bash
git add services/vibe/src/vibe/executor/local.py services/vibe/tests/test_executor_timeout.py
git commit -m "fix(executor): kill the process tree on timeout and on dev-server stop"
```

### R1-T3: Make session delete keep the transcript when the move fails (BE-06)

**Files:**
- Modify: `services/vibe/src/vibe/lifecycle.py:55-70`
- Test: `services/vibe/tests/test_delete_cascade.py`

**Root cause, exactly:** step 3 calls `self._event_log.clear(session_id)` at line 58; step 4
moves the workspace at line 66 and can raise (a locked file, a permission error, a
cross-device rename); step 5 deletes the row. If step 4 raises, the events are already gone
but the row survives — probe 7 measured exactly this: 2 events became 0 while the session row
remained. The user sees an empty conversation and their files still on disk.

- [ ] **Step 1: Write the failing test**

```python
async def test_failed_move_keeps_events_and_row(lifecycle, event_log, monkeypatch):
    sid = await lifecycle._store.create_session(ModelRef("openai", "gpt-4o"))
    await event_log.append(sid, "user/message", {"content": "keep me"})

    def boom(*_args, **_kwargs):
        raise PermissionError("locked")

    monkeypatch.setattr(Path, "rename", boom)

    with pytest.raises(PermissionError):
        await lifecycle.delete(sid)

    assert len(await event_log.get(sid)) == 1, "a failed delete destroyed the transcript"
    assert await lifecycle._store.get_session(sid) is not None, "the row was removed anyway"
```

- [ ] **Step 2: Run it and watch it fail**

Run: `services/vibe/.venv/Scripts/python.exe -m pytest tests/test_delete_cascade.py -k failed_move -v`
Expected: FAIL — the events were cleared at line 58.

- [ ] **Step 3: Reorder so nothing irreversible precedes a step that can fail**

The order becomes: abort run → close executor → drop policy/approvals → **move the workspace**
→ clear events → delete the row. The move is the only step that can fail on environmental
grounds, so it moves ahead of both destructive steps.

```python
        # 4. Move the workspace aside first. It is the only step that can fail
        #    for environmental reasons (a locked file, a permission error), and
        #    everything after it destroys something -- so if it raises, the
        #    transcript and the row are both still here to retry.
        workspace = self._workspace_dir / session_id
        if workspace.exists():
            trash = (self._workspace_dir / ".trash"
                     / f"{session_id}-{datetime.now(UTC):%Y%m%d-%H%M%S}")
            trash.parent.mkdir(parents=True, exist_ok=True)
            workspace.rename(trash)
            logger.info("session %s workspace moved to %s", session_id, trash.name)

        # 5. Now the destructive steps.
        self._event_log.clear(session_id)
        await self._store.delete_session(session_id)
```

- [ ] **Step 4: Run the tests**

Run: `services/vibe/.venv/Scripts/python.exe -m pytest tests/test_delete_cascade.py -q` → PASS
Then re-run probe 7 and confirm it reports a clean failure instead of losing events:
`services/vibe/.venv/Scripts/python.exe ../../docs/reviews/2026-10-11-full-app-review/probes/backend_probe.py`

- [ ] **Step 5: Commit**

```bash
git add services/vibe/src/vibe/lifecycle.py services/vibe/tests/test_delete_cascade.py
git commit -m "fix(lifecycle): move the workspace before clearing events so a failed delete is retryable"
```

### R1-T4: Promote the review probes into the permanent suite

**Files:** Create `services/vibe/tests/test_api_validation.py`,
`services/vibe/tests/test_supply_chain.py`, `services/vibe/tests/test_history.py`,
`services/vibe/tests/test_logging_setup.py`; modify `services/vibe/tests/conftest.py` if a
`tmp_path`-scoped app factory is missing.

Every promoted probe uses `tmp_path`, never the real workspace, and asserts the *code*
(`run_in_progress`, `validation_failed`, a specific allowlist verdict), not just a status. The
probe scripts stay in the review directory as the historical reproduction.

- [ ] Port probe 1 (unvalidated bodies) into `test_api_validation.py`, one case per endpoint,
  parametrized. This is R2-T1's failing test, so write it here and let R2-T1 make it pass.
- [ ] Port probe 2 (allowlist bypass) into `test_supply_chain.py`, marked
  `@pytest.mark.xfail(strict=True, reason="BE-02, fixed in R2-T2")` so the defect stays visible
  in the suite and the marker fails loudly if it ever silently regresses.
- [ ] Port probe 3 (no conversation memory) into `test_history.py`, also `xfail(strict=True)`
  until R3-T1.
- [ ] Port probe 6 (`VIBE_HOST` warning `TypeError`) into `test_logging_setup.py` as
  `xfail(strict=True)` until R3-T3.
- [ ] Commit: `test(backend): promote the review probes into the permanent suite`

**R1 exit gate:** `artifacts/hardening-r1-pytest.txt` shows the full suite PASS with the
`xfail(strict=True)` markers visible; `artifacts/hardening-r1-probe4.txt` and
`artifacts/hardening-r1-probe5.txt` show probes 4 and 5 no longer reproducing.

---

## 7. Phase R2 — Validation and secrets

> **Corrections from phase R1 execution (2026-10-11) — read before starting.** R1 promoted the
> review probes into the permanent suite and measured each one against the current code, which
> changed three details of the spec below. They are already applied in this file; this note
> records why, so nobody "restores" the original.
> 1. The `is_allowlisted` guard in Step 3 of R2-T2 originally read
>    `any(ch in name for ch in "/\\ \t\n")`. That rejects **every scoped package** — `@types/react`
>    contains a `/` — contradicting the same task's ALLOWED list. The corrected code distinguishes
>    a scope separator from a path separator.
> 2. `react@^19 nope` needs the junk-specifier check now in Step 3: it resolves to the
>    allowlisted name `react`, so without that check its strict-xfail case XPASSes and fails the
>    suite.
> 3. R2-T1 must change the existing validation handler from **422 to 400** — see Step 4's
>    correction bullet. The promoted tests already assert 400.

### R2-T1: Typed request models on every route that takes a dict (BE-01)

**Files:**
- Create `services/vibe/src/vibe/api/schemas.py`
- Modify `api/routes/chat.py:28`, `api/routes/sessions.py:27`, `:67`, `:108`, `api/app.py`
- Test `services/vibe/tests/test_api_validation.py` (from R1-T4)

**Root cause:** four routes declare `body: dict`, so FastAPI validates nothing. Probe 1 showed
`{"model": {}}` → 500 and `{"model": {"provider_id": 1}}` → 500, because
`ModelRef(**body["model"])` raises `TypeError` inside the handler. A missing `content` is a
`KeyError` → 500; so is a missing `model`; and `write_file` calls `body.get("content", "")`, so
`{"content": 5}` reaches `write_text` and raises `TypeError`.

- [ ] **Step 1: Write the failing test**

```python
# services/vibe/tests/test_api_validation.py
import pytest

BAD_BODIES = [
    {"model": {}},
    {},
    {"model": {"provider_id": 1, "model_id": "x"}},
    {"model": {"provider_id": "openai"}},
    {"model": ["openai", "gpt-4o"]},
]


@pytest.mark.parametrize("body", BAD_BODIES)
def test_create_session_rejects_bad_bodies(client, body):
    r = client.post("/sessions", json=body)
    assert r.status_code == 400, r.text
    assert r.json()["error"]["code"] == "validation_failed"
    assert "Traceback" not in r.text
```

Add the equivalent for `POST /sessions/{sid}/messages` (`{}`, `{"content": 5}`) and
`PUT /sessions/{sid}/files/x` (`{"content": 5}`).

- [ ] **Step 2: Run it and watch it fail**

Run: `services/vibe/.venv/Scripts/python.exe -m pytest tests/test_api_validation.py -v`
Expected: FAIL — 500 with `{"error": {"code": "internal"}}`

- [ ] **Step 3: Define the schemas**

```python
# services/vibe/src/vibe/api/schemas.py
"""Request bodies. Typed so a malformed request is a 400, never a 500.

Every route used to take body: dict and index into it, so a missing or mistyped
field surfaced as a KeyError/TypeError traceback and a generic internal error.
Validation belongs at the edge, where FastAPI can turn it into a request error
instead of a crash.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ModelRefIn(BaseModel):
    provider_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)


class CreateSessionIn(BaseModel):
    model: ModelRefIn


class UpdateSessionIn(BaseModel):
    title: str | None = None
    model: ModelRefIn | None = None


class AttachmentIn(BaseModel):
    name: str = Field(min_length=1)
    content_type: str = Field(min_length=1)
    data_base64: str = Field(min_length=1)


class SendMessageIn(BaseModel):
    content: str = Field(min_length=1)
    attachments: list[AttachmentIn] = Field(default_factory=list)


class WriteFileIn(BaseModel):
    content: str
```

- [ ] **Step 4: Switch the routes and map validation failures into the taxonomy**

FastAPI raises `RequestValidationError` for a bad model. Add one handler in `api/app.py` beside
the existing `ApiError` handler so the response keeps the single error shape:

```python
@app.exception_handler(RequestValidationError)
async def _validation(request, exc):
    first = exc.errors()[0] if exc.errors() else {}
    loc = ".".join(str(p) for p in first.get("loc", ()) if p != "body")
    detail = first.get("msg", "invalid request")
    message = f"{loc}: {detail}" if loc else detail
    return JSONResponse(status_code=400, content=body(ErrorCode.VALIDATION_FAILED, message))
```

- [ ] **Correction measured during phase R1 (2026-10-11).** `api/app.py` already has a
  validation handler, `_handle_validation_error`, and it returns **422**. The promoted cases in
  `tests/test_api_validation.py` assert **400** `validation_failed`, which is why they are
  `xfail(strict=True)` today. So this step must **replace** that handler (or change its status
  code) rather than add a second one beside it, and it must cover shape errors — a wrong type, a
  missing field and a non-object body — not only missing fields. Every xfail in that file has to
  become a real pass in this task, which is the proof the edge is now typed.

Then in the routes: `body: CreateSessionIn` → `ModelRef(body.model.provider_id, body.model.model_id)`;
`body: UpdateSessionIn` → use `body.title is not None` / `body.model is not None`;
`body: SendMessageIn`; `body: WriteFileIn` → `body.content`.

**Behavior note:** with `str | None = None`, `{"title": null}` now means "no change" rather
than "set the title to null" — correct here, since a null title is not a valid title.

- [ ] **Step 5: Run the tests and the full suite**

Run: `services/vibe/.venv/Scripts/python.exe -m pytest tests/test_api_validation.py -q` → PASS
Run: `services/vibe/.venv/Scripts/python.exe -m pytest -q` → PASS. Some existing tests may send
bodies that now fail validation; fix the test's body, never the schema, and note each.

- [ ] **Step 6: Commit**

```bash
git add services/vibe/src/vibe/api/schemas.py services/vibe/src/vibe/api/app.py services/vibe/src/vibe/api/routes/chat.py services/vibe/src/vibe/api/routes/sessions.py services/vibe/tests/test_api_validation.py
git commit -m "fix(api): type every request body so malformed input is a 400, not a 500"
```

### R2-T2: Close the allowlist bypass (BE-02)

**Files:**
- Modify `services/vibe/src/vibe/supply_chain.py:22-32`
- Test `services/vibe/tests/test_supply_chain.py` (un-xfail the R1-T4 port)

**Root cause, exactly:** `name = package.split("@")[0]` keeps only the part before the first
`@`. For `react@npm:evil-package` that is `react`, which is allowlisted — but npm installs
`evil-package`. The same hole covers `github:`, `git:`, `file:`, `link:`, `http(s):` and
`workspace:` specifiers. The one gate before an install can be redirected.

- [ ] **Step 1: Write the failing test**

```python
# services/vibe/tests/test_supply_chain.py
import pytest

from vibe.supply_chain import is_allowlisted

ALLOWED = ["react", "react@^19", "react@19.0.0", "@types/react", "@types/react@^19", "zustand@^5"]
DENIED = [
    "react@npm:evil-package",      # alias installs something else entirely
    "react@npm:@evil/pkg",         # alias to a scoped package
    "@types/react@npm:evil",       # scoped alias
    "react@github:evil/repo",      # git protocol
    "react@git+https://evil/x.git",
    "react@file:../evil",          # local path
    "react@link:../evil",
    "react@http://evil/x.tgz",
    "react@workspace:*",
    "evil-package",                # simply not on the list
    "react-malicious",             # prefix, not a match
    "", " ", "../evil", "@scope", "react@^19 nope",
]


@pytest.mark.parametrize("spec", ALLOWED)
def test_allowlisted(spec):
    assert is_allowlisted(spec) is True


@pytest.mark.parametrize("spec", DENIED)
def test_denied(spec):
    assert is_allowlisted(spec) is False
```

- [ ] **Step 2: Run it and watch it fail**

Run: `services/vibe/.venv/Scripts/python.exe -m pytest tests/test_supply_chain.py -v`
Expected: FAIL on `react@npm:evil-package` and the other protocol cases — they return True.

- [ ] **Step 3: Parse the specifier instead of truncating it**

```python
# npm dependency specifiers that name something other than the bare package.
# An alias or a protocol installs a package the allowlist never approved, so it
# can never be allowlisted by its left-hand name.
_PROTOCOLS = ("npm:", "github:", "git:", "git+", "file:", "link:", "portal:", "workspace:", "http:", "https:")


def _split_spec(package: str) -> tuple[str, str]:
    """Split an npm dependency specifier into (name, version-or-protocol).

    Handles the scoped form, where the leading '@' belongs to the scope and the
    version separator is the second '@': "@types/react@^19" -> ("@types/react", "^19").
    """
    package = package.strip()
    if package.startswith("@"):
        scope, sep, rest = package.partition("/")
        if not sep:
            return package, ""              # "@scope" alone names nothing installable
        name, _, spec = rest.partition("@")
        return f"{scope}/{name}", spec
    name, _, spec = package.partition("@")
    return name, spec


def is_allowlisted(package: str) -> bool:
    """True only if this exact specifier installs an allowlisted package.

    "react" is not enough to decide: "react@npm:evil-package" also starts with
    "react" but installs evil-package, and "react@file:../evil" installs a local
    path. The name must match the allowlist and the specifier must be a plain
    version range.
    """
    name, spec = _split_spec(package)
    # A scoped name is "@scope/pkg": exactly one "/" belongs to the name, so a
    # blanket "no slash" guard would reject @types/react and every @vitejs
    # plugin. Only a traversal segment, a stray separator or whitespace is a
    # path, and any of those is refused before the allowlist is consulted.
    if not name or name in {".", ".."}:
        return False
    if name.startswith("@"):
        if name.count("/") != 1 or name.endswith("/"):
            return False
    elif "/" in name or "\\" in name:
        return False
    if any(ch.isspace() for ch in name):
        return False
    if any(spec.lower().startswith(p) for p in _PROTOCOLS):
        return False
    # "react@^19 nope" resolves to the allowlisted name but is not a version
    # range. npm never accepts whitespace or these metacharacters in a range, so
    # refusing them closes the last way a junk specifier rides the allowlist.
    if any(ch.isspace() or ch in "<>|$" for ch in spec):
        return False
    return name in ALLOWLIST
```

- [ ] **Step 4: Run the tests**

Run: `services/vibe/.venv/Scripts/python.exe -m pytest tests/test_supply_chain.py -q` → PASS
Run: `services/vibe/.venv/Scripts/python.exe -m pytest -q` → PASS. Check that the tool calling
`is_allowlisted` passes the **raw specifier**, not a pre-split name; if it splits first, fix
that call site too and say so in the commit.

- [ ] **Step 5: Commit**

```bash
git add services/vibe/src/vibe/supply_chain.py services/vibe/tests/test_supply_chain.py
git commit -m "fix(security): an alias or protocol specifier can no longer ride the allowlist"
```

### R2-T3: Validate custom-provider models and make the catalog defensive (BE-14)

**Files:**
- Modify `api/routes/providers.py` (validate `models` on create and update)
- Modify `api/routes/catalog.py:25` (`m.get("id")`; skip and log when absent)
- Modify `providers/custom.py` (a model shape with a required `id`)
- Test `services/vibe/tests/test_custom_providers.py` (port custom-probe 1 and 3)

**Root cause:** `catalog.py:25` indexes `m["id"]` and `POST /providers` accepts any `models`
list, so a model without an `id` is creatable (201) and then `GET /catalog` answers 500 for
every client — the model picker is dead until someone edits the JSON by hand.

- [ ] **Step 1: Write the failing tests**

```python
def test_create_provider_rejects_a_model_without_an_id(client):
    r = client.post("/providers", json={"name": "X", "baseUrl": "http://x", "models": [{"name": "n"}]})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "validation_failed"


def test_catalog_survives_a_hand_edited_store(client, store_path):
    # A store written by an older version or edited by hand.
    store_path.write_text(json.dumps({"p1": {
        "id": "p1", "name": "X", "base_url": "http://x", "api_key": "k",
        "models": [{"name": "no-id"}, {"id": "ok", "name": "Fine"}]}}))
    r = client.get("/catalog")
    assert r.status_code == 200
    ids = [m["id"] for p in r.json() for m in p["models"]]
    assert ids == ["ok"], "the malformed model should be skipped, not crash the catalog"
```

- [ ] **Step 2: Run and watch them fail** — the POST returns 201 and `GET /catalog` returns 500.

- [ ] **Step 3: Fix both ends**

- In the providers route, validate each model: require a non-empty `id`, default `name` to the
  `id`, and reject a duplicate `id` inside one provider. Return
  `ApiError(ErrorCode.VALIDATION_FAILED, ...)` — the 400 the route already uses, which the
  review held up as the honest counterexample.
- In `catalog.py`, replace the comprehension with a loop that skips a model without a string
  `id` and logs a warning naming the provider, so an old store degrades to "that model is not
  offered" instead of "the picker is broken".

- [ ] **Step 4: Run the tests and the full suite.**
- [ ] **Step 5: Commit**

```bash
git add services/vibe/src/vibe/api/routes/providers.py services/vibe/src/vibe/api/routes/catalog.py services/vibe/src/vibe/providers/custom.py services/vibe/tests/test_custom_providers.py
git commit -m "fix(providers): reject a model without an id; make the catalog skip bad entries"
```

### R2-T4: Make the provider store durable and non-blocking (BE-15, BE-16)

**Files:**
- Modify `services/vibe/src/vibe/providers/custom.py:41-73`
- Test `services/vibe/tests/test_custom_providers.py` (port custom-probe 2)

**Root cause:** `_load` runs a bare `json.loads` (a truncated file 500s `/providers` and
`/catalog` forever) and `_save` writes in place, so an interrupted write produces exactly the
corruption that bricks the app. Both run synchronously inside async handlers, and the
read-modify-write is unlocked, so two concurrent creates can lose one provider.

- [ ] **Step 1: Write the failing tests**

```python
def test_corrupt_store_degrades_to_empty(client, store_path):
    store_path.write_text("{not json")
    assert client.get("/providers").status_code == 200
    assert client.get("/catalog").status_code == 200


def test_unreadable_store_is_quarantined(client, store_path):
    store_path.write_text("{not json")
    client.get("/providers")
    assert list(store_path.parent.glob("providers.json.corrupt-*")), "keep the bad file for inspection"


async def test_concurrent_creates_do_not_lose_a_provider(store):
    await asyncio.gather(*[
        asyncio.to_thread(store.create, name=f"p{i}", base_url="http://x", api_key="k", models=[])
        for i in range(5)
    ])
    assert len(store.list()) == 5
```

- [ ] **Step 2: Run and watch them fail** — the first two 500; the third loses providers.

- [ ] **Step 3: Guard the load, make the save atomic, get off the event loop**

```python
    def _load(self) -> dict[str, dict]:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, json.JSONDecodeError) as e:
            # A truncated file must not brick the model picker. Keep the bad file
            # (it may hold a key the user wants back) and start empty.
            quarantine = self._path.with_name(
                f"{self._path.name}.corrupt-{datetime.now(UTC):%Y%m%d-%H%M%S}")
            try:
                self._path.replace(quarantine)
            except OSError:
                pass
            logger.warning("provider store unreadable (%s); quarantined to %s", e, quarantine.name)
            return {}
        return data if isinstance(data, dict) else {}

    def _save(self, data: dict[str, dict]) -> None:
        # Atomic: a reader never sees a half-written file, and an interrupted
        # write leaves the previous store intact rather than a truncated one.
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(tmp, self._path)
```

Add a `threading.Lock` held across the read-modify-write in create/update/delete, and change
the async route handlers to `await asyncio.to_thread(store.create, ...)` — the pattern the
event log already uses.

- [ ] **Step 4: Run the tests and the full suite.**
- [ ] **Step 5: Commit**

```bash
git add services/vibe/src/vibe/providers/custom.py services/vibe/src/vibe/api/routes/providers.py services/vibe/src/vibe/api/routes/catalog.py services/vibe/tests/test_custom_providers.py
git commit -m "fix(providers): atomic, guarded, lock-protected provider store"
```

**R2 exit gate:** `artifacts/hardening-r2-pytest.txt` PASS; probes 1 and 2 and custom-probes
1-3 all report the fixed behavior; `GET /catalog` returns 200 with a corrupt store.


---

## 8. Phase R3 — Product completeness

> **Status 2026-10-11: R3-T1, R3-T2, R3-T3 and the backend half of R3-T4 are
> executed and verified** (304 passed, 0 xfailed, ruff clean). Evidence:
> `artifacts/hardening-r3-report.txt`, `artifacts/hardening-r3-pytest.txt`,
> `artifacts/hardening-r3-probes.txt`, `artifacts/hardening-r3-probe-script.txt`.
> The steps below keep their unticked boxes as the record of what the *plan*
> described; the status note, not a box, is the live truth. R3-T5 to R3-T8 are
> still open, as is the GUI field for the system prompt. **Corrected 2026-10-11:** R3-T5 to R3-T8
> landed (see the `R3` row in TASKS.md, `done`) and the GUI field landed with them (`GET`/`PATCH
> /settings`, `SettingsPanel.tsx`); the unticked boxes above remain only as the record of what the
> plan described.

### R3-T1: Give the agent the conversation (BE-03)

**Record first:** this phase adds **BE-19** to the review register (see R3-T4).

**Files:**
- Modify `services/vibe/src/vibe/api/routes/chat.py` (build `AgentInput.messages` from history)
- Modify `services/vibe/src/vibe/config.py` (add `history_messages`)
- Test `services/vibe/tests/test_history.py` (un-xfail the R1-T4 port)

**Root cause, exactly:** `chat.py:45-47` builds `messages=[Message(role="user", content=body["content"], ...)]`
— one message, always. The transcript route and the event log hold the whole conversation, but
the model never sees it, so "make it blue" has no referent. Probe 3 confirmed the runtime
received exactly one message on every turn of a four-message session.

- [ ] **Step 1: Write the failing test**

```python
async def test_second_turn_includes_the_first(client, recording_runtime, session_id):
    await client.post(f"/sessions/{session_id}/messages", json={"content": "build a counter"})
    recording_runtime.reply = "done"
    await client.post(f"/sessions/{session_id}/messages", json={"content": "make it blue"})

    second = recording_runtime.inputs[-1]
    contents = [m.content for m in second.messages]
    assert contents == ["build a counter", "done", "make it blue"], contents


async def test_history_is_capped(client, recording_runtime, session_id, settings):
    settings.history_messages = 2
    for i in range(6):
        await client.post(f"/sessions/{session_id}/messages", json={"content": f"m{i}"})
    # Corrected during execution: history_messages caps what is replayed *from the
    # log*, and the current turn is appended to that window, so limit=2 yields
    # three messages, not two. Assert the contents, not a length.
    assert [m.content for m in recording_runtime.inputs[-1].messages] == ["m4", "ok", "m5"]
```

- [ ] **Step 2: Run it and watch it fail**

Run: `services/vibe/.venv/Scripts/python.exe -m pytest tests/test_history.py -v`
Expected: FAIL — the second turn's input holds only `["make it blue"]`.

- [ ] **Step 3: Read history from the log before appending the new message**

The `MessageService` the transcript route already uses is the right source: it projects the
log, so history and the UI can never disagree. Build the input *before* the `user/message`
append at line 52, or the current message appears twice.

```python
    # History first, then append the new message: the log is the source of truth
    # for the transcript, so the model and the user see the same conversation.
    history = await deps.messages.history(sid, limit=deps.settings.history_messages)
    inp = AgentInput(session_id=sid,
                     messages=[*history, Message(role="user", content=body.content, attachments=attachments)],
                     model=session.model_ref)
```

Add to `Settings`:

```python
    #: How many prior messages to replay to the model. 0 disables history
    #: (the pre-2026-10-11 behaviour); the cap keeps a long session from
    #: resending its whole transcript on every turn.
    history_messages: int = 24
```

- [ ] **Step 4: Confirm the runtime already handles a list**

`LangGraphRuntime.run` line 108 already maps `input.messages` through `_to_lc_message`, and
line 28 already converts a `system` role — no runtime change is needed for text history.
Two honest notes to record in the finding's fix note: tool calls and tool results are **not**
replayed (the projection keeps only user/assistant text), so the model sees the conversation
but not its own prior tool traffic; and attachments are not replayed, so an image from an
earlier turn is not resent.

- [ ] **Step 5: Run the tests and the suite**

Run: `services/vibe/.venv/Scripts/python.exe -m pytest tests/test_history.py -q` → PASS
Run: `services/vibe/.venv/Scripts/python.exe -m pytest -q` → PASS

- [ ] **Step 6: Commit**

```bash
git add services/vibe/src/vibe/api/routes/chat.py services/vibe/src/vibe/config.py services/vibe/tests/test_history.py
git commit -m "fix(chat): replay the conversation so the agent can follow up"
```

### R3-T2: Log and broadcast the auto-fix turns (BE-08)

**Files:**
- Modify `services/vibe/src/vibe/autorun/policy.py:50-57`
- Test `services/vibe/tests/test_autorun.py`

**Root cause:** `_fix_turn` does `async for _ in self._runtime.run(...)` and throws the events
away, so a fix turn is invisible: its tool calls never reach the log or the stream, its prose
never appears in the transcript, and its token usage is the only trace. "model-visible means
logged" is violated by the one loop the user cannot see.

- [ ] **Step 1: Write the failing test**

```python
async def test_fix_turn_events_reach_the_log_and_the_bus(autorun, event_log, event_bus, stub_runtime):
    stub_runtime.script = [
        AgentEvent(kind="tool_call", data={"tool_call": {"name": "write_file"}}),
        AgentEvent(kind="text_chunk", data={"text": "fixing the build"}),
        AgentEvent(kind="turn_complete", data={}),
    ]
    await autorun.maybe_run(ctx, ["src/App.tsx"])

    types = [e.type for e in await event_log.get(ctx.session_id)]
    assert "tool_call" in types, "a fix turn must be logged like any other turn"
    assert any(e.type == "assistant/message" and "fixing the build" in e.payload["content"]
               for e in await event_log.get(ctx.session_id))
```

- [ ] **Step 2: Run it and watch it fail** — the log holds nothing from the fix turn.

- [ ] **Step 3: Consume the events instead of discarding them**

Reuse the same append-and-publish shape the chat route uses, so both loops write one kind of
history. Factor it rather than copy it: add a small helper to the services layer —

```python
# services/vibe/src/vibe/services/turns.py
class TurnRecorder:
    """Append-and-publish for one turn, so every loop logs the same way."""

    def __init__(self, session_id: str, event_log, event_bus):
        self._sid = session_id
        self._log = event_log
        self._bus = event_bus
        self._text: list[str] = []

    async def consume(self, events) -> str:
        async for event in events:
            if event.kind == "text_chunk":
                self._text.append(event.data.get("text", ""))
                await self._bus.publish(self._sid, Event(session_id=self._sid, seq=self._log.next_seq(self._sid),
                                                         type="text_chunk", payload=event.data))
            elif event.kind in ("tool_call", "tool_result"):
                seq = await self._log.append(self._sid, event.kind, event.data)
                await self._bus.publish(self._sid, Event(session_id=self._sid, seq=seq,
                                                        type=event.kind, payload=event.data))
            elif event.kind == "turn_complete":
                await self._bus.publish(self._sid, Event(session_id=self._sid, seq=self._log.next_seq(self._sid),
                                                         type="turn_complete", payload=event.data))
        return "".join(self._text)
```

Then `_fix_turn` calls `TurnRecorder(...).consume(self._runtime.run(...))` and appends the
returned text as `assistant/message` when it is non-empty. The chat route can adopt the same
helper afterwards as a separate cleanup commit (do not mix it into this one).

- [ ] **Step 4: Respect the abort flag**

A fix turn must stop when the user pressed Stop: check `handle.abort_requested` between
iterations (the chat route already passes the handle through `ctx`) and return early.

- [ ] **Step 5: Run the tests and the suite**, then commit:

```bash
git add services/vibe/src/vibe/autorun/policy.py services/vibe/src/vibe/services/turns.py services/vibe/tests/test_autorun.py
git commit -m "fix(autorun): log and stream the auto-fix turns instead of discarding them"
```

### R3-T3: Fix the VIBE_HOST warning (BE-07)

**Files:** Modify `services/vibe/src/vibe/api/app.py:47-51`; Test `services/vibe/tests/test_logging_setup.py`

**Root cause:** the `logger.warning` call passes one `%s` placeholder and two positional
arguments, so logging raises `TypeError("not all arguments converted during string formatting")`
inside its own handler — the warning is never emitted and the failure is invisible (logging
swallows its own errors unless `raiseExceptions` is on). Probe 6 confirmed the `TypeError`.

- [ ] **Step 1: Un-xfail the R1-T4 port** and assert the captured record:

```python
def test_non_loopback_host_warns(caplog):
    with caplog.at_level(logging.WARNING, logger="vibe.api.app"):
        create_app(Settings(host="0.0.0.0"))
    assert any("0.0.0.0" in r.message for r in caplog.records), "the host warning must be emitted"
    assert not any(r.exc_info for r in caplog.records)
```

- [ ] **Step 2: Fix the format string** so the placeholders match the arguments, and — because
  this class of bug is otherwise silent forever — set `logging.raiseExceptions = True` in the
  test conftest so a future mismatch fails the suite instead of being swallowed.
- [ ] **Step 3: Run the tests**, commit `fix(logging): emit the non-loopback host warning`.

### R3-T4: Add the system prompt (BE-19) — **DECIDED BY THE USER 2026-10-11: add it**

**Finding added while planning:** the backend constructs **no system prompt at all**.
`runtime/langgraph.py` can convert a `system` message (line 28) but nothing ever emits one, and
`AgentInput` has no `system` field. The agent's entire instruction set is therefore the tool
schemas: nothing states the target stack (React + Vite + TypeScript), the one-app-per-session
rule, the install allowlist policy, or any coding convention. Adding conversation history
(R3-T1) makes this sharper — the model receives a transcript with no framing.

**Two options, and the trade-off is real:**

1. **Add a minimal system prompt** (recommended): a new `runtime/prompts.py` with a short,
   honest prompt naming the stack, the workspace, the allowlist, and "prefer small files;
   keep the app runnable". Wire it as the first message in `LangGraphRuntime._build_graph`, and
   assert in a test that the first LLM message is a `SystemMessage` mentioning React/Vite/TS.
   Risk: it changes agent behaviour on every model, so it needs a live E2E re-run (R7) to
   confirm the loop still builds an app.
2. **Keep it implicit**, and instead move the missing context into the tool descriptions.

This is a product call, not a bug fix: it changes what the agent does. Do not execute without
the user's go. If approved, add the task to the R3 phase plan with the test above.

**Executed 2026-10-11 (user approved option 1, verbatim: "add a system prompt and
other need it whether in the config or in the gui").** The seam landed in
`vibe/prompts.py` (`DEFAULT_SYSTEM_PROMPT`, `system_prompt_for`), `AgentInput.system`,
`build_messages` in the runtime, `Settings.system_prompt` (`VIBE_SYSTEM_PROMPT`),
and both callers (chat route and auto-fix loop). Eight cases in
`tests/test_system_prompt.py`. Two things stay open on purpose: the prompt is not
written to the event log (static configuration, not conversation - two sessions under
different prompts are not distinguishable in their logs), and the GUI field the user
also asked for is a frontend follow-up. **Delivered in R3** (`GET`/`PATCH /settings` plus the
`SettingsPanel` field, `SystemPrompt.test.tsx`); the R7 E2E re-run then confirmed the
loop still builds an app with a prompt in place.

### R3-T5: Tell the truth about a missing browser driver (BE-09)

**Files:** Modify `services/vibe/src/vibe/tools/*` (the console/screenshot tools) and the
autorun runtime-error check; Test `services/vibe/tests/test_browser_tools.py`.

**Root cause:** `read_console_logs` returns `None` both when no dev server is running and when
no browser driver can attach, and the tool message collapses both into "no browser driver" —
so a user whose dev server died is told to install Playwright. Make the two causes distinct:
return a small result object or a reason string (`"no-dev-server"` / `"no-driver"`), and phrase
the tool message from the reason. Assert both messages in tests.

### R3-T6: Close the small API gaps (BE-10)

**Files:** `api/routes/sessions.py:39-50`, `api/routes/chat.py:126`; Test `tests/test_api_gaps.py`.

- [ ] Remove the dead `if usage is None` (`:49-50`): the container always builds a
  `UsageTracker`, so the branch is unreachable and its `NOT_FOUND` is a lie. Either delete it
  or make `usage` genuinely optional in the container — pick delete, and note why in the
  commit.
- [ ] Add `created_at`/`updated_at` to `GET /sessions/{sid}` so it matches the list shape (the
  frontend `Session` type already expects them — FE-15).
- [ ] Stop returning the raw exception text to the client at `chat.py:126`. Keep the honest
  `error_code`, but send a generic message with a short correlation id and log the detail with
  that id, so a user can quote it and an operator can find it. The `ProviderNotConfigured`
  path (which the UI *can* act on) keeps its explicit message.
- [ ] Commit `fix(api): drop the unreachable usage branch, add timestamps, stop leaking exception text`.

### R3-T7: Give `.trash/` a retention policy (BE-11)

**Files:** Modify `services/vibe/src/vibe/lifecycle.py` (add `sweep_trash`), call it from the
app lifespan; `config.py` (`trash_retention_days: int = 14`, 0 disables); Test
`tests/test_retention.py`.

Deleted workspaces accumulate forever today. Add a startup sweep that removes `.trash/*`
entries older than the retention window and logs each removal with its age, so a user who
deleted something by mistake still has two weeks to recover it. Test with a directory whose
mtime is set back, and with retention `0` asserting nothing is removed.

### R3-T8: Index the event log now, defer the query split (BE-12)

**Files:** Modify `services/vibe/src/vibe/events/sqlite_log.py` (add an index); Test
`tests/test_event_store.py` (assert `EXPLAIN QUERY PLAN` uses it).

Two measured problems: `MessageService.page` loads the whole session and slices it, and
`UsageTracker._records` scans all events, twice per `/usage` call. At the current scale (25
local sessions) this is invisible, and rewriting the store protocol for it now is the kind of
speculative work the repository's own rules warn against. So: add
`CREATE INDEX IF NOT EXISTS idx_events_session_type_seq ON events(session_id, type, seq)` via
the existing `user_version` migration, record the measured cost (a one-off timing in the
evidence file) and defer the store-level `message_page`/`usage_page` queries to R6-T9 if a
session in the thousands still degrades. Honest label: **deferred, indexed, measured**.

**R3 exit gate:** `artifacts/hardening-r3-pytest.txt` PASS; probes 3 and 6 fixed; the fix-turn
events appear in a live SSE run (`artifacts/hardening-r3-live.txt`).

---

## 9. Phase R4 — Frontend trust and UX

The review labeled all fifteen frontend findings **static** (read from source, not executed).
Every task here therefore starts by reproducing the defect in a test or in the browser, and
records which one — a static finding that a test cannot reproduce gets re-examined, not fixed
blind.

### R4-T1: Make failures visible (FE-02, and the root of FE-01/FE-06/FE-07)

**Files:** `apps/vibe/src/lib/api.ts`, `apps/vibe/src/features/code/store.ts:24-27`,
`features/preview/store.ts`, `features/chat/store.ts`; Create `apps/vibe/src/components/ErrorBanner.tsx`
+ a small `useErrorStore`; Test `apps/vibe/src/features/code/__tests__/store.test.ts`.

**Root cause:** `code/store.ts:24-27` does `.catch(() => [])`, so a dead backend renders as
"No files yet" and an unreadable file as an empty editor. The same swallow appears in the
preview store. The user cannot distinguish "nothing here" from "this is broken".

- [ ] **Step 1: Write the failing test**

```ts
it("surfaces a failed file listing instead of an empty list", async () => {
  vi.mocked(api.listFiles).mockRejectedValue(new Error("boom"));
  await useCodeStore.getState().load("s1");
  expect(useCodeStore.getState().files).toBeNull();          // unknown, not empty
  expect(useCodeStore.getState().error).toMatch(/boom|load/i);
});
```

- [ ] **Step 2: Run it and watch it fail** — `pnpm exec vitest run src/features/code`; the store
  currently yields `[]` and no error.
- [ ] **Step 3: Replace every `.catch(() => ...)` with a `{ data | error }` result; render
  `<ErrorBanner message={error} onRetry={reload} />` above the panel body. Keep the empty
  state for a genuinely empty list.
- [ ] **Step 4: Confirm in the browser** with the backend stopped: the panel must say the
  backend is unreachable and offer Retry, not show an empty app.
- [ ] **Step 5: Commit** `fix(web): a failed load is an error state, not an empty state`.

### R4-T2: Keep the stream honest (FE-01)

**Files:** `apps/vibe/src/lib/sse.ts`, `features/chat/store.ts`; Create `components/ConnectionBanner.tsx`; Test `lib/__tests__/sse.test.ts`.

**Root cause:** after five failed reconnects the client stops silently; the UI still looks
live while it receives nothing. Fix: expose `status: "open" | "reconnecting" | "lost"`, show a
banner with a Retry button when `lost`, and on reconnect replay from the last seen `seq` via
`after_seq` so nothing is missed. Tests: five failures → `lost`; a reconnect after `lost`
resumes from the stored seq; a `seq` regression is still ignored.

### R4-T3: Stop the chat from fighting the user (FE-04, FE-10, FE-11)

**Files:** `features/chat/MessageList.tsx:44-49,56,114`, `features/chat/Composer.tsx`, `features/chat/store.ts`; Test `features/chat/__tests__/*`.

- [ ] **FE-04:** track "pinned to bottom" (within ~24px); only auto-scroll while pinned, and
  show a "Jump to latest" affordance when not. Test: scroll up, append a message, assert
  `scrollTop` unchanged.
- [ ] **FE-10:** delete the dead `isOverLimit` branch (the `maxLength` attribute makes it
  unreachable) or replace `maxLength` with a live counter — pick delete, and note that the
  backend now enforces non-empty content (R2-T1).
- [ ] **FE-11:** on a failed send, remove the optimistic user bubble (or mark it failed with a
  Retry that does not re-append). Test: reject the POST, retry, assert one user message.
- [ ] Commit per file, not one blob: `fix(chat): only auto-scroll while pinned`,
  `fix(chat): drop the unreachable over-limit branch`, `fix(chat): a failed send no longer duplicates the message`.

### R4-T4: Give Monaco the app theme and honest states (FE-05)

**Files:** `features/code/CodePanel.tsx`; Test `features/code/__tests__/CodePanel.test.tsx`.
Pass `theme` from the app theme store (`"vs-dark"` / `"light"`) to the `Editor`, and render
loading/error states instead of a blank editor. Test asserts the prop follows a theme change.
Confirm visually in the browser — this finding was static, so it needs one manual check.

### R4-T5: Stop parsing model ids out of labels (FE-03)

**Files:** `features/chat/ModelPicker.tsx:43-48`; Test `features/chat/__tests__/ModelPicker.test.tsx`.
The picker does `value.split("/")` on a display string, so a model id containing `/` (common
for OpenRouter-style ids) is truncated. Fix: carry `{ providerId, modelId }` through the
component as data and never re-derive it from text. Test with `"openrouter/meta-llama/llama-3"`.

### R4-T6: Key preview state by session (FE-06)

**Files:** `features/preview/store.ts`, `preview/PreviewPanel.tsx`; Test `features/preview/__tests__/store.test.ts`.
A single global URL/status bleeds across sessions. Key it by `sid` (the chat store already
learned this lesson in 2026-09-29 — cite that decision in the commit). Test: load session A,
switch to B, assert A's URL is not shown.

### R4-T7: Make approvals fail loudly and store safely (FE-07, FE-08)

**Files:** `features/chat/ApprovalCard.tsx:11-19`; Test `features/chat/__tests__/ApprovalCard.test.tsx`.
Wrap `savePolicy` in try/catch (a localStorage quota/private-mode failure currently throws
during render), and surface an approve/deny request failure instead of letting the card
silently reappear. Tests: localStorage that throws; a rejected approve call asserting a
visible error.

### R4-T8: Close the shell gaps (FE-09, FE-12)

**Files:** `App.tsx`, `components/CommandPalette.tsx`; Test `App.test.tsx`.
Bind `Cmd/Ctrl+N` to "new session" (the palette already advertises it) or remove it from the
palette — pick binding, since creating a session is the primary action. Wrap the chat and
sessions panels in an error boundary and add one at the root, so a render error in one panel
cannot blank the whole app. Tests: the shortcut creates a session; a throwing child renders
the fallback and the rest of the app survives.

### R4-T9: Gate polling on visibility (FE-13)

**Files:** `hooks/usePolling.ts` and its four call sites; Test `hooks/__tests__/usePolling.test.tsx`.
Pause when `document.hidden`, back off after consecutive failures, and stop entirely after the
stream is `open` for the resources the stream already covers. Test with fake timers and a
simulated `visibilitychange`.

### R4-T10: Fix the nested live regions (FE-14)

**Files:** `features/chat/MessageList.tsx`, the toast container; Test an a11y test asserting
exactly one live region per concern. Nested `aria-live` regions double-announce every chunk;
keep one polite region for the transcript and one assertive region for errors.

### R4-T11: Settings and types (FE-15, BE-17 UI half)

**Files:** `features/settings/SettingsPanel.tsx:70`, `lib/api.ts` (`Session` type), `lib/theme.ts`.
Add a "Clear key" action that sends `apiKey: ""` explicitly (the API already supports it —
review BE-17), fix the `getSession` return type to match the fields R3-T6 adds, and fix the
theme-toggle first-paint edge. Test: clearing the key calls PATCH with `""`, not `undefined`.

**R4 exit gate:** `artifacts/hardening-r4-vitest.txt` PASS; `artifacts/hardening-r4-browser.md`
records the manual checks (backend stopped, theme switch, session switch, reconnect) with a
screenshot path for each.


---

## 10. Phase R5 — Local packaging and operations

This is the phase that makes the product *usable* rather than merely correct. The target
experience: a user clones the repository, double-clicks `start.bat`, waits, and the app opens
in their browser on one port. Everything below serves that sentence, and each task names the
acceptance criterion it satisfies.

### R5-T1: A doctor that names the missing prerequisite (AC-1)

**Files:** Create `services/vibe/src/vibe/doctor.py`, `doctor.bat`; Modify
`services/vibe/src/vibe/__main__.py` (add a `doctor` subcommand); Test `tests/test_doctor.py`.

- [ ] Define `Check = (name, ok, detail, remedy)` and a `run_checks(settings) -> list[Check]`
  covering: Python `>=3.13`; Node present and `>=20`; `pnpm` resolvable on PATH; `uv` present;
  Chromium installed for Playwright (`playwright install chromium` is a separate download a
  fresh clone will not have); the workspace directory exists and is writable; `providers.json`
  parses (report "quarantined" rather than failing); at least one provider configured; the
  chosen ports are free.
- [ ] Print a table with one `PASS`/`FAIL` per line and a `remedy` column naming the exact
  command to run. Exit non-zero if any hard check fails, so `start.bat` can stop early.
- [ ] Test each check by monkeypatching `shutil.which` and the version probes; assert the
  remedy string is non-empty for every failing check (this is what makes the message
  actionable rather than merely truthful).
- [ ] Commit `feat(cli): a doctor that names what to install`

### R5-T2: One command, one window, one port (AC-2)

**Files:** Rewrite `start.bat`; Create `stop.bat`; Test: manual run recorded in
`artifacts/hardening-r5-start.md`.

- [ ] `start.bat`: call `doctor.bat` first and stop with its message on failure; then start the
  backend in *this* window (not a new one), wait for `/health` to answer (poll up to ~30s), and
  open the browser at the printed URL. One window, both logs, Ctrl+C stops both — a second
  `start` window made the logs unreadable and left orphan processes when the user closed only
  one.
- [ ] Add `--dev` support so the current two-server workflow survives: `start.bat dev` keeps the
  Vite dev server for frontend work; the default is the production single-port mode from R5-T3.
- [ ] Create `stop.bat` that calls `GET /admin/shutdown` (added in R5-T6) and reports what it
  stopped — a user who cannot find the process must not have to open Task Manager.
- [ ] Commit `feat(scripts): one-window start with preflight and health wait`

### R5-T3: Serve the built app from FastAPI (AC-2)

**Files:** Create `services/vibe/src/vibe/api/static.py`; Modify `api/app.py`, `config.py`
(`mode: Literal["dev","prod"] = "dev"`, `VIBE_MODE`), `apps/vibe/src/lib/api.ts` (default the
base to same-origin when `VITE_API_URL` is unset); Test `tests/test_static_serving.py`.

- [ ] In production mode, mount `apps/vibe/dist` at `/` with a catch-all that returns
  `index.html` for any non-`/api` path (an SPA needs that fallback or a refresh on a deep link
  404s). Serve `assets` with a long cache header; never cache `index.html`.
- [ ] Fail loudly, not silently, when `dist` is missing: `RuntimeError` naming
  `pnpm run build`, rather than serving a blank page.
- [ ] Test: with a fixture `dist`, `GET /` returns the shell, `GET /assets/x.js` returns the
  asset, `GET /api/nonsense` still 404s as JSON, and an unknown client route returns the shell.
- [ ] Commit `feat(api): serve the built SPA on one port for local production`

### R5-T4: A first run that explains itself (AC-3)

**Files:** `apps/vibe/src/features/settings/SettingsPanel.tsx`, `apps/vibe/src/App.tsx`; Create
`apps/vibe/src/features/onboarding/FirstRun.tsx`; Test `features/onboarding/__tests__`.

- [ ] When `GET /catalog` reports no configured provider, show a first-run panel instead of an
  empty chat: what vibe does, the exact steps to add a key (open Settings with Cmd/Ctrl+, or a
  button), and two example prompts. Link straight to the provider panel.
- [ ] Assert in a test that the panel disappears once a provider is configured, and that the
  example prompts fill the composer.
- [ ] Commit `feat(web): first-run guidance when no provider is configured`

### R5-T5: A log file a user can send you (AC-11)

**Files:** `services/vibe/src/vibe/logging_setup.py`, `config.py`
(`log_file: Path | None`, `VIBE_LOG_FILE`, `log_level`); Test `tests/test_logging_setup.py`.

- [ ] Add a `RotatingFileHandler` (5 × 2 MB by default) writing to
  `<workspace_dir>/logs/vibe.log`, keeping the existing stderr handler. Standard library only —
  no new dependency.
- [ ] Redact secrets before they can reach a file: the provider `_public` projection already
  omits keys; add one test that logs a settings dump and asserts no key value appears.
- [ ] Log the startup banner with versions (app, Python, Node, pnpm, mode, port, workspace
  path) so a bug report starts with the environment.
- [ ] Commit `feat(logging): a rotating log file under the workspace`

### R5-T6: Shut down and start up cleanly (AC-7, AC-9)

**Files:** `api/app.py` (lifespan), `__main__.py`, `runs.py`; Test `tests/test_lifespan.py`.

- [ ] Lifespan shutdown: stop the idle reaper, cancel in-flight runs, stop every executor's dev
  server, then close the stores. Today a Ctrl+C can leave `pnpm dev` children alive.
- [ ] Startup recovery: any session left `running` by a previous crash is marked failed with a
  `turn/aborted`-style event, so no UI shows a spinner that can never end.
- [ ] Add `POST /admin/shutdown` (loopback-only, behind the existing auth) for `stop.bat`.
- [ ] Test with a lifespan context: seed a "running" session row, start the app, assert it is
  reconciled; assert shutdown calls `stop_dev_server` on a fake executor.
- [ ] Commit `fix(lifecycle): reconcile runs and stop children on shutdown`

### R5-T7: Backup and repair (AC-8)

**Files:** Create `services/vibe/src/vibe/maintenance.py`; Modify `__main__.py` (`vibe backup`,
`vibe repair`); Test `tests/test_maintenance.py`.

- [ ] `vibe backup`: copy `sessions.db` (via the SQLite backup API, not a file copy — a WAL
  database cannot be copied safely while open) and `providers.json` into
  `<workspace>/backups/<timestamp>/`, keeping the newest N (default 7).
- [ ] `vibe repair`: verify both databases with `PRAGMA integrity_check`, re-run migrations, and
  quarantine an unreadable `providers.json` (reusing R2-T4's code path). Report what it did.
- [ ] Test each against a temp workspace, including a deliberately corrupt database.
- [ ] Commit `feat(maintenance): backup and repair commands for the local store`

### R5-T8: An offline machine says so (AC-4)

**Files:** `executor/local.py`, `tools/*`; Test `tests/test_install_offline.py`.

- [ ] Before an install, probe the registry with a short timeout (`pnpm ping` or an HTTP HEAD to
  `registry.npmjs.org`) and, when unreachable, fail with "no network access to the npm
  registry — connect once to install dependencies" instead of a 120-second timeout with a
  truncated stack. Cache the probe result per run.
- [ ] Give the same treatment to the first `uv`/`pnpm` invocation in `doctor`.
- [ ] Commit `fix(executor): fail fast and clearly when the registry is unreachable`

### R5-T9: Recover orphan processes from a previous run (AC-9)

**Files:** `executor/local.py`, `maintenance.py`; Test `tests/test_orphans.py`.

- [ ] Write a `<workspace_dir>/dev-servers.json` pidfile entry when a dev server starts and
  remove it on stop. At startup, for any entry whose pid is alive and whose port is bound,
  either adopt it or kill it (choose kill, and log it) — today a crash leaves listeners the
  next run cannot reuse.
- [ ] Guard the pid check against pid reuse by verifying the process command line mentions the
  session's workspace path before killing; never kill a foreign process (repository rule).
- [ ] Commit `fix(executor): adopt or reap dev servers left by a previous run`

### R5-T10: Make CI real (AC-10, DOC-05)

**Files:** `.github/workflows/ci.yml`, Create `scripts/release-check.ps1`.

- [ ] Fix `cache-dependency-path` to the root `pnpm-lock.yaml` (the workspace install moved
  there in P3a) while keeping the frontend commands in `apps/vibe`.
- [ ] Keep the prettier step (now green after R0-T2) and add the `acceptance-local` smoke to a
  separate workflow that is `continue-on-error: false` only once it has run green twice.
- [ ] `scripts/release-check.ps1` runs, in order and stopping at the first failure: backend
  ruff + pytest, frontend eslint + format:check + typecheck + vitest + build, then the doctor.
  It writes `artifacts/release-check.txt`. This is the one command a maintainer runs before
  handing a build to a user.
- [ ] Commit `ci: point the cache at the root lockfile and add a release check`

### R5-T11: Document the product for its actual user (AC-12)

**Files:** Rewrite `README.md`; Create `docs/guides/local-setup.md`; Modify `AGENTS.md`
(document map row, bundled with the R0-T5 decision).

- [ ] README becomes user-facing: what it is, requirements with versions, install, run,
  troubleshooting (the five most likely failures with their remedy — each one already exists as
  a `doctor` check), where data lives, how to back up, how to uninstall (delete the workspace
  directory and the venv), and the Known gaps restated honestly.
- [ ] `docs/guides/local-setup.md` holds the longer walkthrough (provider keys, first app,
  offline notes) so the README stays short.
- [ ] Commit `docs: rewrite the README for a local user and add the setup guide`

**R5 exit gate:** `scripts/acceptance-local.ps1` steps 1, 2, 5, 6, 7 PASS on a clean checkout;
`artifacts/hardening-r5-*.txt` for each task.

---

## 11. Phase R6 — Scalability seams

Each guardrail from `2 becomes enforced. These are deliberately last: they touch many files and
their value is architectural, so they land after behaviour is correct and packaged. Each task
is small, mechanical, and independently reviewable.

### R6-T1: \`owner_id\` on every persisted row (L-1)

**Files:** `store/sqlite.py`, `events/sqlite_log.py`, `lifecycle.py`, `api/deps.py`; Test
`tests/test_migrations.py`.

- [ ] Add `owner_id TEXT NOT NULL DEFAULT 'local'` to the sessions and events tables via a new
  `user_version` step (idempotent, additive, no rewrite of existing rows: SQLite adds a column
  with a default without touching data).
- [ ] Resolve it once from `Principal.id` in the request scope and pass it to the stores; today
  the stores take no owner. New indexes become `(owner_id, session_id, seq)`.
- [ ] Test: an existing database migrates cleanly; two owners' sessions do not see each other
  when the owner is passed explicitly; the default stays `"local"` for the loopback user.
- [ ] Commit `refactor(store): carry owner_id so a second user needs no migration`

### R6-T2: No SQL outside the store providers (L-2)

**Files:** `store/`, `events/`, any offender found; Test `services/vibe/tests/test_seams.py`.

- [ ] Add a test that walks `services/vibe/src/vibe/**/*.py` and fails if `SELECT `, `INSERT `,
  `UPDATE `, or `DELETE ` appears in a module that is not under `store/` or `events/` (allow a
  documented allowlist of zero entries).
- [ ] Move anything the test finds behind a protocol method.
- [ ] Commit `test(arch): SQL stays inside the store providers`

### R6-T3: The executor stays a protocol (L-3)

**Files:** `executor/base.py`, `executor/local.py`; Test `tests/test_seams.py`.

- [ ] Assert that no module outside `executor/` imports `LocalSubprocessExecutor` directly
  (the container is the only construction site), and that `api/routes/*` never names a concrete
  executor class. Add a `DockerExecutor` skeleton only if the user asks — the point is that
  swapping is a one-file change, not that Docker is built.
- [ ] Commit `test(arch): the executor is reached only through its protocol`

### R6-T4: Identity is read only from the principal (L-4)

**Files:** `auth.py`, `container.py`, `api/deps.py`; Test `tests/test_seams.py`.

- [ ] Add a test failing on a `"local"` string literal outside `auth.py` and its tests. Route
  any found literal through `Principal`.
- [ ] Commit `test(arch): identity comes from the principal, never a literal`

### R6-T5: Registries keyed by (owner, session) (L-5)

**Files:** `runs.py`, `executor/` registry in `container.py`, `preview`; Test `tests/test_run_registry.py`.

- [ ] Key `RunRegistry` and the executor/autorun maps by `(owner_id, session_id)` with a small
  frozen `SessionKey` value object; update the four call sites. Behavior for the local user is
  identical.
- [ ] Test: two owners with the same session id do not collide.
- [ ] Commit `refactor(runs): key in-flight state by owner and session`

### R6-T6: Config is the only reader of the environment (L-6)

**Files:** `config.py` plus any offender; Test `tests/test_seams.py`.

- [ ] Add a grep test that no module outside `config.py` reads `os.environ` (allow
  `os.environ.copy()` in the executor's spawn, which is inheritance, not configuration).
- [ ] Commit `test(arch): configuration is read only from Settings`

### R6-T7: One API base in the frontend (L-7)

**Files:** `apps/vibe/src/lib/api.ts`, `lib/sse.ts`; Test `apps/vibe/src/lib/__tests__/api.test.ts`.

- [ ] Grep test: no `localhost` or `127.0.0.1` literal outside `lib/api.ts` and test fixtures;
  every URL goes through the single base (the SSE client must reuse it, not build its own).
- [ ] Commit `test(web): one place builds an API URL`

### R6-T8: Migrations are the only schema writer (L-8)

**Files:** `store/sqlite.py`, `events/sqlite_log.py`; Test `tests/test_migrations.py`.

- [ ] Assert every `CREATE TABLE`/`ALTER TABLE` lives inside the migration function and that
  running migrations twice is a no-op. (R6-T1 is the first real user of this.)
- [ ] Commit `test(store): schema changes only through the migration runner`

### R6-T9: Split the read paths, if measurement still says so (BE-12, deferred)

**Files:** `events/sqlite_log.py`, `services/messages.py`, `usage/tracker.py`; Test
`tests/test_event_store.py`.

- [ ] Only if `artifacts/hardening-r3-perf.txt` shows a session with `>5k` events taking `>200ms`
  to page or report usage: add `message_page`/`usage_page` that query with `LIMIT`/`OFFSET` and
  a count instead of loading the session. If measurement says the index from R3-T8 is enough,
  record that and close BE-12 as **resolved by index** rather than doing the split.
- [ ] Commit either `perf(events): page the log in the store` or `docs(review): close BE-12 with the measurement`.

**R6 exit gate:** `tests/test_seams.py` PASS with zero allowlist entries; `artifacts/hardening-r6-pytest.txt`.

---

## 12. Traceability — every finding has a task

No finding from the review is unassigned. \`NEEDS_USER_DECISION\` marks the two that change
product behavior or stable policy.

| Finding | Sev | Phase | Task | Fix in one line |
|---|---|---|---|---|
| BE-01 | High | R2 | R2-T1 | typed Pydantic bodies on the four `body: dict` routes |
| BE-02 | High | R2 | R2-T2 | parse the specifier; aliases and protocols are never allowlisted |
| BE-03 | High | R3 | R3-T1 | replay history from the event log into `AgentInput.messages` |
| BE-04 | High | R1 | R1-T1 | `try_start` claims the slot synchronously |
| BE-05 | Medium | R1 | R1-T2 | `_kill_tree` on timeout and on dev-server stop |
| BE-06 | Medium | R1 | R1-T3 | move the workspace before clearing events |
| BE-07 | Medium | R3 | R3-T3 | match the `%s` placeholders to the arguments |
| BE-08 | Medium | R3 | R3-T2 | `TurnRecorder` logs and streams fix turns |
| BE-09 | Low | R3 | R3-T5 | distinguish "no dev server" from "no driver" |
| BE-10 | Low | R3 | R3-T6 | drop the dead branch, add timestamps, stop leaking text |
| BE-11 | Low | R3 | R3-T7 | `.trash` retention sweep at startup |
| BE-12 | Low | R3, R6 | R3-T8, R6-T9 | index now; split queries only if measured |
| BE-13 | Low | R6 | R6-T6 | config only reads the environment |
| BE-14 | Medium | R2 | R2-T3 | validate model ids; catalog skips rather than 500s |
| BE-15 | Medium | R2 | R2-T4 | guarded load, atomic save, quarantine |
| BE-16 | Low | R2 | R2-T4 | lock + `to_thread` around the provider store |
| BE-17 | Info | R4 | R4-T11 | a Clear-key action that sends `""` |
| BE-18 | Info | R5 | R5-T5 | documented plaintext storage + a redaction test |
| BE-19 | Medium | R3 | R3-T4 | **decision:** add a system prompt or not |
| FE-01 | Medium | R4 | R4-T2 | connection status + resume from the last seq |
| FE-02 | Medium | R4 | R4-T1 | error state instead of `.catch(() => [])` |
| FE-03 | Medium | R4 | R4-T5 | carry `{providerId, modelId}` as data |
| FE-04 | Medium | R4 | R4-T3 | auto-scroll only while pinned |
| FE-05 | Medium | R4 | R4-T4 | pass the app theme to Monaco |
| FE-06 | Low | R4 | R4-T6 | key preview state by session |
| FE-07 | Low | R4 | R4-T7 | surface a failed approve/deny |
| FE-08 | Low | R4 | R4-T7 | guard `savePolicy` |
| FE-09 | Low | R4 | R4-T8 | bind Cmd/Ctrl+N |
| FE-10 | Low | R4 | R4-T3 | delete the unreachable branch |
| FE-11 | Low | R4 | R4-T3 | no duplicate bubble on retry |
| FE-12 | Low | R4 | R4-T8 | root and panel error boundaries |
| FE-13 | Low | R4 | R4-T9 | visibility gate + backoff |
| FE-14 | Low | R4 | R4-T10 | one live region per concern |
| FE-15 | Low | R4 | R4-T11 | clear key, types, theme edge |
| DOC-01 | Medium | R0 | R0-T2 | format that one file; keep format:check in CI |
| DOC-02 | Low | R0 | R0-T3 | refresh the Git section |
| DOC-03 | Low | R0 | R0-T3 | one current test count, with evidence |
| DOC-04 | Low | R0 | R0-T3 | close the resolved 3680-paths finding |
| DOC-05 | Low | R0, R5 | R0-T4, R5-T10 | fix the cache path; state CI is unverified |
| DOC-06 | Info | R0 | R0-T5 | **decision:** register the two new doc kinds |
| DOC-07 | Low | R0 | R0-T1 | correct the Playwright capability row |
| TEST-01 | Low | R1 | R1-T2 | the subprocess warning closes with deterministic kill |

---

## 13. Validation, evidence, and the acceptance run

### Per-phase commands

```powershell
# Backend
services\vibe\.venv\Scripts\python.exe -m ruff check .        # run from services/vibe
services\vibe\.venv\Scripts\python.exe -m pytest -q

# Frontend (from apps/vibe)
pnpm run lint
pnpm run format:check
pnpm run typecheck
pnpm test
pnpm run build
```

Every phase writes its output to `artifacts/hardening-r<N>-<topic>.txt` and links it from
TASKS.md. Labels are `PASS`/`FAIL`/`SKIPPED`/`BLOCKED`/`NEEDS_USER_DECISION` and nothing else.

### `scripts/acceptance-local.ps1` (created in R5-T10, run in R7)

A single script a human can run on a clean checkout. It prints one labeled line per criterion
and writes `artifacts/acceptance-local.txt`:

```powershell
# step 1  doctor passes on a clean machine except for an unconfigured provider
# step 2  start the app; poll /health; assert the SPA shell is served from that same port
# step 3  create a session, send a prompt, wait for files, then /sessions/{sid}/files > 0.
#         Requires a configured provider, so it SKIPS (not fails) when none is set.
# step 4  start a run, POST /abort, assert the run stops and no child of the backend is alive
# step 5  kill the backend, restart it, assert the transcript and usage survived
# step 6  delete the session, assert .trash/<sid>-* exists and the row is gone
# step 7  unset the provider, assert GET /catalog reports none and the UI first-run panel shows
```

Two rules for this script, because the temptation is real: it must **skip honestly** when no
provider is configured (it cannot fabricate a loop), and it must never mutate the real
workspace — it runs against `$env:TEMP/vibe-acceptance` with `VIBE_WORKSPACE_DIR` set.

### R7 — the release verification

- [x] Run `scripts/release-check.ps1` on a clean checkout → `artifacts/release-check-final.txt`
      (**PASS - 8/8 steps green**: backend 459 passed + ruff clean, frontend 25 files / 158 tests +
      eslint/prettier/tsc/build, doctor 8/8), and re-run after BE-23 →
      `artifacts/release-check-post-be23.txt` (**PASS - 8/8**, backend **464 passed**, frontend 158).
- [x] Run `scripts/acceptance-local.ps1` → `artifacts/acceptance-local.txt` (**RESULT: PASS**, run 9 at
- [x] Re-run both review probe scripts and record the fixed behavior per probe →
      `artifacts/hardening-final-probes.txt`: `backend_probe.py` exit 0; `custom_provider_probe.py`
      exit 0 after a two-line repair (its C3 POST is now refused, which **is** BE-14's fix, so C4 falls
      back to a valid provider - the probe's old expectation was the obsolete part, not the app). The
      re-run records `/catalog` 200 with a model missing `id` (was 500), that POST 400, a corrupt
      `providers.json` 200 `[]` (was 500), and `PATCH {'apiKey': ''}` 200 with `key_configured=False`.
- [x] Run one real end-to-end app build with a configured provider and record the session id
      and the preview URL → `artifacts/hardening-final-e2e.md` (run 2: session `e62f8a3cb20e`, 11 files,
      preview `http://127.0.0.1:58649/` → 200; run 3: `5bcda18cef54`, 9 files).
- [x] Update `CURRENT_STATE.md`, `TASKS.md`, `HANDOFF.md` with the final state and the
      honest label per criterion.
- [x] Re-run the M1-M11 browser checks on the fixed build →
      `artifacts/hardening-r7-browser-recheck.txt` (**7 PASS, 1 FAIL, 2 BLOCKED, 1 SKIPPED**): M6 passes
      from all three entry points, so the pre-fix failure was the BE-23 403 and not the binding; M1-M4,
      M9 and M11 pass with observed values; M7 and M8 stayed BLOCKED, M10 SKIPPED. The one FAIL is
      **FE-16** (Low) - `Jump to latest` offered when the transcript cannot scroll - fixed in
      `MessageList.tsx` with two regression tests. Final gate on that tree:
      `artifacts/release-check-final-post-m5.txt` (**PASS - 8/8 steps green**, backend 464, frontend 160).
---

## 14. Risks, and how each is contained

| Risk | Why it matters | Containment | Rollback |
|---|---|---|---|
| R3-T1 (history) changes what every model sees | agent behavior could regress | `VIBE_HISTORY_MESSAGES=0` restores the old behavior exactly; the cap bounds token growth | one commit; set the env var |
| R3-T4 (system prompt) changes agent behavior | unmeasurable quality shift | decision-gated; live E2E required before merge | revert the commit |
| R6-T1 (`owner_id`) migrates a database with 25 real sessions | data loss is the worst outcome | additive column with a default; `vibe backup` first; migration is idempotent and tested on a copy | restore from backup |
| R5-T3 (static serving) breaks the dev workflow | the maintainer's loop stops working | dev mode stays the default; prod is opt-in via `VIBE_MODE` | `VIBE_MODE=dev` |
| R1-T2 (tree kill) is platform-specific | could kill the wrong process | pid verified by command line (`R5-T9` pattern); POSIX path is untested here and labeled SKIPPED | revert; the old leak returns |
| R2-T1 (typed bodies) rejects a body some existing test sends | red suite mid-phase | fix the test body, never the schema; noted per case | revert the schema |
| Scope creep into M4 (Docker, Postgres, auth) | violates "local now" | `2 lists what is explicitly not built; R6 builds seams, not features | — |
| Windows-only verification | the app is only proven on this machine | POSIX paths guarded and labeled SKIPPED in evidence | — |

---

## 15. Decisions needed before execution

| # | Decision | Recommendation | Why it must be the user's call |
|---|---|---|---|
| D1 | **Runtime shape:** browser + single loopback port (R5-T3) vs a desktop shell (Tauri/Electron) vs keep two dev servers | single loopback port, with `start.bat dev` retained | adding a desktop shell means a new toolchain and a new release artifact; the user asked for local-only, not desktop |
| D2 | **System prompt (BE-19, R3-T4):** add one or rely on tool schemas | add a minimal one | it changes agent behavior on every model and needs a live E2E to justify |
| D3 | **Document-map edits (R0-T5, DOC-06):** register `docs/reviews/` and `docs/superpowers/plans/`, and promote M6 in PLAN.md | yes to both | AGENTS.md and PLAN.md are stable policy; policy changes need the user |
| D4 | **Playwright Chromium:** install it as part of setup (`doctor` check) | yes | it is a ~150 MB download; the user's machine, the user's call |
| D5 | **Scope of R6:** execute all eight guardrails, or only L-1/L-5 (the two that are expensive later) | all eight — each is a small test plus a small refactor | it is architectural work with no user-visible payoff today |
| D6 | **Execution mode:** subagent-driven per task, or inline in one session | subagent-driven | it is a long program; per-task review is what keeps the dirty worktree safe |

---

## 16. Self-review of this plan

**Spec coverage.** Every one of the 41 findings (39 from the review plus BE-19 and DOC-07) has
a task in `12. Every acceptance criterion AC-1..AC-12 names the task or script that proves it.
Every scalability guardrail L-1..L-8 has an R6 task. The three subsystems the user named —
plan/task/memory documents, the fixes, and local production readiness — are `5, `6–`9, and `10
respectively.

**Placeholder scan.** No `TBD`, no "handle edge cases", no "similar to task N". Each fix that
could go wrong in a specific way states the mechanism (the placeholder-argument mismatch, the
`split("@")[0]` truncation, the `clear()`-before-`rename()` ordering, the `m["id"]` index).
R5 tasks give signatures and the library to use rather than an exact final file, because those
files do not exist yet and inventing their full content here would be fiction, not a plan.

**Type consistency.** `RunRegistry.try_start` returns `RunHandle | None` consistently in
R1-T1 and R6-T5; `TurnRecorder.consume` returns `str` (R3-T2) and is used that way;
`ModelRefIn`/`CreateSessionIn`/`UpdateSessionIn`/`SendMessageIn`/`WriteFileIn` are defined once
in R2-T1 and referenced by name; `Settings.history_messages` (R3-T1) and `Settings.trash_retention_days`
(R3-T7) use the same `Settings` field style as the existing config; `owner_id` is spelled
identically in R6-T1 and R6-T5.

**Known gaps in this plan, stated honestly:**
1. `0` references the phase-plan files that do not exist yet; each is written when its phase
   starts, which is the scope split the writing-plans skill asks for on a multi-subsystem spec.
2. R4's findings are static; each task begins by reproducing the defect in a test or the
   browser, and R4-T4 needs one manual visual check.
3. R5's file contents (doctor, startup script, static serving) are specified by contract and
   key code, not verbatim, because those files are new — the R5 phase plan fills them in with
   full step/test code before execution, as `0 promises.
4. The POSIX branch of `_kill_tree` cannot be verified on this machine and must be labeled
   `SKIPPED` in evidence.

---

## 17. Execution handoff

**Plan saved to `docs/superpowers/plans/2026-10-11-local-production-hardening.md`.**

Phase R0 is ready to execute as written and is intentionally first: it makes the repository's
own documents describe the work before any behavior changes, and it turns the one red check
green. R1's plan is already specified to step level here as well.

Two execution options:

1. **Subagent-driven (recommended)** — one fresh subagent per task, a review gate between
   tasks. Right for this program: the phases are independent, and a per-task reviewer is what
   keeps 41 fixes from quietly touching the dirty worktree.
2. **Inline execution** — execute phase by phase in one session with checkpoints at each exit
   gate. Faster to start, but the whole program in one context will lose detail.

Awaiting D1–D6 (`15) and the choice above before touching code.




