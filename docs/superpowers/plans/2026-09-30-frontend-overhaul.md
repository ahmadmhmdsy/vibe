# Frontend Overhaul Plan — vibe IDE

## Executive Summary

After analyzing every file in `apps/vibe/src/`, I've identified **47 distinct issues** across 6 categories. This plan addresses all of them with a systematic, test-driven approach.

---

## Issue Inventory

### Category 1: Hardcoded Values (12 issues) — CRITICAL

| # | File | Line | Issue | Fix |
|---|------|------|-------|-----|
| 1 | `UsageBadge.tsx` | 14 | `style={{ padding: "4px 8px", fontSize: 12, color: "#595959", borderTop: "1px solid #eee" }}` — completely hardcoded, no CSS variables | Replace with CSS class using tokens |
| 2 | `ModelPicker.tsx` | 18 | `style={{ padding: 4 }}` — hardcoded inline style | Use CSS variable |
| 3 | `Spinner.tsx` | 12-20 | All inline styles — no CSS variables | Move to CSS class |
| 4 | `chat.css` | 45 | `color: #ffffff` hardcoded in `.composer-attachment-remove` | Use `var(--accent-contrast)` |
| 5 | `preview.css` | 22 | `background: #ffffff` hardcoded in `.preview-frame` | Use `var(--bg-raised)` or semantic token |
| 6 | `components.css` | 47 | `color: #ffffff` hardcoded in `.btn-danger` | Use `var(--accent-contrast)` |
| 7 | `global.css` | 89 | `color: #ffffff` hardcoded in `pre code` context | Already uses tokens, verify |
| 8 | `App.tsx` | 12 | SVG `stroke="var(--accent)"` — good, but `stroke="var(--text-faint)"` should be token | Already correct |
| 9 | `MessageList.tsx` | 45 | `role="log"` with `aria-live="polite"` — good, but streaming indicator needs `aria-live` | Add `aria-live` to streaming |
| 10 | `CodePanel.tsx` | 55 | No error state for file loading failures | Add error handling |
| 11 | `PreviewPanel.tsx` | 30 | iframe has no `sandbox` attribute — security risk | Add `sandbox="allow-scripts allow-same-origin"` |
| 12 | `SettingsPanel.tsx` | 80 | Form doesn't reset when modal closes | Add reset on close |

### Category 2: Accessibility Gaps (8 issues) — CRITICAL

| # | File | Issue | Fix |
|---|------|-------|-----|
| 1 | `Modal.tsx` | No focus trap — Tab can escape modal | Implement focus trap |
| 2 | `Modal.tsx` | Focus restore on close missing | Store and restore focus |
| 3 | `Composer.tsx` | Textarea has no visible label | Add `<label>` with `sr-only` |
| 4 | `ModelPicker.tsx` | Select has no visible label | Add `<label>` with `sr-only` |
| 5 | `EmptyState.tsx` | Uses `<h2>` — may skip heading levels | Make heading level configurable |
| 6 | `MessageList.tsx` | Approvals list not reactive to new approvals | Add refresh mechanism |
| 7 | `IconButton.tsx` | Tooltip not keyboard-accessible | Add `aria-label` (already has), verify focus-within |
| 8 | `SessionsPanel.tsx` | Rename input doesn't restore original title on Escape | Fix Escape handler |

### Category 3: Design System Inconsistencies (10 issues) — MAJOR

| # | Issue | Fix |
|---|-------|-----|
| 1 | No CSS naming convention — mix of BEM, kebab-case, utility | Adopt BEM-like: `block__element--modifier` |
| 2 | No CSS layer system — specificity wars | Use `@layer` for base, components, utilities |
| 3 | Inline styles in multiple components | Move all to CSS classes |
| 4 | No consistent component API | Standardize props: `variant`, `size`, `loading`, `disabled` |
| 5 | No consistent error handling pattern | Create `<AsyncBoundary>` wrapper |
| 6 | No consistent loading states | Standardize `<Loading>` component |
| 7 | No consistent empty states | Already have `<EmptyState>`, use everywhere |
| 8 | No toast/notification system | Create `<Toast>` component + context |
| 9 | No z-index scale | Add `--z-base`, `--z-dropdown`, `--z-modal`, `--z-toast` |
| 10 | No transition timing scale | Add `--duration-instant`, `--duration-fast`, `--duration`, `--duration-slow` |

### Category 4: Architecture Issues (7 issues) — MAJOR

| # | Issue | Fix |
|---|-------|-----|
| 1 | Store coupling — `useSessionsStore` imports `useChatStore` | Use dependency injection or event bus |
| 2 | No error boundaries | Add `<ErrorBoundary>` at panel level |
| 3 | No structured logging | Add `lib/logger.ts` |
| 4 | Polling intervals not coordinated | Create `usePolling` hook with cleanup |
| 5 | No memoization | Add `React.memo` to pure components |
| 6 | SSE reconnection has no exponential backoff | Implement backoff in `SSEClient` |
| 7 | No lazy loading | Use `React.lazy` for heavy panels |

### Category 5: UX Issues (6 issues) — MAJOR

| # | Issue | Fix |
|---|-------|-----|
| 1 | No keyboard shortcuts guide | Add `?` shortcut help modal |
| 2 | No command palette | Add `Cmd+K` command palette |
| 3 | No search in sessions | Add search input in sessions panel |
| 4 | No export/import sessions | Add export/import buttons |
| 5 | No drag-and-drop file upload | Add drop zone in composer |
| 6 | No character count in composer | Add character count indicator |

