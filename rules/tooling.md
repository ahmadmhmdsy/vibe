---
id: tooling
status: active
scope: repository-wide
applies_when: package managers, venv, or tooling choices
owner: repository-owner
last_reviewed: 2026-09-28
supersedes: none
evidence: ENVIRONMENT.md
---

# Tooling rules

- Frontend (`apps/vibe`): pnpm only, via the lockfile. Never npm/yarn.
- Backend (`services/vibe`): uv only. Every interpreter command goes
  through the venv (`uv run ...`); never bare `python` or `pip`.
- Never mix package managers across ecosystems.
- Never install "just in case" — missing dependencies are installed by uv
  and recorded in ENVIRONMENT.md.
- Node version must match `package.json` engines; Python must match
  `pyproject.toml` requires-python. No unrequested runtime upgrades.
- Batch independent tool calls; front-load discovery.
