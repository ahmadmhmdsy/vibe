# Component Library — vibe IDE

## Overview

The vibe IDE uses a component-based architecture with reusable UI primitives. This document describes each component's API, usage, and customization.

## UI Primitives

### Button

A versatile button component with variants and loading state.

```tsx
import { Button } from "./components/ui/Button";

<Button
  variant="primary"    // "primary" | "secondary" | "ghost" | "danger"
  size="md"           // "sm" | "md"
  loading={false}     // Shows spinner and disables
  disabled={false}
  onClick={handleClick}
>
  Send
</Button>
```

**Props:**
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| variant | "primary" | "secondary" | "ghost" | "danger" | "secondary" | Visual style |
| size | "sm" | "md" | "md" | Button size |
| loading | boolean | false | Shows loading spinner |
| disabled | boolean | false | Disables button |

**CSS Classes:**
- `.btn` — Base button styles
- `.btn-primary` — Primary variant
- `.btn-secondary` — Secondary variant
- `.btn-ghost` — Ghost variant
- `.btn-danger` — Danger variant
- `.btn-sm` — Small size
- `.btn-md` — Medium size

---

### IconButton

An icon-only button with tooltip and 44px touch target.

```tsx
import { IconButton } from "./components/ui/IconButton";

<IconButton
  label="Settings"    // Required: accessible name
  onClick={handleClick}
>
  <svg>...</svg>
</IconButton>
```

**Props:**
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| label | string | — | Required: accessible name |
| children | ReactNode | — | Icon content |

**CSS Classes:**
- `.icon-btn` — Base icon button styles
- `.tooltip-wrap` — Tooltip wrapper
- `.tooltip` — Tooltip content

---

### Modal

An accessible modal dialog with focus trap.

```tsx
import { Modal } from "./components/ui/Modal";

<Modal
  open={isOpen}
  onClose={handleClose}
  title="Settings"
  wide={false}        // Optional: wider modal
  role="dialog"       // "dialog" | "alertdialog"
>
  <p>Modal content</p>
</Modal>
```

**Props:**
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| open | boolean | — | Whether modal is visible |
| onClose | () => void | — | Close handler |
| title | string | — | Modal title |
| wide | boolean | false | Wider modal (640px) |
| role | "dialog" | "alertdialog" | "dialog" | ARIA role |

**Features:**
- Focus trap (Tab cycles within modal)
- Focus restore on close
- Escape to close
- Backdrop click to close

**CSS Classes:**
- `.modal-backdrop` — Backdrop overlay
- `.modal-panel` — Modal container
- `.modal-wide` — Wide variant
- `.modal-header` — Header with title and close
- `.modal-body` — Content area

---

### ConfirmDialog

A confirmation dialog for destructive actions.

```tsx
import { ConfirmDialog } from "./components/ui/ConfirmDialog";

<ConfirmDialog
  open={isOpen}
  onClose={handleCancel}
  onConfirm={handleConfirm}
  title="Delete session?"
  body="This permanently removes the session and its history."
  confirmLabel="Delete"
  cancelLabel="Cancel"
/>
```

**Props:**
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| open | boolean | — | Whether dialog is visible |
| onClose | () => void | — | Cancel handler |
| onConfirm | () => void | — | Confirm handler |
| title | string | — | Dialog title |
| body | string | — | Dialog body |
| confirmLabel | string | "Confirm" | Confirm button text |
| cancelLabel | string | "Cancel" | Cancel button text |

**Features:**
- Enter and Escape both cancel (safe choice for destructive actions)
- Auto-focus on cancel button

---

### Spinner

An animated loading spinner.

```tsx
import { Spinner } from "./components/ui/Spinner";

<Spinner
  size="md"           // "sm" | "md" | "lg"
  label="Loading"     // Accessible label
/>
```

**Props:**
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| size | "sm" | "md" | "lg" | "md" | Spinner size |
| label | string | "Loading" | Accessible label |

**CSS Classes:**
- `.spinner` — Spinner element

---

### EmptyState

A placeholder for empty data.

```tsx
import { EmptyState } from "./components/ui/EmptyState";

<EmptyState
  icon={<svg>...</svg>}           // Optional icon
  title="No files yet"
  body="The agent has not written any files for this session."
  action={<Button>Create file</Button>}  // Optional CTA
  headingLevel="h2"              // "h1" | "h2" | "h3" | "h4"
/>
```

