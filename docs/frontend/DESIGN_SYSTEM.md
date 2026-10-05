# Design System — vibe IDE

## Overview

The vibe IDE design system is built on CSS custom properties (variables) that provide a consistent, themeable foundation for all components. The system is dark-first with a light theme override.

## Design Tokens

### Color Tokens

#### Surfaces

| Token | Dark | Light | Usage |
|-------|------|-------|-------|
| --bg | #0d1117 | #f6f8fa | App background |
| --bg-raised | #161b22 | #ffffff | Elevated surfaces (cards, modals) |
| --bg-hover | #1c2129 | #eef1f4 | Hover state |
| --bg-active | #252c36 | #e4e9ee | Active/pressed state |
| --bg-overlay | rgba(0,0,0,0.55) | rgba(0,0,0,0.3) | Modal backdrop |

#### Borders

| Token | Dark | Light | Usage |
|-------|------|-------|-------|
| --border | #30363d | #d0d7de | Default border |
| --border-strong | #444c56 | #afb8c1 | Emphasized border |
| --border-focus | #8b9cf9 | #4f46e5 | Focus ring |

#### Text

| Token | Dark | Light | Usage |
|-------|------|-------|-------|
| --text | #e6edf3 | #1f2328 | Primary text |
| --text-muted | #9aa7b4 | #59636e | Secondary text |
| --text-faint | #6e7681 | #8c959f | Tertiary text |
| --text-on-accent | #ffffff | #ffffff | Text on accent background |

#### Accent

| Token | Dark | Light | Usage |
|-------|------|-------|-------|
| --accent | #8b9cf9 | #4f46e5 | Primary accent |
| --accent-hover | #a5b4fc | #4338ca | Accent hover |
| --accent-bg | #5b62e0 | #4f46e5 | Accent background |
| --accent-bg-hover | #6b72f0 | #4338ca | Accent bg hover |
| --accent-contrast | #ffffff | #ffffff | Text on accent |
| --accent-subtle | rgba(139,156,249,0.12) | rgba(79,70,229,0.08) | Subtle accent bg |

#### Semantic

| Token | Dark | Light | Usage |
|-------|------|-------|-------|
| --success | #3fb950 | #1a7f37 | Success state |
| --success-bg | rgba(63,185,80,0.12) | rgba(26,127,55,0.08) | Success bg |
| --success-border | rgba(63,185,80,0.4) | rgba(26,127,55,0.3) | Success border |
| --danger | #f85149 | #cf222e | Error state |
| --danger-bg | rgba(248,81,73,0.12) | rgba(207,34,46,0.08) | Error bg |
| --danger-border | rgba(248,81,73,0.4) | rgba(207,34,46,0.3) | Error border |
| --danger-strong | #b3261e | #b3261e | Destructive action |
| --warning | #d29922 | #9a6700 | Warning state |
| --warning-bg | rgba(210,153,34,0.12) | rgba(154,103,0,0.08) | Warning bg |
| --warning-border | rgba(210,153,34,0.4) | rgba(154,103,0,0.3) | Warning border |
| --info | #58a6ff | #0969da | Info state |
| --info-bg | rgba(88,166,255,0.12) | rgba(9,105,218,0.08) | Info bg |
| --info-border | rgba(88,166,255,0.4) | rgba(9,105,218,0.3) | Info border |

### Typography Tokens

#### Font Families

| Token | Value | Usage |
|-------|-------|-------|
| --font-ui | -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, ... | UI text |
| --font-mono | ui-monospace, "SF Mono", "Cascadia Code", Menlo, Consolas, ... | Code |

#### Type Scale (1.125 ratio — major second)

| Token | Size | Usage |
|-------|------|-------|
| --text-xs | 11px | Badges, labels |
| --text-sm | 13px | Secondary text, buttons |
| --text-base | 14px | Body text |
| --text-lg | 16px | Subheadings |
| --text-xl | 20px | Headings |
| --text-2xl | 24px | Large headings |
| --text-3xl | 28px | Display headings |

#### Line Heights

| Token | Value | Usage |
|-------|-------|-------|
| --line-height-tight | 1.25 | Headings |
| --line-height | 1.5 | Body text |
| --line-height-loose | 1.7 | Code blocks |

