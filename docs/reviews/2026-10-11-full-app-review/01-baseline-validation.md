# 01 — Baseline validation (2026-10-11)

Every command below was run from the path shown, in this workspace, and its
full output is stored under `evidence/`. Labels use the repository vocabulary:
PASS / FAIL / SKIPPED / BLOCKED.

## Results

| Check | Command (cwd) | Result | Evidence |
|---|---|---|---|
| Backend tests | `.venv\Scripts\python.exe -m pytest -q` (`services/vibe`) | **PASS** — 190 passed, 2 warnings, 20.92s | `evidence/baseline-pytest.txt` |
| Backend lint | `.venv\Scripts\python.exe -m ruff check .` (`services/vibe`) | **PASS** — all checks passed | `evidence/baseline-ruff.txt` |
| Frontend tests | `pnpm test` (`apps/vibe`, via root workspace) | **PASS** — 104 passed / 18 files | `evidence/baseline-vitest.txt` |
| Frontend typecheck | `pnpm typecheck` | **PASS** — `tsc --noEmit` clean | `evidence/baseline-typecheck.txt` |
| Frontend lint | `pnpm lint` | **PASS** — 0 errors, 9 warnings | `evidence/baseline-eslint.txt` |
| Formatting | `pnpm format:check` | **FAIL** — 1 file | `evidence/baseline-format.txt` |
| Production build | `pnpm build` | **PASS** — 252 modules, 8.21s, 389.93 kB main chunk | `evidence/baseline-build.txt` |

## What the baseline changes about the recorded state

These are documentation-vs-reality deltas, not code defects.

1. **`pnpm format:check` fails today.** The single unformatted file is
   `apps/vibe/src/components/ui/__tests__/CommandPalette.test.tsx` (new,
   uncommitted). Both `TASKS.md` (P3b) and `CURRENT_STATE.md` claim
   `format:check` passes and is in CI. On the current worktree it does not —
   so the working tree would fail the frontend CI job. Tracked as `DOC-01` in
   [FINDINGS.md](./FINDINGS.md) — filed under docs because it is a
   truth-telling gap, not a code bug.
   Evidence: `evidence/baseline-format.txt`.
2. **`CURRENT_STATE.md` Git section is stale.** It records "Latest commit:
   47edd56" and "Dirty files: 96 modified, 46 untracked (146 entries)". The
   worktree actually has HEAD `0849b14` and 9 dirty entries
   (5 modified, 4 untracked). The session snapshot was not refreshed.
3. **Test counts have moved on.** `CURRENT_STATE.md` records 86 frontend
   tests; the suite now reports **104**. `TASKS.md` P3c already records 104,
   so the two state files disagree with each other. Backend count (190)
   matches `TASKS.md` P3a.
4. **pytest emits 2 warnings** on an otherwise green run — a
   `PytestUnraisableExceptionWarning` from `asyncio.base_subprocess.__del__`
   after the loop is closed ("Event loop is closed"). It suggests a subprocess
   transport is not being reaped deterministically in the executor tests. Low
   severity, but it is the only noise in an otherwise clean suite.

## Notes on the frontend build

The main JS chunk is `dist/assets/index-ByCfdiGP.js` at **389.93 kB**
(121.04 kB gzip). Monaco and the feature panels are already code-split
(`CodePanel` 17.21 kB, `PreviewPanel` 1.68 kB). The main chunk is dominated by
React + the app shell; this is reasonable for the feature set but is the one
number to watch as Monaco-adjacent code grows.

## Not run (and why)

- **Live browser E2E (Playwright against the real dev server): SKIPPED.**
  It requires a generated Vite workspace, `pnpm install`, and a browser
  binary; the declared `tests/live` harness needs a live server. The
  backend's own ASGI/SSE harness (190 tests include the SSE and abort paths)
  is the closest deterministic substitute and was covered by pytest.
- **GitHub Actions CI: UNKNOWN.** `CURRENT_STATE.md` states the workflow has
  never executed. Nothing in this session changes that.
