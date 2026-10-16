# Competitor parity & expansion — plan

Status: **proposed** (2026-10-16). User-gated: no phase starts without an
explicit go. Input: [competitive analysis](../../research/2026-10-16-competitive-analysis.md).
Depends on: **M6 — local production readiness** (the hardening program) landing.

## Governing rule

Every capability here is a **seam**, never a one-off. This package must expand
as we move, so the shape is fixed before the first line:

- A capability is a **Definition** (a narrow interface / protocol / dataclass),
  one or more **Providers** (implementations), and a **Consumer** (the code
  that uses it). Nothing reaches across a seam.
- A new stack, template, model, database, VCS or tool is **a new Provider**, not
  a new branch in shared code. If adding one touches more than the seam and its
  registration, the seam is wrong.
- Configuration is a value that never changes in code; a thing that varies is a
  Provider.
- No throwaway scripts: a script that is needed twice becomes a Provider or a
  `python -m vibe <subcommand>`, behind the same `Settings`/`Container`.
- Every phase lands with tests at the Definition/Provider boundary (a fake
  Provider stands in, as `tests/test_events.py` already proves for `EventStore`).

This mirrors the existing seams in [PLAN.md](../../PLAN.md) §2 (LLM, Agent
runtime, Executor, Tools, Sessions, Events) and the guardrails R6 put in place
(`owner_id`, SQL only in store providers, executor only through its protocol).

## Where each capability lands

| Phase | Seam (Definition) | Providers (add as needed) | Consumer |
|---|---|---|---|
| C1 Import + scaffolding | `ProjectSource` (folder, git, template) | `LocalFolderSource`, `GitRepoSource`, `ViteReactTsTemplate` | session creation, `workspace.py` |
| C2 Git | `Vcs` (status/diff/commit/branch) | `GitVcs` (only one for now) | a source-control panel; optional commit-per-turn |
| C3 Checkpoints | `CheckpointStore` (snapshot, restore) | `LocalFsCheckpointStore` | timeline row → "restore here" |
| C4 Plan-before-build | `Planner` node in the LangGraph runtime | model-driven plan node | the existing approval card |
| C5 App persistence + auth | `DataBackend` (schema, auth) | `NoneBackend` (default), `LocalSqliteBackend`, `SupabaseBackend` | the scaffold + install step |
| C6 Quick wins | `LlmPreset` (local models), `ToolSource` (MCP), `CodeScanner` | `OllamaPreset`, `McpToolSource`, `RuleScanner` | settings, `ToolRegistry`, autorun |

Each row is one seam. The phase that adds the *second* provider is the phase
that proves the seam is real.

## Phases

### C1 — Import an existing project (+ workspace scaffolding)

The one phase that unlocks the second audience and everything downstream.
Today `workspace.py` only enumerates files and `ensure_workspace` only mkdirs
(PLAN.md §4), so this also closes that long-open item.

- **Definition:** `ProjectSource` — `materialize(dest) -> ProjectLayout` and
  `describe() -> ProjectInfo` (stack, framework, start command).
- **Providers:** `ViteReactTsTemplate` (the scaffold the plan has always
  promised), `LocalFolderSource` (point at a folder), `GitRepoSource`
  (clone a repo). In-place import is a provider flag, not a special case.
- **Consumer:** `SessionService.create` chooses a `ProjectSource`; the container
  registers the available ones.
- **Also:** a per-project instructions file (the `AI_RULES.md` pattern) that
  extends the existing `VIBE_SYSTEM_PROMPT` → `settings.json` → default
  precedence; import generates one from the detected stack.
- **Done when:** a session can be created from (a) the template, (b) a local
  folder, (c) a git URL; each path has a Provider test and one end-to-end run;
  `describe()` drives the composer's context instead of the hard-coded stack.

### C2 — Git integration

- **Definition:** `Vcs` — `status`, `diff`, `commit`, `branch`, `log`.
- **Provider:** `GitVcs` (the only one for now — do not abstract a second away).
- **Consumer:** a source-control panel; an opt-in "commit each turn" that reuses
  the event log as the message source.
