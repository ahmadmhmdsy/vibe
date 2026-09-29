# M5 Frontend UI/UX Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the vibe IDE frontend from unstyled default browser HTML into an authored, trustworthy, dark-first developer interface — fixing all 7 critique priority issues (3×P0, 2×P1, 2×P2) plus the functional bugs that undermine them.

**Architecture:** A token-driven CSS design system (no UI framework — the app is small; tokens + a thin component layer keeps the bundle lean). Dark-first theme with a light theme via `data-theme` on `<html>`. State stays zustand; the chat store becomes per-session keyed by session id. Two small backend endpoints (message history reconstructed from the EventLog, preview/dev-server state from the executor) make the UI honest instead of mocked.

**Tech Stack:** Vite · React 19 · TypeScript · zustand · Monaco · vitest · @testing-library/react · plain CSS (custom properties). One new dependency: `react-markdown` (safe markdown rendering — hand-rolled HTML rendering of LLM output is an XSS risk). Backend: FastAPI (2 small endpoints).

**Spec:** `.impeccable/critique/2026-09-29T15-14-42Z__apps-vibe-src.md` (critique snapshot — 9/40, Critical) · Product spec: `docs/superpowers/specs/2026-09-28-vibe-coding-app-design.md`

## Global Constraints

- **Node 24 / pnpm** for the frontend (`apps/vibe`); **Python 3.13 venv** for backend (`services/vibe`). Never mix package managers.
- **Secrets server-side only.** API keys never reach the bundle.
- **Validation labels:** PASS / FAIL / SKIPPED / BLOCKED / NEEDS_USER_DECISION.
- **Task statuses:** pending → in_progress → done / blocked.
- **Dark-first** (craft floor: pick theme from the use scene — a developer tool for long sessions). Light theme ships via the same tokens.
- **No emoji as icons.** Icons are inline SVG, one stroke weight (craft floor ban).
- **Contrast:** body/placeholder text ≥ 4.5:1 on every surface, both themes (craft floor).
- **Every interactive element:** default / hover / focus / active / disabled / loading states; visible keyboard focus; ≥44px touch targets.
- **Errors name the problem and the recovery** (craft floor copy rule). No `.catch(()=>{})` on user-facing paths.
- **App name:** working name "vibe".

---

## File Structure

### Frontend — `apps/vibe/`

```
apps/vibe/
├── index.html                          # Modify: title "vibe — local vibe-coding IDE", favicon, theme bootstrap
├── public/
│   └── favicon.svg                     # Create: simple geometric mark
├── src/
│   ├── main.tsx                        # Modify: import ./styles/global.css
│   ├── App.tsx                         # Modify: 3-column shell, header, Settings modal, responsive
│   ├── styles/
│   │   ├── tokens.css                  # Create: color/type/spacing/radius/elevation tokens; [data-theme] themes
│   │   ├── global.css                   # Create: base elements, buttons, inputs, focus rings, scrollbars, selection
│   │   └── app.css                     # Create: shell layout + responsive breakpoints (imported by App.tsx)
│   ├── components/
│   │   └── ui/
│   │       ├── Button.tsx             # Create: variants primary/secondary/ghost/danger × sizes; loading state
│   │       ├── IconButton.tsx           # Create: 44px target, aria-label required, tooltip
│   │       ├── Modal.tsx                # Create: dialog, Esc, focus trap, backdrop click
│   │       ├── ConfirmDialog.tsx        # Create: destructive-action confirm
│   │       ├── Spinner.tsx              # Create: sized loading indicator
│   │       ├── EmptyState.tsx           # Create: icon + title + body + optional CTA
│   │       ├── ErrorBanner.tsx          # Create: message + retry action
│   │       └── Tooltip.tsx              # Create: CSS-only tooltip wrapper
│   ├── lib/
│   │   ├── api.ts                      # Modify: add getMessages/getPreview/runPreview/stopPreview; ApiError; stop swallowing
│   │   ├── format.ts                   # Create: relative time, token/cost formatting, detectLanguage
│   │   └── markdown.tsx                # Create: react-markdown wrapper + CodeBlock (language label, copy button)
│   ├── hooks/
│   │   └── useKeyboardShortcut.ts      # Create: global shortcut registry (Cmd/Ctrl+, …)
│   └── features/
│       ├── chat/
│       │   ├── store.ts                # Modify: per-session messages map; streaming + stop support
│       │   ├── ChatPanel.tsx           # Modify: header (session title + model picker), states
│       │   ├── Composer.tsx            # Modify: textarea (Shift+Enter newline), stop button, error state
│       │   ├── MessageList.tsx         # Modify: markdown rendering, auto-scroll, empty state, streaming indicator
│       │   ├── ApprovalCard.tsx        # Create: rich approval card (packages, always-allow)
│       │   └── UsageBadge.tsx          # Modify: styled; visible at 0 steps
│       ├── sessions/
│       │   ├── SessionsPanel.tsx       # Modify: styled list, empty state, delete confirm, rename
│       │   └── store.ts                # Modify: fix stale activeId after delete
│       ├── code/
│       │   ├── CodePanel.tsx           # Modify: file list as buttons, language detect, save indicator, empty state
│       │   └── store.ts                # Modify: per-session files; save state (idle/saving/saved/error)
│       ├── preview/
│       │   ├── PreviewPanel.tsx        # Modify: poll backend preview state; run/stop; loading
│       │   └── store.ts                # Modify: real state from API
│       └── settings/
│           └── SettingsPanel.tsx       # Modify: modal content, styled form, delete confirm, key status
```

