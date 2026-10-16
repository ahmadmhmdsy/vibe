# Competitive analysis — 2026-10-16

Scope: what the closest competitors ship that **vibe does not yet**, so the roadmap
can be chosen from evidence rather than memory. Read-only research; it changed no
code. Method: public product/marketing/docs pages fetched 2026-10-16 (listed under
Sources). **Honest limitation:** one of four web searches hit the search provider's
free-tier rate limit, so v0 and the local AI IDEs (Cursor/Windsurf) are summarised
from their own docs pages rather than a survey pass; treat those rows as
lower-confidence. Prices and feature lists in this space move monthly — re-verify
before acting on any number here.

Our baseline is [apps/vibe/PRODUCT.md](../../apps/vibe/PRODUCT.md) and
[PLAN.md](../../PLAN.md) as of commit `1deed29` + the four closed decisions.

## 1. The field

| Tier | Product | Model |
|---|---|---|
| **Direct peer (local-first)** | **Dyad** (dyad-sh/dyad, ~20k★, Apache-2.0 with FSL for pro) | desktop app, local, open-source, BYO key |
| Open-source rivals | **bolt.diy** (StackBlitz), **Onlook** | bolt.diy = browser + Electron, 21+ providers incl. local; Onlook = Mac app, local, visual React editor + PR handoff |
| Cloud generators | **Lovable**, **Bolt.new**, **v0**, **Replit Agent** | hosted, full-stack, one-click deploy |
| Local AI IDEs | **Cursor**, **Windsurf** | agent + cloud agents, subagents, checkpoints |

