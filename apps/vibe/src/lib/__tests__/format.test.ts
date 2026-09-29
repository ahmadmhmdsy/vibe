// apps/vibe/src/lib/__tests__/format.test.ts
import { describe, it, expect } from "vitest";
import { detectLanguage } from "../format";

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
