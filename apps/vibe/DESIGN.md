# Design

<!-- impeccable:design-schema 1 -->

Visual authority for `apps/vibe`. Product truth lives in [PRODUCT.md](./PRODUCT.md).

**Status:** the incumbent system is recorded below and is retained. This pass extends it — it
does not replace it. The identity (palette, surfaces, accent, semantic set, spacing grid,
radii, focus ring, scrollbar treatment) was measured against the live page and passes contrast
in both themes, so it is authority, not evidence-to-discard.

## World

A dark-first developer workbench. The reference world is the modern code host and terminal
rather than a marketing page: flat tinted surfaces, one indigo accent, hairline borders doing
the work that shadows would do elsewhere, and a strict 4px rhythm. Density is a feature — this
is a tool the user stares at for an hour, not a page they scroll once.

Light theme is a peer, not an afterthought: the same structure on a cool near-white ground, with
its own border and shadow values rather than a mechanical inversion.

## Palette

Owned by `src/styles/tokens.css`. No component hard-codes a colour.

| role                              | dark                                          | light                                         |
| --------------------------------- | --------------------------------------------- | --------------------------------------------- |
| ground                            | `#0d1117`                                     | `#f6f8fa`                                     |
| raised surface                    | `#161b22`                                     | `#ffffff`                                     |
| hover / active                    | `#1c2129` / `#252c36`                         | `#eef1f4` / `#e4e9ee`                         |
| border / strong                   | `#30363d` / `#444c56`                         | `#d0d7de` / `#afb8c1`                         |
| text                              | `#e6edf3`                                     | `#1f2328`                                     |
| text muted                        | `#9aa7b4`                                     | `#59636e`                                     |
| text faint                        | `#7d8590` (5.1:1)                             | `#656d76` (4.9:1)                             |
| accent                            | `#8b9cf9`                                     | `#4f46e5`                                     |
| accent fill                       | `#5b62e0`                                     | `#4f46e5`                                     |
| success / danger / warning / info | `#3fb950` / `#f85149` / `#d29922` / `#58a6ff` | `#1a7f37` / `#cf222e` / `#9a6700` / `#0969da` |

**Measured contrast violations, dark and light: 0.** Semantic colours are used as
`--x` (foreground) plus `--x-bg` (12% tint) plus `--x-border` (40% tint); a status is never
carried by hue alone — it always ships with a label or an icon.

One accent. Indigo. No second accent, no gradient text, no coloured left borders.

## Type

**The gap in the incumbent system.** A scale exists in tokens but the application does not
follow it: every surface renders at `--text-sm` (13px) or `--text-xs` (11px), and the family is
the platform stack — `document.fonts` is empty, so the app loads no web font at all.

Measured today: brand 16/600, header title 13/400, section label 11/600, session name 13/500,
session meta 11/500, message role 11/600, composer 13/400, file name 11/500. Three sizes,
three weights, one family. That is why the interface reads as a scaffold rather than a product.

This pass fixes it:

- **One bundled variable typeface**, self-hosted from `src/assets/fonts` and declared with
  `@font-face` in `src/styles/fonts.css`. It must be bundled, never fetched at runtime: this is
  a local-first app and a Google Fonts request would be the only thing in the product that
  phones home. A geometric-grotesque with real character at small sizes, with the platform stack
  kept as the fallback in `--font-ui`.
- **Body is 14px, not 13px.** `--text-base` already exists; the components will use it. 13px is
  demoted to metadata and control labels, 11px to micro-labels only.
- **A display step.** The empty state, the first-run state, and section titles get a real size
  (`--text-xl` / `--text-2xl`) with negative tracking at `-0.02em` to `-0.03em`. Tracking never
  goes below `-0.04em`.
- **Measure.** Chat prose is held to 65–75ch.
- **Tabular numerals** on every count, duration, token total, and cost — `font-variant-numeric:
tabular-nums` on a `.tnum` utility.
- **Weights 400 / 500 / 600 only.** No 700; hierarchy comes from size and colour, not boldness.

## Space, shape, depth

- 4px grid, `--space-1` … `--space-9`. Panels use `--space-3`/4 internally and `--space-5`/6
  between regions. More space above a heading than below it.
- Radii: `--radius-sm` 4px on inputs and chips, `--radius-md` 8px on buttons and list rows,
  `--radius-lg` 12px on panels and modals, `--radius-full` only on genuinely round controls
  (status dots, avatars, the send button). Not one radius everywhere.
- **Elevation is declared once.** A panel is either bordered or shadowed, never both. The ghost
  card — a 1px border under a wide soft shadow — is refused. Shadows carry an offset and a soft
  blur and are tinted toward the ground hue.
- One light source, from above. `--shadow-1` … `--shadow-3` are the only shadows.

