# MEMORY.md — durable memory: decisions & lessons

What the next agent must not rediscover. Two ledgers: **Decisions** (user
calls and stable policies; valid until revoked) and **Lessons** (hard-won
technical knowledge). Append-oriented: correct an entry only with a dated
note, never silently.

Provenance: created 2026-09-28 with the project scaffold. HANDOFF.md stays
the state-of-the-run narrative; this file owns durable knowledge.

## Decisions ledger

| Date | Decision | Why | Reference |
|---|---|---|---|
| 2026-09-28 | Server-side sandbox, local-first, core-loop MVP | user-approved design decisions | design spec §2 |
| 2026-09-28 | LangGraph + local subprocess executor | simplest thing that works locally; swappable seams | design spec §3–4 |
| 2026-09-28 | Provider-agnostic + OpenAI/Anthropic/OpenCode Go/custom | model selection requirement; OpenCode Go is dual-protocol | design spec §5 |
| 2026-09-28 | Usage + cost tracking (tokens in/out/cached/cache_hit/total + steps + USD) | user requirement; "how the agent consumes" | design spec §10 |
| 2026-09-28 | pnpm (frontend) + uv (backend), never mix | one manager per ecosystem | ENVIRONMENT.md |

## Lessons

_(No lessons yet — created 2026-09-28. Add every hard-won gotcha immediately, dated.)_
