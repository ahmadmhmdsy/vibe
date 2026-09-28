# TASKS.md — Vibe Coding App

## Next

1. **User reviews the design spec** — in_progress (awaiting approval).
2. Write the implementation plan (writing-plans skill) — pending spec approval.
3. **M1 — Core loop (backend)** — FastAPI + LangGraph scaffold, AgentRuntime seam,
   ToolRegistry (10 tools), LocalSubprocessExecutor, provider seam
   (OpenAI/Anthropic/OpenCode Go/custom), EventLog + SessionStore, SSE, auto-run
   verify-fix policy, usage/cost tracking.
4. **M1 — Core loop (frontend)** — Vite + React + TS scaffold, chat, preview,
   code (Monaco), sessions, settings feature modules.
5. **M1 — E2E smoke** — prompt → generate → build → run → preview → auto-fix.

## Later

- M2: multi-session management, model picker, provider settings UI.
- M3: image input, Monaco hand-editing, supply-chain approval UI, token budgets, a11y audit, full test coverage.
- M4: Docker executor, Postgres, auth, deployment.
