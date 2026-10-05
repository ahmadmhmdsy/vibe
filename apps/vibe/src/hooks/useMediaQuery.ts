// hooks/useMediaQuery.ts — Responsive breakpoint detection.
// Returns true when the media query matches.

import { useState, useEffect } from "react";

const canMatchMedia = () =>
  typeof window !== "undefined" && typeof window.matchMedia === "function";

export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => canMatchMedia() && window.matchMedia(query).matches);

  useEffect(() => {
    if (!canMatchMedia()) return;
    const mql = window.matchMedia(query);
    const onChange = (e: MediaQueryListEvent) => setMatches(e.matches);

    setMatches(mql.matches);
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, [query]);

  return matches;
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
