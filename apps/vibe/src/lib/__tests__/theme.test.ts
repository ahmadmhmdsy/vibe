// apps/vibe/src/lib/__tests__/theme.test.ts
import { describe, it, expect, afterEach } from "vitest";
import { getTheme, setTheme, toggleTheme } from "../theme";

afterEach(() => {
  localStorage.clear();
  document.documentElement.dataset.theme = "dark";
});

describe("theme", () => {
  it("defaults to dark", () => {
    expect(getTheme()).toBe("dark");
  });

  it("setTheme applies the attribute and persists", () => {
    setTheme("light");
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(localStorage.getItem("vibe.theme")).toBe("light");
  });

  it("toggleTheme flips the theme", () => {
    expect(toggleTheme()).toBe("light");
    expect(toggleTheme()).toBe("dark");
  });

  it("reads a saved light theme", () => {
    localStorage.setItem("vibe.theme", "light");
    expect(getTheme()).toBe("light");
  });
});
