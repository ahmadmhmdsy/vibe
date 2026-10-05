# Frontend Architecture — vibe IDE

## Overview

The vibe IDE frontend is a React 19 + TypeScript single-page application built with Vite. It provides a 3-column IDE interface for interacting with an AI coding agent.

## Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Framework | React | 19.0.0 |
| Language | TypeScript | 5.6.0 |
| Build | Vite | 6.0.0 |
| State | Zustand | 5.0.0 |
| Editor | Monaco | 4.6.0 |
| Markdown | react-markdown | 10.1.0 |
| Test | Vitest | 2.1.0 |

## Directory Structure

```
apps/vibe/src/
├── styles/              # Global styles and design tokens
│   ├── tokens.css       # Design tokens (colors, spacing, typography)
│   ├── global.css       # Base element styles with @layer
│   ├── components.css   # UI primitive styles
│   └── app.css          # App shell layout + responsive
├── lib/                 # Shared utilities
│   ├── api.ts           # API client with error handling
│   ├── sse.ts           # SSE client with exponential backoff
│   ├── theme.ts         # Theme management (dark/light)
│   ├── format.ts        # Formatting utilities
│   ├── markdown.tsx     # Markdown renderer
│   └── logger.ts        # Structured logging
├── hooks/               # Shared React hooks
│   ├── useKeyboardShortcut.ts
│   ├── usePolling.ts    # Coordinated polling with cleanup
│   └── useMediaQuery.ts # Responsive breakpoint detection
├── components/
│   ├── ui/              # Reusable UI primitives
│   │   ├── Button.tsx
│   │   ├── IconButton.tsx
│   │   ├── Modal.tsx    # With focus trap
│   │   ├── ConfirmDialog.tsx
│   │   ├── Spinner.tsx
│   │   ├── EmptyState.tsx
│   │   ├── ErrorBanner.tsx
│   │   ├── Tooltip.tsx
│   │   ├── Toast.tsx    # Notification system
│   │   ├── Loading.tsx
│   │   ├── ErrorBoundary.tsx
│   │   ├── ShortcutsHelp.tsx
│   │   └── CommandPalette.tsx
│   └── layout/          # Layout components (future)
├── features/            # Feature modules
│   ├── chat/            # Chat panel (messages, composer, approvals)
│   ├── sessions/        # Session management sidebar
│   ├── code/            # Code editor panel
│   ├── preview/         # Live preview panel
│   └── settings/        # Settings modal
├── App.tsx              # Application shell
├── main.tsx             # Entry point
└── vite-env.d.ts        # Vite environment types
```

## Architecture Patterns

### 1. Feature-Based Organization

Each feature is a self-contained module with its own:
- Components (.tsx)
- Store (store.ts)
- Styles (*.css)
- Tests (__tests__/)

```
features/chat/
├── ChatPanel.tsx       # Main panel component
├── MessageList.tsx     # Message display
├── Composer.tsx        # Input area
├── ApprovalCard.tsx    # Approval flow
├── ModelPicker.tsx     # Model selection
├── UsageBadge.tsx      # Usage stats
├── store.ts            # Zustand store
├── chat.css            # Feature styles
└── __tests__/          # Feature tests
```

### 2. State Management (Zustand)

Each feature has its own Zustand store. Stores are decoupled — no circular dependencies.

```typescript
// features/chat/store.ts
import { create } from "zustand";

interface ChatState {
  messagesBySession: Record<string, ChatMessage[]>;
  isStreamingBySession: Record<string, boolean>;
  // ... actions
}

export const useChatStore = create<ChatState>((set, get) => ({
  // State and actions
}));
```

**Key principles:**
- Select primitives or use useShallow for arrays/objects
- No store imports another store (decoupled)
- Async actions handle errors internally

### 3. API Client

Centralized API client with consistent error handling:

```typescript
// lib/api.ts
export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = "ApiError";
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!resp.ok) throw new ApiError(`API error: ${resp.status}`, resp.status);
  return resp.json() as Promise<T>;
}

export const api = {
  // Typed API methods
};
```

### 4. SSE Client

Server-Sent Events with exponential backoff:

```typescript
// lib/sse.ts
export class SSEClient {
  lastSeq = 0;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private baseReconnectDelay = 1000;

  connect(sessionId: string, onEvent: (e: StreamEvent) => void): void;
  disconnect(): void;
}
```

