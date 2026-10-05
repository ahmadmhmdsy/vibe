// apps/vibe/src/lib/theme.ts
export type Theme = "dark" | "light";

const KEY = "vibe.theme";

export function getTheme(): Theme {
  try {
    const t = localStorage.getItem(KEY);
    return t === "light" ? "light" : "dark";
  } catch {
    return "dark";
  }
}

const THEME_COLOR: Record<Theme, string> = { dark: "#0d1117", light: "#f6f8fa" };

export function setTheme(t: Theme): void {
  document.documentElement.dataset.theme = t;
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", THEME_COLOR[t]);
  try {
    localStorage.setItem(KEY, t);
  } catch {
    // Storage unavailable — the theme still applies for this session.
  }
}

export function toggleTheme(): Theme {
  const next = getTheme() === "dark" ? "light" : "dark";
  setTheme(next);
  return next;
}
