# 03 — Frontend findings

Scope: `apps/vibe/src` — shell, API/SSE clients, the four feature stores and
panels, hooks, and UI primitives. The suite baseline (104 tests, typecheck,
eslint, build) is in [01-baseline-validation.md](./01-baseline-validation.md).

Method note: findings here are from reading the current source. Where a claim
is not empirically run it is labelled **static** rather than probe-verified;
the backend findings are the probe-verified ones.

---

## What is genuinely strong

- **The SSE resume cursor is correct.** `SSEClient.lastSeq` advances only on a
  strictly newer `seq` and is sent back as `after_seq` on reconnect, so a
  dropped connection replays nothing twice and skips nothing. The P14 fallback
  (accept raw frames when the `data: ` prefix is missing) is defensive in the
  right direction. `lib/sse.ts`.
- **Streamed text cannot land in the wrong bubble.** `streamingMessageIdBySession`
  binds a turn to a freshly created message before any chunk arrives
  (`chat/store.ts`), which is exactly the bug a naive "append to last assistant
  message" implementation has.
- **The API client handles the two shapes that actually break clients:** a
  204 with no body (`readBody`) and an error body that is not ours
  (`toApiError`). `lib/api.ts`.
- **Path segments are encoded individually** (`encodePath`), so a filename with
  `#` or `?` no longer truncates the request.
- **Modal is a real dialog:** `role="dialog"`, `aria-modal`, a Tab focus trap,
  Escape handling, focus restore, and backdrop-click close. `useMediaQuery`
  uses `useSyncExternalStore` rather than setState-in-effect.
- **Mobile landmark handling is deliberate:** when the side column owns the
  viewport, `app.css` sets `.app-main { display: none }`, so the temporary
  `role="main"` on the side section does not create a duplicate main landmark.
- **`usePolling` survives a backend restart** via `recoveryInterval` instead of
  stopping for good, with exponential backoff between.
- **Command palette reset is done in render, with tests**, avoiding the
  one-frame stale query an effect would cause.

---

## FE-01 — The event stream can die silently and never recover — **Medium**

**Where:** `lib/sse.ts:39-66`; consumer `features/chat/MessageList.tsx:52-58`.

**What:** after `maxReconnectAttempts = 5` consecutive `onerror` events the
client simply stops scheduling reconnects. It notifies nobody: there is no
callback, no state, and no UI. The chat keeps its last state — a spinner that
never ends if the drop lands mid-turn, or a transcript that quietly stops
updating.

**Impact:** a dev-server restart, a laptop sleep, or a backend restart longer
than ~31 s (1+2+4+8+16) leaves the tab permanently disconnected while looking
connected. Fixing it requires a page reload to remount the effect.

**Static** (logic read from source; not probe-run).

**Fix sketch:** surface connection state from `SSEClient` (an `onStateChange`
callback) and show a "reconnecting / disconnected" affordance with a manual
retry; or drop the attempt cap and keep the backoff capped at ~30 s.

---

## FE-02 — A dead backend is reported as "no files yet" — **Medium**

**Where:** `features/code/store.ts:24-27`, `CodePanel.tsx:30-45`.

**What:** the store swallows every list/read failure into a benign default:

```ts
loadFiles: async (sid) => {
  const files = await api.listFiles(sid).catch(() => [] as string[]);
  set({ files });
},
loadFile: async (sid, path) => {
  const { content } = await api.readFile(sid, path).catch(() => ({ path, content: "" }));
  ...
}
```

`loadFiles` therefore never rejects, so `CodePanel`'s `try/catch` and its
`setError(...)` branches are unreachable. A backend that is down, or a session
whose workspace is gone, renders the empty state **"No files yet — the agent
has not written any files for this session."** and an empty editor.

**Impact:** the user is told something false about the agent's work and has no
signal that a request failed. The same pattern makes a failed file read look
like an empty file, which is dangerous next to a Save button.

**Static.**

**Fix sketch:** let the store propagate errors; keep the optimistic default only
for the "file was deleted mid-edit" case, which is the one it was written for.

---

## FE-03 — Model ids containing "/" are truncated on selection — **Medium**

**Where:** `features/chat/ModelPicker.tsx:37-48`.

**What:** the option value is `${provider_id}/${model_id}` and the change
handler does `e.target.value.split("/")` into exactly two variables:

```ts
const [provider_id, model_id] = e.target.value.split("/");
```

A model id that itself contains a slash — normal for OpenRouter
(`anthropic/claude-3.5-sonnet`), Hugging Face, or any namespaced catalog —
becomes `model_id = "anthropic"`. The wrong model is stored on the session and
sent to the backend.

**Impact:** silent misconfiguration for a whole class of custom providers,
reachable through the primary model-selection UI.

**Static.**

**Fix sketch:** carry the pair on the option itself (e.g. JSON-encoded
`value`, or `data-provider`/`data-model` attributes) and never reconstruct it by
splitting a joined string.

---

