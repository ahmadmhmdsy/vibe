# ENVIRONMENT.md

Machine + toolchain facts (verified by command this session, 2026-09-28).

- OS: Windows; shell: PowerShell via DSH pwsh tool. Native paths (E:\...).
- Node: v24.18.0 (npm 11.18.0 shipped).
- pnpm 12.3.4 — the JS package manager (for `apps/vibe`).
- Python: 3.13.7 (the `py` launcher also offers 3.9.13).
- uv 0.11.22 — the Python package manager (for `services/vibe`).
- Docker 28.3.2 — available; **not needed** for the local-first MVP (M4 scale path).
- Project location: E:\python_projects\apps_building (git repo).
- App layout: `apps/vibe` (Vite + React 19 + TypeScript), `services/vibe` (FastAPI + LangGraph).
- Validation tools: vitest + tsc + eslint (frontend), pytest + mypy/ruff (backend) — configured during implementation.
- Current validation snapshot: **not yet run** — project scaffolded, implementation not started. Update this section after the first validation wave.