#### Font Weights

| Token | Value | Usage |
|-------|-------|-------|
| --font-weight-normal | 400 | Body text |
| --font-weight-medium | 500 | Emphasized text |
| --font-weight-semibold | 600 | Headings, buttons |
| --font-weight-bold | 700 | Strong emphasis |

### Spacing Tokens

4px base grid:

| Token | Value | Usage |
|-------|-------|-------|
| --space-0 | 0 | No spacing |
| --space-1 | 4px | Tight spacing |
| --space-2 | 8px | Small spacing |
| --space-3 | 12px | Medium spacing |
| --space-4 | 16px | Default spacing |
| --space-5 | 24px | Large spacing |
| --space-6 | 32px | Extra large spacing |
| --space-7 | 40px | Huge spacing |
| --space-8 | 48px | Massive spacing |
| --space-9 | 64px | Gigantic spacing |

### Shape Tokens

#### Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| --radius-sm | 4px | Small elements (badges, tags) |
| --radius-md | 8px | Default (buttons, inputs) |
| --radius-lg | 12px | Cards, modals |
| --radius-xl | 16px | Large containers |
| --radius-full | 9999px | Pills, circles |

#### Shadows

| Token | Value | Usage |
|-------|-------|-------|
| --shadow-1 | 0 1px 3px rgba(0,0,0,0.4) | Subtle elevation |
| --shadow-2 | 0 6px 20px rgba(0,0,0,0.5) | Cards, modals |
| --shadow-3 | 0 12px 40px rgba(0,0,0,0.6) | High elevation |
| --shadow-inner | inset 0 1px 2px rgba(0,0,0,0.2) | Inset shadow |

### Z-Index Scale

| Token | Value | Usage |
|-------|-------|-------|
| --z-base | 0 | Base layer |
| --z-dropdown | 10 | Dropdown menus |
| --z-sticky | 20 | Sticky elements |
| --z-fixed | 30 | Fixed elements |
| --z-drawer | 60 | Tablet/mobile slide-in panels |
| --z-header | 70 | App header (stays above drawers) |
| --z-modal-backdrop | 100 | Modal backdrop |
| --z-modal | 110 | Modal content |
| --z-toast | 200 | Toast notifications |
| --z-tooltip | 300 | Tooltips |

### Motion Tokens

#### Durations

| Token | Value | Usage |
|-------|-------|-------|
| --duration-instant | 80ms | Instant feedback |
| --duration-fast | 120ms | Fast transitions |
| --duration | 200ms | Default transitions |
| --duration-slow | 300ms | Slow transitions |
| --duration-slower | 500ms | Very slow transitions |
| --spin-duration | 640ms | Spinner rotation (kept under reduced-motion) |

#### Easing Functions

| Token | Value | Usage |
|-------|-------|-------|
| --ease-out | cubic-bezier(0.16, 1, 0.3, 1) | Exit animations |
| --ease-in | cubic-bezier(0.7, 0, 0.84, 0) | Enter animations |
| --ease-in-out | cubic-bezier(0.65, 0, 0.35, 1) | Bidirectional |

### Layout Tokens

| Token | Value | Usage |
|-------|-------|-------|
| --header-height | 48px | App header height |
| --sidebar-width | 260px | Sessions sidebar width |
| --side-width | 42% | Side panel width |
| --side-min-width | 320px | Side panel min width |
| --mobile-tab-height | 48px | Mobile tab bar height |

### Focus Ring

| Token | Value | Usage |
|-------|-------|-------|
| --focus-ring | 0 0 0 3px color-mix(in srgb, var(--accent) 25%, transparent) | Focus indicator |
| --focus-ring-offset | 2px | Focus ring offset |

### Scrollbar

| Token | Value | Usage |
|-------|-------|-------|
| --scrollbar-width | 10px | Scrollbar width |
| --scrollbar-thumb | var(--border-strong) | Scrollbar thumb |
| --scrollbar-track | transparent | Scrollbar track |

## CSS Layer System

The design system uses CSS @layer to manage specificity:

```css
@layer reset { /* Reset styles */ }
@layer base { /* Element styles */ }
@layer components { /* Component styles */ }
@layer utilities { /* Utility classes */ }
```

