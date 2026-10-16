# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Existing codebase, already answered: React 19 + TypeScript 5.6 + Vite 6 frontend
(`apps/vibe`), FastAPI + LangGraph backend (`services/vibe`), pnpm and a Python 3.13 venv.
Not a greenfield choice.

## Users

One developer, on their own machine, who has an app idea and does not want to hand-assemble
a project to see it. They are not necessarily a strong frontend engineer; the whole premise is
that describing the app is enough. They work in a browser on the same machine that runs the
server, in a single window, over a session that may last minutes and involve many agent steps.

A second, quieter audience: the same developer coming back days later to a workspace they no
longer remember the state of. Session history and file state have to be legible at a glance.

## Product Purpose

Turn a plain-language description into a running multi-file React (Vite + TypeScript) app on
the local machine: the agent writes the files, installs dependencies, builds, runs, previews,
and feeds build and runtime errors back to itself until the app works.

Success means a user who has never opened a terminal reaches a live preview of their own idea,
and can see and steer every step the agent took to get there.

## Positioning

The whole loop — describe, generate, install, build, run, preview, auto-fix — happens inside
one local process against one workspace directory on the user's own disk, with no account, no
payment, and no cloud service. The only outbound traffic is the model call the user configured
and the package downloads a generated app needs.

The thing a neighbouring product could not truthfully copy is the **transparency of that loop**:
because the backend already keeps an append-only event log that is the source of truth for
everything the model saw, the interface can show the user exactly which file the agent wrote,
which command it ran, and which error it recovered from — locally, without a remote service
observing any of it.

## Operating Context

- Windows-first, cross-platform: `start.bat` / `stop.bat` / `doctor.bat` at the repo root.
- One command starts everything: the doctor runs, the first free port from 7321 is chosen, the
  backend serves the built SPA from that same port, and the browser opens on the printed URL.
- `start.bat dev` runs Vite on 5173 with the API beside it.
- Workspaces live under `%USERPROFILE%\vibe-workspaces\<session-id>`; the database is SQLite
  (WAL) beside the app.
- Providers are configured in the UI with keys that stay server-side; a `TestProv` fake provider
  exists for offline work.
- The API listens on loopback only.

## Capabilities and Constraints

Confirmed and implemented today: multi-session chat with SSE streaming and `after_seq` replay;
an append-only per-session event log; an agent tool loop (files, build, run, screenshot) over a
local subprocess executor; a supply-chain approval gate for installs; a Monaco editor over the
workspace files; a dev-server preview in a sandboxed iframe; per-session token and cost usage;
backups; provider CRUD; a system prompt with environment/file/default precedence.

Durable technical constraints that shape any interface work:

- **The event log is the source of truth.** Anything the model saw is reconstructable from it;
  history and the live stream must never be able to disagree. `GET /sessions/{sid}/events`
  replays the whole log from `after_seq` and then streams live — it is the intended transcript
  transport, and it already carries `tool_call` and `tool_result` events that the current UI
  discards.
- **Capability seams.** Every swappable part has a Definition, a Provider, and a Consumer; narrow
  interfaces, and nothing reaches across a seam.
- **Feature modules are self-contained.** A frontend feature owns its state, components, and API
  calls; features are composed only at the application root. Chat never imports preview.
- **Single-user, loopback owner.** There is no auth, no tenancy, and no remote deployment in
  scope.
- The API has **no `/api` prefix**: `/health`, `/providers`, `/sessions`.

Explicitly undecided: the product's permanent name ("vibe" is a working name, per PLAN.md §4);
the M4 scale path (Docker executor, Postgres, auth, deployment) is deferred behind the same
interfaces rather than designed.

## Brand Commitments

- The name **vibe** and the wordmark `vibe` in the header.
- **Dark-first**, with a real light theme as an equal citizen — both must clear WCAG AA.
- The composer's framing line, "Describe the app you want to build…", is the product's single
  best piece of copy and sets the correct mental model. Keep it.
- No emoji as interface iconography; no third-party analytics; nothing that phones home.

## Evidence on Hand

- `README.md` — the user-facing product description and the one-command run path.
- `docs/superpowers/specs/2026-09-28-vibe-coding-app-design.md` — the approved design spec, with
  the user-confirmed decision table in §2.
- `docs/superpowers/plans/2026-10-11-local-production-hardening.md` — the 12 acceptance criteria
  for "ready to run on one local machine".
- A real generated workspace for session `bfafa5c99779` (a to-do app: `index.html`,
  `package.json`, `vite.config.ts`, `src/App.tsx`, `src/types.ts`, and
  `src/components/{TodoForm,TodoItem,TodoList}.tsx`) — the honest sample the interface is
  designed against.
- 37 real sessions on this machine, the oldest several days old — the honest scale for the
  session list.

Absent and not to be fabricated: no users other than the operator, no testimonials, no pricing,
no hosted deployment, no benchmarks.

## Product Principles

1. **The work must be visible.** An agent step the user cannot see is a step the user cannot
   trust. Tool calls, file writes, commands, and errors are first-class interface content, not
   diagnostics.
2. **Local and honest.** No interface element may imply a service, account, or capability that
   does not exist on this machine. A dead backend must never look like an empty one.
3. **The conversation is the spine.** Chat is how the user steers; preview and code are how they
   verify. The layout must express that order rather than giving all three equal weight.
4. **Scale by composition, not by rewriting.** New features arrive as new feature modules and new
   primitives over a stable token and layout contract. A future multi-user or remote mode changes
   providers behind existing seams, never the structure of a feature.
5. **Never make the user recall.** Names, states, and affordances are shown in place; the palette
   and shortcuts reach everything, but nothing is reachable _only_ by memory.

## Accessibility & Inclusion

Target: **WCAG 2.2 Level AA**, in both themes. This is a stated requirement, not an aspiration —
`rules/frontend.md` makes accessibility part of correctness, and the 2026-09-29 critique already
recorded real axe violations.

Specifically required: a visible focus ring on every control; one `main` landmark in every
responsive state; no interactive element outside the accessibility tree or with an unlabelled
role; keyboard reachability for every primary action without traversing the session list; text
and placeholder contrast at or above 4.5:1; and no information conveyed by colour alone.
