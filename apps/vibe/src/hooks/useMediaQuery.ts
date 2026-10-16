// hooks/useMediaQuery.ts — Responsive breakpoint detection.
// Returns true when the media query matches.

import { useCallback, useSyncExternalStore } from "react";

const canMatchMedia = () =>
  typeof window !== "undefined" && typeof window.matchMedia === "function";

export function useMediaQuery(query: string): boolean {
  // useSyncExternalStore is the canonical React hook for subscribing to an
  // external store (here, matchMedia). It replaces the useState + useEffect
  // pattern, which called setState synchronously inside an effect.
  const subscribe = useCallback(
    (onStoreChange: () => void) => {
      if (!canMatchMedia()) return () => {};
      const mql = window.matchMedia(query);
      mql.addEventListener("change", onStoreChange);
      return () => mql.removeEventListener("change", onStoreChange);
    },
    [query]
  );

  const getSnapshot = useCallback(
    () => (canMatchMedia() ? window.matchMedia(query).matches : false),
    [query]
  );

  return useSyncExternalStore(subscribe, getSnapshot);
}

/** Predefined breakpoints matching app.css */
export function useIsMobile() {
  return useMediaQuery("(max-width: 768px)");
}

export function useIsTablet() {
  return useMediaQuery("(max-width: 1100px)");
}

export function useIsDesktop() {
  return useMediaQuery("(min-width: 1101px)");
}