**Benefits:**
- Predictable cascade
- No specificity wars
- Easy to override

**Order rule:** the `@layer reset, base, components, utilities;` statement
must be the first thing in `global.css`, before any `@import`. Layer order
is decided by first appearance, so importing a component sheet before the
statement inverts the whole cascade and lets base element rules win.

## Naming Convention

### CSS Classes

- **Blocks**: .button, .modal, .composer
- **Elements**: .button__icon, .modal__header
- **Modifiers**: .button--primary, .modal--wide
- **Utilities**: .sr-only, .muted, .flex

### TypeScript

- **Components**: PascalCase (Button, Modal)
- **Props**: camelCase (variant, size)
- **Hooks**: use prefix (usePolling, useMediaQuery)
- **Stores**: use prefix + Store (useChatStore)

## Theme System

### Dark Theme (Default)

```css
:root {
  --bg: #0d1117;
  --text: #e6edf3;
  --accent: #8b9cf9;
}
```

### Light Theme

```css
[data-theme="light"] {
  --bg: #f6f8fa;
  --text: #1f2328;
  --accent: #4f46e5;
}
```

### Theme Toggle

```typescript
import { getTheme, toggleTheme } from "./lib/theme";

const theme = getTheme(); // "dark" | "light"
const next = toggleTheme(); // Toggles and returns new theme
```

### Theme Persistence

Theme is stored in localStorage under "vibe.theme".

## Responsive Design

### Breakpoints

| Breakpoint | Width | Layout |
|-----------|-------|--------|
| Desktop | > 1100px | 3-column (sidebar + chat + side) |
| Tablet | 768-1100px | 2-column (chat + side overlay) |
| Mobile | < 768px | 1-column + tab bar |

### Media Queries

```css
/* Tablet */
@media (max-width: 1100px) {
  .app-side {
    position: fixed;
    /* ... */
  }
}

/* Mobile */
@media (max-width: 768px) {
  .app-sidebar {
    position: fixed;
    /* ... */
  }
}
```

### useMediaQuery Hook

```typescript
import { useIsMobile, useIsTablet, useIsDesktop } from "./hooks/useMediaQuery";

const isMobile = useIsMobile();
const isTablet = useIsTablet();
const isDesktop = useIsDesktop();
```

## Accessibility

### Focus Management

- All interactive elements have visible focus indicators
- Focus trap in modals
- Focus restore on modal close

### Color Contrast

- All text meets WCAG 2.2 AA contrast requirements (4.5:1)
- Interactive elements have sufficient contrast

### Keyboard Navigation

- All interactive elements are keyboard accessible
- Tab order follows visual order
- Escape closes modals

### Screen Readers

- Semantic HTML elements
- ARIA labels on icon-only buttons
- Live regions for dynamic content

## Reduced Motion

```css
@media (prefers-reduced-motion: reduce) {
  :root {
    --duration-instant: 0ms;
    --duration-fast: 0ms;
    --duration: 0ms;
    --duration-slow: 0ms;
    --duration-slower: 0ms;
  }
}
```

## Usage Examples

### Using Tokens in Components

```tsx
// Good: Using CSS variables
<div style={{ padding: "var(--space-4)" }}>

// Bad: Hardcoded values
<div style={{ padding: "16px" }}>
```

### Using Tokens in CSS

```css
/* Good: Using CSS variables */
.my-component {
  padding: var(--space-4);
  background: var(--bg-raised);
  border-radius: var(--radius-md);
}

/* Bad: Hardcoded values */
.my-component {
  padding: 16px;
  background: #161b22;
  border-radius: 8px;
}
```

### Creating a New Token

1. Add to tokens.css:

```css
:root {
  --my-token: value;
}

[data-theme="light"] {
  --my-token: light-value;
}
```

2. Use in components:

```css
.my-component {
  property: var(--my-token);
}
```

## Future Improvements

- [ ] Add more semantic tokens (e.g., --text-link, --bg-input)
- [ ] Add animation tokens (e.g., --animation-slide-in)
- [ ] Add more breakpoints (e.g., --breakpoint-xl)
- [ ] Add dark mode variants for semantic colors
- [ ] Add token documentation generation