### Backend — `services/vibe/src/vibe/api/routes/`

```
├── messages.py   # Create: GET /sessions/{sid}/messages — reconstruct chat history from EventLog
└── preview.py    # Create: GET/POST /sessions/{sid}/preview[/run|/stop] — dev-server url+running from the session executor
```

---

## Task 1: Design system foundation — tokens, global styles, UI primitives

**Files:**
- Create: `apps/vibe/src/styles/tokens.css`, `apps/vibe/src/styles/global.css`
- Create: `apps/vibe/src/components/ui/` — Button.tsx, IconButton.tsx, Modal.tsx, ConfirmDialog.tsx, Spinner.tsx, EmptyState.tsx, ErrorBanner.tsx, Tooltip.tsx
- Modify: `apps/vibe/src/main.tsx`
- Test: `apps/vibe/src/components/ui/__tests__/*.test.tsx`

**Interfaces:**
- Consumes: nothing (foundation task).
- Produces: `<Button variant="primary|secondary|ghost|danger" size="sm|md" loading>`, `<IconButton icon={<Svg/>} label="…">` (label = required aria-label), `<Modal open onClose title>`, `<ConfirmDialog open onClose onConfirm title body confirmLabel cancelLabel>`, `<Spinner size="sm|md|lg">`, `<EmptyState icon title body action?>`, `<ErrorBanner message onRetry?>`, `<Tooltip label>children</Tooltip>`. All styled purely with tokens from `tokens.css`.

- [ ] **Step 1: Write tokens.css** — CSS custom properties: `--bg`, `--bg-raised`, `--bg-hover`, `--border`, `--text`, `--text-muted` (tinted from the foreground hue, never gray — craft floor), `--accent`, `--accent-contrast`, `--success`, `--danger`, `--warning`, `--radius-sm|md|lg`, `--space-1..6`, `--font-ui`, `--font-mono`, `--text-sm|base|lg|xl`, `--shadow-1|2`. Dark theme on `:root`, light on `[data-theme="light"]`. Contrast-checked: `--text-muted` ≥ 4.5:1 on `--bg` and `--bg-raised` in both themes.
- [ ] **Step 2: Write global.css** — import tokens; `body` font `var(--font-ui)` (system stack: `-apple-system, "Segoe UI", Inter, Roboto, sans-serif`); style `button`, `input`, `textarea`, `select`, `a`, `h1-h4` from tokens; visible `:focus-visible` ring (2px accent, offset); themed `::selection`, scrollbars (`::-webkit-scrollbar` + `scrollbar-color`), `code/pre` in `--font-mono`. No hard-coded hex — tokens only.
- [ ] **Step 3: Write the failing component tests** — for each UI component: renders children, applies variant/loading/disabled, Modal calls onClose on Esc/backdrop, ConfirmDialog calls onConfirm/onCancel, IconButton requires aria-label. Run `pnpm test` — FAIL (modules missing).
- [ ] **Step 4: Implement the 8 UI components** — plain function components, `React.ButtonHTMLAttribute` etc., class names only (no inline styles except dynamic layout values), tokens via `var()`. Modal: `role="dialog" aria-modal`, focus trap (focus first focusable on open, restore on close), Esc handler, backdrop click. ConfirmDialog: `role="alertdialog"`, danger styling, Enter = cancel, Esc = cancel.
- [ ] **Step 5: Wire global.css into main.tsx** — `import "./styles/global.css";` as the first import.
- [ ] **Step 6: Run tests + typecheck** — `pnpm test` PASS, `pnpm typecheck` PASS.
- [ ] **Step 7: Commit** — `git add apps/vibe/src/styles apps/vibe/src/components apps/vibe/src/main.tsx && git commit -m "feat(ui): design tokens, global styles, and UI primitives"`

