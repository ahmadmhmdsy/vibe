# ENVIRONMENT.md — stable environment policy and machine profiles

This file is STABLE: it holds policy, durable constraints, and the
machine profiles kept for reference. It deliberately does NOT hold
volatile current facts. Where they live instead:

- Current machine, disk, and availability: [CURRENT_STATE.md](./CURRENT_STATE.md)
  (session snapshot) — defaults to `UNKNOWN` until a session verifies them.
- Stable software inventory: this file (below).
- Verify at session start before any launch.

## Command and dependency policy (stable)

- Frontend (`apps/vibe`): pnpm only, via the lockfile. Never npm/yarn
  for this app.
- Backend (`services/vibe`): uv only. Run interpreter commands via the
  venv directly: `services/vibe/.venv/Scripts/python.exe`. Install with
  `uv sync --extra dev`; add one with `uv add` (runtime) or
  `uv add --optional dev` (dev extra). Never a bare `python` or `pip`.
  **Corrected 2026-10-04:** this file claimed PyPI was unreachable and that
  `uv run` hangs on resolution. Both are now false — `uv add --optional dev
  ruff` resolved and downloaded from PyPI, as did `uv run --with pyyaml`.
  The `--offline` flag is no longer required (and would now be wrong).
- Never mix package managers across ecosystems; never install "just in
  case" — missing dependencies are installed into the venv by uv and then
  recorded here.
- Node version must match `package.json` engines; Python must match
  `pyproject.toml` requires-python. Do not upgrade runtimes unrequested.

## Lint and format policy (stable)

- Backend lint: `ruff`, configured in `services/vibe/pyproject.toml`
  (`[tool.ruff]`). Run it through the venv:
  `services/vibe/.venv/Scripts/python.exe -m ruff check .`
- Frontend lint/format: `eslint` (flat config, `apps/vibe/eslint.config.js`)
  and `prettier` (`apps/vibe/.prettierrc`), both driven by pnpm:
  `pnpm run lint`, `pnpm run format`, `pnpm run format:check`.
- Lint must be clean of **errors** before a change is called done. Warnings
  are allowed but must be triaged in the config with a written reason, not
  silently ignored — see `apps/vibe/eslint.config.js`.
- `pnpm test` runs `vitest run` (one shot). Use `pnpm run test:watch` for
  watch mode. Never `pnpm test -- --run`: pnpm passes the `--` through and
  the extra flag lands on vitest.

## Security policy (stable)

- LLM API keys and provider credentials live in backend config only
  (`.env`, gitignored). Never in the React bundle, never in commits.
- The frontend sees only provider names and masked key status.
- Generated code runs with the user's own permissions (local-first
  trade-off) — documented in the design spec §9.

## Workspace policy (stable)

- Generated app projects live under `~/vibe-workspaces/<session-id>/`
  (gitignored). One directory per session; the agent is confined to it.
- Dev servers run on a fixed local port range; killed on session delete
  or idle timeout.

## Machine profiles (verified 2026-10-04)

- OS: Windows; shell: PowerShell via DSH pwsh tool. Native paths (E:\...).
- Node: v24.18.0 (npm 11.18.0 shipped).
- pnpm 12.3.4 — JS package manager.
- Python: 3.13.7 (the `py` launcher also offers 3.9.13).
- uv 0.11.22 — Python package manager.
- ruff 0.16.10 — backend linter (dev extra).
- eslint 10.12.0 + typescript-eslint 8.71.0 + eslint-plugin-react-hooks 7.1.1
  + prettier 3.9.9 — frontend lint/format (devDependencies).
- Docker 28.3.2 — available; not needed for the local-first MVP (M4).
- Network: PyPI REACHABLE as of 2026-10-04 (verified by `uv add ruff` and
  `uv run --with pyyaml`). npm registry REACHABLE. GitHub Actions is
  assumed reachable — the CI workflow in `.github/workflows/ci.yml` has
  never been executed, so treat it as **`SKIPPED`**, never assumed green.
  **Two known reasons its first run would have failed (found 2026-10-11):**
  (1) the frontend Format (prettier) step failed on one untracked test file
  (DOC-01) — fixed by R0-T2 of the hardening program, which re-formatted
  `apps/vibe/src/components/ui/__tests__/CommandPalette.test.tsx` by exact path;
  the repo-wide check is re-verified in `artifacts/hardening-r0-docs.txt`.
  (2) after P3a the install is owned by the **root** workspace, so
  `cache-dependency-path: apps/vibe/pnpm-lock.yaml` keys on a lockfile pnpm does
  not use for a workspace install — tracked as R5-T10 of the plan.
  Subagent foreground dispatch times out at 10 min — use background dispatch.

## Capability table (durable)

| Capability | State |
|---|---|
| Local subprocess execution | available (LocalSubprocessExecutor) |
| Docker isolation | available on the machine; M4 scale path |
| Playwright browser capture | **available** — driver implemented (`executor/browser.py`: `playwright.async_api` import, `chromium.launch`), `playwright>=1.63.0` a runtime dependency (`services/vibe/pyproject.toml`), and the browser binary installed with `playwright install chromium` (a fresh clone needs that step — R5-T1 puts it in the setup path). Re-verified 2026-10-11: `playwright 1.63.0` in the venv |
| LLM providers | OpenAI / Anthropic / OpenCode Go / custom (provider seam) |
| Monaco editor | available via @monaco-editor/react (CDN loader; offline needs local config) |
| react-markdown | available (v10.1.0) for LLM output rendering |
| zustand | available (v5.0.0) for state management |
| Backend linting | available (ruff 0.16.10, clean) |
| Frontend linting/formatting | available (eslint 10 flat config: 0 errors / 9 triaged warnings — `artifacts/p3c-eslint-after.txt`; prettier applied 2026-10-05 (P3b) and enforced by `pnpm format:check` in the frontend CI job) |
| CI | defined (.github/workflows/ci.yml) but NEVER EXECUTED — unverified |