## Motion

One authored moment per surface, not an identical entrance everywhere.

- `--duration-fast` 120ms for hover and focus, `--duration` 200ms for disclosure and state
  changes, `--duration-slow` 300ms for drawers and modals.
- `--ease-out` `cubic-bezier(0.16, 1, 0.3, 1)` for anything entering; `--ease-in` for anything
  leaving.
- Animate `transform`, `opacity`, `clip-path`, and `filter` — never `top`, `left`, `width`, or
  `height`.
- The agent timeline's step appearing is the one authored moment in the chat: a short
  translate-and-fade as a step lands, staggered only when several land together.
- `prefers-reduced-motion: reduce` collapses every duration token to `0ms`. Spinners keep turning
  (`--spin-duration` is deliberately excluded) because a progress indicator that stops is a lie.

## Components

Two layers, and the boundary is enforced.

**Primitives** (`src/components/ui/`) own appearance and interaction and know nothing about the
product: Button, IconButton, Input, Textarea, Select, SearchField, Checkbox, Modal, Drawer,
Menu, Tabs, Splitter, Tree, Tooltip, Toast, Badge, Chip, Kbd, StatusDot, Spinner, Skeleton,
EmptyState, ErrorBanner, ConfirmDialog, Toolbar, ScrollArea.

**Feature components** (`src/features/*`) own meaning: MessageList, AgentTimeline, Composer,
SessionsPanel, PreviewPanel, CodePanel, SettingsPanel.

Rules:

- A feature never re-implements a primitive, and a primitive never imports a feature.
- Every control has hover, active, focus-visible, disabled, and where relevant loading and error
  states. A control with no disabled treatment is unfinished.
- Focus is always visible: `--focus-ring` plus `--focus-ring-offset`, never `outline: none`
  without a replacement.
- Iconography is **one authored SVG set** (`src/components/icons/`) at one stroke weight, drawn
  as components so colour and size come from tokens. No emoji, no per-file inline SVG, no mixed
  icon libraries.
- A tooltip is never the only label for a control. Every icon-only control carries an
  `aria-label`; a tooltip is decoration on top of that, and it is marked `aria-hidden` until it
  is actually shown.

## Layout contract

The incumbent contract was documented but never enforced: `app.css` refers to
`.panel-preview` and `.panel-code` as the classes that make the side panels `display: flex`,
and **neither class is defined in any stylesheet**. The consequence is measured and real — the
code editor renders at height 0 on desktop and tablet.

The replacement is explicit and testable:

- **One grid.** The app shell is a single CSS Grid with named regions: `header`, `sidebar`,
  `main`, `side`, `tabs`. No component computes its own position with percentage flex math.
- **A panel primitive owns its own display.** `.panel` is the only thing that establishes a
  flex or grid context for a panel; a feature sheet may arrange children but may never be the
  reason a panel is a flex container.
- **Every scroll container is declared.** A region that scrolls sets `min-height: 0` on the
  chain above it. The shell itself never scrolls; only the regions inside it do.
- **Column hierarchy.** At ≥1101px: sidebar fixed 260px, conversation flexible and the widest
  column, side column `clamp(320px, 34%, 560px)`, user-resizable, collapsible, and hosting
  preview and code behind tabs. At ≤1100px the side column becomes a right drawer; at ≤768px a
  single panel with a bottom tab bar.
- Breakpoints: 1101px, 1100px, 768px, and 430px.

## Browser surfaces

The parts nobody draws still carry the design, themed from the palette: text selection
(`::selection`), the caret (`caret-color`), scrollbars (`--scrollbar-*`), focus rings, underline
offset, `color-scheme` so native selects and checkboxes follow the theme, and
`font-variant-numeric` on tabular data.

## Copy

The product's own language, sentence case, active voice. A control names its action ("Run
preview", not "Submit"). An error names the problem and the recovery. No "Oops", no exclamation
marks, no "Elevate / Seamless / Unleash".

## Accessibility

WCAG 2.2 AA in both themes. Non-negotiables: one `main` landmark in every state; a named
`<aside>` and `<nav>`; a heading structure that describes the page rather than a lone `<h1>`;
a tab order that follows the work instead of traversing the session list; 44px touch targets on
touch breakpoints; no `role="tooltip"` node left in the accessibility tree while hidden.

## What is refused

Cards as page structure; nested cards; the hero-metric template; a kicker or eyebrow above a
heading; numbered sections; gradient text; glass and blur as decoration; a coloured
`border-left` above 1px on any callout; hard offset shadows; sparklines and progress rings
standing in for content; monospace as a costume for "technical"; emoji as an icon system;
borders and shadows on the same element; a modal for a task that needs no interruption.