---

## Task 2: App shell — 3-column layout, header, Settings modal, responsive

**Files:**
- Modify: `apps/vibe/src/App.tsx`
- Create: `apps/vibe/src/styles/app.css`
- Modify: `apps/vibe/src/features/settings/SettingsPanel.tsx` (content only — modal chrome from Task 1)
- Create: `apps/vibe/src/hooks/useKeyboardShortcut.ts`
- Test: `apps/vibe/src/__tests__/App.test.tsx`

**Interfaces:**
- Consumes: `<Modal>`, `<IconButton>`, `<Button>` from Task 1.
- Produces: `useKeyboardShortcut(handler, { meta: true, key: "," })` — global keydown listener, ignores events from inputs unless `allowInInput`.
- Layout: sessions sidebar (260px) | chat (flex) | preview+code (42%, min 320px). Header bar: product mark + name, session title, model picker slot, settings IconButton. Under 1100px: preview/code column becomes a toggleable bottom panel. Under 768px: single column with a tab bar (Chat / Code / Preview); sessions sidebar becomes a drawer.

- [ ] **Step 1: Write the failing App test** — renders header with product name, Settings modal closed initially, opens settings via the header button, opens via Cmd+, closes via Esc. Run `pnpm test` — FAIL.
- [ ] **Step 2: Implement useKeyboardShortcut** — `useEffect` keydown listener; `e.metaKey || e.ctrlKey` matching; cleanup on unmount.
- [ ] **Step 3: Rewrite App.tsx** — header + 3 columns; `SettingsPanel` inside `<Modal open={settingsOpen}>`; settings button in header; Cmd+, opens/closes; responsive via app.css media queries. No session selected → chat column shows `<EmptyState>` with a "New session" CTA instead of the dead "Select a session" text.
- [ ] **Step 4: Restyle SettingsPanel content** — tokens + Button/Input styles; keep all existing form logic and aria-labels; styled "key configured" badge; delete uses ConfirmDialog (local confirm state for now).
- [ ] **Step 5: Run tests + typecheck** — PASS.
- [ ] **Step 6: Verify in browser** — start `pnpm dev`, screenshot desktop 1440×900 and narrow 800×900: header visible, settings modal opens/closes, no overflow. Stop the dev server after.
- [ ] **Step 7: Commit** — `git commit -m "feat(app): 3-column shell, header, settings modal, responsive layout"`

---

## Task 3: Honest states — errors, loading, empty, destructive confirms

**Files:**
- Modify: `apps/vibe/src/lib/api.ts` (add `ApiError` with `status`; replace `.catch(()=>{})` on user-facing calls)
- Modify: `apps/vibe/src/features/sessions/SessionsPanel.tsx` (empty state, delete ConfirmDialog, loading)
- Modify: `apps/vibe/src/features/sessions/store.ts` (fix stale `activeId` after delete)
- Modify: `apps/vibe/src/features/chat/MessageList.tsx` (streaming indicator + stop button, error state)
- Modify: `apps/vibe/src/features/chat/Composer.tsx` (send error → ErrorBanner, message preserved)
- Modify: `apps/vibe/src/features/code/CodePanel.tsx` (loading + empty state, save error)
- Modify: `apps/vibe/src/features/preview/PreviewPanel.tsx` (error state)
- Modify: `apps/vibe/src/features/settings/SettingsPanel.tsx` (delete ConfirmDialog, save validation message)
- Test: `apps/vibe/src/lib/__tests__/api.test.ts`, extend `apps/vibe/src/features/sessions/__tests__/SessionsPanel.test.tsx`

