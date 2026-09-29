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
| 5b | M1 backend: wire UsageTracker into runtime + expose /usage endpoint | `done` | records usage_metadata; /sessions/{sid}/usage live | services/vibe/src/vibe/{usage/,runtime/langgraph.py,api/routes/sessions.py} |
| 6 | M1 frontend: Vite + React + TS scaffold, feature modules | `done` | all feature modules exist | apps/vibe/src/features/ |
| 7 | M1 frontend: chat, preview, code (Monaco), sessions, settings | `done` | all panels exist | apps/vibe/src/features/ |
| 8 | M1 E2E smoke: prompt → generate → build → run → preview → auto-fix | `done` | PASS 2026-09-29 (longcat only) | E2E run session ae75b0d6738a |

## Later

| # | Task | Status | Gate / next action | Evidence |
|---|---|---|---|---|
| 9 | M2: multi-session management, model picker, provider settings UI | `done` | sessions sidebar (rename/badge/activity), model picker persists to session, provider settings (key status + custom provider CRUD) | apps/vibe/src/features/{sessions,chat,settings}/; services/vibe/src/vibe/providers/custom.py |
| 10 | M3: image input, Monaco hand-editing, supply-chain approval, budgets, a11y, tests | `done` | all M3 features complete + tested | services/vibe/src/vibe/{supply_chain,approvals,usage/,api/routes/approvals.py}; apps/vibe/src/features/{chat,code}/ |
| 11 | M4: Docker executor, Postgres, auth, deployment | `pending` | gated on M3 | — |
| 12 | M5: frontend UI/UX overhaul — design system, shell, states, chat, approvals, code, preview | `done` | all 8 tasks complete; verified in browser (desktop + mobile) | docs/superpowers/plans/2026-09-29-m5-frontend-ui-ux-overhaul.md; commits 504be45..HEAD |
| 12.1 | Task 1: design tokens, global styles, UI primitives | `done` | 13 tests | apps/vibe/src/styles/, apps/vibe/src/components/ui/ |
| 12.2 | Task 2: app shell — 3-col layout, header, Settings modal, responsive | `done` | 4 tests; browser-verified | apps/vibe/src/App.tsx |
| 12.3 | Task 3: honest states — errors, loading, empty, delete confirms | `done` | error banners, spinners, empty states, ConfirmDialog | apps/vibe/src/lib/api.ts + panels |
| 12.4 | Task 4: chat — per-session store, history, markdown, composer | `done` | messages endpoint + react-markdown; stop button | apps/vibe/src/features/chat/ + services/vibe/src/vibe/api/routes/messages.py |
| 12.5 | Task 5: approval flow — rich cards | `done` | always-allow localStorage policy; 6 tests | apps/vibe/src/features/chat/ApprovalCard.tsx |
| 12.6 | Task 6: code panel — accessible file list, language detect, save indicator | `done` | aria-pressed file buttons; detectLanguage; Saving/Saved | apps/vibe/src/features/code/ |
| 12.7 | Task 7: preview panel — real backend state | `done` | preview endpoints + polling store; 4 tests | apps/vibe/src/features/preview/ + services/vibe/src/vibe/api/routes/preview.py |
| 12.8 | Task 8: polish pass — favicon, title, theme toggle, verification sweep | `done` | 53 tests, typecheck, build, a11y 0 violations (desktop+mobile) | apps/vibe/index.html, apps/vibe/src/lib/theme.ts |