**Dyad is the real comparator.** It runs the same pitch we do ("local,
open-source, own your code, no lock-in"), and on the local-first axis it is
currently *ahead* of us. bolt.diy and Onlook are the other two open-source
references worth reading before we build anything.

## 2. Our moat — what they do not have

- **An append-only event log as the source of truth** with `after_seq` replay, so
  the UI can prove exactly which file the agent wrote, which command it ran, and
  which error it recovered from. This is our stated positioning
  ([PRODUCT.md](../../apps/vibe/PRODUCT.md) §Positioning) and no competitor
  exposes it.
- **A supply-chain approval gate** at install time (they scan *after* generation;
  we stop the install *before* it happens).
- **Fully local with no account, payment, or telemetry**, plus loopback-or-token
  auth with a fail-closed non-loopback bind.
- **Doctor / offline-first** with a non-blocking network check; per-session token
  and cost tracking; a system prompt with environment → file → default
  precedence; **WCAG 2.2 AA** as a stated target.

## 3. What they have that we do not

| # | Capability | Who ships it | Why it matters to us |
|---|---|---|---|
| 1 | **Import an existing project** (local folder + GitHub, in-place) | Dyad, Bolt, Lovable, Onlook | We can only create fresh workspaces. Also blocks our second audience (PLAN.md §4 flags scaffolding as *not implemented*). |
| 2 | **Git integration** (init/commit/branch/diff, PR handoff) | Dyad (native git), Lovable (commit per generation), Onlook (hand off a PR) | We have none; no `origin` even configured. Cheap, high value. |
| 3 | **Per-step checkpoints / restore a point from the chat** | Cursor, Replit, Lovable, bolt.diy | We only have whole-workspace `vibe backup`. A chat row → "restore here" fits our event log. |
| 4 | **Generated-app database + auth** (Supabase/Neon one-click: schema, migrations, RLS, auth, storage) | Dyad, Lovable, Bolt v2, Replit | Our generated apps are frontend-only — no persistence story. Biggest capability gap. |
| 5 | **Plan/blueprint review before building** | Replit, Lovable, Cursor Plan Mode | We go straight to build. Plan-then-approve fits "the work must be visible". |
| 6 | **Visual point-and-click editing of the running app** | Lovable Visual Edits, Dyad select-UI-to-edit, Onlook (whole product), Replit Design Mode | We have chat + Monaco only. Onlook is the reference if we ever do it. |
| 7 | **Multi-stack templates** (Next.js, Vue, Svelte, Astro, Remix, Expo/RN, Capacitor) | Dyad, Bolt, bolt.diy, Replit | We are locked to Vite+React+TS (deliberate per PLAN, but a ceiling). |
| 8 | **Local models first-class** (Ollama, LM Studio) | Dyad, bolt.diy | We support custom OpenAI-compatible (so Ollama *works*), but it is not advertised or first-class. |
| 9 | **MCP extensibility** | Dyad, Bolt, Cursor, bolt.diy | We have a fixed tool registry. MCP gets Chrome DevTools/browsing/custom tools without us writing each. |
| 10 | **Security scan of generated code** (injection, secrets, misconfig) | Dyad, Lovable, Replit (Semgrep) | We gate installs but do not scan what the agent wrote. |
| 11 | **User-facing preview devtools** (inspect console/network in the preview) | Dyad (Chrome DevTools MCP), Cursor Browser | We capture console + screenshots for the *agent*; the user cannot look. |
| 12 | **Smart context** (auto-select relevant files for large repos) | Dyad Smart Context | Only matters once #1 lands. |
| 13 | **Multi-agent / parallel work** | Cursor (8 parallel, subagents), Lovable, Replit | We are one agent, one loop. |
| 14 | **Mobile output & deploy** | Replit (RN+Expo), Dyad (Capacitor), all cloud (hosting) | Deploy/collab/hosting are cloud features we deliberately skip; mobile is a real product-scope question. |

## 4. Recommended priority

Close, in order (the [parity plan](../superpowers/plans/2026-10-16-competitor-parity.md)
turns these into phases):

1. **Import an existing project** (folder + GitHub) — unlocks the second audience
   and everything downstream.
2. **Git integration** — commit/branch/diff + PR handoff; cheap and expected.
3. **Per-step checkpoints / restore-from-chat** — the event log already anchors it.
4. **Plan-before-build** — a reviewable blueprint before the first file is written.
5. **App persistence + auth for generated apps** — the biggest gap vs Dyad/Lovable;
   decide local (SQLite/Postgres) vs Supabase one-click.

**Quick wins:** advertise Ollama/LM Studio as first-class; add MCP; add a
generated-code security scan; surface the preview console to the user.

## 5. Deliberately not chasing

Deploy/hosting, real-time collaboration, multi-tenancy, SOC 2 and cloud agents
are features of the *hosted* products. They are out of scope for a single-user
local tool — not gaps. The M4 scale path (Docker executor, Postgres, auth,
deployment) already records them as deferred behind the same seams.

## Sources

- Dyad — <https://www.dyad.sh/>, <https://www.dyad.sh/docs/roadmap>,
  <https://www.dyad.sh/blog/import-project-ai-app-builder>,
  <https://github.com/dyad-sh/dyad/releases/tag/v0.33.0>
- Lovable / Bolt / Replit comparison —
  <https://vibecoding.app/blog/bolt-vs-lovable-vs-replit>,
  <https://lovable.dev/guides/bolt-vs-replit-vs-lovable>,
  <https://ca.hostadvice.com/ai-app-builders/lovable-vs-bolt-vs-replit/>,
  <https://pondero.ai/coding/guides/replit-vs-bolt-vs-lovable-may-2026/>
- Onlook — <https://www.onlook.com/features/builder>,
  <https://docs.onlook.com/start/welcome>, <https://docs.onlook.com/start/interface>,
  <https://github.com/onlook-dev/onlook>
- bolt.diy — <https://github.com/stackblitz-labs/bolt.diy>
- Cursor — <https://cursor.com/docs/agent/overview>,
  <https://cursor.com/docs/subagents>, <https://cursor.com/changelog/2-0>,
  <https://cursor.com/help/ai-features/background-agents>