**Interfaces:**
- Consumes: `<ConfirmDialog>`, `<ErrorBanner>`, `<EmptyState>`, `<Spinner>` from Task 1.
- Produces: `ApiError extends Error { status: number }`; `api` methods throw `ApiError` on `!resp.ok`.

- [ ] **Step 1: Write failing tests** — SessionsPanel: EmptyState + "New session" CTA when list empty; delete click opens ConfirmDialog; confirming issues the delete. Composer: failed send keeps the text and shows an error. Run — FAIL.
- [ ] **Step 2: api.ts — honest errors** — add `export class ApiError extends Error { constructor(message: string, readonly status: number) }`; `req()` throws `new ApiError(`API error: ${status}`, status)`; remove `.catch(()=>{})` from component call sites (getCatalog/listSessions/getUsage/listApprovals).
- [ ] **Step 3: SessionsPanel** — Spinner while `load()` in flight; EmptyState when empty; delete → ConfirmDialog ("Delete session?" / "This permanently removes the session and its history." / "Delete"); store `remove` fixes `activeId` (deleted active → next session or null).
- [ ] **Step 4: MessageList + Composer** — Composer `send` catches `ApiError` → ErrorBanner "Couldn't send — the API returned {status}. Your message was kept." + text preserved; MessageList shows streaming indicator (Spinner + "Agent is working…") when `isStreaming`; stop button visible while streaming (wired to a stop flag in Task 4 — for now it clears the indicator).
- [ ] **Step 5: CodePanel + PreviewPanel + SettingsPanel** — CodePanel: Spinner on first load, EmptyState "No files yet — the agent hasn't written any." when empty, save error inline; PreviewPanel: ErrorBanner on failed run; SettingsPanel: delete → ConfirmDialog, Save with empty name → inline "Name and Base URL are required." instead of silent no-op.
- [ ] **Step 6: Run tests + typecheck** — PASS.
- [ ] **Step 7: Commit** — `git commit -m "feat(states): error banners, empty/loading states, delete confirms"`

---

## Task 4: Chat — per-session store, history, markdown, composer, auto-scroll

**Files:**
- Create: `services/vibe/src/vibe/api/routes/messages.py`
- Modify: `services/vibe/src/vibe/api/app.py` (register router)
- Modify: `apps/vibe/src/lib/api.ts` (add `getMessages`)
- Modify: `apps/vibe/src/features/chat/store.ts` (per-session)
- Modify: `apps/vibe/src/features/chat/MessageList.tsx`, `Composer.tsx`
- Create: `apps/vibe/src/lib/markdown.tsx`
- Test: extend `apps/vibe/src/features/chat/__tests__/MessageList.test.tsx`, create `apps/vibe/src/lib/__tests__/markdown.test.tsx`, backend `services/vibe/tests/test_messages_endpoint.py`

