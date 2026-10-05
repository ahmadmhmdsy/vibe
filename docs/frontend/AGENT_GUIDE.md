# Agent Guide — vibe IDE Frontend

## Purpose

This guide helps AI agents understand the vibe IDE frontend architecture, conventions, and patterns so they can make consistent, maintainable changes.

## Quick Start

### Understanding the Codebase

1. **Read the architecture doc**: `docs/frontend/ARCHITECTURE.md`
2. **Read the components doc**: `docs/frontend/COMPONENTS.md`
3. **Read the design system doc**: `docs/frontend/DESIGN_SYSTEM.md`
4. **Read this guide**: `docs/frontend/AGENT_GUIDE.md`

### Making Changes

1. **Identify the feature**: Which feature does this change belong to?
2. **Check existing patterns**: How are similar changes implemented?
3. **Follow conventions**: Use the same patterns, naming, and structure
4. **Write tests**: Every change should have tests
5. **Update docs**: If you change behavior, update the docs

## File Organization

### Where to Put New Code

| Type of Code | Location |
|-------------|----------|
| UI primitive | `components/ui/<Name>.tsx` |
| Feature component | `features/<name>/<Name>.tsx` |
| Feature store | `features/<name>/store.ts` |
| Feature styles | `features/<name>/<name>.css` |
| Shared utility | `lib/<name>.ts` |
| Shared hook | `hooks/<name>.ts` |
| Global styles | `styles/<name>.css` |
| Tests | `<feature>/__tests__/<Name>.test.tsx` |

### Naming Conventions

| Type | Convention | Example |
|------|-----------|---------|
| Component file | PascalCase | `Button.tsx` |
| Store file | camelCase + store | `chatStore.ts` |
| CSS file | kebab-case | `chat.css` |
| Test file | Component + .test | `Button.test.tsx` |
| Hook file | use + PascalCase | `usePolling.ts` |

## Common Tasks

### Adding a New UI Primitive

1. Create `components/ui/<Name>.tsx`:

```tsx
import { memo } from "react";

interface MyComponentProps {
  // Define props
}

export const MyComponent = memo(function MyComponent({}: MyComponentProps) {
  return (
    <div className="my-component">
      {/* Component content */}
    </div>
  );
});
```

2. Add styles to `components.css`:

```css
@layer components {
  .my-component {
    padding: var(--space-4);
    background: var(--bg-raised);
    border-radius: var(--radius-md);
  }
}
```

3. Add tests to `components/ui/__tests__/<Name>.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MyComponent } from "../MyComponent";

describe("MyComponent", () => {
  it("renders correctly", () => {
    render(<MyComponent />);
    expect(screen.getByRole("...")).toBeInTheDocument();
  });
});
```

### Adding a New Feature

1. Create `features/<name>/` directory
2. Add `store.ts` for state management
3. Add components (`.tsx`)
4. Add styles (`.css`)
5. Add tests (`__tests__/`)
6. Import in `App.tsx`

### Adding a New API Endpoint

1. Add method to `lib/api.ts`:

```typescript
export const api = {
  // ... existing methods
  myNewMethod: (param: string) =>
    req<MyResponse>(`/my-endpoint/${param}`, { method: "GET" }),
};
```

2. Define TypeScript interface for response:

```typescript
export interface MyResponse {
  id: string;
  name: string;
}
```

3. Use in feature store or component:

```typescript
const data = await api.myNewMethod(param);
```

### Adding a New Hook

1. Create `hooks/<name>.ts`:

```typescript
import { useState, useEffect } from "react";

export function useMyHook() {
  const [state, setState] = useState();

  useEffect(() => {
    // Hook logic
  }, []);

  return state;
}
```

2. Use in component:

```tsx
import { useMyHook } from "../../hooks/useMyHook";

const value = useMyHook();
```

## State Management

### Zustand Store Pattern

```typescript
// features/chat/store.ts
import { create } from "zustand";

interface ChatState {
  // State
  messagesBySession: Record<string, ChatMessage[]>;
  isStreamingBySession: Record<string, boolean>;

  // Actions
  addMessage: (sid: string, m: ChatMessage) => void;
  appendChunk: (sid: string, text: string) => void;
  setStreaming: (sid: string, v: boolean) => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  // Initial state
  messagesBySession: {},
  isStreamingBySession: {},

  // Actions
  addMessage: (sid, m) =>
    set((s) => ({
      messagesBySession: {
        ...s.messagesBySession,
        [sid]: [...(s.messagesBySession[sid] ?? []), m],
      },
    })),

  appendChunk: (sid, text) =>
    set((s) => {
      const msgs = [...(s.messagesBySession[sid] ?? [])];
      const last = msgs[msgs.length - 1];
      if (last?.role === "assistant") {
        msgs[msgs.length - 1] = { ...last, content: last.content + text };
      } else {
        msgs.push({ role: "assistant", content: text });
      }
      return { messagesBySession: { ...s.messagesBySession, [sid]: msgs } };
    }),

  setStreaming: (sid, v) =>
    set((s) => ({
      isStreamingBySession: { ...s.isStreamingBySession, [sid]: v },
    })),
}));
```

