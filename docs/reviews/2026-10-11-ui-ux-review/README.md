# UI/UX review — vibe IDE frontend (2026-10-11)

**Target:** `apps/vibe` (React 19 + TypeScript + Vite SPA), served by `python -m vibe serve` on
`http://127.0.0.1:7321/`.
**Method:** live measurement in headless Chromium via the Python Playwright in
`services/vibe/.venv`. Every claim below is a computed style, a bounding box, a hit-test, a
DOM/ARIA read, or a contrast ratio read out of the live page — never an impression from a
screenshot (this reviewing model has no image input).
**Evidence:** `artifacts/ui-review/report-01.json`, `artifacts/ui-review/probe2.py`,
`artifacts/ui-review/10-desktop-dark.png`, `11-desktop-light.png`, `12-tablet.png`,
`12-mobile.png`.

Scope of this review: the interface and the experience it creates. Backend correctness is out of
scope; the 2026-10-11 full-app review and the local-production hardening plan already own that.

> **Resolved 2026-10-11.** Every finding below was fixed by the M7 overhaul
> ([plan](docs/superpowers/plans/2026-10-11-ui-ux-overhaul.md)); the per-finding outcome and the
> re-measured numbers are in [Resolution](#resolution--what-changed-2026-10-11) at the end of this
> document. The findings themselves are left exactly as measured — this is the evidence the rebuild
> was scoped from, and editing them would destroy that record.

---

## Scorecard (Nielsen heuristics, honest scoring)

This supersedes the 2026-09-29 critique, whose 9/40 was measured before the 2026-09-30 polish
pass. Contrast, layering, the mobile tab bar, and error surfacing have since been fixed; the
structural problems below have not.

| # | Heuristic | Score | Evidence |
|---|-----------|-------|----------|
| 1 | Visibility of system status | **2** | The agent's entire tool activity is dropped by the client — see UX-02. `isStreaming` now renders, and the preview status chip works. |
| 2 | Match with the real world | **3** | Composer placeholder, approval copy, and preview URL chip are product-specific. Model ids still leak as raw ids in the session meta line. |
| 3 | User control and freedom | **2** | Stop exists; confirm-dialog on delete exists; Escape closes drawers. But there is no cancel for a build, no undo for a file edit, and no way to re-run a failed step. |
| 4 | Consistency and standards | **2** | The token system is consistent, but the layout contract is not: the code panel is the one panel whose internal flexbox was never actually enabled (UX-01), and `.panel-code`/`.panel-preview` are referenced as styling hooks that do not exist anywhere. |
| 5 | Error prevention | **3** | Confirm dialogs, idempotent delete, save-state chip. No validation on the composer beyond `maxLength`. |
| 6 | Recognition over recall | **2** | Sessions show model + relative time. But there is no file tree, no breadcrumb, no "what changed" list, and the current phase of the agent is invisible (UX-02). |
| 7 | Flexibility and efficiency | **1** | Keyboard path to the composer crosses every session row's hidden Rename/Delete buttons (UX-04). No slash commands, no prompt templates, no file tree navigation, no panel resizing, no workspace tabs. |
| 8 | Aesthetic and minimalist design | **2** | Clean and restrained, but the visual hierarchy is inverted: the preview/code column is wider than the conversation (UX-03), and the type system is three sizes of one system font (UX-07). |
| 9 | Error recovery | **3** | `ErrorBanner` + retry on every surface, `ErrorBoundary` around lazy panels, degraded polling. A failed agent turn is still only prose in the transcript. |
| 10 | Help and documentation | **2** | `ShortcutsHelp` and the command palette exist. But 79 tooltips are unlabelled phantom nodes (UX-06), and there is no in-context explanation of what the agent is doing. |
| | **Total** | **22/40** | **Acceptable band, bottom.** The mechanics are sound; the information architecture is not. |

---

## What is genuinely working (do not regress)

1. **The token system is real and it passes.** `apps/vibe/src/styles/tokens.css` drives surfaces,
   text, accent, semantic, a 4px spacing grid, radii, shadows, a z-index scale, motion, focus
   rings, and scrollbars, with a `[data-theme="light"]` override. Measured contrast violations in
   **dark and light: 0**. Primary text `rgb(230,237,243)` on `rgb(22,27,34)`; muted
   `rgb(154,167,180)`. This is the part worth building on rather than replacing.
2. **The CSS layer order is correct and load-bearing.** `global.css` declares
   `@layer reset, base, components, utilities` *before* importing `tokens.css` and
   `components.css`. The comment saying so is accurate and must survive any refactor.
3. **Every surface has an error path with a retry.** `ErrorBanner`, `ErrorBoundary`, and
   `usePolling`'s degraded-recovery cadence together mean a dead backend is no longer
   indistinguishable from an empty one.
4. **Landmarks and one-main are correct in every responsive state.** `header`, `aside`,
   `main.app-main`, and `nav[aria-label="Panels"]` are all present; the mobile side column takes
   `role="main"` while it owns the viewport. The 2026-09-29 axe `landmark-one-main` violation is
   gone.
5. **Zero page errors, zero console errors** at 1440×900, 1024×768, and 390×844.

---

## Findings

Severity: **P0** blocks the core loop · **P1** materially degrades daily use · **P2** polish and
scale.

### UX-01 — P0 — The code editor is invisible on desktop and tablet, and it scrolls the whole app

`.code-panel` sets `flex-direction: row` but **never sets `display: flex`**. Computed
`display: block`. The two children therefore stack vertically, and because `.code-file-list` is
456px tall inside a 426px panel, `.code-editor` is pushed out of the panel entirely.

| measurement | value |
|---|---|
| `.code-panel` computed `display` / `flex-direction` | `block` / `row` |
| `.code-panel` height | 426 |
| `.code-file-list` | 200 × **456** (taller than its own panel) |
| `.code-editor` | 604 × **0**, at y = **930** (below the 900px viewport) |
| `.app-shell` scrollHeight vs clientHeight | **930 vs 900** — the app shell itself scrolls |

At 1024×768 the same defect reproduces (panel 479×360, file list 456, editor height 0 at
y = 864). The Monaco editor — the surface the user opens the Code tab *for* — has never been
visible at these sizes.

Root cause is a one-line omission, but it is a symptom of a bigger problem: **`.panel-code` and
`.panel-preview` are referenced as layout hooks in `app.css` and used as class names in the
components, yet neither class is defined in any stylesheet.** A grep across `apps/vibe/src`
returns zero CSS rules for either. The comment in `app.css` claiming "the feature sheets set
them to `display:flex`" is false, and the layout contract it documents was never enforced.

### UX-02 — P0 — The agent's work is invisible

This is the single largest experience gap, and it is the one that matters most for a
vibe-coding tool.

The backend already emits the data. `services/vibe/src/vibe/models.py:60` defines
`AgentEvent.kind` as `"text_chunk" | "tool_call" | "tool_result" | "error" | "turn_complete"`;
`api/routes/chat.py:101-104` **appends and publishes every `tool_call` and `tool_result` to the
event log and the SSE bus**, and `services/turns.py:23` keeps them in the logged set so they
survive a reconnect.

The client throws all of it away:

- `features/chat/MessageList.tsx` handles exactly two SSE event types — `text_chunk` and
  `turn_complete`. `tool_call`, `tool_result`, and `error` fall through the `switch` and are
  discarded.
- `features/chat/store.ts:36` — `toChatMessage` flattens every persisted event to
  `{ role, content }`. `ChatMessage.tool_calls` exists on the type (line 10) and is **never
  populated by any code path**.

Consequence: the user watches a spinner, then a paragraph of prose. They cannot see that the
agent wrote `src/components/TodoItem.tsx`, ran `pnpm install`, hit a TypeScript error, and
fixed it — even though the server sent each of those steps and the app's own design spec
(`docs/superpowers/specs/2026-09-28-vibe-coding-app-design.md`) names the event log as the
transcript authority.

For a product whose value proposition is *watching an agent build your app*, this is the
difference between a tool that feels trustworthy and one that feels like a chat box with a
mystery behind it.

### UX-03 — P1 — The information hierarchy is inverted

At 1440×900, measured:

| column | width |
|---|---|
| `.app-sidebar` | 260 |
| `.app-main` (the conversation) | **575** |
| `.app-side` (preview + code) | **605** |

The secondary output column is 30px **wider** than the primary conversation, and the right
column then splits its 605px **50/50** between preview and code with no tabs, no splitter, no
maximize, and no resize — so a 426px-tall preview and a 426px-tall editor fight each other
permanently. The user's actual workflow is: read the conversation → glance at the preview →
occasionally inspect a file. The layout gives all three equal weight.

### UX-04 — P1 — Keyboard navigation is unusable past the third tab stop

Measured tab order from a cold load, first 24 focusable elements:

```
1-3   header: side-toggle, theme, settings
4-6   sidebar: Export, New, Search
7     session row 1: select
8     session row 1: Rename
9     session row 1: Delete
10    session row 2: select
11    session row 2: Rename
12    session row 2: Delete
...   (repeating)
```

**22 of the first 24 tab stops are session-row buttons.** The workspace has 37 sessions, so
reaching the composer by keyboard costs roughly **114 tab presses**. The Rename and Delete
buttons are `opacity: 0` and only revealed on hover, but they remain in the tab order and are
announced to screen readers regardless.

The session list is also a flat `div` list, not a listbox: no arrow-key navigation, no roving
tabindex, no `aria-selected` on the active row, no grouping by recency, and no virtualization
(`.sessions-list` scrollHeight 1716 vs clientHeight 753).

### UX-05 — P1 — Session rows overflow horizontally and clip their own title

`.session-row` scrollWidth **302** vs clientWidth **241**. Inside it, `.session-select` gets 151px
and `.session-actions` reserves 70px at x = 172, in a 235px content box. `.session-meta`
(model + relative time) measures scrollWidth 178 vs clientWidth 151, so
"LongCat 2.5 Preview Free · 48m ago" is truncated at rest.

The hidden action buttons permanently consume 30% of the row's width. A row that reveals
actions on hover should reclaim that width when they are hidden.

### UX-06 — P1 — 79 phantom tooltips pollute the accessibility tree

Measured: **79** elements carry `role="tooltip"`; **0** of them set `aria-hidden`; **0**
elements in the document carry `aria-describedby`. Each tooltip computes to
`display: block; visibility: visible; opacity: 0` — invisible to the eye, present to a screen
reader.

So a screen reader walking the header announces "Preview and code, Toggle theme, Settings" and
then the same three strings again as separate nodes; the session list does the same 37 times
over. The `.tooltip-wrap` elements also overflow their containers (scrollWidth 29 vs
clientWidth 0) because the hidden tooltip is positioned outside the wrapper's box.

Compounding this: tooltips are revealed on `hover` and `focus-within` only. On a touch device
there is no hover and no keyboard, so a tooltip is the *only* label for an icon-only control and
it is unreachable.

### UX-07 — P1 — There is no type system, and no display voice

Measured typography across every named class in the app:

| role | size | weight | family |
|---|---|---|---|
| brand | 16px | 600 | `-apple-system` |
| header title | 13px | 400 | `-apple-system` |
| section label ("Sessions") | 11px | 600 | `-apple-system` |
| session name | 13px | 500 | `-apple-system` |
| session meta | 11px | 500 | `-apple-system` |
| message role | 11px | 600 | `-apple-system` |
| composer input | 13px | 400 | `-apple-system` |
| file name | 11px | 500 | `ui-monospace` |

Three sizes, three weights, and a **system font stack**. `document.fonts` is **empty** — the app
loads no web font at all. There is no scale, no display size, no line-height rhythm, no optical
tracking except the brand's `-0.16px`, and 13px body text is small for long prose. Nothing here
carries identity; the same stack is the default of every Electron app and every GitHub clone.

### UX-08 — P2 — Heading structure and landmark naming

The entire application contains **one heading**: `<h1>vibe</h1>`. "Sessions" is a `span`, and
the chat, preview, and code surfaces have no headings at all. `<aside>` and `<main>` carry no
accessible name, so a screen-reader user cannot distinguish the sessions sidebar from the
preview column when navigating by landmark.

### UX-09 — P2 — Preview is a bare iframe with two buttons

`PreviewPanel.tsx` is 69 lines: Run, Stop, a URL chip, and a sandboxed `<iframe>`. Missing for
the workflow it serves: reload, open-in-new-tab, a viewport-size switcher, a visible
build/compile status, and — most importantly — **the generated app's own console output and
runtime errors**, which today go nowhere the user can see.

### UX-10 — P2 — Code is a flat file list, not an editor workspace

`.code-file-list` renders one `<button>` per path with the full path as its label, in a 200px
column. There is no directory tree, no collapse, no filter, no dirty indicator, no
"changed by the agent since the last turn" marker, and no diff. `saveState` is a three-state
chip (`idle | saving | saved`) that lives at the top of the editor and is easy to miss.

### UX-11 — P2 — The composer assumes you already know what to type

`Composer.tsx` is a well-built textarea — auto-grow, Enter-to-send, image attach, drag-and-drop,
optimistic bubble with withdrawal on failure. It has no slash commands, no prompt templates, no
file references, no plan/act toggle, and no indication of which tools the agent will be allowed
to use. For a first-time user, "Describe the app you want to build…" is the only guidance in the
product.

### UX-12 — P2 — Responsive behaviour is correct but thin

At 390×844 the layout is genuinely right: `.app-side` is 0×0, `.app-main` is 390×747, and the
bottom tab bar works. But the sessions drawer and the preview/code drawer have **no scrim**,
no swipe-to-dismiss, and no focus trap — and the 34px header icon buttons are below the 44px
touch-target guidance.

---

## Capability gaps that block "make creating an app easier with agents"

These are not defects; they are the features the product needs next, and they are the reason
"reusable and scalable" matters here.

1. **Agent activity timeline.** Tool calls, file writes, commands, build results, and errors, in
   order, with per-step status and duration (UX-02).
2. **A turn summary.** "9 files changed · build passed" with a jump-to-file affordance.
3. **A real workspace.** Tabs and a splitter so preview and code share the column on the user's
   terms (UX-03), and a file tree that scales past a flat list (UX-10).
4. **Live app diagnostics.** The generated app's console and runtime errors, surfaced in the IDE
   (UX-09).
5. **A first-class empty state and prompt library.** Templates and examples so the first message
   is not a blank page (UX-11).
6. **Keyboard-first operation.** A shortcut for every primary action, a palette that reaches
   everything, and a tab order that respects the work (UX-04).

---

## Recommended direction

Keep the identity — the token system, the dark-first palette, the layer order, and the contrast
results are good and were expensive to get right. Rebuild the **structure** on top of it:

- a **documented design system** (`apps/vibe/PRODUCT.md`, `apps/vibe/DESIGN.md`, a token layer
  that adds type scale, motion, and elevation as first-class tokens);
- a **layout contract that is actually enforced** — one grid, named regions, panel primitives
  that own their own `display`, replacing the `.panel-*` classes that were never defined;
- an **agent activity timeline** driven by the tool events the backend already publishes;
- a **workspace** with tabs, a resizable split, a file tree, and live diagnostics;
- a **sidebar and composer** that scale to hundreds of sessions and to a user who has never
  built an app before.

---

## Resolution — what changed (2026-10-11)

The findings above are preserved as measured. This table records what happened to each one, and the
re-measured numbers come from the three-viewport probe at 1440×900 / 1024×768 / 390×844
(`artifacts/ui-review/report-m7.json`). The code-panel figures are the exception: that sweep
measures with **Preview** active, where `.code-panel` is correctly `0×0`, so UX-01's editor size is
taken from a targeted probe with the **Code** tab selected (`artifacts/ui-review/probe-code-tab.txt`).

| Finding | Outcome | What changed | Re-measured |
|---|---|---|---|
| UX-01 — the code editor is invisible, and the app shell scrolls | **Fixed** | Both panels rebuilt on one `.panel` / `.panel-header` / `.panel-body[data-direction]` contract; the `flex-direction: row` with no `display: flex` is gone | `.code-editor` **263×771** (was 604×0); `.app-shell` overflow `[0,0]` (was 930 vs 900) |
| UX-02 — the agent's work is invisible | **Fixed** | The transcript is event-sourced: `tool_call`, `tool_result`, `assistant/error` and `error` are folded into a `role="log"` timeline; tool rows expand to their arguments and output | every event type the backend publishes now renders; three reducer tests pin the error branches |
| UX-03 — the information hierarchy is inverted | **Fixed** | Conversation primary; the side column is `clamp(320px, 34%, 560px)`, user-resizable, with Preview and Code as **tabs** and a splitter between the tree and the editor | desktop `260 / 684 / 6 / 490` — the conversation is now the widest (was 575 vs 605) |
| UX-04 — keyboard navigation is unusable | **Fixed** | Roving tabindex on the session list (one stop, not 37 rows), the row actions moved behind one labelled menu, ARIA tabs on the side column | tab stops **30 of 36** before the composer at desktop, 27 of 31 at mobile (was ~114); `session-select[tabindex="-1"]`: 36 |
| UX-05 — session rows overflow and clip their title | **Fixed** | The row no longer reserves width for hover-only actions; meta truncates deliberately with a title attribute | no horizontal overflow in the sidebar at any breakpoint |
| UX-06 — 79 phantom tooltips | **Fixed** | `Tooltip` renders through a portal, only while shown, `aria-hidden`, and never `role="tooltip"` | `role="tooltip"` elements: **0** (was 79) |
| UX-07 — no type system, no display voice | **Fixed** | Self-hosted IBM Plex Sans + IBM Plex Mono, a 11/12/13/14/16/20/24/28 scale, tracking tokens, a measure | body font `"IBM Plex Sans Variable"`; `document.fonts` size **9** (was `-apple-system` / empty) |
| UX-08 — heading structure and landmark naming | **Fixed** | The session title is the page's only `h1`; `aside` and `main` are named; the sidebar groups sessions under real `h3` headings | `h1: ["hi"]`; landmarks `HEADER, ASIDE[Sessions], NAV[Sessions], MAIN[Conversation], SECTION[Preview and code], NAV[Panels]` |
| UX-09 — preview is a bare iframe | **Fixed** | The panel header carries the URL with copy, reload, open-in-new-tab, and a Run/Stop button with a Badge + StatusDot status chip; polling is gated on the active tab | panel header measured; status is colour **and** text |
| UX-10 — code is a flat file list | **Fixed** | An accessible `Tree` with `aria-level`/`posinset`/`setsize`/`expanded`, folders expanded by default, a filter, a splitter, and the selected path in the header | `.tree-item` rows carry the full ARIA structure; 9 tree tests |
| UX-11 — the composer assumes you know what to type | **Fixed** | A composer toolbar (reference, templates, model, plan/act), a data-driven prompt template library, slash commands, and a rebuilt first-run state with real examples | Phase F; `features/chat/Composer.tsx` |
| UX-12 — responsive behaviour is correct but thin | **Fixed** | The scrim now exists exactly where a drawer does, both drawers are focus-managed, and header controls take a 44px target on `(pointer: coarse)` | scrim present when a drawer is open at 1024/390; mobile body is a single track |

**Two defects the overhaul introduced, found by Phase G and fixed in it.** The desktop
`grid-column: 2` pin survived into the `≤768px` query, where the grid has one track, so
`.app-main` measured **0×747** on every phone; both panels are now placed in the single cell.
And the first probe reported the tablet drawer as an overlapping panel because it tested the bounding
rect of a `visibility: hidden` element — the probe was wrong, not the CSS.

**Three accessibility defects the overhaul introduced, found by axe-core and fixed in Phase G.**
`aria-expanded` sat on the composer textarea, where `textbox` does not support it — and HTML-ARIA
forbids the `combobox` role that would make it legal on a `textarea`, so the slash menu's open state
is now carried by `aria-controls` plus `aria-activedescendant`. The header search trigger lost its
accessible name the moment its label collapsed to an icon under 900px, so the name no longer depends
on the visible text. And the resize handle was a sibling of every landmark, which fails axe's
`region` rule; it is now rendered inside the section it resizes. A fourth fix is smaller but the same
kind of bug: the visually-hidden file input was a second, invisible "Attach image" tab stop beside the
visible button, and now takes `tabIndex={-1}`.

**Accessibility re-measured:** axe-core **0 violations** at 1440 dark, 1440 light, 1024 and 390, and
**0 contrast violations** in every one of those states (`artifacts/ui-review/report-m7.json`). The
only visible font families are now `IBM Plex Sans Variable` and `IBM Plex Mono`.

**Still open** (see TASKS.md M7 "Open user decisions"): a skip link for the transcript (15 tool rows
are genuine controls, so a long run still adds tab stops), and the removal of the confirmed-dead
`lib/markdown.tsx` and its `react-markdown` dependency.

---

## Limitations of this review

- The reviewing model has no image input. No claim here rests on a screenshot; all visual
  findings were substituted with computed styles, bounding boxes, contrast ratios, DOM/ARIA
  reads, and `elementFromPoint` hit-tests.
- Measurements were taken against the **built** SPA in `apps/vibe/dist` served on port 7321,
  built 2026-10-11 22:19. Source and bundle agree on every finding checked.
- The running server exposes only the `TestProv` provider, so a live agent turn with real tool
  calls could not be driven end-to-end; UX-02 is proven by reading the client's event handling
  and the server's publish path, not by observing a live tool call in the DOM.
- Touch behaviour was measured at 390×844 with a desktop engine and a synthetic viewport; real
  iOS/Android hover and `dvh` behaviour is not covered.
