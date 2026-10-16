# UI/UX overhaul — vibe IDE frontend

**Status:** approved 2026-10-11. Owner: frontend line (`apps/vibe`), with one narrow backend
addition in Phase E.
**Review this plan answers:** [docs/reviews/2026-10-11-ui-ux-review/README.md](../../reviews/2026-10-11-ui-ux-review/README.md)
**Product record:** [apps/vibe/PRODUCT.md](../../../apps/vibe/PRODUCT.md) ·
**Design record:** [apps/vibe/DESIGN.md](../../../apps/vibe/DESIGN.md)
**Milestone:** PLAN.md M7.

---

## 1. Objective

Take the interface from "the mechanics work, the information architecture does not" (22/40 on
the heuristic scorecard, with the code editor invisible and the agent's work discarded) to a
production-grade, reusable, scalable surface for a tool that will keep growing.

Three things have to be true at the end:

1. **Nothing is broken.** The code editor renders, the shell does not scroll, no row overflows,
   no phantom nodes in the accessibility tree.
2. **The agent's work is visible.** Every tool call, file write, command, and error the backend
   already publishes is rendered as a first-class step in the conversation.
3. **It is a system, not a screen.** New features arrive as new feature modules over a stable
   token and layout contract, without touching the shell.

## 2. Decisions taken (user-confirmed, 2026-10-11)

| # | Decision | Answer |
|---|---|---|
| 1 | Visual direction | Keep the incumbent identity — palette and tokens are retained. Add a real type system (bundled variable typeface, scale, display step) and rebuild the structure. |
| 2 | Wide-screen hierarchy | Conversation primary and widest; side column `clamp(320px, 34%, 560px)`, user-resizable, collapsible, hosting preview and code behind tabs. |
| 3 | Scope | All capability gaps: agent timeline, tabbed workspace, sidebar, composer, onboarding, accessibility, tests. |

Because the visual world is settled and explicitly retained, this is **extension and refinement
inside an established world**, not a replacement: no direction tournament, no concept seeding.
DESIGN.md records the incumbent system and the approved extensions.

## 3. What does not change

- `src/styles/tokens.css` palette, surfaces, accent, semantic set, spacing grid, radii, z-index
  scale, focus ring, scrollbar tokens, reduced-motion block. **Extended, never replaced.**
- The CSS layer order — `global.css` must declare `@layer reset, base, components, utilities`
  **before** importing `tokens.css` and `components.css`. This is load-bearing and was a real
  defect once.
- The backend contract: `/health`, `/providers`, `/sessions`, `/sessions/{sid}/events`,
  `/messages`, `/files`, `/preview`, `/approvals`. **No `/api` prefix.** The only backend
  addition is one read-only preview-log route (E2).
- `lib/api.ts`'s single `API_BASE` and `lib/sse.ts`'s `after_seq` resume protocol.
- Feature isolation: a feature owns its state, components, and API calls; features are composed
  only at the application root. Chat never imports preview.

## 4. Target structure

```
apps/vibe/src/
  app/                    composition root (was App.tsx + app.css)
    App.tsx  AppShell.tsx  SideWorkspace.tsx  MobileTabs.tsx
    CommandPalette.tsx  ShortcutsHelp.tsx  SettingsModal.tsx
  styles/                 design system
    tokens.css  global.css  base.css  components.css  layout.css  fonts.css
  components/
    ui/                   primitives, product-agnostic
    icons/                one authored SVG set
  features/
    chat/                 store, MessageList, AgentTimeline, TurnSummary, Composer, Approvals, UsageBadge
    sessions/             store, SessionsPanel, SessionList, SessionRow, grouping
    preview/              store, PreviewPanel, PreviewToolbar, DiagnosticsPane
    code/                 store, CodePanel, FileTree, EditorPane
    settings/             store, SettingsPanel
  hooks/  lib/
```

The tab host that composes preview and code lives in `app/`, not in a feature, because it is
composition and features may not import each other.

## 5. Phases

Each phase ends with its own acceptance check. A phase is not done until its evidence file
exists.

### Phase A — Design system foundation

| # | Task | Files |
|---|---|---|
| A1 | Bundle one variable typeface self-hosted (no runtime fetch), `@font-face` with `font-display: swap` and the platform stack as fallback | `styles/fonts.css`, `src/assets/fonts/`, `package.json` |
| A2 | Extend tokens: use the existing scale, add `--measure`, `--panel-header-height`, `--panel-min`, elevation aliases. Palette untouched | `styles/tokens.css` |
| A3 | Enforce the layout contract: one grid, named regions, `.panel` owns its own display, `.scroll-region` owns `min-height: 0` | `styles/layout.css` (new) |
| A4 | New primitives: Tabs, Splitter, Menu, Tree, SearchField, Skeleton, Kbd, StatusDot, Badge, Chip, Toolbar, ScrollArea | `components/ui/*` |
| A5 | Fix Tooltip: `aria-hidden` while hidden, never the only label, reachable on touch | `components/ui/Tooltip.tsx` + css |
| A6 | One authored SVG icon set at one stroke weight, replacing emoji and scattered inline SVG | `components/icons/*` |
| A7 | Apply the type scale to existing primitives; body becomes 14px | `styles/components.css`, primitives |

**Acceptance:** `tsc` clean; every primitive has a story-free unit test where it has logic;
a primitives contact-sheet route renders every primitive in both themes for measurement.
**Evidence:** `artifacts/ui-review/phase-a/*`.

### Phase B — App shell and workspace

| # | Task |
|---|---|
| B1 | `AppShell` as one CSS Grid with named regions; the shell never scrolls; only regions do |
| B2 | Column hierarchy: sidebar 260px, conversation flexible and widest, side `clamp(320px, 34%, 560px)` |
| B3 | `SideWorkspace`: Preview / Code / Diagnostics tabs, drag-to-resize splitter, collapse, state persisted per session |
| B4 | **Delete the false comment** in `app.css` about `.panel-preview`/`.panel-code` and make `.panel` the only display authority — this is the UX-01 fix |
| B5 | Headings and landmark names: a real `h2` per region, named `aside` and `nav` |
| B6 | Mobile: drawers get a scrim, a focus trap, Escape, and 44px targets |

**Acceptance:** `.code-editor` height > 0 at 1440×900 and 1024×768; `.app-shell` scrollHeight ==
clientHeight at every breakpoint; side column resizable and persisted.
**Evidence:** `artifacts/ui-review/phase-b/report.json`.

### Phase C — Agent activity timeline (the UX-02 fix)

The backend already does its half. `api/routes/chat.py:101-104` appends and publishes every
`tool_call` and `tool_result`; `services/turns.py:23` keeps them in the logged set;
`GET /sessions/{sid}/events` replays the whole log from `after_seq` and then streams live.
The client discards all of it.

| # | Task |
|---|---|
| C1 | Replace the flat message list with an **event-sourced timeline**: `timelineBySession: TimelineItem[]`, reduced from the SSE stream. Subscribe with `after_seq=0` so history and live come from the same source |
| C2 | The reducer, with exact payload shapes: `tool_call {tool_call:{id,name,args}}`, `tool_result {tool_call_id,name,content,is_error}`, `user/message {content}`, `assistant/message {content}`, `assistant/error {content}`, `text_chunk {text}`, `turn_complete {}`, `turn/aborted {}`, `error {message}` |
| C3 | `text_chunk` opens a streaming item; `assistant/message` **finalizes** that item rather than appending a second one — the one duplication trap in this design |
| C4 | `AgentTimeline`: each step is a row with an icon, a human title (`Write src/App.tsx`, `Run pnpm install`), a status (running / ok / failed), and a duration |
| C5 | `TurnSummary`: "N files changed · build passed · 12.4s" with jump-to-file |
| C6 | Approvals render inline in the timeline where they occur, not in a separate poll-only block |
| C7 | Long sessions: render the newest window with an explicit "show earlier" control. No virtualizer |
| C8 | Errors are steps too: a failed turn is a red step with the message and a retry |

**Acceptance:** with a replayed log, every `tool_call` in the log has a rendered step; a live
turn with a tool call renders the step without duplication at turn end.
**Evidence:** `artifacts/ui-review/phase-c/report.json` + vitest reducer tests.

### Phase D — Sessions sidebar

| # | Task |
|---|---|
| D1 | Recency grouping (Today / Yesterday / Previous 7 days / Older) with sticky group headers |
| D2 | Listbox semantics: roving tabindex, arrow keys, Home/End, `aria-selected`; the session list is **one** tab stop |
| D3 | Fix the row overflow (UX-05): actions live behind a single menu trigger; the title reclaims the reserved width; meta no longer clips |
| D4 | Rename inline, delete via menu + confirm, duplicate; all reachable from the keyboard |
| D5 | Search with a shortcut, a result count, and a real no-results state |
| D6 | Cap the rendered list with "show more" so 37 sessions do not mean 1716px of DOM |

**Acceptance:** the composer is reachable in ≤ 6 tab presses from a cold load; `.session-row`
scrollWidth == clientWidth; no `.session-meta` clipping.
**Evidence:** `artifacts/ui-review/phase-d/report.json`.

### Phase E — Preview and code workspace

| # | Task |
|---|---|
| E1 | Preview toolbar: reload, open in a new tab, viewport presets (390 / 768 / 1024 / fill), running status with a stop |
| E2 | **Diagnostics**: a read-only backend route `GET /sessions/{sid}/preview/logs` returning the captured dev-server output tail, rendered in a Diagnostics tab. Narrow addition over the existing executor; tests on the backend line |
| E3 | File tree: directories, collapse/expand, filter, and a changed-since-last-turn marker |
| E4 | Editor: dirty indicator, Ctrl+S, and the save state moved into the panel header |
| E5 | Empty states for "no files yet", "no preview yet", and "preview failed" that name the next action |

**Acceptance:** the file list is a tree with real directories; the preview toolbar has reload and
open-external; diagnostics shows the dev-server tail when a preview fails.
**Evidence:** `artifacts/ui-review/phase-e/report.json`.

### Phase F — Composer and onboarding

| # | Task |
|---|---|
| F1 | Composer toolbar: attach, templates, model, and a plan/act toggle |
| F2 | A prompt template library (data-driven, in one file) surfaced in the composer and in the first-run state |
| F3 | Slash commands in the composer (`/` opens a filtered menu) |
| F4 | First-run and empty states rebuilt on the display type step: what this is, what to type, three real examples |
| F5 | Keyboard: Ctrl+Enter send, Shift+Enter newline, Ctrl+K palette, Ctrl+, settings, Ctrl+B sidebar, Ctrl+J side panel |

**Acceptance:** a first-time user reaches a real prompt in one click from the empty state; the
composer exposes templates and slash commands by keyboard.
**Evidence:** `artifacts/ui-review/phase-f/report.json`.

### Phase G — Verification and close-out

| # | Task |
|---|---|
| G1 | `pnpm run typecheck`, `pnpm run lint`, `pnpm exec vitest run`, `pnpm run build` |
| G2 | Backend: `ruff check`, `pytest` (for E2) |
| G3 | Playwright measurement matrix: 1440×900, 1024×768, 390×844 × dark/light. Contrast, targets, overflow, tab order, landmarks, headings, a11y tree |
| G4 | axe-core audit at every breakpoint and both themes — target 0 violations |
| G5 | `impeccable detect --json` over the changed targets, and the craft-floor checklist |
| G6 | Docs: PLAN.md M7, TASKS.md rows, HANDOFF.md, MEMORY.md, CURRENT_STATE.md, review index |

**Acceptance:** every check above has a recorded result with a PASS/FAIL/SKIPPED/BLOCKED label
and an exact evidence path.

## 6. Verification matrix

| Check | Command | Where |
|---|---|---|
| Types | `pnpm run typecheck` | `apps/vibe` |
| Lint | `pnpm run lint` | `apps/vibe` |
| Unit | `pnpm exec vitest run` | `apps/vibe` |
| Build | `pnpm run build` | `apps/vibe` |
| Backend lint | `ruff check` | `services/vibe` |
| Backend tests | `pytest` | `services/vibe` |
| Layout + a11y | `artifacts/ui-review/audit.py` + phase probes | repo root |
| Detector | `impeccable.cmd detect --json apps/vibe/src` | repo root |

## 7. Risks

| Risk | Mitigation |
|---|---|
| The typeface cannot be bundled offline | Network is available; install `@fontsource-variable/*` and self-host. If it fails, keep the platform stack and record it — the scale still lands |
| Event-sourced transcript duplicates the final assistant message | C3's finalize rule plus a seq-based dedupe; covered by a reducer unit test with a recorded real log |
| Removing the REST history path breaks existing tests | Keep `api.getMessages` and adapt tests deliberately rather than deleting coverage |
| Subagents editing shared files concurrently | Phase A freezes tokens and primitives first; parallel work is confined to separate feature directories; the shell is owned by one writer |
| `text_chunk` uses `next_seq`, which can equal a later event's seq | Track seen seqs for dedupe and test the boundary explicitly |
| Scope creep across seven phases | Each phase has an acceptance check and an evidence file; a phase that cannot produce its evidence is reported BLOCKED rather than claimed |

## 8. Out of scope

- Backend correctness and the remaining hardening items (owned by the 2026-10-11 hardening plan).
- M4 scale path: Docker executor, Postgres, auth, deployment.
- Any change to the palette, the accent, or the semantic colour set.
- Workspace scaffolding on session creation (PLAN.md §4 open item).
