// components/ui/Menu.tsx — a trigger button plus an accessible dropdown menu.
//
// Replaces the pattern the sessions list used, where rename and delete were
// hover-only affordances on every row: 22 of the first 24 tab stops on a cold
// load were session-row buttons, and the actions were invisible to anyone not
// using a mouse. One trigger per row, with a real menu behind it, fixes both.

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { Tooltip, type TooltipSide } from "./Tooltip";

export interface MenuItemDef {
  id: string;
  label: string;
  icon?: ReactNode;
  /** Right-aligned hint, usually a keyboard shortcut. */
  hint?: string;
  danger?: boolean;
  disabled?: boolean;
  onSelect: () => void;
}

export interface MenuSeparatorDef {
  id: string;
  separator: true;
}

export type MenuEntry = MenuItemDef | MenuSeparatorDef;

export interface MenuProps {
  /** Accessible name for both the trigger and the menu. */
  label: string;
  icon: ReactNode;
  entries: readonly MenuEntry[];
  align?: "start" | "end";
  tooltipSide?: TooltipSide;
  className?: string;
}

const isItem = (entry: MenuEntry): entry is MenuItemDef => !("separator" in entry);

export function Menu({
  label,
  icon,
  entries,
  align = "end",
  tooltipSide = "bottom",
  className,
}: MenuProps) {
  const [open, setOpen] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const popupRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  // Memoised on purpose. A fresh array on every render gave the effect below a
  // new dependency each time, so it re-ran after every state change and reset
  // the active item back to the first one — ArrowDown never moved anywhere.
  const items = useMemo(() => entries.filter(isItem).filter((entry) => !entry.disabled), [entries]);

  const close = useCallback((restoreFocus: boolean) => {
    setOpen(false);
    setActiveId(null);
    if (restoreFocus) triggerRef.current?.focus();
  }, []);

  const focusItem = useCallback((id: string) => {
    const buttons = popupRef.current?.querySelectorAll<HTMLButtonElement>('[role="menuitem"]');
    if (!buttons) return;
    for (const button of buttons) {
      if (button.dataset.itemId === id) {
        button.focus();
        return;
      }
    }
  }, []);

  const move = useCallback(
    (direction: 1 | -1) => {
      if (items.length === 0) return;
      const current = items.findIndex((entry) => entry.id === activeId);
      const next = (current + direction + items.length) % items.length;
      const entry = items[next];
      if (entry) setActiveId(entry.id);
    },
    [activeId, items]
  );

  // Decide the active item where the menu opens, not in an effect. An effect
  // that setState()s would re-run on every dependency change and fight the
  // arrow keys for control of the roving tabindex.
  const openMenu = useCallback(
    (edge: "first" | "last" = "first") => {
      const target = edge === "last" ? items[items.length - 1] : items[0];
      setActiveId(target ? target.id : null);
      setOpen(true);
    },
    [items]
  );

  // Reflect the already-decided active item into DOM focus. Only focus moves
  // here, so the roving tabindex and the real focus can never drift apart.
  useLayoutEffect(() => {
    if (!open || activeId === null) return;
    focusItem(activeId);
  }, [open, activeId, focusItem]);

  useEffect(() => {
    if (!open) return;
    const onDocumentPointerDown = (event: Event) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) close(false);
    };
    document.addEventListener("pointerdown", onDocumentPointerDown, true);
    return () => document.removeEventListener("pointerdown", onDocumentPointerDown, true);
  }, [open, close]);

  // A menu button opens on the first item with ArrowDown and on the last with
  // ArrowUp, which is what makes it usable from the keyboard alone.
  const handleTriggerKeyDown = useCallback(
    (event: KeyboardEvent<HTMLButtonElement>) => {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        openMenu("first");
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        openMenu("last");
      }
    },
    [openMenu]
  );

  const handlePopupKeyDown = useCallback(
    (event: KeyboardEvent<HTMLDivElement>) => {
      switch (event.key) {
        case "Escape":
          event.stopPropagation();
          event.preventDefault();
          close(true);
          return;
        case "Tab":
          close(false);
          return;
        case "ArrowDown":
          event.preventDefault();
          move(1);
          return;
        case "ArrowUp":
          event.preventDefault();
          move(-1);
          return;
        case "Home": {
          event.preventDefault();
          const first = items[0];
          if (first) setActiveId(first.id);
          return;
        }
        case "End": {
          event.preventDefault();
          const last = items[items.length - 1];
          if (last) setActiveId(last.id);
          return;
        }
        default:
          return;
      }
    },
    [close, items, move]
  );

  return (
    <div ref={rootRef} className={["menu", className].filter(Boolean).join(" ")}>
      <Tooltip label={label} side={tooltipSide} disabled={open}>
        <button
          ref={triggerRef}
          type="button"
          className="icon-btn"
          aria-label={label}
          aria-haspopup="menu"
          aria-expanded={open}
          onClick={() => (open ? close(false) : openMenu())}
          onKeyDown={handleTriggerKeyDown}
        >
          {icon}
        </button>
      </Tooltip>

      {open ? (
        <div
          ref={popupRef}
          role="menu"
          aria-label={label}
          className="menu-popup"
          data-align={align}
          onKeyDown={handlePopupKeyDown}
        >
          {entries.map((entry) =>
            isItem(entry) ? (
              <button
                key={entry.id}
                type="button"
                role="menuitem"
                data-item-id={entry.id}
                tabIndex={entry.id === activeId ? 0 : -1}
                disabled={entry.disabled}
                className={["menu-item", entry.danger ? "menu-item-danger" : ""]
                  .filter(Boolean)
                  .join(" ")}
                onClick={() => {
                  entry.onSelect();
                  close(false);
                }}
              >
                {entry.icon}
                <span className="menu-item-label">{entry.label}</span>
                {entry.hint ? <span className="menu-item-hint">{entry.hint}</span> : null}
              </button>
            ) : (
              <div key={entry.id} role="separator" className="menu-separator" />
            )
          )}
        </div>
      ) : null}
    </div>
  );
}
