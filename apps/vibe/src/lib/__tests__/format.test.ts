// apps/vibe/src/lib/__tests__/format.test.ts
import { describe, it, expect } from "vitest";
import { detectLanguage, formatRelativeTime } from "../format";

describe("detectLanguage", () => {
  it("maps common extensions to Monaco languages", () => {
    expect(detectLanguage("src/App.tsx")).toBe("typescript");
    expect(detectLanguage("src/main.ts")).toBe("typescript");
    expect(detectLanguage("script.py")).toBe("python");
    expect(detectLanguage("styles.css")).toBe("css");
    expect(detectLanguage("index.html")).toBe("html");
    expect(detectLanguage("data.json")).toBe("json");
    expect(detectLanguage("README.md")).toBe("markdown");
  });

  it("falls back to plaintext for unknown extensions", () => {
    expect(detectLanguage("Makefile")).toBe("plaintext");
    expect(detectLanguage("file.unknownext")).toBe("plaintext");
  });
});

describe("formatRelativeTime", () => {
  const now = new Date("2026-09-30T12:00:00Z").getTime();
  const ago = (ms: number) => new Date(now - ms).toISOString();

  it("collapses the last minute", () => {
    expect(formatRelativeTime(ago(5_000), now)).toBe("just now");
  });

  it("reports minutes, hours, and days", () => {
    expect(formatRelativeTime(ago(5 * 60_000), now)).toBe("5m ago");
    expect(formatRelativeTime(ago(3 * 3_600_000), now)).toBe("3h ago");
    expect(formatRelativeTime(ago(2 * 86_400_000), now)).toBe("2d ago");
  });

  it("falls back to a short date beyond a week", () => {
    expect(formatRelativeTime(ago(30 * 86_400_000), now)).toMatch(/[A-Za-z]{3}/);
  });

  it("returns an empty string for an unparseable timestamp", () => {
    expect(formatRelativeTime("not-a-date", now)).toBe("");
  });
});