### Using Stores in Components

```tsx
import { useChatStore } from "./store";
import { useShallow } from "zustand/react/shallow";

// For primitives
const isStreaming = useChatStore((s) => s.isStreamingBySession[sessionId] ?? false);

// For arrays/objects
const messages = useChatStore(useShallow((s) => s.messagesBySession[sessionId] ?? []));

// For actions
const addMessage = useChatStore((s) => s.addMessage);
```

## Styling

### Using CSS Variables

Always use CSS variables, never hardcode values:

```css
/* Good */
.my-component {
  padding: var(--space-4);
  background: var(--bg-raised);
  color: var(--text);
  border-radius: var(--radius-md);
}

/* Bad */
.my-component {
  padding: 16px;
  background: #161b22;
  color: #e6edf3;
  border-radius: 8px;
}
```

### Adding New Styles

1. Add to appropriate CSS file:
   - UI primitives → `components.css`
   - Feature-specific → `features/<name>/<name>.css`
   - App shell → `app.css`

2. Use @layer components:

```css
@layer components {
  .my-component {
    /* Styles */
  }
}
```

### Responsive Styles

Use media queries in `app.css`:

```css
@media (max-width: 1100px) {
  .app-side {
    position: fixed;
    /* Tablet styles */
  }
}

@media (max-width: 768px) {
  .app-sidebar {
    position: fixed;
    /* Mobile styles */
  }
}
```

## Testing

### Writing Tests

```tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { MyComponent } from "../MyComponent";

// Mock dependencies
vi.mock("../../lib/api", () => ({
  api: {
    myMethod: vi.fn().mockResolvedValue({ data: "test" }),
  },
}));

afterEach(cleanup);

describe("MyComponent", () => {
  it("renders correctly", () => {
    render(<MyComponent />);
    expect(screen.getByRole("...")).toBeInTheDocument();
  });

  it("handles click", () => {
    const onClick = vi.fn();
    render(<MyComponent onClick={onClick} />);
    fireEvent.click(screen.getByRole("button"));
    expect(onClick).toHaveBeenCalled();
  });
});
```

### Running Tests

```bash
cd apps/vibe
pnpm test --run
```

## Common Patterns

### Error Handling

```typescript
try {
  await api.someMethod();
} catch (e) {
  if (e instanceof ApiError) {
    setError(`API error: ${e.status}`);
  } else {
    setError("An unexpected error occurred");
  }
}
```

### Loading States

```tsx
const [loading, setLoading] = useState(true);

useEffect(() => {
  api.getData()
    .then(setData)
    .catch(setError)
    .finally(() => setLoading(false));
}, []);

if (loading) return <Loading label="Loading data" />;
if (error) return <ErrorBanner message={error} />;
return <div>{data}</div>;
```

### Empty States

```tsx
if (data.length === 0) {
  return (
    <EmptyState
      title="No data"
      body="There is no data to display."
      action={<Button>Create</Button>}
    />
  );
}
```

### Polling

```tsx
import { usePolling } from "../../hooks/usePolling";

usePolling(
  async () => {
    const data = await api.getData();
    setData(data);
  },
  { interval: 5000, enabled: true }
);
```

### SSE Connection

```tsx
import { SSEClient } from "../../lib/sse";

useEffect(() => {
  const sse = new SSEClient(import.meta.env.VITE_API_URL ?? "http://localhost:7321");
  sse.connect(sessionId, (e) => {
    if (e.type === "text_chunk") appendChunk(sessionId, e.payload.text);
    if (e.type === "turn_complete") setStreaming(sessionId, false);
  });
  return () => sse.disconnect();
}, [sessionId]);
```

## Troubleshooting

### Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Styles not applying | CSS layer order | Check @layer order in global.css |
| State not updating | Zustand selector | Use useShallow for arrays/objects |
| Memory leaks | Missing cleanup | Check useEffect cleanup functions |
| Polling not stopping | Missing cleanup | Use usePolling hook |
| SSE not reconnecting | Max attempts reached | Check network, increase max attempts |
| Tests failing | Mock not set up | Check vi.mock calls |

### Debugging Tips

1. **Check the browser console** for errors
2. **Use React DevTools** to inspect component state
3. **Add console.log** temporarily to trace execution
4. **Check network tab** for API calls
5. **Run tests** to verify behavior

## Code Review Checklist

Before submitting changes:

- [ ] All tests pass (`pnpm test --run`)
- [ ] Type checking passes (`pnpm typecheck`)
- [ ] Build succeeds (`pnpm build`)
- [ ] No hardcoded colors/spacing/typography
- [ ] All async operations have loading and error states
- [ ] All interactive elements are keyboard accessible
- [ ] All forms have visible labels
- [ ] Documentation is updated
- [ ] No console.log statements left in code
- [ ] No TODO comments without issue references

## Getting Help

- **Architecture questions**: See `docs/frontend/ARCHITECTURE.md`
- **Component questions**: See `docs/frontend/COMPONENTS.md`
- **Design system questions**: See `docs/frontend/DESIGN_SYSTEM.md`
- **This guide**: `docs/frontend/AGENT_GUIDE.md`
