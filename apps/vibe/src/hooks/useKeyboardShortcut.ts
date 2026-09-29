// apps/vibe/src/hooks/useKeyboardShortcut.ts
import { useEffect, useRef } from "react";

export interface ShortcutOptions {
  /** Require Cmd (mac) / Ctrl (others). Default false. */
  meta?: boolean;
  /** Key to match, case-insensitive. */
  key: string;
  /** Fire even when focus is in an input/textarea. Default false. */
  allowInInput?: boolean;
}

export function useKeyboardShortcut(handler: () => void, { meta = false, key, allowInInput = false }: ShortcutOptions) {
  const handlerRef = useRef(handler);
  handlerRef.current = handler;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (meta && !(e.metaKey || e.ctrlKey)) return;
      if (!meta && (e.metaKey || e.ctrlKey)) return;
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
  }, [meta, key, allowInInput]);
}
