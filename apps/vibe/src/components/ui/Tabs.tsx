// components/ui/Tabs.tsx — an accessible tablist plus its panels.
//
// Implements the ARIA tabs pattern properly: roving tabindex (one tab stop for
// the whole list, not one per tab), automatic activation on arrow keys, and
// aria-controls pointing at a real tabpanel. The old shell had no tabs at all —
// Preview and Code were stacked in one column at 50/50 with no way to choose.

import { useCallback, useRef, type KeyboardEvent, type ReactNode } from "react";

export interface TabItem {
  id: string;
  label: string;
  icon?: ReactNode;
  /** Optional right-aligned count, e.g. the number of changed files. */
  count?: number;
  disabled?: boolean;
}

export interface TabsProps {
  items: readonly TabItem[];
  value: string;
  onChange: (id: string) => void;
  /** Accessible name for the tablist. Required. */
  label: string;
  variant?: "pill" | "underline";
  /** Prefix used to wire each tab to its panel with aria-controls. */
  idPrefix?: string;
  className?: string;
}

export function Tabs({
  items,
  value,
  onChange,
  label,
  variant = "pill",
  idPrefix,
  className,
}: TabsProps) {
  const listRef = useRef<HTMLDivElement>(null);

  const enabled = items.filter((item) => !item.disabled);
  const enabledIds = enabled.map((item) => item.id);
  const currentIndex = Math.max(0, enabledIds.indexOf(value));
  // If `value` matches nothing, the list still needs one reachable stop.
  const rovingId = enabledIds.includes(value) ? value : enabledIds[0];

  const focusTab = useCallback((id: string) => {
    const buttons = listRef.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]');
    if (!buttons) return;
    for (const button of buttons) {
      if (button.dataset.tabId === id) {
        button.focus();
        return;
      }
    }
  }, []);

  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLDivElement>) => {
      if (enabledIds.length === 0) return;
      let nextIndex: number | undefined;

      switch (event.key) {
        case "ArrowRight":
        case "ArrowDown":
          nextIndex = (currentIndex + 1) % enabledIds.length;
          break;
        case "ArrowLeft":
        case "ArrowUp":
          nextIndex = (currentIndex - 1 + enabledIds.length) % enabledIds.length;
          break;
        case "Home":
          nextIndex = 0;
          break;
        case "End":
          nextIndex = enabledIds.length - 1;
          break;
        default:
          return;
      }

      if (nextIndex === undefined) return;
      event.preventDefault();
      const nextId = enabledIds[nextIndex];
      if (!nextId) return;
      if (nextId !== value) onChange(nextId);
      focusTab(nextId);
    },
    [currentIndex, enabledIds, focusTab, onChange, value]
  );

  return (
    <div
      ref={listRef}
      role="tablist"
      aria-label={label}
      className={["tabs", className].filter(Boolean).join(" ")}
      data-variant={variant}
      onKeyDown={handleKeyDown}
    >
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          role="tab"
          data-tab-id={item.id}
          id={idPrefix ? `${idPrefix}-tab-${item.id}` : undefined}
          aria-selected={item.id === value}
          aria-controls={idPrefix ? `${idPrefix}-panel-${item.id}` : undefined}
          tabIndex={item.id === rovingId ? 0 : -1}
          disabled={item.disabled}
          className="tab"
          onClick={() => onChange(item.id)}
        >
          {item.icon}
          <span>{item.label}</span>
          {typeof item.count === "number" ? <span className="tab-count">{item.count}</span> : null}
        </button>
      ))}
    </div>
  );
}

export interface TabPanelProps {
  id: string;
  idPrefix?: string;
  active: boolean;
  children: ReactNode;
  className?: string;
}

/** Panels stay mounted and are hidden with the `hidden` attribute, so a tab
 *  switch never tears down the preview iframe or the Monaco model. */
export function TabPanel({ id, idPrefix, active, children, className }: TabPanelProps) {
  return (
    <div
      role="tabpanel"
      id={idPrefix ? `${idPrefix}-panel-${id}` : undefined}
      aria-labelledby={idPrefix ? `${idPrefix}-tab-${id}` : undefined}
      hidden={!active}
      tabIndex={0}
      className={["tab-panel", className].filter(Boolean).join(" ")}
    >
      {children}
    </div>
  );
}