**Reconnection strategy:**
- Attempt 1: 1s delay
- Attempt 2: 2s delay
- Attempt 3: 4s delay
- Attempt 4: 8s delay
- Attempt 5: 16s delay
- After 5 attempts: stop reconnecting

### 5. Polling Hook

Coordinated polling with automatic cleanup:

```typescript
// hooks/usePolling.ts
usePolling(
  async () => { /* poll logic */ },
  { interval: 5000, enabled: true, maxRetries: 3 }
);
```

**Features:**
- Automatic cleanup on unmount
- Exponential backoff on errors
- Max retry limit
- Enable/disable control

### 6. Component Patterns

#### UI Primitives

All UI primitives follow this API:

```typescript
interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md";
  loading?: boolean;
}
```

#### Error Handling

```typescript
// Wrap panels with ErrorBoundary
<ErrorBoundary>
  <ChatPanel sessionId={activeId} />
</ErrorBoundary>
```

#### Loading States

```typescript
// Use Loading component for async operations
<Loading label="Loading messages" />
```

#### Empty States

```typescript
// Use EmptyState for empty data
<EmptyState
  title="No messages yet"
  body="Start a conversation with the agent."
  action={<Button>Send message</Button>}
/>
```

## CSS Architecture

### Layer System

```css
@layer reset { /* Reset styles */ }
@layer base { /* Element styles */ }
@layer components { /* Component styles */ }
@layer utilities { /* Utility classes */ }
```

### Design Tokens

All values come from CSS custom properties:

```css
:root {
  --bg: #0d1117;
  --text: #e6edf3;
  --accent: #8b9cf9;
  --space-4: 16px;
  --radius-md: 8px;
  --duration: 200ms;
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
}
```

### Naming Convention

- **Blocks**: .button, .modal, .composer
- **Elements**: .button__icon, .modal__header
- **Modifiers**: .button--primary, .modal--wide
- **Utilities**: .sr-only, .muted, .flex

## Responsive Design

### Breakpoints

| Breakpoint | Width | Layout |
|-----------|-------|--------|
| Desktop | > 1100px | 3-column (sidebar + chat + side) |
| Tablet | 768-1100px | 2-column (chat + side overlay) |
| Mobile | < 768px | 1-column + tab bar |

### Mobile Navigation

- Sessions sidebar becomes a drawer
- Side panel becomes an overlay
- Bottom tab bar for panel switching

## Performance

### Optimizations

1. **Lazy loading**: Heavy panels (Preview, Code) are lazy loaded
2. **Memoization**: Pure components use React.memo
3. **Polling coordination**: Single hook manages all polling
4. **SSE reconnection**: Exponential backoff prevents thundering herd

### Bundle Size

- Monaco editor is the largest dependency (~3MB)
- Consider code-splitting for production

## Testing

### Test Structure

```
src/
├── __tests__/           # App-level tests
├── components/ui/__tests__/  # UI primitive tests
└── features/*/__tests__/     # Feature tests
```

### Running Tests

```bash
cd apps/vibe
pnpm test --run
```

### Test Coverage

- 55 tests across 12 test files
- All UI primitives tested
- All features tested
- Library utilities tested

## Common Patterns

### Adding a New Feature

1. Create features/<name>/ directory
2. Add store.ts for state management
3. Add components (.tsx)
4. Add styles (.css)
5. Add tests (__tests__/)
6. Import in App.tsx

### Adding a New UI Primitive

1. Create components/ui/<Name>.tsx
2. Add styles to components.css
3. Add tests to components/ui/__tests__/
4. Export from components/ui/index.ts (if needed)

### Adding a New API Endpoint

1. Add method to lib/api.ts
2. Define TypeScript interface for response
3. Use in feature store or component

## Troubleshooting

### Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Styles not applying | CSS layer order | Check @layer order |
| State not updating | Zustand selector | Use useShallow for arrays |
| Memory leaks | Missing cleanup | Check useEffect cleanup |
| Polling not stopping | Missing cleanup | Use usePolling hook |
| SSE not reconnecting | Max attempts reached | Check network, increase max |

## Future Improvements

- [ ] Add ESLint configuration
- [ ] Add Prettier configuration
- [ ] Add Storybook for component development
- [ ] Add E2E tests with Playwright
- [ ] Add PWA support
- [ ] Add offline support
- [ ] Add i18n support
- [ ] Add analytics