- **Local-first:** no implicit remote push. A remote is a user action, and the
  repo currently has none.
- **Done when:** a generated app can be committed, diffed and branched from the
  UI; a turn can be committed on demand; the panel degrades cleanly when the
  workspace is not a repo.

### C3 — Per-step checkpoints / restore-from-chat

- **Definition:** `CheckpointStore` — `snapshot(seq, paths)`, `restore(seq)`,
  `list(session)`.
- **Provider:** `LocalFsCheckpointStore` (copies + the existing `vibe backup`
  machinery; anchored to the event-log `seq`).
- **Consumer:** the timeline — a row offers "restore to here", which reverts the
  workspace to the state at that seq. This is the Cursor model, done locally.
- **Done when:** restoring from any row reproduces that point's files; restoring
  is itself logged as an event; a huge workspace's snapshots are pruned by the
  same retention policy as backups.

### C4 — Plan-before-build

- **Definition:** a `Planner` node in the runtime graph producing a `Plan`
  (ordered steps, files, risks) that the run pauses on.
- **Consumer:** the existing approval card — a plan is an approval with more
  content, so no new UI primitive is required.
- **Reuses:** the human-in-the-loop pause already used by the install
  approval; the plan is logged like any other model-visible artifact.
- **Done when:** a build can be configured to plan-then-approve or to run
  straight through; the chosen plan is the turn's first event.

### C5 — App persistence + auth for generated apps

The biggest gap, and the one with the most design choice — needs a user
decision on the default (local vs Supabase).

- **Definition:** `DataBackend` — `emit_schema(model)`, `emit_auth()`, and the
  env it injects into the generated app.
- **Providers:** `NoneBackend` (today's frontend-only output, the default
  until decided), `LocalSqliteBackend` (local-first: SQLite + a tiny server
  the scaffold runs), `SupabaseBackend` (one-click hosted, opt-in).
- **Consumer:** the scaffold and the install step; the generated app gets a
  working data layer or a clear "no backend" note.
- **Security:** whatever provider runs, RLS/ownership is generated with the
  schema, not bolted on; secrets stay server-side of *our* app and are emitted
  as `.env.local` the generated app reads, never into the bundle.
- **Done when:** a prompt can produce an app that persists rows across restarts
  under at least one non-`None` backend, chosen at generation time.

### C6 — Quick wins (local models, MCP, generated-code scan)

Small, independent, each its own seam:

- **Local models first-class:** `LlmPreset` — `OllamaPreset`, `LmStudioPreset`
  over the existing OpenAI-compatible provider. No new code path — a preset is
  a `Settings` value plus a catalogue entry. Ship it as advertising + a test.
- **MCP:** `ToolSource` — `McpToolSource` feeds the existing
  `ToolRegistry`; a fixed registry becomes a composition of sources.
- **Generated-code security scan:** `CodeScanner` — `RuleScanner` first
  (secrets, obvious injection sinks), run in autorun and surfaced like any other
  tool result; pairs with the existing install approval gate.

## Non-goals

Deploy/hosting, real-time collaboration, multi-tenancy and cloud agents — the
hosted products' features, out of scope for a single-user local tool (see the
analysis §5). Mobile output and visual point-and-click editing are real
product-scope questions but are **not** in this plan; they get their own plan
if chosen.

## Sequencing

C1 → C2 → C3 are the local-first spine and can ship independently. C4 and C6
are independent of the spine. C5 is independent technically but wants the C1
seam (a scaffold) to land first, and needs a user decision on the default.

## Open questions for the user

1. **C5 default:** local SQLite, or Supabase one-click, or both (local default,
   Supabase opt-in)?
2. **C1 import:** folder, git, or both first — and is in-place import required,
   or is a managed copy acceptable for v1?
3. **C2:** is Git a first-class UI panel, or a thin "commit / diff" action set
   on the existing workspace panel?
4. **C6 MCP:** in scope now, or after the spine?