**Props:**
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| icon | ReactNode | — | Optional icon |
| title | string | — | Title text |
| body | string | — | Description text |
| action | ReactNode | — | Optional CTA |
| headingLevel | "h1" | "h2" | "h3" | "h4" | "h2" | Heading level |

**CSS Classes:**
- `.empty-state` — Container
- `.empty-state-icon` — Icon wrapper
- `.empty-state-action` — CTA wrapper

---

### ErrorBanner

An error message banner with optional retry.

```tsx
import { ErrorBanner } from "./components/ui/ErrorBanner";

<ErrorBanner
  message="API error: 400"
  onRetry={handleRetry}    // Optional retry button
/>
```

**Props:**
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| message | string | — | Error message |
| onRetry | () => void | — | Optional retry handler |

**CSS Classes:**
- `.error-banner` — Banner container
- `.error-banner-message` — Message text

---

### Tooltip

A hover/focus tooltip.

```tsx
import { Tooltip } from "./components/ui/Tooltip";

<Tooltip label="Settings">
  <button>...</button>
</Tooltip>
```

**Props:**
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| label | string | — | Tooltip text |
| children | ReactNode | — | Wrapped element |

**CSS Classes:**
- `.tooltip-wrap` — Wrapper
- `.tooltip` — Tooltip content

---

### Toast

A transient notification.

```tsx
import { useToast } from "./components/ui/Toast";

function MyComponent() {
  const { toast } = useToast();

  const handleClick = () => {
    toast("Session created", "success");
  };

  return <button onClick={handleClick}>Create</button>;
}
```

**API:**
| Method | Description |
|--------|-------------|
| toast(message, variant?) | Show a toast notification |

**Variants:** "success" | "error" | "info" | "warning"

**CSS Classes:**
- `.toast-container` — Container
- `.toast` — Toast item
- `.toast-success` — Success variant
- `.toast-error` — Error variant
- `.toast-warning` — Warning variant
- `.toast-info` — Info variant

---

### Loading

A loading indicator.

```tsx
import { Loading } from "./components/ui/Loading";

<Loading
  label="Loading messages"
  size="md"           // "sm" | "md" | "lg"
  overlay={false}     // Full-screen overlay
/>
```

**Props:**
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| label | string | "Loading" | Loading message |
| size | "sm" | "md" | "lg" | "md" | Spinner size |
| overlay | boolean | false | Full-screen overlay |

**CSS Classes:**
- `.loading` — Loading container
- `.loading-text` — Loading text
- `.loading-overlay` — Overlay variant

---

### ErrorBoundary

An error boundary for panel-level isolation.

```tsx
import { ErrorBoundary } from "./components/ui/ErrorBoundary";

<ErrorBoundary>
  <ChatPanel sessionId={activeId} />
</ErrorBoundary>
```

**Props:**
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| children | ReactNode | — | Wrapped content |
| fallback | ReactNode | — | Custom fallback UI |
| resetKey | string | — | Reset error state on change |

**CSS Classes:**
- `.error-boundary` — Error container

---

### ShortcutsHelp

A keyboard shortcuts help modal.

```tsx
import { ShortcutsHelp } from "./components/ui/ShortcutsHelp";

<ShortcutsHelp
  open={isOpen}
  onClose={handleClose}
/>
```

**Props:**
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| open | boolean | — | Whether modal is visible |
| onClose | () => void | — | Close handler |

**CSS Classes:**
- `.shortcuts-list` — List container
- `.shortcut-row` — Shortcut row
- `.shortcut-keys` — Keys container
- `.shortcut-key` — Individual key
- `.shortcut-description` — Description

---

### CommandPalette

A command palette for quick actions.

```tsx
import { CommandPalette } from "./components/ui/CommandPalette";

<CommandPalette
  open={isOpen}
  onClose={handleClose}
  commands={[
    {
      id: "new-session",
      title: "New session",
      description: "Create a new chat session",
      action: () => create(),
      shortcut: ["Cmd", "N"],
    },
  ]}
/>
```

**Props:**
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| open | boolean | — | Whether palette is visible |
| onClose | () => void | — | Close handler |
| commands | Command[] | — | Available commands |

**Command Interface:**
```typescript
interface Command {
  id: string;
  title: string;
  description?: string;
  action: () => void;
  shortcut?: string[];
}
```