## FE-04 — Reading history is impossible while the agent streams — **Medium**

**Where:** `features/chat/MessageList.tsx:44-49`.

**What:** an effect with no "is the user near the bottom?" test forces the list
to the bottom on every content change:

```ts
useEffect(() => {
  const el = listRef.current;
  if (el) el.scrollTop = el.scrollHeight;
}, [lastMessage?.id, lastMessage?.content, isStreaming, approvals]);
```

The comment addresses only the *prepend* case (it keys on the last message so
loading older messages does not yank). Streaming into the last message still
does.

**Impact:** a user who scrolls up to read the previous turn is pulled back down
on every streamed chunk — the transcript is effectively frozen at the bottom
for the duration of a turn.

**Static.**

**Fix sketch:** track whether the user is within a small threshold of the
bottom; auto-scroll only then, and offer a "jump to latest" affordance
otherwise.

---

## FE-05 — Monaco renders its light theme inside a dark app — **Medium (visual)**

**Where:** `features/code/CodePanel.tsx:97-104`.

**What:** `<Editor path language value onChange />` passes no `theme`, and a
search of `apps/vibe/src` finds no `vs-dark` or `beforeMount` theme setup
anywhere. `@monaco-editor/react` defaults to Monaco's light theme, while
`tokens.css` is dark-first.

**Impact:** the Code panel — one of the three primary panels — shows a white
editor inside the dark shell for every default user.

**Static** (not confirmed on screen; the check is that no theme is set).

**Fix sketch:** pass `theme={theme === "dark" ? "vs-dark" : "light"}` from the
app theme, or define a custom theme in `beforeMount`.

---

## FE-06 — The preview panel bleeds the previous session's app — **Low**

**Where:** `features/preview/store.ts`; `PreviewPanel.tsx`.

**What:** the preview store is a single global object keyed by nothing. The
panel is not remounted on session change (the `ErrorBoundary` only resets its
own error state), so switching from a running session to an idle one shows the
old session's URL and `isRunning = true` in the iframe until the next 2 s poll.

**Impact:** for up to two seconds the user is shown another project's running
app and a Stop button that will stop the wrong server. The code store has the
same global shape (`files`/`selectedFile`/`contents`), so a path that exists in
both projects can briefly show the previous session's content.

**Static.**

**Fix sketch:** clear state on `sessionId` change, or key the store per session
the way the chat store already does with its `*BySession` maps.

---

## FE-07 — Approve/deny failures are swallowed and the card reappears — **Low**

**Where:** `features/chat/MessageList.tsx:84-96`.

**What:** `api.approve(a.id).catch(() => {})` then `resolveApproval(a.id)`
removes the card locally regardless of the result. If the request failed, the
3 s approvals poll sees the approval still `pending` and re-adds the card with
no explanation.

**Impact:** the user clicks Approve, the card vanishes, then comes back — with
no error. The agent, meanwhile, is still blocked.

**Static.**

---

## FE-08 — `savePolicy` is unguarded while `loadPolicy` is guarded — **Low**

**Where:** `features/chat/ApprovalCard.tsx:11-19`, `31-36`.

`loadPolicy` wraps `localStorage.getItem` in try/catch; the sibling
`savePolicy` calls `localStorage.setItem` bare. In a privacy mode or at quota,
"Always allow" throws inside `approve()` **before** `setStatus` and `onApprove()`,
so the click does nothing at all. **Static.**

---

## FE-09 — The palette advertises a shortcut that is not bound — **Low**

**Where:** `App.tsx:76-100`; bound shortcuts are only `Cmd/Ctrl+,`, `Cmd/Ctrl+K`
and `?` (`App.tsx:45-47`).

The "New session" command renders a `Cmd N` hint purely from its
`shortcut: ["Cmd", "N"]` data; no handler listens for it. **Static.**

---

## FE-10 — The composer's over-limit branch is dead — **Low**

**Where:** `features/chat/Composer.tsx:22-24`, `232-239`.

`<textarea maxLength={MAX_CHARS}>` means the value can never exceed
`MAX_CHARS`, so `isOverLimit` is always false: the `send()` guard, the
destructive char-count styling, and the `disabled` condition on Send are all
unreachable. Only `isNearLimit` does anything. **Static.**

---

## FE-11 — A failed send duplicates the user's message — **Low**

**Where:** `features/chat/Composer.tsx:96-117`.

`addMessage(...)` appends the user bubble optimistically, then on failure the
draft text is restored. The transcript keeps the optimistic bubble, so pressing
Send again renders the same prompt twice while the backend processed it zero or
one times. **Static.** (Ties to BE-04: a 409 from the concurrency guard is one
way to hit this.)

---

## FE-12 — Only the side panels have an error boundary — **Low**

**Where:** `App.tsx:222-260`, `main.tsx`.

`ErrorBoundary` wraps `PreviewPanel` and `CodePanel`. `ChatPanel` and
`SessionsPanel` are bare, and there is no root boundary, so a render error in
either unmounts the whole tree and leaves a blank page. **Static.**

