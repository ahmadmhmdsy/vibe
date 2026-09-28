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
- Backend (`services/vibe`): uv only. Every interpreter command goes
  through the repo venv (`uv run ...`); never a bare `python` or `pip`
  invocation and never outside the environment.
- Never mix package managers across ecosystems; never install "just in
  case" — missing dependencies are installed into the venv by uv and then
  recorded here.
- Node version must match `package.json` engines; Python must match
  `pyproject.toml` requires-python. Do not upgrade runtimes unrequested.

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

## Machine profiles (verified 2026-09-28)

- OS: Windows; shell: PowerShell via DSH pwsh tool. Native paths (E:\...).
- Node: v24.18.0 (npm 11.18.0 shipped).
- pnpm 12.3.4 — JS package manager.
- Python: 3.13.7 (the `py` launcher also offers 3.9.13).
- uv 0.11.22 — Python package manager.
- Docker 28.3.2 — available; not needed for the local-first MVP (M4).

## Capability table (durable)

| Capability | State |
|---|---|
| Local subprocess execution | available (LocalSubprocessExecutor) |
| Docker isolation | available on the machine; M4 scale path |
| Playwright browser capture | to be installed with the backend |
| LLM providers | OpenAI / Anthropic / OpenCode Go / custom (provider seam) |