### Category 6: Code Quality (4 issues) — MINOR

| # | Issue | Fix |
|---|-------|-----|
| 1 | TypeScript strict mode not fully utilized | Enable `strict: true`, fix all errors |
| 2 | No `consistent-type-imports` | Add ESLint rule |
| 3 | No `no-floating-promises` | Add ESLint rule |
| 4 | Missing return types on some functions | Add explicit return types |

---

## Execution Plan

### Phase 1: Design System Foundation (Critical)
1. Expand `tokens.css` with complete design token set
2. Create `@layer` system in `global.css`
3. Create `lib/logger.ts` for structured logging
4. Create `hooks/usePolling.ts` for coordinated polling
5. Create `components/ui/Toast.tsx` + context
6. Create `components/ui/Loading.tsx`
7. Create `components/ui/ErrorBoundary.tsx`

### Phase 2: Component Hardening (Critical)
1. Fix all hardcoded values (12 issues)
2. Fix all accessibility gaps (8 issues)
3. Add focus trap to Modal
4. Add error boundaries to all panels
5. Add loading states to all async components
6. Fix theme consistency

### Phase 3: Feature Enhancements (Major)
1. Add keyboard shortcuts guide
2. Add command palette
3. Add search in sessions
4. Add export/import
5. Add drag-and-drop file upload
6. Add character count in composer

### Phase 4: Architecture Improvements (Major)
1. Decouple stores
2. Add memoization
3. Add SSE exponential backoff
4. Add lazy loading
5. Standardize component APIs

### Phase 5: Documentation (Critical)
1. Create `docs/frontend/ARCHITECTURE.md`
2. Create `docs/frontend/COMPONENTS.md`
3. Create `docs/frontend/DESIGN_SYSTEM.md`
4. Create `docs/frontend/AGENT_GUIDE.md`
5. Update `HANDOFF.md` with new state

---

## File Structure (Target)

```
apps/vibe/src/
├── styles/
│   ├── tokens.css          # Design tokens (expanded)
│   ├── global.css          # Base styles with @layer
│   ├── components.css      # Component styles (expanded)
│   └── app.css             # App shell layout
├── lib/
│   ├── api.ts              # API client (improved)
│   ├── sse.ts              # SSE client (with backoff)
│   ├── theme.ts            # Theme management
│   ├── format.ts           # Formatting utilities
│   ├── markdown.tsx        # Markdown renderer
│   └── logger.ts           # Structured logging (NEW)
├── hooks/
│   ├── useKeyboardShortcut.ts
│   ├── usePolling.ts       # NEW
│   └── useMediaQuery.ts    # NEW
├── components/
│   ├── ui/
│   │   ├── Button.tsx
│   │   ├── IconButton.tsx
│   │   ├── Modal.tsx       # With focus trap
│   │   ├── ConfirmDialog.tsx
│   │   ├── Spinner.tsx
│   │   ├── EmptyState.tsx
│   │   ├── ErrorBanner.tsx
│   │   ├── Tooltip.tsx
│   │   ├── Toast.tsx       # NEW
│   │   ├── Loading.tsx     # NEW
│   │   └── ErrorBoundary.tsx # NEW
│   └── layout/
│       ├── AppShell.tsx    # NEW
│       ├── Header.tsx      # NEW
│       └── Sidebar.tsx     # NEW
├── features/
│   ├── chat/
│   │   ├── ChatPanel.tsx
│   │   ├── MessageList.tsx
│   │   ├── Composer.tsx
│   │   ├── ApprovalCard.tsx
│   │   ├── ModelPicker.tsx
│   │   ├── UsageBadge.tsx
│   │   ├── store.ts
│   │   └── chat.css
│   ├── sessions/
│   │   ├── SessionsPanel.tsx
│   │   ├── store.ts
│   │   └── sessions.css
│   ├── code/
│   │   ├── CodePanel.tsx
│   │   ├── store.ts
│   │   └── code.css
│   ├── preview/
│   │   ├── PreviewPanel.tsx
│   │   ├── store.ts
│   │   └── preview.css
│   └── settings/
│       ├── SettingsPanel.tsx
│       ├── store.ts
│       └── settings.css
├── App.tsx
├── main.tsx
└── vite-env.d.ts
```

---

## Validation Strategy

1. **Type checking**: `pnpm typecheck` must pass
2. **Unit tests**: `pnpm test --run` must pass (53+ tests)
3. **Build**: `pnpm build` must succeed
4. **Accessibility**: axe-core 0 violations (desktop + mobile)
5. **Visual**: Screenshot comparison (desktop + mobile)
6. **Manual**: Browser testing of all interactions

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking existing functionality | Medium | High | TDD — write tests first |
| Scope creep | High | Medium | Strict phase boundaries |
| Performance regression | Low | Medium | Benchmark before/after |
| Accessibility regression | Low | High | axe-core in CI |

---

## Success Criteria

- [ ] Zero hardcoded colors/spacing/typography in components
- [ ] All components use CSS variables
- [ ] All interactive elements keyboard accessible
- [ ] All forms have visible labels
- [ ] All async operations have loading states
- [ ] All errors are handled gracefully
- [ ] All panels have error boundaries
- [ ] Documentation complete for future agents
- [ ] All tests pass
- [ ] Build succeeds
- [ ] Accessibility audit passes