---

## FE-13 — Four always-on polling loops, no visibility gate — **Low**

**Where:** `hooks/usePolling.ts`; call sites: approvals 3 s
(`MessageList.tsx:29-36`), files 3 s (`CodePanel.tsx:24-37`), usage 5 s
(`UsageBadge.tsx:12-18`), preview 2 s (`PreviewPanel.tsx:14-20`).

All four run for as long as their panel is mounted, whether or not anything can
have changed, with no `document.visibilityState` check and no backoff on
success. Most browsers throttle hidden-tab timers, which keeps this from being
worse; it is still steady background traffic against a local server.

Related: `UsageBadge` polls even when the previous response had
`steps === 0`, and `CodePanel` polls a file list that in practice changes only
during a run. **Static.**

---

## FE-14 — Live regions are nested — **Low**

**Where:** `MessageList.tsx:56` (`role="log" aria-live="polite"`) wrapping
`MessageList.tsx:114-119` (`role="status" aria-live="polite"`); `Toast.tsx:69-71`
(`aria-live="polite"` container wrapping per-toast `role="status"`).

Every streaming tick is announced by the outer region and the inner one, and
the whole message list is a live region that re-renders on each chunk. Screen
reader output for a long turn is likely to be noisy or duplicated. **Static**
(needs a screen-reader pass to judge severity).

---

## FE-15 — Small truthfulness and coverage gaps — **Low / Info**

- **`lib/logger.ts:3`** promises "In production, logs can be sent to a remote
  service" — no such transport exists anywhere. Aspirational comment.
- **`lib/api.ts:107-113`** types `getSession` as a full `Session` including
  `created_at`/`updated_at`, but the backend's single-session response omits
  both (BE-10). Only `.model` is actually safe to read.
- **`lib/theme.ts:34-37`** `toggleTheme` derives the next theme from
  `getTheme()` (localStorage). With storage unavailable `getTheme()` always
  answers `"dark"`, so the toggle can switch to light but never back.
- **The stored API key still cannot be cleared from the UI.** Editing a
  provider sends `apiKey: form.apiKey || undefined`; the backend reads a missing
  key as "unchanged", so there is no path back to "no key". README lists this
  under Known gaps; it is **confirmed**, not newly found.
- **Test coverage gaps:** there is no test file for `SettingsPanel` (the whole
  custom-provider CRUD path), `ModelPicker`, or `UsageBadge`. 18 test files
  cover the rest, including `CodePanel`, `PreviewPanel`, `SessionsPanel`,
  `Composer`, `ApprovalCard`, `MessageList`, both hooks, and the palette.

---

## FE-16 — "Jump to latest" is offered when the transcript cannot scroll — **Low**

Found by the R7 browser re-check (M5) rather than by reading: with a two-message
transcript the log measured `scrollHeight 444 == clientHeight 444`, `scrollTop 0` —
already at the bottom, nothing to scroll — yet the button was laid out and visible
(`offsetParent !== null`, 89x28 px).

`MessageList.tsx` gated the control on `isPinned` alone, and `isPinned` is only
recomputed by the `onScroll` handler. A transcript that fits its box never fires a
scroll event, so the flag kept whatever the last event had left it as (a streamed
chunk can leave it false) and the control stayed on screen with nothing to jump to.

**Fix:** scrollability is measured rather than assumed. A `measure()` helper computes
both values from the element (`overflow = scrollHeight - clientHeight`;
`canScroll = overflow > PINNED_THRESHOLD_PX`; `isPinned = overflow - scrollTop <=
PINNED_THRESHOLD_PX`), is wired to `onScroll`, runs after the follow effect has assigned
`scrollTop`, and is re-run by a `ResizeObserver` when the panel or window changes size.
The control now renders only when `canScroll && !isPinned`.

**Evidence:** two new tests in `MessageList.test.tsx` (`shows no jump control when the
transcript cannot scroll at all`, `hides the jump control again once the bottom is
reached`) — 13 tests in that file — and the release gate re-run after the change
(`artifacts/release-check-final-post-m5.txt`). The browser-level counterpart is M5 of
`artifacts/hardening-r7-browser-recheck.txt`, screenshot
`artifacts/browser-check-recheck-M5-scrolled.png`.

**Not established:** whether pinning holds through a long streaming turn — the
re-check's transcript never overflowed, so that half of M5 stays unverified.

---

## Cross-cutting note: silent degradation

The strongest frontend pattern — `readBody` tolerating a missing body and
`SSEClient` tolerating a missing `data: ` prefix — is also, when over-applied,
the weakest: `catch(() => [])`, `.catch(() => 0)`, and `.catch(() => {})` appear
at the store and panel boundaries in FE-02, FE-06 and FE-07 and convert failure
into a plausible-looking empty state. The backend made the same choice
deliberately and correctly for `read_console_logs` (`None` means "not checked",
never "clean"); the frontend mostly fails the other way.
