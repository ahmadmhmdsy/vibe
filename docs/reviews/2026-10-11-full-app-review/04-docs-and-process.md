# 04 — Documentation, process, and test-suite findings

The repository's documentation is a first-class artifact here: AGENTS.md is a
real router, CURRENT_STATE.md is a session snapshot, and TASKS.md carries
evidence links. That discipline is why the drift below is worth recording — the
docs are load-bearing, so a stale line is a real defect, not a cosmetic one.

## What is genuinely strong

- **AGENTS.md is a genuine router**, not a README: an authority order, a
  task-routed read matrix, per-scope instruction files, and a document map that
  says where each concern lives. Very few repositories this size have this.
- **Evidence discipline is real.** TASKS.md links an exact artifact path for
  every completed phase, and the artifacts exist on disk.
- **Honest labels are used where it matters.** `CURRENT_STATE.md` records that
  "GitHub Actions has never been executed — the CI workflow is unverified",
  and README keeps an explicit Known gaps section. Both are exactly the kind of
  limitation most projects omit.
- **The CI file explains its Windows choice** and installs the optional
  Playwright browser deliberately, "so a regression in the driver itself is
  caught rather than silently skipped". That reasoning is sound.

---

## DOC-01 — `format:check` fails today while two docs say it passes — **Medium**

**Where:** `TASKS.md` P3b and `CURRENT_STATE.md` (P3b, P3 decisions);
`.github/workflows/ci.yml` frontend "Format (prettier)" step.

**Reality:** `pnpm format:check` **FAILS** on the current worktree — the single
unformatted file is
`apps/vibe/src/components/ui/__tests__/CommandPalette.test.tsx` (new,
uncommitted). Evidence: `evidence/baseline-format.txt`.

**Impact:** the frontend CI job would fail on the current tree even though every
other frontend check passes, and the two documents that promise otherwise are
wrong. Cheap to fix (`pnpm format` on that one file) but it is a real red
check sitting in the worktree.

---

## DOC-02 — `CURRENT_STATE.md` Git section is stale — **Low**

The snapshot records "Latest commit: 47edd56" and "96 modified, 46 untracked
(146 entries)". Actual HEAD is `0849b14` ("P3b — prettier sweep") and
`git status --porcelain` returns **9** entries (5 modified, 4 untracked).
HEAD has moved on since the recorded commit; the tip sequence is now
`0849b14` → `e6a5c75` → `b377020` → `47edd56` → `635828d`. The snapshot was not
refreshed at session start, which is precisely what the file promises.

---

## DOC-03 — The two state files disagree on the test count — **Low**

`CURRENT_STATE.md` M5 says "53 frontend tests", its P6/P3a entries say 86, and
`TASKS.md` P3c says 104. The current suite is **104** (`evidence/baseline-vitest.txt`).
The per-era numbers are historically accurate, but a document whose job is to be
the current snapshot should not carry three different totals without a
"latest" marker.

---

## DOC-04 — A listed "open finding" is already fixed — **Low**

`CURRENT_STATE.md` ends its M5 entry with:

> Open finding for a backend decision: `GET /sessions/{sid}/files` returns 3680
> paths (3667 under `node_modules`).

`TASKS.md` task 16 marks the vendored-directory prune **done**, and the code
agrees. Verified against the real E2E workspace (`2943b651ae98`) with the same
shared walk the route uses:

```
total paths returned by the shared walk: 10
paths under node_modules: 0
```

Both databases are read-only here; no workspace was modified. The "open finding"
should be closed in the snapshot.

---

## DOC-05 — CI is unverified and one of its inputs moved — **Low**

- The workflow has still never run (the docs say so honestly). Nothing in this
  review changes that; the pytest/ruff/vitest/tsc/eslint/build results above are
  all local.
- After P3a the install is owned by the **root** workspace
  (`pnpm-workspace.yaml` + root `pnpm-lock.yaml` + `packageManager`), but the
  frontend job still runs in `apps/vibe` and points
  `cache-dependency-path` at `apps/vibe/pnpm-lock.yaml`. Both lockfiles exist,
  so the cache now keys on a file pnpm does not use for a workspace install.
  Harmless today; confusing and fragile as a template.
- Because DOC-01 is real, the first actual CI run would fail at the prettier
  step — the specific thing the workflow comment says it exists to prevent.

---

## DOC-06 — The new review artifacts are outside the document map — **Info**

AGENTS.md states the rule plainly: "A new durable knowledge kind must land in
the document map above — a document outside the map does not exist for the next
agent." These review documents (`docs/reviews/2026-10-11-full-app-review/`) are a
new durable kind and are not in that table. Registering them is a stable-policy
edit, so this review recommends it rather than doing it unprompted; the smallest
version is one row under "Architecture audit" pointing at this directory.

---


## DOC-07 — The Playwright capability row is stale — **Low**

**Where:** `ENVIRONMENT.md`, capability table, the "Playwright browser capture" row.

**Reality:** the row reads "REMOVED from deps (offline, not cached). Post-M1
refinement — restore when network returns." That is false on the current tree in
two independent ways:

- `services/vibe/src/vibe/executor/browser.py:56` imports `playwright.async_api`,
  and `:62` calls `self._playwright.chromium.launch(...)` — the driver is
  implemented (P5, 2026-10-05, recorded in MEMORY.md).
- `services/vibe/pyproject.toml:13` declares `playwright>=1.63.0` as a runtime
  dependency, and the venv has exactly that version installed:

```
$ services\vibe\.venv\Scripts\python.exe -c "import playwright, importlib.metadata as m; print(m.version('playwright'))"
playwright 1.63.0
```

**Impact:** a reader deciding whether the browser checks can work is told the
capability is absent when it is present, installed, and reachable from the
executor — the same class of drift as DOC-02, but worse in direction: it
understates the product. Documentation only; the code is correct.

---

## TEST-01 — pytest leaves two resource warnings — **Low**

`190 passed, 2 warnings`: a `PytestUnraisableExceptionWarning` from
`asyncio.base_subprocess.__del__` reporting "Event loop is closed" after a test
that started a subprocess. It means a transport is being reclaimed by the GC
rather than closed deterministically — invisible today, but it is the kind of
warning that hides a real leak once more subprocess tests are added.
Evidence: `evidence/baseline-pytest.txt`.

---

## Test-suite quality (overall)

**Strengths.** 190 backend + 104 frontend tests, deterministic (no network, no
LLM): the backend stubs the agent runtime and drives the real ASGI app, and the
frontend mocks the API and Monaco. Coverage follows the seams — the container,
the event log, path confinement (including a symlink escape), the message
projection, the delete cascade, the SSE cursor, the polling hook, and the four
feature panels. The live ASGI/SSE harness is a genuinely good idea: it proves
streaming and abort over the real stack without needing a model.

**Gaps.**

- No test covers `SettingsPanel`'s provider CRUD — which is where BE-14/BE-15
  live; a single create-then-catalog test would have caught the `KeyError`.
- No test asserts the `GET /catalog` contract against a malformed store.
- No test asserts the `VIBE_HOST` warning branch (BE-07).
- No test asserts that a second concurrent `POST /messages` gets 409 (BE-04).
- No test asserts that a timed-out executor command is dead afterwards (BE-05).
- No test asserts conversation continuity across turns (BE-03).
- No test asserts `is_allowlisted` against npm alias/protocol specifiers (BE-02).

Each of those is a small, cheap test that would have turned a shipped defect
into a red check — the strongest argument that the suite is broad but not yet
adversarial.
