// apps/vibe/src/hooks/useKeyboardShortcut.ts
import { useEffect, useRef } from "react";

export interface ShortcutOptions {
  /** Require the primary modifier: Cmd on macOS, Ctrl elsewhere. Default false. */
  meta?: boolean;
  /** Require Ctrl itself, for bindings that must not fire on Cmd. Default false. */
  ctrl?: boolean;
  /** Require Alt (Option) in addition to the other modifiers. Default false. */
  alt?: boolean;
  /** Key to match, case-insensitive. */
  key: string;
  /** Fire even when focus is in an input/textarea. Default false. */
  allowInInput?: boolean;
}

export function useKeyboardShortcut(
  handler: () => void,
  { meta = false, ctrl = false, alt = false, key, allowInInput = false }: ShortcutOptions
) {
  const handlerRef = useRef(handler);

  // Keep the ref current without writing to it during render (which the
  // react-hooks/refs rule forbids). This effect runs after every render, so
  // the ref always holds the latest handler by the time a key fires.
  useEffect(() => {
    handlerRef.current = handler;
  });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const primaryRequired = meta || ctrl;
      const hasPrimary = e.metaKey || e.ctrlKey;
      if (primaryRequired !== hasPrimary) return;
      // ctrl demands Ctrl itself, so Cmd+N (mac) and Ctrl+Alt+N (elsewhere) can
      // coexist without either one claiming the other's combination.
      if (ctrl && !e.ctrlKey) return;
      if (alt) {
        if (!e.altKey) return;
      } else if (primaryRequired && e.altKey) {
        // A modified shortcut must not also answer to a longer combination.
        return;
      }
      if (e.key.toLowerCase() !== key.toLowerCase()) return;
      const target = e.target as HTMLElement | null;
      const inInput =
        !!target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.tagName === "SELECT" ||
          target.isContentEditable);
      if (inInput && !allowInInput) return;
      e.preventDefault();
      handlerRef.current();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [meta, ctrl, alt, key, allowInInput]);
}