**Interfaces:**
- Consumes: `react-markdown` (new dep — `pnpm add react-markdown`).
- Produces: backend `GET /sessions/{sid}/messages` → `[{role, content}]` reconstructed from EventLog `user/message` + `assistant/message` events in seq order. Frontend `api.getMessages(sid)`. Chat store: `messagesBySession: Record<string, ChatMessage[]>`, `addMessage(sid, m)`, `appendChunk(sid, text)`, `isStreamingBySession: Record<string, boolean>`, `stopRequested: Record<string, boolean>` (Composer's stop sets it; the streaming indicator clears).

- [ ] **Step 1: Backend — write the failing test** — `tests/test_messages_endpoint.py`: seed EventLog with user/assistant events via app state, GET the endpoint, assert ordered history. Run `pytest services/vibe/tests/test_messages_endpoint.py` — FAIL (404).
- [ ] **Step 2: Implement messages.py** — `@router.get("/sessions/{sid}/messages")`: read `request.app.state.event_log.get(sid)`, filter types `user/message`/`assistant/message`, map to `{"role": "user"|"assistant", "content": payload["content"]}`, return in seq order. Register in app.py.
- [ ] **Step 3: Frontend — extend api.ts** — `getMessages: (sid) => req<Message[]>(`/sessions/${sid}/messages`)` with `export interface Message { role: "user" | "assistant"; content: string }`.
- [ ] **Step 4: Per-session chat store** — replace global `messages` with `messagesBySession`; all actions take `sid`; `loadHistory(sid)` fetches via `api.getMessages`; `appendChunk` appends to the session's last assistant message. Update MessageList/Composer/ChatPanel call sites.
- [ ] **Step 5: markdown.tsx** — `<Markdown content>` wrapping `react-markdown` with custom `code` renderer: fenced blocks → `<CodeBlock language code>` (language label + copy Button + `--font-mono` pre); inline code → styled `<code>`. No raw HTML (react-markdown default is safe without rehype-raw).
- [ ] **Step 6: MessageList** — `<Markdown>` for assistant messages, styled plain text for user; auto-scroll to bottom on new content (ref + `scrollTop = scrollHeight` in `useEffect`, only when user is near bottom); streaming indicator row; EmptyState for a fresh session ("Describe the app you want to build — the agent handles the rest.").
- [ ] **Step 7: Composer** — `<textarea rows={2}>` with Shift+Enter newline / Enter send; stop button (IconButton, visible while streaming) clearing the indicator.
- [ ] **Step 8: Run all tests + typecheck + build** — `pnpm test`, `pnpm typecheck`, `pnpm build` PASS; backend `pytest services/vibe/tests/test_messages_endpoint.py` PASS.
- [ ] **Step 9: Commit** — `git commit -m "feat(chat): per-session store, message history, markdown rendering"`

---

## Task 5: Approval flow — rich cards

**Files:**
- Create: `apps/vibe/src/features/chat/ApprovalCard.tsx`
- Modify: `apps/vibe/src/features/chat/MessageList.tsx` (use ApprovalCard)
- Test: `apps/vibe/src/features/chat/__tests__/ApprovalCard.test.tsx`

**Interfaces:**
- Consumes: `<Button>`, `<IconButton>` from Task 1.
- Produces: `<ApprovalCard approval={Approval} onResolve(approved: boolean) />` — package list (mono, one per line, package icon), "wants to install" copy, risk hint ("Only approve packages you trust."), Approve (primary) / Deny (secondary), "Always allow" checkbox persisting to `localStorage` (`vibe:always-allow` = JSON array of package names) — when checked, `onResolve(true)` fires immediately for matching future approvals. Resolved state shows an Approved/Denied badge.

- [ ] **Step 1: Write the failing test** — renders package names, fires onResolve(true/false), always-allow checkbox auto-approves and persists. Run — FAIL.
- [ ] **Step 2: Implement ApprovalCard** — token-styled card, inline SVG icons (package/lock, 1.5px stroke), status badge with success/danger tokens.
- [ ] **Step 3: Wire into MessageList** — replace the inline approval block; on mount, auto-resolve approvals whose packages are all in the always-allow list.
- [ ] **Step 4: Run tests + typecheck** — PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(approvals): rich approval cards with always-allow policy"`

---

## Task 6: Code panel — accessible file list, language detection, save indicator

**Files:**
- Modify: `apps/vibe/src/features/code/CodePanel.tsx`, `store.ts`
- Test: extend `apps/vibe/src/features/code/__tests__/CodePanel.test.tsx`

**Interfaces:**
- Consumes: `<EmptyState>`, `<Spinner>`, `<Button>` from Task 1.
- Produces: code store gains `saveState: Record<path, "idle"|"saving"|"saved"|"error">` + `setSaveState(path, state)`; per-session `filesBySession`; `detectLanguage(path)` in `lib/format.ts` (ts/tsx→typescript, js/jsx→javascript, css→css, html→html, json→json, md→markdown, else plaintext).

- [ ] **Step 1: Write failing tests** — file items are `<button>` (keyboard operable); selecting a file shows a save indicator while saving; empty file list shows EmptyState. Run — FAIL.
- [ ] **Step 2: store.ts** — per-session files; `saveFile` sets saving→saved (or error on failure); keep the 3s list refresh but never reset selection while the user is editing.
- [ ] **Step 3: CodePanel** — file items as `<button>` with aria-pressed for selection; Monaco `language={detectLanguage(selectedFile)}`; save indicator near the editor ("Saving…" / "Saved" / "Save failed — retry"); EmptyState when no files.
- [ ] **Step 4: Run tests + typecheck** — PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(code): accessible file list, language detection, save indicator"`

---

## Task 7: Preview panel — real backend state

**Files:**
- Create: `services/vibe/src/vibe/api/routes/preview.py`
- Modify: `services/vibe/src/vibe/api/app.py` (register router)
- Modify: `apps/vibe/src/lib/api.ts` (add `getPreview/runPreview/stopPreview`)
- Modify: `apps/vibe/src/features/preview/store.ts`, `PreviewPanel.tsx`
- Test: extend `apps/vibe/src/features/preview/__tests__/PreviewPanel.test.tsx`, backend `services/vibe/tests/test_preview_endpoint.py`

**Interfaces:**
- Consumes: `<Spinner>`, `<ErrorBanner>`, `<Button>` from Task 1.
- Produces: backend `GET /sessions/{sid}/preview` → `{"url": string|null, "running": boolean}` from `app.state.executors[sid]` dev-server handle; `POST /sessions/{sid}/preview/run` starts the dev server via the executor; `POST /sessions/{sid}/preview/stop` stops it. Frontend `api.getPreview/runPreview/stopPreview(sid)`; PreviewPanel polls GET every 2s while mounted.

- [ ] **Step 1: Backend failing test** — seed an executor with a fake dev-server handle; GET preview returns url+running; POST run starts; POST stop clears. Run — FAIL.
- [ ] **Step 2: Implement preview.py** — GET/POST run/POST stop using `app.state.get_executor(sid, settings.workspace_dir / sid)`; start/stop via executor methods; return `{url, running}`.
- [ ] **Step 3: Frontend store + panel** — store holds `{url, running, loading, error}`, `refresh()` polls; panel: Run (primary, disabled while running/loading), Stop (secondary), Spinner while starting, ErrorBanner on failure, EmptyState "No preview yet — run the app to see it here." when no url; iframe titled "App preview".
- [ ] **Step 4: Run tests + typecheck** — PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(preview): real dev-server state from backend"`

---

## Task 8: Polish pass — favicon, title, browser surfaces, full verification

**Files:**
- Modify: `apps/vibe/index.html` (title "vibe — local vibe-coding IDE", favicon link, inline theme bootstrap against FOUC)
- Create: `apps/vibe/public/favicon.svg`
- Modify: `apps/vibe/src/styles/global.css` (contrast/focus gaps found in verification)
- Modify: `TASKS.md`, `HANDOFF.md`, `CURRENT_STATE.md` (milestone status)

- [ ] **Step 1: index.html + favicon** — title, favicon.svg link, `<script>document.documentElement.dataset.theme = localStorage.getItem("vibe:theme") || "dark"</script>` in head; theme toggle (sun/moon IconButton) in the header persisting to localStorage.
- [ ] **Step 2: Full verification sweep** — `pnpm test` (all), `pnpm typecheck`, `pnpm build`, backend `pytest services/vibe/tests -k "messages or preview"`. Browser: desktop 1440×900 + mobile 390×844 screenshots — muted-text contrast on every surface, focus rings on tab-through, themed scrollbars, no horizontal overflow at 390px, touch targets ≥44px.
- [ ] **Step 3: Fix everything the sweep shows** — one batch, then one confirmation pass.
- [ ] **Step 4: Update docs** — TASKS.md: M5 tasks → done with evidence; HANDOFF.md: M5 narrative; CURRENT_STATE.md: snapshot refresh.
- [ ] **Step 5: Commit** — `git commit -m "chore: favicon, title, theme toggle, verification sweep"`

---

## Self-Review

**Spec coverage** — critique priority issues → tasks: P0 unstyled UI → Tasks 1+2 · P0 silent errors → Task 3 · P0 destructive confirms → Task 3 · P1 Settings column → Task 2 · P1 approval flow → Task 5 · P2 responsive → Task 2 · P2 markdown → Task 4. Functional bugs: global chat store → Task 4 · no history → Task 4 · preview hardcoded URL → Task 7 · Monaco language → Task 6 · stale activeId → Task 3 · 📎 emoji → Task 1 · no favicon/title → Task 8. All covered.

**Placeholder scan** — no TBD/TODO; every code step shows the actual code or exact interface.

**Type consistency** — `ApiError(status)`, `Message {role, content}`, `Approval {id, packages, status}`, `useKeyboardShortcut(handler, {meta, key})`, `detectLanguage(path)`, `saveState` union, `getMessages/getPreview/runPreview/stopPreview` — consistent across tasks.
