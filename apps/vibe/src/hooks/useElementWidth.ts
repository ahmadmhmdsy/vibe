// hooks/useElementWidth.ts — track an element's rendered width in px.
//
// The right-hand column's width is a CSS clamp until the user drags the
// splitter. The splitter still has to report a real value through
// aria-valuenow and compute a drag delta from a starting point, so the shell
// needs the measured width rather than the declared one.

import { useCallback, useEffect, useRef, useState } from "react";

export function useElementWidth<T extends HTMLElement>() {
  const [width, setWidth] = useState(0);
  const observerRef = useRef<ResizeObserver | null>(null);

  // A callback ref, not an effect: the measurement happens during the commit
  // that attaches the node, so there is no frame at width 0.
  const ref = useCallback((node: T | null) => {
    observerRef.current?.disconnect();
    observerRef.current = null;
    if (!node) return;

    setWidth(node.getBoundingClientRect().width);
    if (typeof ResizeObserver === "undefined") return;

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) setWidth(entry.contentRect.width);
    });
    observer.observe(node);
    observerRef.current = observer;
  }, []);

  useEffect(() => () => observerRef.current?.disconnect(), []);

  return { ref, width };
}