**CSS Classes:**
- `.command-palette` — Container
- `.command-palette-input` — Search input
- `.command-palette-list` — Command list
- `.command-item` — Command item
- `.command-item-active` — Selected item
- `.command-item-title` — Command title
- `.command-item-description` — Command description
- `.command-item-shortcut` — Keyboard shortcut

---

## Feature Components

### ChatPanel

Main chat panel container.

```tsx
import { ChatPanel } from "./features/chat/ChatPanel";

<ChatPanel sessionId="session-id" />
```

**Props:**
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| sessionId | string | — | Active session ID |

---

### MessageList

Chat message list with streaming.

```tsx
import { MessageList } from "./features/chat/MessageList";

<MessageList sessionId="session-id" />
```

**Props:**
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| sessionId | string | — | Active session ID |

---

### Composer

Message input with image attachment.

```tsx
import { Composer } from "./features/chat/Composer";

<Composer sessionId="session-id" />
```

**Props:**
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| sessionId | string | — | Active session ID |

**Features:**
- Text input with character count
- Image attachment (click or drag-and-drop)
- Send/Stop button
- Error handling with message preservation

---

### ApprovalCard

Package approval card.

```tsx
import { ApprovalCard } from "./features/chat/ApprovalCard";

<ApprovalCard
  approval={approval}
  onApprove={handleApprove}
  onDeny={handleDeny}
/>
```

**Props:**
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| approval | Approval | — | Approval data |
| onApprove | () => void | — | Approve handler |
| onDeny | () => void | — | Deny handler |

---

### ModelPicker

Model selection dropdown.

```tsx
import { ModelPicker } from "./features/chat/ModelPicker";

<ModelPicker sessionId="session-id" />
```

**Props:**
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| sessionId | string | null | — | Active session ID |

---

### UsageBadge

Usage statistics badge.

```tsx
import { UsageBadge } from "./features/chat/UsageBadge";

<UsageBadge sessionId="session-id" />
```

**Props:**
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| sessionId | string | — | Active session ID |

---

### SessionsPanel

Session management sidebar.

```tsx
import { SessionsPanel } from "./features/sessions/SessionsPanel";

<SessionsPanel />
```

**Features:**
- Session list with search
- Create/Rename/Delete sessions
- Export/Import sessions
- Model badge display

---

### CodePanel

Code editor panel.

```tsx
import { CodePanel } from "./features/code/CodePanel";

<CodePanel sessionId="session-id" />
```

**Props:**
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| sessionId | string | — | Active session ID |

**Features:**
- File tree with selection
- Monaco editor integration
- Auto-save with debounce
- Save status indicator

---

### PreviewPanel

Live preview panel.

```tsx
import { PreviewPanel } from "./features/preview/PreviewPanel";

<PreviewPanel sessionId="session-id" />
```

**Props:**
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| sessionId | string | — | Active session ID |

**Features:**
- Run/Stop dev server
- Live iframe preview
- Error handling

---

### SettingsPanel

Settings modal content.

```tsx
import { SettingsPanel } from "./features/settings/SettingsPanel";

<SettingsPanel />
```

**Features:**
- Built-in provider list
- Custom provider CRUD
- API key management

---

## Creating a New Component

### Step 1: Create the Component File

```tsx
// components/ui/MyComponent.tsx
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

### Step 2: Add Styles

```css
/* components.css */
@layer components {
  .my-component {
    /* Use CSS variables */
    padding: var(--space-4);
    background: var(--bg-raised);
    border-radius: var(--radius-md);
  }
}
```

### Step 3: Add Tests

```tsx
// components/ui/__tests__/MyComponent.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MyComponent } from "../MyComponent";

describe("MyComponent", () => {
  it("renders correctly", () => {
    render(<MyComponent />);
    expect(screen.getByRole("...")).toBeInTheDocument();
  });
});
```

### Step 4: Export (if needed)

```tsx
// components/ui/index.ts
export { MyComponent } from "./MyComponent";
```

---

## Best Practices

1. **Always use CSS variables** — never hardcode colors, spacing, or typography
2. **Use React.memo** for pure components
3. **Handle loading and error states** — every async operation needs both
4. **Use TypeScript** — define prop interfaces
5. **Write tests** — every component should have tests
6. **Follow naming conventions** — BEM-like for CSS, PascalCase for components
7. **Document props** — use JSDoc comments for complex props
